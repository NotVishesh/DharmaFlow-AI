"""
DharmaFlow AI — TTS Provider Interface
Supports gTTS (free online), edge-tts (Microsoft, free), Piper (local), and Kokoro (local).
"""
from __future__ import annotations

import logging
import subprocess
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class TTSProvider(ABC):
    """Abstract text-to-speech interface."""

    @abstractmethod
    def synthesize(self, text: str, output_path: Path, speed: float = 1.0) -> Path:
        """Synthesize speech and write to output_path. Returns the output path."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        ...

    def estimate_duration(self, text: str, language: str = "hi") -> float:
        """Rough estimate of speech duration in seconds."""
        words = len(text.split())
        # ~130 words/min for Hindi, ~150 for English
        wpm = 120 if language in ("hi", "hi-en") else 145
        return (words / wpm) * 60


class GTTSProvider(TTSProvider):
    """
    Google Text-to-Speech (gTTS) — free, requires internet.
    License: Free for personal and commercial use.
    Voice is not cloned from any real person.
    """

    def __init__(self, language: str = "hi", slow: bool = False):
        self.language = language
        self.slow = slow

    def is_available(self) -> bool:
        try:
            import gtts  # noqa
            return True
        except ImportError:
            return False

    def synthesize(self, text: str, output_path: Path, speed: float = 1.0) -> Path:
        try:
            from gtts import gTTS
        except ImportError:
            raise RuntimeError("gtts not installed. Run: pip install gtts")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # gTTS outputs MP3; convert to WAV if needed
        mp3_path = output_path.with_suffix(".mp3")
        tts = gTTS(text=text, lang=self.language, slow=self.slow)
        tts.save(str(mp3_path))

        if output_path.suffix.lower() == ".wav":
            _convert_to_wav(mp3_path, output_path, speed=speed)
            mp3_path.unlink(missing_ok=True)
        else:
            mp3_path.rename(output_path)

        if not output_path.exists() or output_path.stat().st_size < 1000:
            raise RuntimeError(f"TTS output is empty or missing: {output_path}")

        logger.info("gTTS synthesized: %s (%.1f KB)", output_path.name, output_path.stat().st_size / 1024)
        return output_path


class EdgeTTSProvider(TTSProvider):
    """
    Microsoft Edge TTS — free, requires internet, high quality.
    Voice: hi-IN-SwaraNeural (Hindi), en-IN-NeerjaNeural (Indian English).
    License: Free for use; not a voice clone of any real person.
    """

    def __init__(self, voice: str = "hi-IN-SwaraNeural"):
        self.voice = voice

    def is_available(self) -> bool:
        try:
            import edge_tts  # noqa
            return True
        except ImportError:
            return False

    def synthesize(self, text: str, output_path: Path, speed: float = 1.0) -> Path:
        try:
            import asyncio
            import edge_tts
        except ImportError:
            raise RuntimeError("edge-tts not installed. Run: pip install edge-tts")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # edge-tts natively writes MP3; convert if WAV requested
        mp3_path = output_path.with_suffix(".mp3")

        async def _synth():
            communicate = edge_tts.Communicate(text, self.voice)
            await communicate.save(str(mp3_path))

        asyncio.run(_synth())

        if output_path.suffix.lower() == ".wav":
            _convert_to_wav(mp3_path, output_path, speed=speed)
            mp3_path.unlink(missing_ok=True)
        else:
            mp3_path.rename(output_path)

        if not output_path.exists() or output_path.stat().st_size < 1000:
            raise RuntimeError(f"EdgeTTS output is empty: {output_path}")

        logger.info("EdgeTTS synthesized: %s", output_path.name)
        return output_path


class PiperTTSProvider(TTSProvider):
    """
    Piper TTS — local, offline, high-quality VITS-based voices.
    License: MIT (engine). Voice model licenses vary — verify before use.
    See: https://github.com/rhasspy/piper
    """

    def __init__(self, model_path: str, voice: str = ""):
        self.model_path = Path(model_path) if model_path else None
        self.voice = voice

    def is_available(self) -> bool:
        if not self.model_path or not self.model_path.exists():
            return False
        result = subprocess.run(["piper", "--version"], capture_output=True, text=True)
        return result.returncode == 0

    def synthesize(self, text: str, output_path: Path, speed: float = 1.0) -> Path:
        if not self.is_available():
            raise RuntimeError(
                "Piper TTS is not available. Install piper and set PIPER_MODEL_PATH in config."
            )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "piper",
            "--model", str(self.model_path),
            "--output_file", str(output_path),
        ]
        result = subprocess.run(cmd, input=text, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Piper failed: {result.stderr}")
        return output_path

class Qwen3TTSProvider(TTSProvider):
    """
    Qwen3-TTS — Open-source emotional, expressive speech synthesis model by Qwen / Alibaba Cloud.
    Features natural emotion, tone, and prosody control via 'instruct' prompt and multiple expressive voices.
    Model checkpoints: Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice (recommended for 6GB VRAM) or 1.7B.
    Supported speakers: ryan, serena, vivian, aiden, uncle_fu, ono_anna, sohee, eric, dylan.
    """

    SUPPORTED_SPEAKERS = {"serena", "vivian", "uncle_fu", "ryan", "aiden", "ono_anna", "sohee", "eric", "dylan"}

    def __init__(
        self,
        model_name: str = "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
        speaker: str = "ryan",
        language: str = "auto",
        instruct: str = "Speak in a calm, serene, deeply emotional, devotional tone with reverence.",
        device: Optional[str] = None,
    ):
        self.model_name = model_name
        self.speaker = speaker.lower() if speaker else "ryan"
        self.language = language
        self.instruct = instruct
        self.device = device
        self._model = None

    def is_available(self) -> bool:
        try:
            import qwen_tts
            return True
        except ImportError:
            return False

    def _get_model(self):
        if self._model is None:
            import torch
            from qwen_tts import Qwen3TTSModel
            device_str = self.device or ("cuda:0" if torch.cuda.is_available() else "cpu")
            dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32

            # Try local snapshot resolution first for instant offline startup
            model_target = self.model_name
            try:
                from huggingface_hub import snapshot_download
                local_path = snapshot_download(self.model_name, local_files_only=True)
                model_target = local_path
                logger.info("Found cached Qwen3-TTS weights at %s", local_path)
            except Exception:
                logger.info("No local cache found, downloading '%s'...", self.model_name)

            logger.info("Loading Qwen3-TTS model on %s...", device_str)
            self._model = Qwen3TTSModel.from_pretrained(
                model_target,
                device_map=device_str,
                dtype=dtype,
            )
        return self._model

    def synthesize(self, text: str, output_path: Path, speed: float = 1.0) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            import soundfile as sf
            model = self._get_model()

            # Map language: English -> 'english', all others (hi, sanskrit, hinglish, auto) -> 'auto'
            lang_lower = (self.language or "auto").lower()
            if lang_lower in ("en", "english"):
                target_lang = "english"
            else:
                target_lang = "auto"

            target_speaker = self.speaker.lower() if self.speaker else "ryan"
            if target_speaker not in self.SUPPORTED_SPEAKERS:
                logger.info("Speaker '%s' not in supported list, defaulting to 'ryan'", target_speaker)
                target_speaker = "ryan"

            logger.info(
                "Synthesizing speech with Qwen3-TTS (speaker=%s, lang=%s)...",
                target_speaker,
                target_lang,
            )
            wavs, sr = model.generate_custom_voice(
                text=text,
                speaker=target_speaker,
                language=target_lang,
                instruct=self.instruct,
            )

            sf.write(str(output_path), wavs[0], sr)

            if speed != 1.0:
                tmp_wav = output_path.with_name(f"tmp_{output_path.name}")
                output_path.rename(tmp_wav)
                _convert_to_wav(tmp_wav, output_path, speed=speed)
                tmp_wav.unlink(missing_ok=True)

            logger.info("Qwen3-TTS synthesized successfully: %s", output_path.name)
            return output_path
        except Exception as e:
            logger.warning(
                "Qwen3-TTS synthesis failed: %s. Using high-quality EdgeTTS neural fallback.",
                e,
            )
            fallback = EdgeTTSProvider() if EdgeTTSProvider().is_available() else GTTSProvider()
            return fallback.synthesize(text, output_path, speed=speed)


class SilentFallbackProvider(TTSProvider):
    """
    Emergency fallback: generates a silent WAV. Used only for rendering tests.
    Never use for actual content publishing.
    """

    def __init__(self, duration_seconds: float = 10.0):
        self.duration_seconds = duration_seconds

    def is_available(self) -> bool:
        return True

    def synthesize(self, text: str, output_path: Path, speed: float = 1.0) -> Path:
        logger.warning("Using test audio fallback TTS — this output is for testing only!")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        estimated = self.estimate_duration(text)
        _generate_silence_wav(output_path, duration=estimated)
        return output_path


def _convert_to_wav(mp3_path: Path, wav_path: Path, speed: float = 1.0) -> None:
    """Use FFmpeg to convert MP3 to WAV with optional speed adjustment."""
    filters = f"atempo={speed}" if speed != 1.0 else "anull"
    cmd = [
        "ffmpeg", "-y", "-i", str(mp3_path),
        "-af", filters,
        "-ar", "22050", "-ac", "1",
        str(wav_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg MP3->WAV conversion failed: {result.stderr[-400:]}")


def _generate_silence_wav(path: Path, duration: float, sample_rate: int = 22050) -> None:
    """Generate a subtle test audio tone WAV file using FFmpeg."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"sine=frequency=220:sample_rate={sample_rate}",
        "-t", f"{duration:.3f}",
        "-af", "volume=0.05",
        "-ar", str(sample_rate), "-ac", "1",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to generate silence WAV: {result.stderr[-200:]}")


def validate_audio_file(path: Path) -> dict:
    """Use FFprobe to validate an audio file. Returns probe dict."""
    import json as _json
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", str(path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFprobe failed on {path}: {result.stderr}")
    data = _json.loads(result.stdout)
    streams = data.get("streams", [])
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    if not audio:
        raise ValueError(f"No audio stream in {path}")
    return data
