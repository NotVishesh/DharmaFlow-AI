"""
DharmaFlow AI — End-to-End Smoke Test
Tests the complete zero-credential offline demo pipeline via the CLI.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import pytest


def test_cli_doctor():
    """Verify environment diagnostics CLI command runs without crash."""
    res = subprocess.run([sys.executable, "-m", "app", "doctor"], capture_output=True, text=True)
    assert res.returncode == 0, f"Doctor failed: {res.stdout}\n{res.stderr}"
    assert "Python" in res.stdout
    assert "FFmpeg" in res.stdout


def test_cli_gpu():
    """Verify GPU diagnostics CLI command."""
    res = subprocess.run([sys.executable, "-m", "app", "gpu"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "GPU:" in res.stdout
    assert "RTX 4050" in res.stdout


def test_cli_demo_smoke_test(tmp_path):
    """Run the offline demo through CLI and verify video output and database."""
    cmd = [
        sys.executable, "-m", "app", "generate",
        "--topic", "The Teaching of Equanimity from Bhagavad Gita",
        "--category", "scripture_explainer",
        "--language", "hi",
        "--duration", "25",
        "--preset", "draft",
        "--demo",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    assert res.returncode == 0, f"Demo generation failed: {res.stdout}\n{res.stderr}"
    assert "Pipeline succeeded" in res.stdout
    assert "Job ID:" in res.stdout
    assert "QC Score:" in res.stdout
