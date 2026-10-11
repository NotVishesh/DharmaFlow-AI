"""
DharmaFlow AI — Originality Checker
Fingerprint-based duplicate detection for scripts.
"""
from __future__ import annotations

import difflib
import hashlib
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.content.schemas import OriginalityReport, ScriptSchema
from app.database.models import Script

logger = logging.getLogger(__name__)


def _compute_text_fingerprint(text: str) -> str:
    return hashlib.sha256(text.strip().lower().encode("utf-8")).hexdigest()


def _similarity_ratio(a: str, b: str) -> float:
    """Normalized similarity [0..1] using SequenceMatcher."""
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def check_originality(
    script: ScriptSchema,
    db: Session,
    similarity_threshold: float = 0.75,
) -> OriginalityReport:
    """
    Check a script against the database for duplicate or near-duplicate content.

    Returns an OriginalityReport. Sets passed=False if a duplicate is found.
    """
    narration = script.narration or ""
    fingerprint = _compute_text_fingerprint(narration)

    # Exact duplicate check
    exact_match = db.query(Script).filter(Script.fingerprint == fingerprint).first()
    if exact_match:
        logger.warning("Exact duplicate detected: matches script %s", exact_match.id)
        return OriginalityReport(
            fingerprint=fingerprint,
            is_duplicate=True,
            similar_scripts=[exact_match.id],
            similarity_scores={exact_match.id: 1.0},
            hook_diversity_score=0.0,
            metadata_similarity_warnings=["Exact duplicate narration detected."],
            passed=False,
        )

    # Near-duplicate check against recent scripts (last 100)
    recent_scripts = db.query(Script).order_by(Script.created_at.desc()).limit(100).all()
    similar: dict[str, float] = {}
    warnings: list[str] = []

    for s in recent_scripts:
        if not s.narration:
            continue
        ratio = _similarity_ratio(narration, s.narration)
        if ratio > similarity_threshold:
            similar[s.id] = ratio
            warnings.append(
                f"High similarity ({ratio:.0%}) with script {s.id[:8]} on topic: {s.topic[:50]}"
            )

    is_duplicate = any(v >= 0.95 for v in similar.values())

    # Hook diversity check
    proposed_hook = script.opening_hook or ""
    hook_similarities = []
    for s in recent_scripts[:20]:
        if s.scenes:
            existing_hook = (s.scenes[0] or {}).get("narration_text", "") if isinstance(s.scenes, list) else ""
            hook_similarities.append(_similarity_ratio(proposed_hook, existing_hook))
    hook_diversity = 1.0 - (max(hook_similarities) if hook_similarities else 0.0)

    # Title metadata check
    proposed_titles = set(t.lower() for t in (script.title_options or []))
    for s in recent_scripts[:30]:
        if s.title_options and isinstance(s.title_options, list):
            existing_titles = set(t.lower() for t in s.title_options)
            overlap = len(proposed_titles & existing_titles)
            if overlap > 0:
                warnings.append(
                    f"Title overlap ({overlap} matching) with script {s.id[:8]}"
                )

    report = OriginalityReport(
        fingerprint=fingerprint,
        is_duplicate=is_duplicate,
        similar_scripts=list(similar.keys()),
        similarity_scores=similar,
        hook_diversity_score=min(1.0, max(0.0, hook_diversity)),
        metadata_similarity_warnings=warnings,
        passed=not is_duplicate,
    )

    if similar:
        logger.info(
            "Similarity check: %d near-duplicates found (max: %.0f%%)",
            len(similar),
            max(similar.values()) * 100 if similar else 0,
        )

    return report
