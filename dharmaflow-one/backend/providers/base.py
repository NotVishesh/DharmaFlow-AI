from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate_script_and_metadata(self, topic: str, style: str, target_duration_seconds: int = 60) -> dict[str, Any]:
        """
        Generate raw_script, yt_title, yt_description, and yt_tags.
        """
        pass

    @abstractmethod
    async def parse_scenes(self, raw_script: str) -> list[dict[str, Any]]:
        """
        Parse raw_script into ordered scenes with dialogue_or_lyrics and visual_prompt.
        """
        pass

class BaseTTSProvider(ABC):
    @abstractmethod
    async def synthesize(self, text: str, out_wav_path: Path) -> Path:
        """
        Synthesize speech audio to out_wav_path.
        """
        pass

class BaseVisualProvider(ABC):
    @abstractmethod
    async def generate_visual(self, prompt: str, out_path: Path, duration_sec: float = 3.0, dialogue: str = None, **kwargs) -> Path:
        """
        Generate a real multi-frame motion video covering the requested duration.
        """
        pass
