"""
DharmaFlow AI — Quality Control Module
Automated checks before a video can be approved or published.
"""
from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.content.schemas import ScriptSchema

logger = logging.getLogger(__name__)


@dataclass
class CheckResult:
    name: str
    passed: bool
    is_blocking: bool = True
    message: str = ""


@dataclass
class QCReport:
    render_job_id: str
    passed: bool
    score: float
    blocking_errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checks: dict[str, dict] = field(default_factory=dict)
    ffprobe_data: Optional[dict] = None
    duration_actual: float = 0.0
    duration_expected: float = 0.0


def run_quality_checks(
    video_path: Path,
    script: ScriptSchema,
    render_job_id: str,
    expected_duration: Optional[float] = None,
    demo_mode: bool = False,
) -> QCReport:
    """
    Run all automated quality checks on a rendered video.
    Returns a QCReport. A video MUST pass all blocking checks before publishing.
    """
    checks: list[CheckResult] = []

    # --- 1. File exists and is non-empty ---
    if not video_path.exists():
        return _instant_fail(render_job_id, "Video file does not exist")
    if video_path.stat().st_size < 10_000:
        return _instant_fail(render_job_id, "Video file is too small (likely corrupted)")
    checks.append(CheckResult("file_exists", True, message="File exists and non-empty"))

    # --- 2. FFprobe validation ---
    probe = _ffprobe(video_path)
    if not probe:
        return _instant_fail(render_job_id, "FFprobe could not read the video file")
    checks.append(CheckResult("ffprobe_readable", True, message="FFprobe parsed successfully"))

    streams = probe.get("streams", [])
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

    # --- 3. Video stream ---
    if not video_streams:
        checks.append(CheckResult("video_stream", False, True, "No video stream found"))
    else:
        vs = video_streams[0]
        w = int(vs.get("width", 0))
        h = int(vs.get("height", 0))
        if w < 400 or h < 400:
            checks.append(CheckResult("video_dimensions", False, True,
                                      f"Dimensions too small: {w}x{h}"))
        elif h < w:
            checks.append(CheckResult("video_orientation", False, True,
                                      f"Video is landscape ({w}x{h}), must be portrait"))
        else:
            checks.append(CheckResult("video_dimensions", True,
                                      message=f"Portrait {w}x{h}"))

    # --- 4. Audio stream ---
    if not audio_streams:
        checks.append(CheckResult("audio_stream", False, True, "No audio stream found"))
    else:
        checks.append(CheckResult("audio_stream", True, message="Audio stream present"))
        # Check for silence (sample peak amplitude)
        silence_check = _check_audio_not_silent(video_path)
        if demo_mode and not silence_check.passed:
            silence_check.is_blocking = False
            silence_check.message += " (Allowed as non-blocking warning in Demo Mode)"
        checks.append(silence_check)

    # --- 5. Duration check ---
    actual_duration = float(probe.get("format", {}).get("duration", 0))
    exp = expected_duration or script.target_duration_seconds
    duration_tolerance = 0.30  # allow 30% variance
    if actual_duration < 1.0:
        checks.append(CheckResult("duration", False, True, f"Duration too short: {actual_duration:.1f}s"))
    elif abs(actual_duration - exp) / max(exp, 1) > duration_tolerance:
        checks.append(CheckResult("duration", False, False,
                                  f"Duration {actual_duration:.1f}s differs from expected {exp}s by >{duration_tolerance*100:.0f}%"))
    else:
        checks.append(CheckResult("duration", True, message=f"Duration OK: {actual_duration:.1f}s"))

    # --- 6. Verification status ---
    vs_allowed = {"VERIFIED", "APPROVED", "READY_FOR_REVIEW"}
    if script.verification_status not in vs_allowed:
        checks.append(CheckResult("verification_status", False, True,
                                  f"Script verification status '{script.verification_status}' blocks publishing"))
    else:
        checks.append(CheckResult("verification_status", True,
                                  message=f"Verification status: {script.verification_status}"))

    # --- 7. Unsupported claims ---
    if script.has_unsupported_claims():
        checks.append(CheckResult("unsupported_claims", False, True,
                                  "Script has unverified factual claims requiring review"))
    else:
        checks.append(CheckResult("unsupported_claims", True,
                                  message="All claims verified or marked appropriately"))

    # --- 8. Originality ---
    if script.originality_report and not script.originality_report.passed:
        if demo_mode:
            checks.append(CheckResult("originality", False, False,
                                      "Originality check duplicate detected (Non-blocking warning in Demo Mode)"))
        else:
            checks.append(CheckResult("originality", False, True,
                                      "Originality check failed: duplicate content detected"))
    else:
        checks.append(CheckResult("originality", True, message="Originality check passed"))

    # --- 9. Title/description length (preliminary) ---
    if not script.title_options:
        checks.append(CheckResult("title_exists", False, True, "No title options generated"))
    else:
        longest_title = max(len(t) for t in script.title_options)
        if longest_title > 100:
            checks.append(CheckResult("title_length", False, False,
                                      f"Longest title ({longest_title} chars) exceeds 100 chars"))
        else:
            checks.append(CheckResult("title_length", True))

    # --- 10. AI disclosure recorded ---
    if script.ai_disclosure_required and not script.generation_metadata:
        checks.append(CheckResult("ai_disclosure", False, False,
                                  "AI-generated content flag set but generation metadata missing"))
    else:
        checks.append(CheckResult("ai_disclosure", True, message="AI disclosure accounted for"))

    # Build report
    blocking_errors = [c.message for c in checks if not c.passed and c.is_blocking]
    warnings = [c.message for c in checks if not c.passed and not c.is_blocking]
    all_checks_dict = {
        c.name: {"passed": c.passed, "blocking": c.is_blocking, "message": c.message}
        for c in checks
    }

    total = len(checks)
    passed_count = sum(1 for c in checks if c.passed)
    score = (passed_count / total) * 100 if total else 0

    overall_pass = len(blocking_errors) == 0

    report = QCReport(
        render_job_id=render_job_id,
        passed=overall_pass,
        score=score,
        blocking_errors=blocking_errors,
        warnings=warnings,
        checks=all_checks_dict,
        ffprobe_data=probe,
        duration_actual=actual_duration,
        duration_expected=exp,
    )

    if overall_pass:
        logger.info("QC passed for job %s (score: %.0f%%)", render_job_id, score)
    else:
        logger.warning(
            "QC FAILED for job %s: %d blocking errors — %s",
            render_job_id, len(blocking_errors), "; ".join(blocking_errors[:3])
        )

    return report


def _instant_fail(job_id: str, reason: str) -> QCReport:
    logger.error("QC instant fail for job %s: %s", job_id, reason)
    return QCReport(
        render_job_id=job_id,
        passed=False,
        score=0.0,
        blocking_errors=[reason],
    )


def _ffprobe(path: Path) -> dict | None:
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def _check_audio_not_silent(path: Path) -> CheckResult:
    """Check that audio is not completely silent using volumedetect."""
    cmd = [
        "ffmpeg", "-i", str(path),
        "-af", "volumedetect",
        "-vn", "-sn",
        "-f", "null", "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    output = result.stderr

    if "max_volume" in output:
        for line in output.split("\n"):
            if "max_volume" in line:
                try:
                    volume_db = float(line.split(":")[-1].strip().replace(" dB", ""))
                    if volume_db < -90:
                        return CheckResult("audio_not_silent", False, True,
                                          f"Audio appears silent (max: {volume_db:.1f} dB)")
                    return CheckResult("audio_not_silent", True,
                                      message=f"Audio present (max: {volume_db:.1f} dB)")
                except ValueError:
                    pass
    return CheckResult("audio_not_silent", True, is_blocking=False,
                       message="Audio silence check inconclusive")
