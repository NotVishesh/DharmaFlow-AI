"""
DharmaFlow AI — Unit Tests: Video Renderer and QC
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.video.renderer import RenderConfig, VideoRenderer, SceneAssets, _seconds_to_ass


def has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


class TestASStimestamp:
    def test_zero(self):
        assert _seconds_to_ass(0.0) == "0:00:00.00"

    def test_one_minute(self):
        assert _seconds_to_ass(60.0) == "0:01:00.00"

    def test_partial_second(self):
        ts = _seconds_to_ass(10.5)
        assert "10" in ts
        assert ".50" in ts


@pytest.mark.skipif(not has_ffmpeg(), reason="FFmpeg not available")
class TestVideoRenderer:
    def test_render_requires_scenes(self, tmp_path):
        config = RenderConfig(width=540, height=960, preset="ultrafast", crf=35)
        renderer = VideoRenderer(config, temp_dir=tmp_path / "temp")
        result = renderer.render([], tmp_path / "out.mp4", job_id="test-empty")
        assert not result.success
        assert "No scenes" in result.error

    def test_render_missing_audio_fails(self, tmp_path):
        """Renderer should fail gracefully if audio file doesn't exist."""
        from PIL import Image
        img_path = tmp_path / "scene_001.png"
        img = Image.new("RGB", (540, 960), color=(100, 80, 60))
        img.save(str(img_path))

        config = RenderConfig(width=540, height=960, preset="ultrafast", crf=35, ken_burns_enabled=False)
        renderer = VideoRenderer(config, temp_dir=tmp_path / "temp")

        scenes = [SceneAssets(
            scene_number=1,
            image_path=img_path,
            audio_path=tmp_path / "nonexistent.wav",  # doesn't exist
            subtitle_text="Test",
            duration_seconds=3.0,
            narration_text="Test narration",
        )]

        result = renderer.render(scenes, tmp_path / "out.mp4", job_id="test-missing-audio")
        assert not result.success


class TestQualityChecker:
    def test_qc_missing_file(self):
        from app.quality.checker import run_quality_checks, _instant_fail
        from app.content.schemas import ScriptSchema
        import json

        # Create minimal script
        script = ScriptSchema.model_validate({
            "topic": "Valid Test Topic", "category": "scripture_explainer", "language": "hi",
            "target_duration_seconds": 30,
            "title_options": ["Test title"], "opening_hook": "Test opening hook here",
            "narration": "This is a sufficiently long narration text for testing purposes",
            "scenes": [
                {"scene_number": 1, "narration_text": "Test narration",
                 "approximate_duration_seconds": 10.0,
                 "visual_prompt": "Test visual prompt for ancient temple spiritual scene",
                 "subtitle_text": "Test subtitle"},
                {"scene_number": 2, "narration_text": "Test narration 2",
                 "approximate_duration_seconds": 10.0,
                 "visual_prompt": "Another test visual prompt for mountain sunrise scene",
                 "subtitle_text": "Test subtitle 2"},
            ],
            "closing_line": "Closing line",
            "verification_status": "VERIFIED",
        })

        from pathlib import Path
        report = run_quality_checks(
            video_path=Path("/nonexistent/video.mp4"),
            script=script,
            render_job_id="test-123",
        )
        assert not report.passed
        assert len(report.blocking_errors) > 0

    def test_qc_unverified_status_blocks(self):
        from app.quality.checker import run_quality_checks
        from app.content.schemas import ScriptSchema
        from pathlib import Path

        script = ScriptSchema.model_validate({
            "topic": "Valid Test Topic", "category": "scripture_explainer", "language": "hi",
            "target_duration_seconds": 30,
            "title_options": ["Test title"], "opening_hook": "Test opening hook here",
            "narration": "This is a sufficiently long narration text for testing purposes",
            "scenes": [
                {"scene_number": 1, "narration_text": "Test narration",
                 "approximate_duration_seconds": 10.0,
                 "visual_prompt": "Test visual prompt for ancient temple spiritual scene",
                 "subtitle_text": "Test subtitle"},
                {"scene_number": 2, "narration_text": "Test narration 2",
                 "approximate_duration_seconds": 10.0,
                 "visual_prompt": "Another test visual prompt for mountain sunrise scene",
                 "subtitle_text": "Test subtitle 2"},
            ],
            "closing_line": "Closing line",
            "verification_status": "DRAFT",  # not approved
        })

        report = run_quality_checks(
            video_path=Path("/nonexistent/video.mp4"),
            script=script,
            render_job_id="test-456",
        )
        assert not report.passed
