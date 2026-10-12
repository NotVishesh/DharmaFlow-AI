"""
DharmaFlow AI — Environment Diagnostics
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from typing import Any


def _check(name: str, ok: bool, message: str, required: bool = True) -> dict:
    return {"name": name, "ok": ok, "message": message, "required": required}


def run_diagnostics() -> list[dict[str, Any]]:
    """Run all environment checks and return a list of results."""
    results = []

    # Python version
    major, minor = sys.version_info[:2]
    ok = major == 3 and minor >= 10
    results.append(_check("Python 3.10+", ok, f"Python {major}.{minor}"))

    # FFmpeg
    ffmpeg = shutil.which("ffmpeg")
    results.append(_check("FFmpeg", bool(ffmpeg), ffmpeg or "Not found on PATH"))

    # FFprobe
    ffprobe = shutil.which("ffprobe")
    results.append(_check("FFprobe", bool(ffprobe), ffprobe or "Not found on PATH"))

    # PyTorch + CUDA
    try:
        import torch
        cuda_ok = torch.cuda.is_available()
        cuda_msg = f"PyTorch {torch.__version__}, CUDA: {'available' if cuda_ok else 'NOT available'}"
        if cuda_ok:
            cuda_msg += f", GPU: {torch.cuda.get_device_name(0)}"
        results.append(_check("PyTorch+CUDA", cuda_ok, cuda_msg, required=False))
    except ImportError:
        results.append(_check("PyTorch+CUDA", False, "PyTorch not installed", required=False))

    # Pillow
    try:
        import PIL
        results.append(_check("Pillow", True, f"Pillow {PIL.__version__}"))
    except ImportError:
        results.append(_check("Pillow", False, "Pillow not installed — placeholder visuals unavailable"))

    # FastAPI
    try:
        import fastapi
        results.append(_check("FastAPI", True, f"FastAPI {fastapi.__version__}", required=False))
    except ImportError:
        results.append(_check("FastAPI", False, "FastAPI not installed", required=False))

    # SQLAlchemy
    try:
        import sqlalchemy
        results.append(_check("SQLAlchemy", True, f"SQLAlchemy {sqlalchemy.__version__}"))
    except ImportError:
        results.append(_check("SQLAlchemy", False, "SQLAlchemy not installed"))

    # Pydantic
    try:
        import pydantic
        results.append(_check("Pydantic", True, f"Pydantic {pydantic.__version__}"))
    except ImportError:
        results.append(_check("Pydantic", False, "Pydantic not installed"))

    # pydantic-settings
    try:
        import pydantic_settings
        results.append(_check("pydantic-settings", True, "pydantic-settings installed"))
    except ImportError:
        results.append(_check("pydantic-settings", False, "pydantic-settings not installed"))

    # PyYAML
    try:
        import yaml
        results.append(_check("PyYAML", True, "PyYAML installed"))
    except ImportError:
        results.append(_check("PyYAML", False, "PyYAML not installed"))

    # gTTS
    try:
        import gtts
        results.append(_check("gTTS", True, "gTTS available (requires internet)", required=False))
    except ImportError:
        results.append(_check("gTTS", False, "gTTS not installed — TTS unavailable without alternative provider", required=False))

    # Qwen3-TTS (Open-source emotional AI TTS)
    try:
        import qwen_tts
        results.append(_check("Qwen3-TTS", True, "Qwen3-TTS emotional AI model library installed", required=False))
    except ImportError:
        results.append(_check("Qwen3-TTS", False, "Qwen3-TTS not installed (pip install qwen-tts)", required=False))

    # edge-tts
    try:
        import edge_tts
        results.append(_check("edge-tts", True, "edge-tts available (requires internet)", required=False))
    except ImportError:
        results.append(_check("edge-tts", False, "edge-tts not installed", required=False))

    # Ollama
    try:
        import httpx
        r = httpx.get("http://localhost:11434/api/tags", timeout=3.0)
        ok = r.status_code == 200
        msg = "Ollama running locally" if ok else f"Ollama unreachable (status {r.status_code})"
    except Exception as e:
        ok = False
        msg = f"Ollama not running — use demo mode or configure external LLM ({e.__class__.__name__})"
    results.append(_check("Ollama (local LLM)", ok, msg, required=False))

    # ComfyUI
    try:
        import httpx
        r = httpx.get("http://127.0.0.1:8188/system_stats", timeout=3.0)
        ok = r.status_code == 200
        msg = "ComfyUI running" if ok else f"ComfyUI unreachable (status {r.status_code})"
    except Exception as e:
        ok = False
        msg = f"ComfyUI not running — visuals will use placeholder ({e.__class__.__name__})"
    results.append(_check("ComfyUI", ok, msg, required=False))

    # Disk space
    import shutil as _shutil
    usage = _shutil.disk_usage(".")
    free_gb = usage.free / (1024 ** 3)
    ok = free_gb > 5
    results.append(_check("Disk space", ok, f"{free_gb:.1f} GB free"))

    return results
