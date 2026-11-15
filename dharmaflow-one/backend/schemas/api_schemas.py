from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from backend.db.models import HardwareTier, ExecutionMode, ProjectStatus

class ModelArtifactSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    role: str
    tier: HardwareTier
    url: str
    filename: str
    sha256: str
    size_bytes: int
    downloaded_bytes: int = 0
    is_ready: bool = False

class HardwareProfileResponse(BaseModel):
    generation: dict = Field(default_factory=dict)
    hardware_tier: HardwareTier
    vram_gb: float
    ram_gb: float
    models_ready: bool
    models: list[ModelArtifactSchema] = []

class YouTubeChannelSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    channel_id: str
    account_email: str
    title: str
    thumbnail_url: str
    subscriber_count: int = 0
    is_selected: bool = False

class SelectChannelRequest(BaseModel):
    channel_id: str

class CreateProjectRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=500)
    style: str = "cinematic"
    lip_sync: bool = False
    target_duration_seconds: int = Field(default=60, ge=15, le=120)
    mode: ExecutionMode = ExecutionMode.REVIEW

class SceneSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    scene_index: int
    dialogue_or_lyrics: str
    visual_prompt: str
    audio_path: str | None = None
    duration_ms: int | None = None
    visual_path: str | None = None
    muxed_scene_path: str | None = None

class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    topic: str
    style: str
    mode: ExecutionMode
    lip_sync: bool = False
    target_duration_seconds: int = 60
    status: ProjectStatus
    raw_script: str | None = None
    yt_title: str | None = None
    yt_description: str | None = None
    yt_tags: list[str] | None = None
    yt_privacy: str = "private"
    target_channel_id: str | None = None
    final_video_path: str | None = None
    youtube_video_id: str | None = None
    error_message: str | None = None
    created_at: datetime
    scenes: list[SceneSchema] = []

class ApproveScriptRequest(BaseModel):
    raw_script: str = Field(min_length=1, max_length=20000)

class SceneUpdateRequest(BaseModel):
    id: str
    dialogue_or_lyrics: str = Field(min_length=1, max_length=2000)
    visual_prompt: str = Field(min_length=1, max_length=4000)

class ApproveScenesRequest(BaseModel):
    scenes: list[SceneUpdateRequest]

class UpdateMetadataRequest(BaseModel):
    yt_title: str | None = None
    yt_description: str | None = None
    yt_tags: list[str] | None = None
    yt_privacy: str | None = None
    target_channel_id: str | None = None
