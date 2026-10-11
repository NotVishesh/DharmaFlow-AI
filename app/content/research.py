"""
DharmaFlow AI — Research Module
Gathers scripture references, extracts factual claims, and identifies doctrinal traditions.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from app.content.schemas import ClaimAndEvidence, ClaimType, SourceReference
from app.research.sources import TRUSTED_SOURCES, get_source_by_name

logger = logging.getLogger(__name__)


class ResearchEngine:
    """Extracts claims and associates references from scriptures and traditions."""

    @staticmethod
    def identify_references_for_topic(topic: str, category: str) -> list[SourceReference]:
        """Match relevant sources from the trusted registry based on keywords."""
        topic_lower = topic.lower()
        matched: list[SourceReference] = []

        if "gita" in topic_lower or "bhagavad" in topic_lower or "krishna" in topic_lower:
            src = get_source_by_name("Gita Supersite (IIT Kanpur)") or TRUSTED_SOURCES[1]
            matched.append(
                SourceReference(
                    name=src["name"],
                    url=src.get("url"),
                    source_type=src["source_type"],
                    author=src.get("author", "IIT Kanpur"),
                    passage="Bhagavad Gita original verses and authentic commentaries",
                    license_notes=src.get("license_notes", "Educational use"),
                )
            )

        if "ramayana" in topic_lower or "rama" in topic_lower or "lakshmana" in topic_lower or "hanuman" in topic_lower:
            src = get_source_by_name("Valmiki Ramayana (translation by Desiraju Hanumanta Rao)") or TRUSTED_SOURCES[2]
            matched.append(
                SourceReference(
                    name=src["name"],
                    url=src.get("url"),
                    source_type=src["source_type"],
                    author="Valmiki / Desiraju Hanumanta Rao",
                    passage="Valmiki Ramayana verses",
                    license_notes=src.get("license_notes", "Educational use"),
                )
            )

        if "diwali" in topic_lower or "navaratri" in topic_lower or "shivaratri" in topic_lower or "festival" in topic_lower:
            src = get_source_by_name("Drik Panchang") or TRUSTED_SOURCES[6]
            matched.append(
                SourceReference(
                    name=src["name"],
                    url=src.get("url"),
                    source_type=src["source_type"],
                    author="Drik Panchang Almanac",
                    passage="Hindu Lunar Calendar & Regional festival observances",
                    license_notes=src.get("license_notes", "Public factual information"),
                )
            )

        # Fallback to general scripture archive if empty
        if not matched:
            src = TRUSTED_SOURCES[4]
            matched.append(
                SourceReference(
                    name=src["name"],
                    url=src.get("url"),
                    source_type=src["source_type"],
                    author="Sacred Texts Archive",
                    passage="Public domain translations of ancient Hindu texts",
                    license_notes=src.get("license_notes", "Public domain"),
                )
            )

        return matched

    @staticmethod
    def extract_claims_from_narration(narration: str, topic: str) -> list[ClaimAndEvidence]:
        """
        Parses narration text to detect explicit verse claims, quotations,
        and attributions.
        """
        claims: list[ClaimAndEvidence] = []
        sentences = [s.strip() for s in re.split(r"[।\.\!\?]", narration) if len(s.strip()) > 10]

        # Regex patterns for scriptures
        verse_pattern = re.compile(r"(\d+)\s*[:\.]\s*(\d+)")
        sanskrit_indicators = ["कर्मण्येवाधिकारस्ते", "यदा यदा हि", "ॐ नमः शिवाय", "महामृत्युंजय", "श्लोक"]

        for sent in sentences:
            has_sanskrit = any(s in sent for s in sanskrit_indicators)
            has_verse = verse_pattern.search(sent)

            if has_verse or has_sanskrit:
                claims.append(
                    ClaimAndEvidence(
                        claim_text=sent,
                        claim_type=ClaimType.DIRECT_QUOTATION if has_sanskrit else ClaimType.TRADITIONAL_INTERPRETATION,
                        source_name="Scriptural Reference",
                        source_reference=has_verse.group(0) if has_verse else "Traditional Shloka",
                        verified=True,
                        needs_review=False,
                    )
                )
            elif any(w in sent.lower() for w in ["history", "built in", "century", "century ce", "temple was constructed"]):
                claims.append(
                    ClaimAndEvidence(
                        claim_text=sent,
                        claim_type=ClaimType.HISTORICAL_CLAIM,
                        source_name="Historical / Archaeological Records",
                        source_reference=None,
                        verified=False,
                        needs_review=True,
                        reviewer_notes="Verify against archaeological / epigraphical records before publication",
                    )
                )

        return claims
