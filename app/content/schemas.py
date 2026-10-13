"""
DharmaFlow AI — Script Pydantic Schemas
Validated JSON schema for every script record and scene.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class SceneVisualType(str, Enum):
    ILLUSTRATION = "illustration"
    CINEMATIC = "cinematic"
    INFOGRAPHIC = "infographic"
    FUTURISTIC = "futuristic"
    HISTORICAL = "historical"
    ACTION = "action"
    MINIMALIST = "minimalist"
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"
    ABSTRACT = "abstract"
    DEITY = "deity"
    SCRIPTURE = "scripture"
    TEMPLE = "temple"
    NATURE = "nature"
    MAP = "map"
    PLACEHOLDER = "placeholder"


class CameraMovement(str, Enum):
    STATIC = "static"
    SLOW_ZOOM_IN = "slow_zoom_in"
    SLOW_ZOOM_OUT = "slow_zoom_out"
    SLOW_PAN_LEFT = "slow_pan_left"
    SLOW_PAN_RIGHT = "slow_pan_right"
    SLOW_PAN_UP = "slow_pan_up"
    KEN_BURNS = "ken_burns"


class ClaimType(str, Enum):
    DIRECT_QUOTATION = "direct_quotation"
    TRANSLATION = "translation"
    TRADITIONAL_INTERPRETATION = "traditional_interpretation"
    HISTORICAL_CLAIM = "historical_claim"
    SCIENTIFIC_CLAIM = "scientific_claim"
    EDUCATIONAL_FACT = "educational_fact"
    ORIGINAL_COMMENTARY = "original_commentary"
    FICTIONALIZED_STORYTELLING = "fictionalized_storytelling"


class SceneSchema(BaseModel):
    scene_number: int
    narration_text: str = Field(..., min_length=5)
    approximate_duration_seconds: float = Field(gt=0.0, lt=60.0)
    visual_prompt: str = Field(..., min_length=10)
    visual_type: SceneVisualType = SceneVisualType.ILLUSTRATION
    camera_movement: CameraMovement = CameraMovement.SLOW_ZOOM_IN
    subtitle_text: str
    sound_effects: Optional[list[str]] = None
    source_reference: Optional[str] = None
    asset_generation_status: str = "pending"
    asset_path: Optional[str] = None

    @field_validator("visual_type", mode="before")
    @classmethod
    def normalize_visual_type(cls, v):
        if isinstance(v, SceneVisualType):
            return v
        if isinstance(v, str):
            val = v.strip().lower().split("|")[0].strip()
            valid = {item.value for item in SceneVisualType}
            if val in valid:
                return val
        return SceneVisualType.ILLUSTRATION.value

    @field_validator("camera_movement", mode="before")
    @classmethod
    def normalize_camera_movement(cls, v):
        if isinstance(v, CameraMovement):
            return v
        if isinstance(v, str):
            val = v.strip().lower().split("|")[0].strip()
            valid = {item.value for item in CameraMovement}
            if val in valid:
                return val
        return CameraMovement.SLOW_ZOOM_IN.value

    @field_validator("visual_prompt")
    @classmethod
    def no_copyrighted_characters(cls, v: str) -> str:
        import re
        blocked = ["bollywood", "copyright", "trademarked", "logo"]
        for b in blocked:
            if re.search(rf"\b{re.escape(b)}\b", v, re.IGNORECASE):
                raise ValueError(f"Visual prompt contains restricted term: {b}")
        return v


class ClaimAndEvidence(BaseModel):
    claim_text: str
    claim_type: ClaimType = ClaimType.ORIGINAL_COMMENTARY
    source_name: Optional[str] = None
    source_reference: Optional[str] = None
    verified: bool = False
    needs_review: bool = False
    reviewer_notes: Optional[str] = None

    @field_validator("claim_type", mode="before")
    @classmethod
    def normalize_claim_type(cls, v):
        if isinstance(v, ClaimType):
            return v
        if isinstance(v, str):
            val = v.strip().lower().split("|")[0].strip()
            valid = {item.value for item in ClaimType}
            if val in valid:
                return val
            if "quote" in val or "quotation" in val:
                return ClaimType.DIRECT_QUOTATION.value
            if "scien" in val or "fact" in val:
                return ClaimType.SCIENTIFIC_CLAIM.value
            if "histor" in val:
                return ClaimType.HISTORICAL_CLAIM.value
            if "story" in val or "fiction" in val:
                return ClaimType.FICTIONALIZED_STORYTELLING.value
        return ClaimType.ORIGINAL_COMMENTARY.value


class SourceReference(BaseModel):
    name: str
    url: Optional[str] = None
    source_type: str
    author: Optional[str] = None
    passage: Optional[str] = None
    license_notes: Optional[str] = None


class GenerationMetadata(BaseModel):
    llm_provider: str
    llm_model: str
    generation_timestamp: str
    attempts: int = 1
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    cost_usd: Optional[float] = None


class OriginalityReport(BaseModel):
    fingerprint: str
    is_duplicate: bool = False
    similar_scripts: list[str] = Field(default_factory=list)
    similarity_scores: dict[str, float] = Field(default_factory=dict)
    hook_diversity_score: float = Field(ge=0.0, le=1.0, default=1.0)
    metadata_similarity_warnings: list[str] = Field(default_factory=list)
    passed: bool = True


class ScriptSchema(BaseModel):
    """Complete validated script record."""
    topic: str = Field(..., min_length=5, max_length=512)
    category: str
    language: str = Field(pattern=r"^(hi|en|hi-en)$")
    target_duration_seconds: int = Field(ge=15, le=60, default=45)
    title_options: list[str] = Field(..., min_length=1, max_length=5)
    opening_hook: str = Field(..., min_length=10)
    narration: str = Field(..., min_length=50)
    scenes: list[SceneSchema] = Field(..., min_length=2, max_length=12)
    closing_line: str
    call_to_action: Optional[str] = None
    source_references: list[SourceReference] = Field(default_factory=list)
    claims_and_evidence: list[ClaimAndEvidence] = Field(default_factory=list)
    copyright_notes: str = ""
    ai_disclosure_required: bool = True
    verification_status: str = "DRAFT"
    originality_report: Optional[OriginalityReport] = None
    generation_metadata: Optional[GenerationMetadata] = None

    @field_validator("title_options")
    @classmethod
    def titles_not_clickbait(cls, v: list[str]) -> list[str]:
        """Reject common manipulative clickbait patterns."""
        flagged = [
            "you won't believe",
            "secret they hid",
            "this one trick",
            "guarantee",
            "100%",
            "exposed",
        ]
        for title in v:
            for f in flagged:
                if f.lower() in title.lower():
                    raise ValueError(
                        f"Title '{title}' contains discouraged clickbait phrase: '{f}'"
                    )
        return v

    @field_validator("opening_hook")
    @classmethod
    def hook_not_fear_based(cls, v: str) -> str:
        import re
        fear_phrases = [
            "you will die", "curse", "sin", "hellfire", "disaster if you don't"
        ]
        for phrase in fear_phrases:
            if re.search(rf"\b{re.escape(phrase)}\b", v, re.IGNORECASE):
                raise ValueError(f"Hook uses fear-based language: '{phrase}'")
        return v

    def total_narration_duration(self) -> float:
        return sum(s.approximate_duration_seconds for s in self.scenes)

    def has_unsupported_claims(self) -> bool:
        return any(
            not c.verified and c.claim_type in (
                ClaimType.HISTORICAL_CLAIM,
                ClaimType.DIRECT_QUOTATION,
                ClaimType.SCIENTIFIC_CLAIM,
            )
            for c in self.claims_and_evidence
        )
