"""
DharmaFlow AI — Audio Generation Manager
Coordinates text-to-speech synthesis, speech duration estimation, and audio validation.
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Optional

from app.content.schemas import SceneSchema
from app.providers.tts import TTSProvider, get_tts_provider
from app.providers.tts.providers import _generate_silence_wav, validate_audio_file

logger = logging.getLogger(__name__)


class AudioManager:
    """Manages narration voiceover generation."""

    def __init__(self, provider: Optional[TTSProvider] = None, speed: float = 1.0):
        self.provider = provider or get_tts_provider()
        self.speed = speed

    def generate_scene_narration(
        self,
        scene: SceneSchema,
        output_dir: Path,
    ) -> Path:
        """Synthesize narration WAV for a scene."""
        output_dir.mkdir(parents=True, exist_ok=True)
        wav_path = output_dir / f"audio_{scene.scene_number:03d}.wav"

        try:
            self.provider.synthesize(
                text=scene.narration_text,
                output_path=wav_path,
                speed=self.speed,
            )
            # Inspect probe data to confirm duration
            probe = validate_audio_file(wav_path)
            actual_duration = float(probe.get("format", {}).get("duration", scene.approximate_duration_seconds))
            scene.approximate_duration_seconds = actual_duration
        except Exception as e:
            logger.warning("TTS generation failed for scene %d: %s. Using silence fallback.", scene.scene_number, e)
            _generate_silence_wav(wav_path, duration=scene.approximate_duration_seconds)

        return wav_path

    @staticmethod
    def compute_file_hash(path: Path) -> str:
        """Compute SHA-256 hash of generated audio asset."""
        sha = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha.update(chunk)
        return sha.hexdigest()
