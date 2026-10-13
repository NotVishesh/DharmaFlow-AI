"""
DharmaFlow AI — Source Verifier
Enforces theological and factual verification states:
  DRAFT -> SOURCES_PENDING -> VERIFIED -> READY_FOR_REVIEW -> APPROVED
"""
from __future__ import annotations

import logging
from typing import Tuple

from app.content.schemas import ClaimAndEvidence, ClaimType, ScriptSchema
from app.database.models import VerificationStatus

logger = logging.getLogger(__name__)


class SourceVerifier:
    """Validates script factual integrity and manages verification lifecycle."""

    @classmethod
    def verify_script(cls, script: ScriptSchema) -> Tuple[str, list[str]]:
        """
        Evaluate all claims and references in a script.
        Returns: (new_verification_status, list_of_blocking_reasons)
        """
        reasons: list[str] = []

        # 1. Must have at least one source reference if dealing with scriptures
        if script.category in ("scripture_explainer", "temple_historical") and not script.source_references:
            reasons.append("Category requires explicit primary source references, but none were provided.")

        # 2. Check for unsupported historical or quote claims
        unverified_critical_claims = [
            c for c in script.claims_and_evidence
            if not c.verified and c.claim_type in (
                ClaimType.DIRECT_QUOTATION,
                ClaimType.HISTORICAL_CLAIM,
                ClaimType.SCIENTIFIC_CLAIM,
            )
        ]

        if unverified_critical_claims:
            for c in unverified_critical_claims:
                reasons.append(f"Unverified {c.claim_type.value}: '{c.claim_text[:80]}...'")

        # 3. Check for source/verse citations in scripture explainers
        if script.category == "scripture_explainer":
            has_verse_citation = (
                any(c.source_reference and len(c.source_reference.strip()) > 1 for c in script.claims_and_evidence)
                or any((ref.passage and len(ref.passage.strip()) > 1) or (ref.name and len(ref.name.strip()) > 2) for ref in script.source_references)
                or any(s.source_reference and len(s.source_reference.strip()) > 1 for s in script.scenes)
                or any(ch.isdigit() for ch in script.topic)
            )
            if not has_verse_citation:
                reasons.append("Scripture explainer must provide source or verse references.")

        if reasons:
            logger.warning("Script '%s' failed verification checks: %s", script.topic[:50], "; ".join(reasons))
            return VerificationStatus.SOURCES_PENDING.value, reasons

        # 4. Check if any claim needs human review
        has_review_items = any(c.needs_review for c in script.claims_and_evidence)
        if has_review_items:
            logger.info("Script '%s' has claims flagged for review -> READY_FOR_REVIEW", script.topic[:50])
            return VerificationStatus.READY_FOR_REVIEW.value, []

        # If all claims verified and sources exist:
        logger.info("Script '%s' passed automated verification -> VERIFIED", script.topic[:50])
        return VerificationStatus.VERIFIED.value, []

    @classmethod
    def update_verification_status(cls, script: ScriptSchema, target_status: str, reviewer_notes: str = "") -> bool:
        """
        Validates state machine transitions:
        DRAFT -> SOURCES_PENDING -> VERIFIED -> READY_FOR_REVIEW -> APPROVED
        """
        valid_transitions = {
            VerificationStatus.DRAFT.value: [VerificationStatus.SOURCES_PENDING.value, VerificationStatus.VERIFIED.value],
            VerificationStatus.SOURCES_PENDING.value: [VerificationStatus.VERIFIED.value, VerificationStatus.REJECTED.value],
            VerificationStatus.VERIFIED.value: [VerificationStatus.READY_FOR_REVIEW.value, VerificationStatus.REJECTED.value],
            VerificationStatus.READY_FOR_REVIEW.value: [VerificationStatus.APPROVED.value, VerificationStatus.REJECTED.value],
            VerificationStatus.APPROVED.value: [VerificationStatus.REJECTED.value],
            VerificationStatus.REJECTED.value: [VerificationStatus.DRAFT.value],
        }

        current = script.verification_status
        allowed = valid_transitions.get(current, [])

        if target_status not in allowed:
            logger.error("Invalid verification transition: %s -> %s (Allowed: %s)", current, target_status, allowed)
            return False

        script.verification_status = target_status
        return True
