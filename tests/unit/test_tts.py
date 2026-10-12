"""Unit tests for TTS providers and factory."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from app.providers.tts.factory import get_tts_provider
from app.providers.tts.providers import (
    EdgeTTSProvider,
    GTTSProvider,
    PiperTTSProvider,
    Qwen3TTSProvider,
    SilentFallbackProvider,
)


class TestTTSFactory:
    """Test factory routing to proper providers."""

    def test_qwen3_provider_resolution(self):
        provider = get_tts_provider("qwen3")
        assert isinstance(provider, Qwen3TTSProvider)

    def test_qwen3_alias_resolution(self):
        provider = get_tts_provider("qwen")
        assert isinstance(provider, Qwen3TTSProvider)
        provider2 = get_tts_provider("qwen3_tts")
        assert isinstance(provider2, Qwen3TTSProvider)

    def test_gtts_resolution(self):
        provider = get_tts_provider("gtts")
        assert isinstance(provider, GTTSProvider)

    def test_edge_tts_resolution(self):
        provider = get_tts_provider("edge_tts")
        assert isinstance(provider, EdgeTTSProvider)

    def test_silent_resolution(self):
        provider = get_tts_provider("silent")
        assert isinstance(provider, SilentFallbackProvider)

    def test_invalid_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown TTS provider"):
            get_tts_provider("nonexistent_tts")


class TestQwen3TTSProvider:
    """Test Qwen3-TTS provider parameters, availability, and error handling."""

    def test_qwen3_init_params(self):
        provider = Qwen3TTSProvider(
            model_name="Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
            speaker="Ryan",
            language="Hindi",
            instruct="Devotional serene tone",
        )
        assert provider.model_name == "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"
        assert provider.speaker == "ryan"
        assert provider.language == "Hindi"
        assert provider.instruct == "Devotional serene tone"

    def test_qwen3_availability(self):
        provider = Qwen3TTSProvider()
        # Since qwen-tts is installed in the test environment, this should return True
        assert provider.is_available() is True

    @patch("app.providers.tts.providers.EdgeTTSProvider.synthesize")
    def test_qwen3_fallback_on_model_failure(self, mock_edge_synth, tmp_path):
        provider = Qwen3TTSProvider()
        out_file = tmp_path / "test_out.wav"

        # Force _get_model to fail to simulate download/network failure
        with patch.object(provider, "_get_model", side_effect=RuntimeError("Connection reset")):
            mock_edge_synth.return_value = out_file
            result = provider.synthesize("ॐ नमः शिवाय", out_file)
            assert result == out_file
            mock_edge_synth.assert_called_once()
