"""
DharmaFlow AI — Metadata Generator
Produces YouTube Shorts & Instagram Reels titles, descriptions, hashtags,
source notes, and platform AI disclosure statements.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.content.schemas import ScriptSchema

logger = logging.getLogger(__name__)

CATEGORY_HASHTAGS: dict[str, list[str]] = {
    "general": ["#Shorts", "#Explained", "#Knowledge", "#Facts", "#LearnOnYouTube", "#ViralShorts"],
    "tech_ai": ["#AI", "#Technology", "#FutureTech", "#Coding", "#Innovation", "#Shorts"],
    "science_space": ["#Science", "#Space", "#Astrophysics", "#Universe", "#STEM", "#Shorts"],
    "motivation_mindset": ["#Motivation", "#Mindset", "#SelfImprovement", "#Success", "#Discipline", "#Shorts"],
    "history_culture": ["#History", "#AncientHistory", "#Civilization", "#WorldHistory", "#Documentary", "#Shorts"],
    "finance_business": ["#Finance", "#Investing", "#Economics", "#Business", "#Wealth", "#Shorts"],
    "storytelling": ["#Storytime", "#Storytelling", "#LifeLessons", "#Inspiration", "#Shorts"],
    "facts_trivia": ["#Facts", "#DidYouKnow", "#Trivia", "#MindBlowing", "#AmazingFacts", "#Shorts"],
    "health_psychology": ["#Psychology", "#BrainHealth", "#Neuroscience", "#MentalHealth", "#Wellness", "#Shorts"],
    "philosophy_wisdom": ["#Philosophy", "#Wisdom", "#Mindfulness", "#Stoicism", "#Spirituality", "#Shorts"],
    "scripture_explainer": ["#SanatanDharma", "#BhagavadGita", "#Hinduism", "#SpiritualWisdom", "#Shorts"],
    "epic_storytelling": ["#Ramayana", "#Mahabharata", "#IndianEpics", "#Mythology", "#Shorts"],
    "devotional_reflection": ["#Devotional", "#Bhakti", "#Meditation", "#InnerPeace", "#Shorts"],
    "festival_cultural": ["#IndianCulture", "#Festivals", "#Tradition", "#Heritage", "#Shorts"],
    "temple_historical": ["#AncientTemples", "#Architecture", "#History", "#Heritage", "#Shorts"],
}

DEFAULT_HASHTAGS = CATEGORY_HASHTAGS["general"]


class MetadataGenerator:
    """Formats publishing metadata with strict compliance to platform policies across all genres."""

    @classmethod
    def _get_hashtags(cls, category: str) -> list[str]:
        return CATEGORY_HASHTAGS.get((category or "general").lower(), DEFAULT_HASHTAGS)

    @classmethod
    def generate_youtube_metadata(cls, script: ScriptSchema) -> dict[str, str | list[str]]:
        """
        Creates title (<= 100 chars), rich description with source notes,
        appropriate category tag, and tags list.
        """
        # 1. Best title selection
        title = script.title_options[0] if script.title_options else script.topic
        if len(title) > 90:
            title = title[:87] + "..."
        if "#Shorts" not in title and len(title) <= 90:
            title = f"{title} #Shorts"

        hashtags = cls._get_hashtags(script.category)

        # 2. Build structured description with source notes
        desc_lines = [
            f"{script.topic}\n",
            f"📌 Summary: {script.narration[:220]}...\n",
            "📚 Sources & References:",
        ]

        if script.source_references:
            for ref in script.source_references:
                passage_text = f" ({ref.passage})" if ref.passage else ""
                url_text = f" - {ref.url}" if ref.url else ""
                desc_lines.append(f"• {ref.name}{passage_text}{url_text}")
        else:
            desc_lines.append("• Verified educational & reference synthesis.")

        desc_lines.append("\n⚠️ Content & AI Disclosure:")
        if script.ai_disclosure_required:
            desc_lines.append(
                "Visual animations and voice narration were synthetically assisted "
                "in accordance with YouTube's Altered/Synthetic Content transparency policy."
            )
        else:
            desc_lines.append("Original educational and informational commentary.")

        desc_lines.append("\n🔔 Subscribe for daily high-impact Shorts!")
        desc_lines.append(" ".join(hashtags))

        description = "\n".join(desc_lines)

        # 3. Dynamic tags list
        clean_tags = [h.lstrip("#") for h in hashtags]
        tags = clean_tags + [
            script.category.replace("_", " ").title(),
            "YouTube Shorts",
            "Explainer",
        ]

        # YouTube Category ID: 28 = Science & Tech, 27 = Education
        yt_cat = "28" if script.category in ("tech_ai", "science_space") else "27"

        return {
            "title": title,
            "description": description,
            "tags": tags,
            "category_id": yt_cat,
            "language": script.language,
        }

    @classmethod
    def generate_instagram_metadata(cls, script: ScriptSchema) -> dict[str, str]:
        """Creates caption optimized for Instagram Reels."""
        hashtags = cls._get_hashtags(script.category)
        caption_lines = [
            script.opening_hook,
            "",
            script.closing_line,
            "",
            "Source: " + (", ".join(r.name for r in script.source_references) if script.source_references else "Educational Synthesis"),
            "",
            " ".join(hashtags + ["#Reels", "#ExplorePage"]),
        ]
        return {
            "caption": "\n".join(caption_lines),
        }
