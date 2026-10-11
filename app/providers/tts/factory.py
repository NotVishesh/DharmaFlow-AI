"""TTS provider factory."""
from __future__ import annotations

from app.core.settings import get_settings
from app.providers.tts.providers import (
    EdgeTTSProvider, GTTSProvider, PiperTTSProvider,
    SilentFallbackProvider, TTSProvider,
)


def get_tts_provider(override: str | None = None) -> TTSProvider:
    settings = get_settings()
    name = override or settings.tts.provider

    if name == "gtts":
        return GTTSProvider(language=settings.tts.gtts_language, slow=settings.tts.gtts_slow)
    elif name == "edge_tts":
        return EdgeTTSProvider(voice=settings.tts.edge_tts_voice)
    elif name == "piper":
        return PiperTTSProvider(model_path=settings.tts.piper_model_path, voice=settings.tts.piper_voice)
    elif name == "silent":
        return SilentFallbackProvider()
    else:
        raise ValueError(f"Unknown TTS provider: {name}")
