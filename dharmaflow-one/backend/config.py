import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr, Field
from typing import Literal

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
MEDIA_DIR = BASE_DIR / "media"
TEMP_DIR = BASE_DIR / "temp"

for d in [DATA_DIR, MODELS_DIR, MEDIA_DIR, TEMP_DIR]:
    d.mkdir(parents=True, exist_ok=True)

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    DHARMAFLOW_MOCK_AI: bool = os.getenv("DHARMAFLOW_MOCK_AI", "0") in ("1", "true", "True")
    DATABASE_URL: str = f"sqlite+aiosqlite:///{DATA_DIR.as_posix()}/dharmaflow.db"
    CLIENT_SECRETS_PATH: Path = BASE_DIR / "client_secrets.json"
    MODELS_DIR: Path = MODELS_DIR
    MEDIA_DIR: Path = MEDIA_DIR
    TEMP_DIR: Path = TEMP_DIR
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    VIDEO_PROVIDER: Literal['local', 'fal', 'local_then_fal'] = 'local'
    VIDEO_MODEL_ID: str = 'Wan-AI/Wan2.1-T2V-1.3B-Diffusers'
    VIDEO_MODEL_DIR: Path = MODELS_DIR / 'wan-2.1-1.3b'
    VIDEO_STEPS: int = Field(default=30, ge=10, le=60)
    VIDEO_OFFLOAD: Literal['resident', 'sequential'] = 'resident'
    VIDEO_SEED: int = 42
    VIDEO_TIMEOUT_SECONDS: int = 7200
    FAL_KEY: SecretStr = SecretStr('')
    OLLAMA_URL: str = 'http://127.0.0.1:11434'
    OLLAMA_MODEL: str = 'llama3.2:3b'

    def __init__(self, **values):
        super().__init__(**values)
        raw_url = os.getenv("DHARMAFLOW_DATABASE_URL") or self.DATABASE_URL
        if raw_url.startswith("sqlite:///") and not raw_url.startswith("sqlite+aiosqlite:///"):
            raw_url = raw_url.replace("sqlite:///", "sqlite+aiosqlite:///")
        self.DATABASE_URL = raw_url

settings = Settings()
