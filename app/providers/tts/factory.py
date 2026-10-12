"""TTS provider factory."""
from __future__ import annotations

from app.core.settings import get_settings
from app.providers.tts.providers import (
    EdgeTTSProvider, GTTSProvider, PiperTTSProvider,
    Qwen3TTSProvider, SilentFallbackProvider, TTSProvider,
)


def get_tts_provider(override: str | None = None, language: str | None = None) -> TTSProvider:
    settings = get_settings()
    name = (override or settings.tts.provider).lower()
    lang = language or settings.tts.language

    if name in ("qwen3", "qwen3_tts", "qwen"):
        return Qwen3TTSProvider(
            model_name=getattr(settings.tts, "qwen3_model_name", "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"),
            speaker=getattr(settings.tts, "qwen3_speaker", "ryan"),
            language=lang,
            instruct=getattr(settings.tts, "qwen3_instruct", "Speak in a calm, serene, deeply emotional and respectful devotional tone."),
        )
    elif name == "gtts":
        return GTTSProvider(language=lang or settings.tts.gtts_language, slow=settings.tts.gtts_slow)
    elif name == "edge_tts":
        return EdgeTTSProvider(voice=settings.tts.edge_tts_voice)
    elif name == "piper":
        return PiperTTSProvider(model_path=settings.tts.piper_model_path, voice=settings.tts.piper_voice)
    elif name == "silent":
        return SilentFallbackProvider()
    else:
        raise ValueError(f"Unknown TTS provider: {name}")
