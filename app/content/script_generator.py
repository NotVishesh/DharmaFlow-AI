"""
DharmaFlow AI — Script Generator
Generates structured Pydantic-validated scripts using any configured LLM.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone

from pydantic import ValidationError

from app.content.schemas import ScriptSchema
from app.providers.llm import get_llm_provider, LLMProvider

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a knowledgeable, respectful Hindu devotional content writer creating educational short video scripts.

IMPORTANT RULES:
1. All factual claims MUST be sourced. Never invent scripture verses.
2. Never fabricate Sanskrit verses and present them as verified quotations.
3. Distinguish clearly between: direct quotation, translation, traditional interpretation, and original commentary.
4. No clickbait, fear-based hooks, or superstitious claims.
5. Respectful depictions of all deities, traditions, and sects.
6. Output ONLY valid JSON matching the exact schema requested. No prose before or after.
7. Never attribute invented sentences to Krishna, Rama, Shiva, or historical figures.
8. Acknowledge when different traditions tell a story differently.

You write for genuine educational and devotional value."""

SCRIPT_PROMPT_TEMPLATE = """Generate a complete Hindu devotional short video script as a JSON object.

Topic: {topic}
Category: {category}
Language: {language} (hi=Hindi, en=English, hi-en=Hinglish)
Target duration: {target_duration_seconds} seconds
Visual style: vertical 9:16 portrait format for YouTube Shorts

Return ONLY a JSON object with these exact fields:
{{
  "topic": "string",
  "category": "string",
  "language": "string",
  "target_duration_seconds": number,
  "title_options": ["title1", "title2", "title3"],
  "opening_hook": "compelling but truthful opening (0-3 seconds of narration)",
  "narration": "full narration text for the entire video",
  "scenes": [
    {{
      "scene_number": 1,
      "narration_text": "text for this scene",
      "approximate_duration_seconds": 8.0,
      "visual_prompt": "detailed English prompt for image generation, portrait orientation, classical Indian art style",
      "visual_type": "illustration",
      "camera_movement": "slow_zoom_in|slow_zoom_out|slow_pan_left|slow_pan_right|ken_burns|static",
      "subtitle_text": "displayed subtitle text (shorter than narration_text)",
      "sound_effects": null,
      "source_reference": "chapter/verse or null"
    }}
  ],
  "closing_line": "meaningful conclusion",
  "call_to_action": "gentle CTA or null",
  "source_references": [
    {{
      "name": "source name",
      "url": "url or null",
      "source_type": "scripture|translation|academic|calendar",
      "author": "author or null",
      "passage": "specific passage or null",
      "license_notes": "license info"
    }}
  ],
  "claims_and_evidence": [
    {{
      "claim_text": "factual claim",
      "claim_type": "direct_quotation|translation|traditional_interpretation|historical_claim|original_commentary",
      "source_name": "source or null",
      "source_reference": "reference or null",
      "verified": true/false,
      "needs_review": false,
      "reviewer_notes": null
    }}
  ],
  "copyright_notes": "notes on copyright status",
  "ai_disclosure_required": true,
  "verification_status": "DRAFT"
}}

Guidelines:
- Create {num_scenes} scenes totaling approximately {target_duration_seconds} seconds
- Each scene should have different visual composition
- Visual prompts must be in English, highly descriptive, portrait orientation
- For each scene, visual_type MUST be exactly one value from this list: illustration, portrait, landscape, abstract, deity, scripture, temple, nature, map, placeholder. Do not combine values or include the "|" character.
- For each scene, camera_movement MUST be exactly one value from this list: static, slow_zoom_in, slow_zoom_out, slow_pan_left, slow_pan_right, slow_pan_up, ken_burns.
- If using a Sanskrit verse, cite the exact chapter and verse number
- Narration should feel natural when spoken, not like written text
- Language {language}: write narration in the appropriate language/script"""


def _compute_fingerprint(script_data: dict) -> str:
    """SHA-256 of the normalized script narration for duplicate detection."""
    narration = script_data.get("narration", "") + "".join(
        s.get("narration_text", "") for s in script_data.get("scenes", [])
    )
    return hashlib.sha256(narration.strip().lower().encode("utf-8")).hexdigest()


def generate_script(
    topic: str,
    category: str,
    language: str = "hi",
    target_duration_seconds: int = 45,
    llm_provider: LLMProvider | None = None,
    max_attempts: int = 3,
    demo_mode: bool = False,
) -> ScriptSchema:
    """
    Generate and validate a script. Raises ValueError on unrecoverable failure.

    Args:
        topic: The video topic.
        category: Content category (e.g. 'scripture_explainer').
        language: 'hi', 'en', or 'hi-en'.
        target_duration_seconds: Target video length.
        llm_provider: Override the default LLM provider.
        max_attempts: Max regeneration attempts.
        demo_mode: Use mock provider regardless of config.

    Returns:
        Validated ScriptSchema.
    """
    if demo_mode:
        from app.providers.llm.providers import MockLLMProvider
        provider = MockLLMProvider()
    else:
        provider = llm_provider or get_llm_provider()

    if not provider.is_available() and not demo_mode:
        raise RuntimeError(
            f"LLM provider is not available. Check configuration. "
            f"For offline testing, use demo_mode=True."
        )

    # Estimate number of scenes: roughly 1 scene per 8-10 seconds
    num_scenes = max(2, min(8, target_duration_seconds // 8))

    prompt = SCRIPT_PROMPT_TEMPLATE.format(
        topic=topic,
        category=category,
        language=language,
        target_duration_seconds=target_duration_seconds,
        num_scenes=num_scenes,
    )

    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        logger.info("Script generation attempt %d/%d for topic: %s", attempt, max_attempts, topic)
        try:
            raw_data = provider.generate_json(prompt, system_prompt=SYSTEM_PROMPT)

            # Inject required fields if LLM omitted them
            if "verification_status" not in raw_data:
                raw_data["verification_status"] = "DRAFT"
            if "ai_disclosure_required" not in raw_data:
                raw_data["ai_disclosure_required"] = True

            # Validate with Pydantic
            script = ScriptSchema.model_validate(raw_data)

            # Add fingerprint and metadata
            fingerprint = _compute_fingerprint(raw_data)
            script.originality_report = type(script.originality_report or None).__new__(
                type(None)  # type: ignore
            ) if False else None  # We'll set it differently below

            # Build generation metadata
            gen_meta_data = {
                "llm_provider": type(provider).__name__,
                "llm_model": getattr(provider, "model", "unknown"),
                "generation_timestamp": datetime.now(timezone.utc).isoformat(),
                "attempts": attempt,
            }
            from app.content.schemas import GenerationMetadata, OriginalityReport
            script.generation_metadata = GenerationMetadata(**gen_meta_data)
            script.originality_report = OriginalityReport(fingerprint=fingerprint)

            logger.info("Script generated successfully: %s", topic[:60])
            return script

        except ValidationError as e:
            logger.warning("Validation failed attempt %d: %s", attempt, str(e)[:200])
            last_error = e
        except Exception as e:
            logger.warning("Generation error attempt %d: %s", attempt, str(e)[:200])
            last_error = e

    raise ValueError(
        f"Script generation failed after {max_attempts} attempts. Last error: {last_error}"
    )
