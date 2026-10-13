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

SYSTEM_PROMPT = """You are an expert short-form video creator, researcher, and scriptwriter capable of producing engaging, accurate, high-retention scripts on ANY topic (Technology & AI, Science & Space, History, Motivation & Mindset, Finance & Business, Storytelling, Health & Psychology, Facts & Trivia, Philosophy & Spirituality, etc.).

IMPORTANT RULES:
1. All factual, scientific, historical, or scriptural claims MUST be accurate and well-sourced. Never fabricate facts, statistics, or quotes.
2. Adapt your tone, pacing, and visual art direction dynamically to match the requested topic and category.
3. Distinguish clearly between: direct quotation, scientific/educational fact, historical claim, storytelling, and original commentary.
4. No deceptive clickbait, fear-mongering hooks, or manipulative claims.
5. Output ONLY valid JSON matching the exact schema requested. No prose before or after.
6. Never use copyrighted character names, logos, or trademarked terms in visual prompts.

You write for maximum viewer engagement, clarity, retention, and genuine educational or entertainment value."""

SCRIPT_PROMPT_TEMPLATE = """Generate a complete vertical short-form video script (YouTube Shorts / Instagram Reels) as a JSON object.

Topic: {topic}
Category: {category}
Language: {language} (en=English, hi=Hindi, hi-en=Hinglish)
Target duration: {target_duration_seconds} seconds
Visual style: vertical 9:16 portrait format tailored to the topic ({category})

Return ONLY a JSON object with these exact fields:
{{
  "topic": "{topic}",
  "category": "{category}",
  "language": "{language}",
  "target_duration_seconds": {target_duration_seconds},
  "title_options": ["title1", "title2", "title3"],
  "opening_hook": "compelling, curiosity-driven opening hook (0-3 seconds of narration)",
  "narration": "full cohesive narration text for the entire video (at least 60 characters)",
  "scenes": [
    {{
      "scene_number": 1,
      "narration_text": "spoken narration text for this scene",
      "approximate_duration_seconds": 8.0,
      "visual_prompt": "detailed English prompt for image generation in 9:16 portrait orientation matching the topic's visual aesthetic (e.g. cinematic, futuristic, photorealistic, historical, or artistic)",
      "visual_type": "cinematic",
      "camera_movement": "slow_zoom_in",
      "subtitle_text": "concise displayed subtitle text",
      "sound_effects": null,
      "source_reference": "source or reference note or null"
    }}
  ],
  "closing_line": "memorable takeaway or conclusion",
  "call_to_action": "engaging CTA or null",
  "source_references": [
    {{
      "name": "authoritative source or reference name",
      "url": "url or null",
      "source_type": "academic|scientific|historical|literature|scripture|reference",
      "author": "author/organization or null",
      "passage": "specific paper, book, study, or chapter reference",
      "license_notes": "Public factual information / Educational use"
    }}
  ],
  "claims_and_evidence": [
    {{
      "claim_text": "key factual or educational point made in the script",
      "claim_type": "original_commentary",
      "source_name": "source name",
      "source_reference": "reference detail",
      "verified": true,
      "needs_review": false,
      "reviewer_notes": null
    }}
  ],
  "copyright_notes": "Original script and narration.",
  "ai_disclosure_required": true,
  "verification_status": "VERIFIED"
}}

Guidelines:
- Create {num_scenes} scenes totaling approximately {target_duration_seconds} seconds
- Each scene's narration_text MUST be 2 to 3 complete sentences (around {words_per_scene} words per scene) so the spoken audio naturally matches the {target_duration_seconds}-second target duration
- Each scene must have a distinct, vivid visual composition tailored to the topic
- Visual prompts must be in English, highly descriptive, portrait orientation (avoid words like 'logo', 'copyright', 'trademarked', 'bollywood')
- For each scene, visual_type MUST be one of: cinematic, illustration, infographic, futuristic, historical, action, minimalist, portrait, landscape, abstract, nature, map, deity, scripture, temple, placeholder
- For each scene, camera_movement MUST be one of: static, slow_zoom_in, slow_zoom_out, slow_pan_left, slow_pan_right, slow_pan_up, ken_burns
- Narration should sound natural, expressive, and conversational when spoken aloud
- Language {language}: write narration and subtitles in the requested language"""


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

    # Estimate number of scenes: roughly 1 scene per 7-8 seconds
    num_scenes = max(2, min(8, round(target_duration_seconds / 7.5)))
    words_per_scene = max(18, int((target_duration_seconds / num_scenes) * 2.5))

    prompt = SCRIPT_PROMPT_TEMPLATE.format(
        topic=topic,
        category=category,
        language=language,
        target_duration_seconds=target_duration_seconds,
        num_scenes=num_scenes,
        words_per_scene=words_per_scene,
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
