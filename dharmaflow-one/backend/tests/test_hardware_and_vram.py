import hashlib
from types import SimpleNamespace
from unittest.mock import MagicMock
import httpx
import pytest

from backend.core.hardware import detect_hardware_profile
from backend.core.vram_guard import vram_guard
from backend.core.downloader import download_model_artifact
from backend.db.models import HardwareTier, ModelArtifact

def test_tier_classification_by_vram(monkeypatch):
    class MockMemInfo:
        def __init__(self, gb: float):
            self.total = int(gb * (1024 ** 3))

    for gb, expected_tier in [
        (4.0, HardwareTier.TIER_LOW),
        (8.0, HardwareTier.TIER_MID),
        (16.0, HardwareTier.TIER_HIGH),
    ]:
        mock_pynvml = MagicMock()
        mock_pynvml.nvmlInit = MagicMock()
        mock_pynvml.nvmlDeviceGetCount = MagicMock(return_value=1)
        mock_pynvml.nvmlDeviceGetHandleByIndex = MagicMock(return_value="handle0")
        mock_pynvml.nvmlDeviceGetMemoryInfo = MagicMock(return_value=MockMemInfo(gb))
        mock_pynvml.nvmlShutdown = MagicMock()

        monkeypatch.setattr("pynvml.nvmlInit", mock_pynvml.nvmlInit)
        monkeypatch.setattr("pynvml.nvmlDeviceGetCount", mock_pynvml.nvmlDeviceGetCount)
        monkeypatch.setattr("pynvml.nvmlDeviceGetHandleByIndex", mock_pynvml.nvmlDeviceGetHandleByIndex)
        monkeypatch.setattr("pynvml.nvmlDeviceGetMemoryInfo", mock_pynvml.nvmlDeviceGetMemoryInfo)
        monkeypatch.setattr("pynvml.nvmlShutdown", mock_pynvml.nvmlShutdown)

        result = detect_hardware_profile()
        assert result["tier"] == expected_tier

@pytest.mark.asyncio
async def test_vram_guard_sequential_unload():
    vram_guard.unload_history.clear()
    observed_active = []

    async with vram_guard.acquire_model("LLM", lambda: "llm_instance"):
        observed_active.append(vram_guard._active_model_name)
        assert vram_guard._active_model_name == "LLM"

    async with vram_guard.acquire_model("TTS", lambda: "tts_instance"):
        observed_active.append(vram_guard._active_model_name)
        assert vram_guard._active_model_name == "TTS"

    async with vram_guard.acquire_model("VIDEO", lambda: "video_instance"):
        observed_active.append(vram_guard._active_model_name)
        assert vram_guard._active_model_name == "VIDEO"

    assert observed_active == ["LLM", "TTS", "VIDEO"]
    assert vram_guard.unload_history == ["LLM", "TTS", "VIDEO"]
    assert vram_guard._active_model_instance is None

@pytest.mark.asyncio
async def test_downloader_sha256_verification(tmp_path):
    payload = b"DHARMAFLOW_ONE_TEST_MODEL_WEIGHTS_DATA"
    valid_sha256 = hashlib.sha256(payload).hexdigest()
    corrupted_sha256 = "0000000000000000000000000000000000000000000000000000000000000000"

    def handler(request: httpx.Request):
        return httpx.Response(200, content=payload, headers={"Content-Length": str(len(payload))})

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    # Test 1: Valid sha256
    valid_artifact = ModelArtifact(
        id="test_model_valid",
        role="LLM",
        tier=HardwareTier.TIER_LOW,
        url="http://mock.local/model.bin",
        filename="model_valid.bin",
        sha256=valid_sha256,
        size_bytes=len(payload),
        downloaded_bytes=0,
        is_ready=False,
    )
    res = await download_model_artifact(valid_artifact, tmp_path, client=mock_client)
    assert res is True
    assert valid_artifact.is_ready is True
    assert (tmp_path / "model_valid.bin").exists()

    # Test 2: Corrupted sha256
    corrupted_artifact = ModelArtifact(
        id="test_model_corrupted",
        role="LLM",
        tier=HardwareTier.TIER_LOW,
        url="http://mock.local/model.bin",
        filename="model_corrupt.bin",
        sha256=corrupted_sha256,
        size_bytes=len(payload),
        downloaded_bytes=0,
        is_ready=False,
    )
    with pytest.raises(ValueError, match="Checksum mismatch"):
        await download_model_artifact(corrupted_artifact, tmp_path, client=mock_client)

    assert corrupted_artifact.is_ready is False
    assert not (tmp_path / "model_corrupt.bin").exists()
