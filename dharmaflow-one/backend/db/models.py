import enum
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, Boolean, Text, ForeignKey, JSON, Enum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class HardwareTier(str, enum.Enum):
    TIER_LOW = "TIER_LOW"       # < 6GB VRAM or CPU only
    TIER_MID = "TIER_MID"       # 6GB to 11.9GB VRAM
    TIER_HIGH = "TIER_HIGH"     # >= 12GB VRAM

class ExecutionMode(str, enum.Enum):
    REVIEW = "REVIEW"
    TURBO = "TURBO"

class ProjectStatus(str, enum.Enum):
    IDLE = "IDLE"
    GENERATING_SCRIPT = "GENERATING_SCRIPT"
    WAIT_SCRIPT_REVIEW = "WAIT_SCRIPT_REVIEW"
    GENERATING_SCENES = "GENERATING_SCENES"
    WAIT_SCENE_REVIEW = "WAIT_SCENE_REVIEW"
    GENERATING_AUDIO = "GENERATING_AUDIO"
    GENERATING_VISUALS = "GENERATING_VISUALS"
    MUXING_VIDEO = "MUXING_VIDEO"
    WAIT_VIDEO_REVIEW = "WAIT_VIDEO_REVIEW"
    UPLOADING = "UPLOADING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class ModelArtifact(Base):
    __tablename__ = "model_artifacts"
    id: Mapped[str] = mapped_column(String(64), primary_key=True) # e.g., "llm_qwen_3b_q4"
    role: Mapped[str] = mapped_column(String(32))                 # "LLM" | "TTS" | "VIDEO"
    tier: Mapped[HardwareTier] = mapped_column(Enum(HardwareTier))
    url: Mapped[str] = mapped_column(String(512))
    filename: Mapped[str] = mapped_column(String(256))
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer)
    downloaded_bytes: Mapped[int] = mapped_column(Integer, default=0)
    is_ready: Mapped[bool] = mapped_column(Boolean, default=False)

class YouTubeChannel(Base):
    __tablename__ = "youtube_channels"
    channel_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_email: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(255))
    thumbnail_url: Mapped[str] = mapped_column(String(512))
    subscriber_count: Mapped[int] = mapped_column(Integer, default=0)
    is_selected: Mapped[bool] = mapped_column(Boolean, default=False)

class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True) # UUID4
    topic: Mapped[str] = mapped_column(String(500))
    style: Mapped[str] = mapped_column(String(64), default="cinematic")
    mode: Mapped[ExecutionMode] = mapped_column(Enum(ExecutionMode), default=ExecutionMode.REVIEW)
    status: Mapped[ProjectStatus] = mapped_column(Enum(ProjectStatus), default=ProjectStatus.IDLE)
    
    target_duration_seconds: Mapped[int] = mapped_column(Integer, default=60, server_default="60")

    lip_sync: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    # Script & Auto-filled YouTube Metadata
    raw_script: Mapped[str | None] = mapped_column(Text, nullable=True)
    yt_title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    yt_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    yt_tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    yt_privacy: Mapped[str] = mapped_column(String(32), default="private") # "public" | "unlisted" | "private"
    target_channel_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    
    # Output & Upload tracking
    final_video_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    youtube_video_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    scenes: Mapped[list["Scene"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="Scene.scene_index",
        lazy="selectin",
    )

class Scene(Base):
    __tablename__ = "scenes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    scene_index: Mapped[int] = mapped_column(Integer) # 0-based order
    
    # User-editable fields in Review Mode
    dialogue_or_lyrics: Mapped[str] = mapped_column(Text)
    visual_prompt: Mapped[str] = mapped_column(Text)
    
    # Audio-First Synchronization fields
    audio_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True) # Measured from ffprobe
    visual_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    muxed_scene_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    project: Mapped["Project"] = relationship(back_populates="scenes")
