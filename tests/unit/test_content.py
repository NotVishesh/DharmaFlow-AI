"""
DharmaFlow AI — Unit Tests: Content and Script Generation
"""
from __future__ import annotations

import json
import pytest
from pydantic import ValidationError

from app.content.schemas import ScriptSchema, SceneSchema, OriginalityReport, GenerationMetadata


# ── Sample valid script data ───────────────────────────────────────────────────

def make_valid_script() -> dict:
    return {
        "topic": "Bhagavad Gita Chapter 2 Verse 47 — Karma without attachment",
        "category": "scripture_explainer",
        "language": "hi",
        "target_duration_seconds": 40,
        "title_options": [
            "भगवद गीता 2:47 — कर्मयोग का सार",
            "Bhagavad Gita: Act Without Attachment",
        ],
        "opening_hook": "क्या आप जानते हैं कि भगवद गीता का एक श्लोक आपका जीवन बदल सकता है?",
        "narration": (
            "कुरुक्षेत्र में अर्जुन को श्री कृष्ण ने कहा: "
            "कर्मण्येवाधिकारस्ते मा फलेषु कदाचन। "
            "तुम्हारा अधिकार केवल कर्म पर है। यही जीवन का सत्य है।"
        ),
        "scenes": [
            {
                "scene_number": 1,
                "narration_text": "भगवद गीता 2:47 — कर्मण्येवाधिकारस्ते",
                "approximate_duration_seconds": 8.0,
                "visual_prompt": "Ancient battlefield at sunrise, warrior in chariot, classical Indian art style, vertical 9:16",
                "visual_type": "illustration",
                "camera_movement": "slow_zoom_in",
                "subtitle_text": "कर्मण्येवाधिकारस्ते",
                "source_reference": "Bhagavad Gita 2:47",
            },
            {
                "scene_number": 2,
                "narration_text": "फल की चिंता मत करो — बस कर्म करते रहो",
                "approximate_duration_seconds": 8.0,
                "visual_prompt": "Meditating figure at sunrise, Himalayan backdrop, spiritual atmosphere, portrait orientation",
                "visual_type": "illustration",
                "camera_movement": "slow_zoom_out",
                "subtitle_text": "कर्म करो, फल की चिंता मत करो",
                "source_reference": None,
            },
        ],
        "closing_line": "यही है भगवद गीता का कालजयी संदेश।",
        "call_to_action": "Like करें और Follow करें।",
        "source_references": [
            {
                "name": "Bhagavad Gita 2:47",
                "url": "https://www.gitasupersite.iitk.ac.in/",
                "source_type": "scripture",
                "author": "Vyasa",
                "passage": "कर्मण्येवाधिकारस्ते मा फलेषु कदाचन",
                "license_notes": "Ancient scripture, public domain",
            }
        ],
        "claims_and_evidence": [
            {
                "claim_text": "Bhagavad Gita 2:47 teaches karma without attachment",
                "claim_type": "traditional_interpretation",
                "source_name": "Bhagavad Gita 2:47",
                "verified": True,
                "needs_review": False,
            }
        ],
        "copyright_notes": "Original narration. Sanskrit verse is ancient scripture.",
        "ai_disclosure_required": True,
        "verification_status": "VERIFIED",
    }


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestScriptSchema:
    def test_valid_script_accepted(self):
        data = make_valid_script()
        script = ScriptSchema.model_validate(data)
        assert script.topic == data["topic"]
        assert len(script.scenes) == 2
        assert script.verification_status == "VERIFIED"

    def test_missing_topic_rejected(self):
        data = make_valid_script()
        del data["topic"]
        with pytest.raises(ValidationError):
            ScriptSchema.model_validate(data)

    def test_short_narration_rejected(self):
        data = make_valid_script()
        data["narration"] = "Too short"
        with pytest.raises(ValidationError):
            ScriptSchema.model_validate(data)

    def test_invalid_language_rejected(self):
        data = make_valid_script()
        data["language"] = "fr"
        with pytest.raises(ValidationError):
            ScriptSchema.model_validate(data)

    def test_duration_out_of_range_rejected(self):
        data = make_valid_script()
        data["target_duration_seconds"] = 200
        with pytest.raises(ValidationError):
            ScriptSchema.model_validate(data)

    def test_clickbait_title_rejected(self):
        data = make_valid_script()
        data["title_options"] = ["You won't believe this spiritual secret"]
        with pytest.raises(ValidationError):
            ScriptSchema.model_validate(data)

    def test_fear_based_hook_rejected(self):
        data = make_valid_script()
        data["opening_hook"] = "You will die if you ignore this divine warning!"
        with pytest.raises(ValidationError):
            ScriptSchema.model_validate(data)

    def test_copyrighted_visual_prompt_rejected(self):
        data = make_valid_script()
        data["scenes"][0]["visual_prompt"] = "Bollywood celebrity in copyright scene"
        with pytest.raises(ValidationError):
            ScriptSchema.model_validate(data)

    def test_unsupported_claims_detected(self):
        data = make_valid_script()
        data["claims_and_evidence"][0]["claim_type"] = "historical_claim"
        data["claims_and_evidence"][0]["verified"] = False
        script = ScriptSchema.model_validate(data)
        assert script.has_unsupported_claims() is True

    def test_verified_claims_pass(self):
        script = ScriptSchema.model_validate(make_valid_script())
        assert script.has_unsupported_claims() is False

    def test_total_duration_calculation(self):
        script = ScriptSchema.model_validate(make_valid_script())
        total = script.total_narration_duration()
        assert total == pytest.approx(16.0, abs=0.1)


class TestSceneSchema:
    def test_valid_scene_accepted(self):
        scene = SceneSchema(
            scene_number=1,
            narration_text="This is a test narration",
            approximate_duration_seconds=8.0,
            visual_prompt="Ancient temple with divine light, portrait orientation, Indian art style",
            subtitle_text="Test subtitle",
        )
        assert scene.scene_number == 1

    def test_negative_duration_rejected(self):
        with pytest.raises(ValidationError):
            SceneSchema(
                scene_number=1,
                narration_text="Test",
                approximate_duration_seconds=-1.0,
                visual_prompt="Ancient temple with divine light and devotional atmosphere",
                subtitle_text="Test",
            )


class TestOriginalityReport:
    def test_duplicate_detection(self):
        report = OriginalityReport(
            fingerprint="abc123",
            is_duplicate=True,
            similar_scripts=["script-1"],
            similarity_scores={"script-1": 1.0},
            passed=False,
        )
        assert report.passed is False

    def test_unique_passes(self):
        report = OriginalityReport(fingerprint="unique-hash", passed=True)
        assert report.passed is True
