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

DEFAULT_HASHTAGS = [
    "#SanatanDharma",
    "#BhagavadGita",
    "#Hinduism",
    "#Devotional",
    "#Shorts",
    "#SpiritualWisdom",
]


class MetadataGenerator:
    """Formats publishing metadata with strict compliance to platform policies."""

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

        # 2. Build structured description with source notes
        desc_lines = [
            f"{script.topic}\n",
            f"🌿 Summary: {script.narration[:200]}...\n",
            "📖 Authentic Sources & References:",
        ]

        if script.source_references:
            for ref in script.source_references:
                passage_text = f" ({ref.passage})" if ref.passage else ""
                url_text = f" - {ref.url}" if ref.url else ""
                desc_lines.append(f"• {ref.name}{passage_text}{url_text}")
        else:
            desc_lines.append("• Ancient Hindu scripture & traditional oral traditions.")

        desc_lines.append("\n⚠️ Content & AI Disclosure:")
        if script.ai_disclosure_required:
            desc_lines.append(
                "Visual animations and voice narration were synthetically assisted "
                "in accordance with YouTube's Altered/Synthetic Content transparency policy. "
                "Scripture verses and philosophical concepts are derived from authentic primary sources."
            )
        else:
            desc_lines.append("Educational devotional commentary.")

        desc_lines.append("\n🔔 Subscribe to DharmaFlow AI for daily devotional wisdom!")
        desc_lines.append(" ".join(DEFAULT_HASHTAGS))

        description = "\n".join(desc_lines)

        # 3. Tags list
        tags = [
            "Hinduism",
            "Bhagavad Gita",
            "Sanatan Dharma",
            "Krishna",
            "Spirituality",
            "Devotional Short",
            "DharmaFlow",
            script.category.replace("_", " ").title(),
        ]

        return {
            "title": title,
            "description": description,
            "tags": tags,
            "category_id": "29",  # Nonprofits & Activism / Education
            "language": script.language,
        }

    @classmethod
    def generate_instagram_metadata(cls, script: ScriptSchema) -> dict[str, str]:
        """Creates caption optimized for Instagram Reels."""
        caption_lines = [
            script.opening_hook,
            "",
            script.closing_line,
            "",
            "Source: " + (", ".join(r.name for r in script.source_references) if script.source_references else "Sanatana Dharma traditions"),
            "",
            " ".join(DEFAULT_HASHTAGS + ["#ReelsIndia", "#Bhakti", "#HinduTraditions"]),
        ]
        return {
            "caption": "\n".join(caption_lines),
        }
