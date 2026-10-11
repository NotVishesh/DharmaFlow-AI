"""
DharmaFlow AI — SQLAlchemy Database Models
All tables use UUIDs as primary keys and carry creation/update timestamps.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


# ── Enumerations ──────────────────────────────────────────────────────────────

class VerificationStatus(str, PyEnum):
    DRAFT = "DRAFT"
    SOURCES_PENDING = "SOURCES_PENDING"
    VERIFIED = "VERIFIED"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class JobStatus(str, PyEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    RETRYING = "RETRYING"


class ApprovalStatus(str, PyEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REQUIRES_EDIT = "REQUIRES_EDIT"


class ContentCategory(str, PyEnum):
    SCRIPTURE_EXPLAINER = "scripture_explainer"
    EPIC_STORYTELLING = "epic_storytelling"
    DEVOTIONAL_REFLECTION = "devotional_reflection"
    FESTIVAL_CULTURAL = "festival_cultural"
    TEMPLE_HISTORICAL = "temple_historical"


class Language(str, PyEnum):
    HINDI = "hi"
    ENGLISH = "en"
    HINGLISH = "hi-en"


class PrivacyStatus(str, PyEnum):
    PRIVATE = "private"
    UNLISTED = "unlisted"
    PUBLIC = "public"


class AssetType(str, PyEnum):
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    SUBTITLE = "subtitle"
    THUMBNAIL = "thumbnail"


# ── Helper mixin ──────────────────────────────────────────────────────────────

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# ── Models ────────────────────────────────────────────────────────────────────

class ContentIdea(TimestampMixin, Base):
    """A raw content idea before a script is generated."""
    __tablename__ = "content_ideas"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    topic: Mapped[str] = mapped_column(String(512), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    language: Mapped[str] = mapped_column(String(8), default="hi")
    priority: Mapped[int] = mapped_column(Integer, default=5)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    source_hint: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list | None] = mapped_column(JSON)

    scripts: Mapped[list["Script"]] = relationship(back_populates="idea")


class ResearchSource(TimestampMixin, Base):
    """A verified source that can be associated with scripts and claims."""
    __tablename__ = "research_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    url: Mapped[str | None] = mapped_column(String(1024))
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    author: Mapped[str | None] = mapped_column(String(256))
    publisher: Mapped[str | None] = mapped_column(String(256))
    edition: Mapped[str | None] = mapped_column(String(256))
    license_notes: Mapped[str | None] = mapped_column(Text)
    verification_date: Mapped[str | None] = mapped_column(String(32))
    reliability_notes: Mapped[str | None] = mapped_column(Text)
    passage_locator: Mapped[str | None] = mapped_column(String(512))
    is_trusted: Mapped[bool] = mapped_column(Boolean, default=True)

    claims: Mapped[list["Claim"]] = relationship(back_populates="source")


class Script(TimestampMixin, Base):
    """A fully structured video script with verification state."""
    __tablename__ = "scripts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    idea_id: Mapped[str | None] = mapped_column(ForeignKey("content_ideas.id"))
    topic: Mapped[str] = mapped_column(String(512), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    language: Mapped[str] = mapped_column(String(8), default="hi")
    target_duration_seconds: Mapped[int] = mapped_column(Integer, default=45)
    title_options: Mapped[list | None] = mapped_column(JSON)
    opening_hook: Mapped[str | None] = mapped_column(Text)
    narration: Mapped[str | None] = mapped_column(Text)
    scenes: Mapped[list | None] = mapped_column(JSON)
    closing_line: Mapped[str | None] = mapped_column(Text)
    call_to_action: Mapped[str | None] = mapped_column(Text)
    source_references: Mapped[list | None] = mapped_column(JSON)
    claims_and_evidence: Mapped[list | None] = mapped_column(JSON)
    copyright_notes: Mapped[str | None] = mapped_column(Text)
    ai_disclosure_required: Mapped[bool] = mapped_column(Boolean, default=True)
    verification_status: Mapped[str] = mapped_column(
        String(32), default=VerificationStatus.DRAFT
    )
    originality_report: Mapped[dict | None] = mapped_column(JSON)
    generation_metadata: Mapped[dict | None] = mapped_column(JSON)
    fingerprint: Mapped[str | None] = mapped_column(String(256))
    llm_provider: Mapped[str | None] = mapped_column(String(64))
    llm_model: Mapped[str | None] = mapped_column(String(128))

    idea: Mapped["ContentIdea | None"] = relationship(back_populates="scripts")
    claims: Mapped[list["Claim"]] = relationship(back_populates="script")
    render_jobs: Mapped[list["RenderJob"]] = relationship(back_populates="script")


class Claim(TimestampMixin, Base):
    """A factual claim extracted from a script, linked to evidence."""
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    script_id: Mapped[str] = mapped_column(ForeignKey("scripts.id"), nullable=False)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("research_sources.id"))
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[str] = mapped_column(String(64), default="factual")
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)

    script: Mapped["Script"] = relationship(back_populates="claims")
    source: Mapped["ResearchSource | None"] = relationship(back_populates="claims")


class MediaAsset(TimestampMixin, Base):
    """A generated or imported media file with provenance."""
    __tablename__ = "media_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    render_job_id: Mapped[str | None] = mapped_column(ForeignKey("render_jobs.id"))
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_hash: Mapped[str | None] = mapped_column(String(128))
    provider: Mapped[str | None] = mapped_column(String(64))
    prompt: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(String(128))
    license: Mapped[str | None] = mapped_column(String(256))
    scene_number: Mapped[int | None] = mapped_column(Integer)
    is_placeholder: Mapped[bool] = mapped_column(Boolean, default=False)
    generation_params: Mapped[dict | None] = mapped_column(JSON)

    render_job: Mapped["RenderJob | None"] = relationship(back_populates="assets")


class RenderJob(TimestampMixin, Base):
    """Tracks the full lifecycle of a video render."""
    __tablename__ = "render_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    script_id: Mapped[str] = mapped_column(ForeignKey("scripts.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=JobStatus.PENDING)
    render_preset: Mapped[str] = mapped_column(String(32), default="standard")
    output_path: Mapped[str | None] = mapped_column(String(1024))
    output_hash: Mapped[str | None] = mapped_column(String(128))
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    config_snapshot: Mapped[dict | None] = mapped_column(JSON)
    error_detail: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    compute_seconds: Mapped[float | None] = mapped_column(Float)
    provenance_manifest: Mapped[dict | None] = mapped_column(JSON)

    script: Mapped["Script"] = relationship(back_populates="render_jobs")
    assets: Mapped[list["MediaAsset"]] = relationship(back_populates="render_job")
    qc_result: Mapped["QCResult | None"] = relationship(back_populates="render_job", uselist=False)
    approval: Mapped["Approval | None"] = relationship(back_populates="render_job", uselist=False)
    publish_jobs: Mapped[list["PublishJob"]] = relationship(back_populates="render_job")


class QCResult(TimestampMixin, Base):
    """Quality-control results for a rendered video."""
    __tablename__ = "qc_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    render_job_id: Mapped[str] = mapped_column(ForeignKey("render_jobs.id"), unique=True, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[float | None] = mapped_column(Float)
    checks: Mapped[dict | None] = mapped_column(JSON)
    blocking_errors: Mapped[list | None] = mapped_column(JSON)
    warnings: Mapped[list | None] = mapped_column(JSON)
    ffprobe_data: Mapped[dict | None] = mapped_column(JSON)
    duration_actual: Mapped[float | None] = mapped_column(Float)
    duration_expected: Mapped[float | None] = mapped_column(Float)

    render_job: Mapped["RenderJob"] = relationship(back_populates="qc_result")


class Approval(TimestampMixin, Base):
    """Human approval record for a render job."""
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    render_job_id: Mapped[str] = mapped_column(ForeignKey("render_jobs.id"), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=ApprovalStatus.PENDING)
    approved_by: Mapped[str | None] = mapped_column(String(256))
    notes: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    render_job: Mapped["RenderJob"] = relationship(back_populates="approval")


class PublishJob(TimestampMixin, Base):
    """A platform-publishing attempt."""
    __tablename__ = "publish_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    render_job_id: Mapped[str] = mapped_column(ForeignKey("render_jobs.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)  # youtube | instagram
    status: Mapped[str] = mapped_column(String(32), default=JobStatus.PENDING)
    privacy: Mapped[str] = mapped_column(String(32), default="private")
    title: Mapped[str | None] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list | None] = mapped_column(JSON)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    platform_video_id: Mapped[str | None] = mapped_column(String(256))
    platform_url: Mapped[str | None] = mapped_column(String(1024))
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_detail: Mapped[str | None] = mapped_column(Text)
    ai_disclosure_set: Mapped[bool] = mapped_column(Boolean, default=False)
    upload_response: Mapped[dict | None] = mapped_column(JSON)

    render_job: Mapped["RenderJob"] = relationship(back_populates="publish_jobs")
    analytics: Mapped[list["AnalyticsSnapshot"]] = relationship(back_populates="publish_job")


class AnalyticsSnapshot(TimestampMixin, Base):
    """A point-in-time analytics record for a published video."""
    __tablename__ = "analytics_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    publish_job_id: Mapped[str] = mapped_column(ForeignKey("publish_jobs.id"), nullable=False)
    snapshot_date: Mapped[str] = mapped_column(String(32), nullable=False)
    views: Mapped[int | None] = mapped_column(Integer)
    likes: Mapped[int | None] = mapped_column(Integer)
    comments: Mapped[int | None] = mapped_column(Integer)
    watch_time_minutes: Mapped[float | None] = mapped_column(Float)
    avg_view_duration_seconds: Mapped[float | None] = mapped_column(Float)
    impressions: Mapped[int | None] = mapped_column(Float)
    ctr: Mapped[float | None] = mapped_column(Float)
    subscribers_gained: Mapped[int | None] = mapped_column(Integer)
    raw_data: Mapped[dict | None] = mapped_column(JSON)

    publish_job: Mapped["PublishJob"] = relationship(back_populates="analytics")


class AutomationRun(TimestampMixin, Base):
    """Record of a daily automation run."""
    __tablename__ = "automation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    status: Mapped[str] = mapped_column(String(32), default=JobStatus.PENDING)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False)
    trigger: Mapped[str] = mapped_column(String(64), default="scheduler")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    videos_generated: Mapped[int] = mapped_column(Integer, default=0)
    videos_published: Mapped[int] = mapped_column(Integer, default=0)
    error_detail: Mapped[str | None] = mapped_column(Text)
    lock_file: Mapped[str | None] = mapped_column(String(1024))


class ModelConfig(TimestampMixin, Base):
    """Runtime configuration snapshot for AI models."""
    __tablename__ = "model_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    model_type: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str] = mapped_column(String(256), nullable=False)
    config: Mapped[dict | None] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    license_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    license_notes: Mapped[str | None] = mapped_column(Text)


class CostRecord(TimestampMixin, Base):
    """API and compute cost tracking."""
    __tablename__ = "cost_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_id: Mapped[str | None] = mapped_column(String(36))
    job_type: Mapped[str | None] = mapped_column(String(64))
    provider: Mapped[str | None] = mapped_column(String(64))
    operation: Mapped[str | None] = mapped_column(String(128))
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Float)
    compute_seconds: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
