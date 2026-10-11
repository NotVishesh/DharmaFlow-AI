"""
DharmaFlow AI — Application Configuration
Loads config.yaml + environment variables. No secrets in code.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ── Root paths ────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_FILE = PROJECT_ROOT / "config" / "config.yaml"


def _load_yaml(path: Path) -> dict[str, Any]:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


# ── Sub-config models ─────────────────────────────────────────────────────────

class ContentConfig(BaseModel):
    timezone: str = "Asia/Kolkata"
    daily_video_limit: int = 1
    daily_upload_limit: int = 1
    require_human_approval: bool = True
    default_language: str = "hi"
    target_duration_seconds: int = 45
    min_duration_seconds: int = 15
    max_duration_seconds: int = 60
    max_regeneration_attempts: int = 3
    category_distribution: dict[str, float] = Field(default_factory=lambda: {
        "scripture_explainer": 0.30,
        "epic_storytelling": 0.25,
        "devotional_reflection": 0.20,
        "festival_cultural": 0.15,
        "temple_historical": 0.10,
    })
    blocked_topics: list[str] = Field(default_factory=list)
    review_required_topics: list[str] = Field(default_factory=lambda: [
        "caste", "conversion", "political", "real person", "miracle cure"
    ])


class LLMLocalConfig(BaseModel):
    engine: str = "ollama"
    model: str = "llama3.2:3b"
    base_url: str = "http://localhost:11434"
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout_seconds: int = 120


class LLMConfig(BaseModel):
    provider: str = "local"
    local: LLMLocalConfig = Field(default_factory=LLMLocalConfig)
    openai_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-3-5-haiku-20241022"
    gemini_model: str = "gemini-1.5-flash"
    temperature: float = 0.7
    max_tokens: int = 4096


class TTSConfig(BaseModel):
    provider: str = "gtts"
    language: str = "hi"
    speed: float = 1.0
    edge_tts_voice: str = "hi-IN-SwaraNeural"
    gtts_language: str = "hi"
    gtts_slow: bool = False
    piper_model_path: str = ""
    piper_voice: str = ""
    kokoro_model_path: str = ""
    kokoro_voice: str = "af_heart"
    inter_scene_pause_ms: int = 400
    output_format: str = "wav"


class ComfyUIConfig(BaseModel):
    enabled: bool = False
    url: str = "http://127.0.0.1:8188"
    workflow_file: str = "workflows/dharma_t2i.json"
    checkpoint: str = "v1-5-pruned-emaonly.safetensors"
    width: int = 768
    height: int = 1344
    steps: int = 25
    cfg_scale: float = 7.0
    timeout_seconds: int = 120
    max_retries: int = 3


class VisualsConfig(BaseModel):
    provider: str = "placeholder"
    comfyui: ComfyUIConfig = Field(default_factory=ComfyUIConfig)
    placeholder_width: int = 1080
    placeholder_height: int = 1920


class VideoRenderPreset(BaseModel):
    preset: str = "medium"
    crf: int = 23
    width: int = 1080
    height: int = 1920


class VideoConfig(BaseModel):
    width: int = 1080
    height: int = 1920
    fps: int = 30
    codec: str = "libx264"
    audio_codec: str = "aac"
    preset: str = "medium"
    crf: int = 23
    audio_bitrate: str = "192k"
    subtitle_font_size: int = 52
    subtitle_safe_margin: int = 100
    ken_burns_enabled: bool = True
    transition_duration: float = 0.4
    background_music_enabled: bool = False
    background_music_volume: float = 0.10
    intro_seconds: int = 0
    render_presets: dict[str, VideoRenderPreset] = Field(default_factory=lambda: {
        "draft": VideoRenderPreset(preset="ultrafast", crf=35, width=540, height=960),
        "standard": VideoRenderPreset(preset="medium", crf=23),
        "archival": VideoRenderPreset(preset="slow", crf=18),
    })


class YouTubeConfig(BaseModel):
    enabled: bool = False
    client_secrets_file: str = "config/client_secret.json"
    token_file: str = "config/youtube_token.json"
    default_privacy: str = "private"
    category_id: str = "29"
    default_language: str = "hi"
    made_for_kids: bool = False
    notify_subscribers: bool = False
    upload_chunk_size_mb: int = 256
    max_upload_retries: int = 5


class InstagramConfig(BaseModel):
    enabled: bool = False
    access_token: str = ""
    business_account_id: str = ""
    max_retries: int = 3


class CostsConfig(BaseModel):
    monthly_api_spend_cap_usd: float = 10.0
    track_compute_time: bool = True
    alert_on_cap_reached: bool = True


class StorageConfig(BaseModel):
    output_dir: str = "output"
    logs_dir: str = "logs"
    temp_dir: str = "temp"
    database_url: str = "sqlite:///./data/dharmaflow.db"
    max_storage_gb: float = 50.0
    keep_temp_on_error: bool = False


class LoggingConfig(BaseModel):
    level: str = "INFO"
    max_bytes: int = 10_485_760
    backup_count: int = 5
    format: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


# ── Main settings ─────────────────────────────────────────────────────────────

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    dharmaflow_env: str = "development"
    dharmaflow_secret_key: str = "change-me-please"
    dharmaflow_host: str = "127.0.0.1"
    dharmaflow_port: int = 8000
    dharmaflow_debug: bool = False

    # Database
    database_url: str = "sqlite:///./data/dharmaflow.db"

    # API Keys (never expose in logs or frontend)
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""

    # YouTube
    youtube_enabled: bool = False

    # Instagram
    instagram_enabled: bool = False
    instagram_access_token: str = ""
    instagram_business_account_id: str = ""

    # Overrides from YAML (populated after loading)
    content: ContentConfig = Field(default_factory=ContentConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    tts: TTSConfig = Field(default_factory=TTSConfig)
    visuals: VisualsConfig = Field(default_factory=VisualsConfig)
    video: VideoConfig = Field(default_factory=VideoConfig)
    youtube: YouTubeConfig = Field(default_factory=YouTubeConfig)
    instagram: InstagramConfig = Field(default_factory=InstagramConfig)
    costs: CostsConfig = Field(default_factory=CostsConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    logging_config: LoggingConfig = Field(default_factory=LoggingConfig)
    safe_mode: bool = True

    @field_validator("dharmaflow_secret_key")
    @classmethod
    def validate_secret(cls, v: str) -> str:
        if v in ("change-me-please", "", "change-me-to-a-random-string-at-least-32-chars"):
            import warnings
            warnings.warn(
                "DHARMAFLOW_SECRET_KEY is not set to a secure value. "
                "Set it in .env before production use.",
                stacklevel=2,
            )
        return v

    def is_production(self) -> bool:
        return self.dharmaflow_env == "production"

    def get_output_dir(self) -> Path:
        return (PROJECT_ROOT / self.storage.output_dir).resolve()

    def get_logs_dir(self) -> Path:
        return (PROJECT_ROOT / self.storage.logs_dir).resolve()

    def get_temp_dir(self) -> Path:
        return (PROJECT_ROOT / self.storage.temp_dir).resolve()

    def get_data_dir(self) -> Path:
        return (PROJECT_ROOT / "data").resolve()


def _merge_yaml_into_settings(settings: Settings, yaml_data: dict[str, Any]) -> Settings:
    """Deep-merge YAML config into the settings object."""
    data = settings.model_dump()

    if "content" in yaml_data:
        data["content"].update(yaml_data["content"])
    if "llm" in yaml_data:
        ld = yaml_data["llm"]
        if "local" in ld:
            data["llm"]["local"].update(ld.pop("local"))
        data["llm"].update({k: v for k, v in ld.items() if k != "local"})
    if "tts" in yaml_data:
        t = yaml_data["tts"]
        for k, v in t.items():
            if isinstance(v, dict):
                pass  # nested sections handled field-by-field
            else:
                data["tts"][k] = v
    if "visuals" in yaml_data:
        vd = yaml_data["visuals"]
        if "comfyui" in vd:
            data["visuals"]["comfyui"].update(vd.pop("comfyui"))
        data["visuals"].update(vd)
    if "video" in yaml_data:
        vd = yaml_data["video"]
        if "render_presets" in vd:
            for name, preset_data in vd.pop("render_presets").items():
                if name in data["video"]["render_presets"]:
                    data["video"]["render_presets"][name].update(preset_data)
        data["video"].update(vd)
    if "youtube" in yaml_data:
        data["youtube"].update(yaml_data["youtube"])
    if "instagram" in yaml_data:
        data["instagram"].update(yaml_data["instagram"])
    if "costs" in yaml_data:
        data["costs"].update(yaml_data["costs"])
    if "storage" in yaml_data:
        data["storage"].update(yaml_data["storage"])
    if "logging" in yaml_data:
        data["logging_config"].update(yaml_data["logging"])
    if "application" in yaml_data:
        app = yaml_data["application"]
        for k in ("env", "host", "port", "debug", "secret_key", "safe_mode"):
            if k in app:
                if k == "secret_key" and not app[k]:
                    continue
                mapped = f"dharmaflow_{k}" if k != "safe_mode" else "safe_mode"
                if mapped in data:
                    data[mapped] = app[k]

    return Settings(**data)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the application settings singleton."""
    yaml_data = _load_yaml(CONFIG_FILE)
    base = Settings()
    return _merge_yaml_into_settings(base, yaml_data)


def reload_settings() -> Settings:
    """Force reload (clears cache). Use after config file changes."""
    get_settings.cache_clear()
    return get_settings()
