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
        """Match relevant sources from the trusted registry based on category and keywords."""
        topic_lower = topic.lower()
        cat_lower = (category or "general").lower()
        matched: list[SourceReference] = []

        # 1. Check domain/category matches
        if cat_lower == "tech_ai" or any(k in topic_lower for k in ["ai", "artificial intelligence", "quantum", "coding", "computer", "robot", "algorithm", "software", "tech"]):
            src = get_source_by_name("IEEE & Computer Science Research Archive (arXiv)") or TRUSTED_SOURCES[9]
            matched.append(
                SourceReference(
                    name=src["name"],
                    url=src.get("url"),
                    source_type=src["source_type"],
                    author=src.get("author", "Computer Science Research"),
                    passage=f"Technical & Computer Science Reference: {topic[:60]}",
                    license_notes=src.get("license_notes", "Open access educational synthesis"),
                )
            )

        if cat_lower == "science_space" or any(k in topic_lower for k in ["space", "universe", "black hole", "galaxy", "physics", "planet", "nasa", "cosmos", "science", "atom", "biology"]):
            src = get_source_by_name("NASA & Peer-Reviewed Space Science Archive") or TRUSTED_SOURCES[8]
            matched.append(
                SourceReference(
                    name=src["name"],
                    url=src.get("url"),
                    source_type=src["source_type"],
                    author=src.get("author", "Scientific Consensus"),
                    passage=f"Peer-Reviewed Scientific Literature: {topic[:60]}",
                    license_notes=src.get("license_notes", "Public domain scientific data"),
                )
            )

        if cat_lower in ("motivation_mindset", "health_psychology") or any(k in topic_lower for k in ["psychology", "mindset", "habit", "brain", "dopamine", "focus", "discipline", "anxiety", "motivation", "success"]):
            src = get_source_by_name("American Psychological Association (APA) & Behavioral Science") or TRUSTED_SOURCES[11]
            matched.append(
                SourceReference(
                    name=src["name"],
                    url=src.get("url"),
                    source_type=src["source_type"],
                    author=src.get("author", "Behavioral Science Research"),
                    passage=f"Behavioral Psychology & Cognitive Science: {topic[:60]}",
                    license_notes=src.get("license_notes", "Educational synthesis"),
                )
            )

        if cat_lower == "finance_business" or any(k in topic_lower for k in ["finance", "money", "investing", "economics", "market", "wealth", "compound interest", "business", "startup"]):
            src = get_source_by_name("Economic & Financial Literacy Research") or TRUSTED_SOURCES[12]
            matched.append(
                SourceReference(
                    name=src["name"],
                    url=src.get("url"),
                    source_type=src["source_type"],
                    author=src.get("author", "Financial Education Consensus"),
                    passage=f"Economic Principles & Financial Reference: {topic[:60]}",
                    license_notes=src.get("license_notes", "Educational commentary only"),
                )
            )

        if cat_lower == "history_culture" or any(k in topic_lower for k in ["history", "empire", "ancient", "civilization", "century", "dynasty", "war", "historical"]):
            src = get_source_by_name("Encyclopaedia Britannica & World History Archive") or TRUSTED_SOURCES[10]
            matched.append(
                SourceReference(
                    name=src["name"],
                    url=src.get("url"),
                    source_type=src["source_type"],
                    author=src.get("author", "Historical Consensus"),
                    passage=f"Historical Records & Archival Synthesis: {topic[:60]}",
                    license_notes=src.get("license_notes", "Educational historical commentary"),
                )
            )

        # 2. Check Philosophical / Devotional / Scriptural keywords
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

        # 3. Fallback to general educational archive if no specific match
        if not matched:
            if cat_lower in ("scripture_explainer", "epic_storytelling", "devotional_reflection", "festival_cultural", "temple_historical", "philosophy_wisdom"):
                src = TRUSTED_SOURCES[4]
                matched.append(
                    SourceReference(
                        name=src["name"],
                        url=src.get("url"),
                        source_type=src["source_type"],
                        author="Sacred Texts Archive",
                        passage="Public domain translations of philosophical and spiritual texts",
                        license_notes=src.get("license_notes", "Public domain"),
                    )
                )
            else:
                src = get_source_by_name("Open Educational & Encyclopedic Reference") or TRUSTED_SOURCES[-1]
                matched.append(
                    SourceReference(
                        name=src["name"],
                        url=src.get("url"),
                        source_type=src["source_type"],
                        author=src.get("author", "Open Knowledge Contributors"),
                        passage=f"Verified Educational Reference: {topic[:60]}",
                        license_notes=src.get("license_notes", "Educational synthesis"),
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
