"""
DharmaFlow AI — FFmpeg Video Renderer
Renders a vertical 1080×1920 MP4 from scenes: images + narration + subtitles.

Design:
- Each scene gets an image with Ken Burns pan/zoom via FFmpeg zoompan filter.
- Audio comes from per-scene WAV files, concatenated with gaps.
- Subtitles are rendered via ASS format (allows Devanagari via libass).
- Final output is H.264 + AAC, validated with FFprobe.
"""
from __future__ import annotations

import hashlib
import json
import logging
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SceneAssets:
    scene_number: int
    image_path: Path
    audio_path: Path
    subtitle_text: str
    duration_seconds: float
    narration_text: str


@dataclass
class RenderConfig:
    width: int = 1080
    height: int = 1920
    fps: int = 30
    codec: str = "libx264"
    audio_codec: str = "aac"
    preset: str = "medium"
    crf: int = 23
    audio_bitrate: str = "192k"
    subtitle_font_size: int = 52
    subtitle_safe_margin: int = 100
    ken_burns_enabled: bool = True
    transition_duration: float = 0.4
    background_music_path: Optional[Path] = None
    background_music_volume: float = 0.10
    output_format: str = "mp4"


@dataclass
class RenderResult:
    success: bool
    output_path: Optional[Path] = None
    duration_seconds: float = 0.0
    file_size_bytes: int = 0
    file_hash: str = ""
    error: Optional[str] = None
    ffprobe_data: Optional[dict] = None


class VideoRenderer:
    """FFmpeg-based video renderer for vertical devotional shorts."""

    def __init__(self, config: RenderConfig, temp_dir: Optional[Path] = None):
        self.config = config
        self.temp_dir = temp_dir or Path(tempfile.gettempdir()) / "dharmaflow"
        self._check_ffmpeg()

    def _check_ffmpeg(self) -> None:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True)
        if result.returncode != 0:
            raise RuntimeError("FFmpeg is not installed or not on PATH.")

    def render(
        self,
        scenes: list[SceneAssets],
        output_path: Path,
        job_id: str = "unknown",
    ) -> RenderResult:
        """
        Full render pipeline:
        1. Generate ASS subtitle file.
        2. Per-scene: apply Ken Burns + encode to intermediate.
        3. Concatenate all scene clips.
        4. Mix narration audio.
        5. Burn subtitles.
        6. Validate output.
        """
        if not scenes:
            return RenderResult(success=False, error="No scenes provided.")

        job_temp = self.temp_dir / job_id
        job_temp.mkdir(parents=True, exist_ok=True)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            start = time.time()

            # Step 1: Concatenate audio
            combined_audio = job_temp / "combined_audio.wav"
            self._concat_audio(scenes, combined_audio)

            # Step 2: Generate ASS subtitle file
            ass_path = job_temp / "subtitles.ass"
            total_duration = sum(s.duration_seconds for s in scenes)
            self._write_ass_subtitles(scenes, ass_path)

            # Step 3: Build video from scenes
            raw_video = job_temp / "raw_video.mp4"
            self._render_scenes_to_video(scenes, raw_video)

            # Step 4: Mux audio + video + subtitles → final output
            self._mux_final(raw_video, combined_audio, ass_path, output_path)

            elapsed = time.time() - start
            result = self._validate_output(output_path)
            result.error = None  # clear any validation error
            logger.info(
                "Render complete: %s in %.1fs (%.1fMB)",
                output_path.name, elapsed, output_path.stat().st_size / 1_048_576
            )
            return result

        except Exception as e:
            logger.error("Render failed: %s", str(e), exc_info=True)
            return RenderResult(success=False, error=str(e))
        finally:
            # Clean up temp files (keep on error if configured)
            from app.core.settings import get_settings
            if not (get_settings().storage.keep_temp_on_error and not output_path.exists()):
                shutil.rmtree(job_temp, ignore_errors=True)

    def _concat_audio(self, scenes: list[SceneAssets], output: Path) -> None:
        """Concatenate scene audio files with silence gaps between scenes."""
        from app.core.settings import get_settings
        gap_ms = get_settings().tts.inter_scene_pause_ms
        gap_sec = gap_ms / 1000.0

        concat_list = output.parent / "audio_concat.txt"
        silence_files: list[Path] = []

        entries: list[str] = []
        for i, scene in enumerate(scenes):
            if not scene.audio_path.exists():
                raise FileNotFoundError(f"Audio missing for scene {scene.scene_number}: {scene.audio_path}")
            entries.append(f"file '{scene.audio_path.as_posix()}'\n")
            if i < len(scenes) - 1 and gap_sec > 0:
                sil = output.parent / f"silence_{i}.wav"
                self._generate_silence(sil, gap_sec)
                silence_files.append(sil)
                entries.append(f"file '{sil.as_posix()}'\n")

        concat_list.write_text("".join(entries), encoding="utf-8")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-ar", "44100", "-ac", "2",
            str(output),
        ]
        self._run(cmd, "Audio concatenation")

    def _generate_silence(self, path: Path, duration: float) -> None:
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo",
            "-t", f"{duration:.3f}",
            str(path),
        ]
        self._run(cmd, "Silence generation")

    def _render_scenes_to_video(self, scenes: list[SceneAssets], output: Path) -> None:
        """Render each scene image with Ken Burns effect, then concatenate."""
        w, h = self.config.width, self.config.height
        fps = self.config.fps
        scene_clips: list[Path] = []

        for scene in scenes:
            clip_path = output.parent / f"scene_{scene.scene_number:03d}.mp4"
            dur = scene.duration_seconds

            if self.config.ken_burns_enabled:
                # zoompan for Ken Burns effect — gentle zoom
                zoom_expr = "min(zoom+0.0004,1.05)"
                vf = (
                    f"scale={w*2}:{h*2},"
                    f"zoompan=z='{zoom_expr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                    f":d={int(dur * fps)}:fps={fps}:s={w}x{h}"
                )
            else:
                vf = f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                vf += f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black"

            cmd = [
                "ffmpeg", "-y",
                "-loop", "1",
                "-i", str(scene.image_path),
                "-vf", vf,
                "-t", str(dur),
                "-c:v", self.config.codec,
                "-preset", "ultrafast",  # fast for intermediate
                "-crf", "28",
                "-pix_fmt", "yuv420p",
                "-r", str(fps),
                str(clip_path),
            ]
            self._run(cmd, f"Scene {scene.scene_number} video")
            scene_clips.append(clip_path)

        # Concatenate all scene clips
        concat_list = output.parent / "video_concat.txt"
        concat_list.write_text(
            "\n".join(f"file '{p.as_posix()}'" for p in scene_clips),
            encoding="utf-8"
        )
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c:v", self.config.codec,
            "-preset", self.config.preset,
            "-crf", str(self.config.crf),
            "-pix_fmt", "yuv420p",
            "-an",  # no audio in video-only track
            str(output),
        ]
        self._run(cmd, "Video concatenation")

    def _mux_final(
        self,
        video: Path,
        audio: Path,
        ass: Path,
        output: Path,
    ) -> None:
        """Combine video + audio + burn subtitles."""
        # On Windows, backslashes in ass path need escaping for FFmpeg's filter
        ass_escaped = str(ass).replace("\\", "/").replace(":", "\\:")

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video),
            "-i", str(audio),
            "-vf", f"ass='{ass_escaped}'",
            "-c:v", self.config.codec,
            "-preset", self.config.preset,
            "-crf", str(self.config.crf),
            "-pix_fmt", "yuv420p",
            "-c:a", self.config.audio_codec,
            "-b:a", self.config.audio_bitrate,
            "-shortest",
            "-movflags", "+faststart",
            str(output),
        ]
        self._run(cmd, "Final mux")

    def _write_ass_subtitles(self, scenes: list[SceneAssets], output: Path) -> None:
        """
        Generate an ASS subtitle file from scene subtitle texts.
        ASS format supports Devanagari via libass with appropriate fonts.
        """
        margin = self.config.subtitle_safe_margin
        font_size = self.config.subtitle_font_size
        w, h = self.config.width, self.config.height

        # Choose a font available on Windows that supports Devanagari
        font_name = "Noto Sans Devanagari"  # fallback: Arial Unicode MS

        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 1

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,3,1,2,{margin},{margin},{margin},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        events: list[str] = []
        current_time = 0.0

        for scene in scenes:
            start = current_time
            end = current_time + scene.duration_seconds
            current_time = end

            if not scene.subtitle_text:
                continue

            # Break long subtitles across lines (max ~35 chars per line for Hindi)
            words = scene.subtitle_text.split()
            lines: list[str] = []
            current_line = ""
            for word in words:
                if len(current_line) + len(word) + 1 > 32:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
                else:
                    current_line = f"{current_line} {word}".strip()
            if current_line:
                lines.append(current_line)
            subtitle_text = "\\N".join(lines)

            start_str = _seconds_to_ass(start)
            end_str = _seconds_to_ass(end)
            events.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{subtitle_text}")

        output.write_text(header + "\n".join(events) + "\n", encoding="utf-8")

    def _validate_output(self, path: Path) -> RenderResult:
        """Run FFprobe on the output and return a RenderResult."""
        if not path.exists():
            return RenderResult(success=False, error=f"Output file not found: {path}")

        file_size = path.stat().st_size
        if file_size < 10_000:
            return RenderResult(success=False, error=f"Output file too small: {file_size} bytes")

        probe = _ffprobe(path)
        if probe is None:
            return RenderResult(success=False, error="FFprobe failed on output")

        streams = probe.get("streams", [])
        has_video = any(s.get("codec_type") == "video" for s in streams)
        has_audio = any(s.get("codec_type") == "audio" for s in streams)

        if not has_video:
            return RenderResult(success=False, error="Output has no video stream")
        if not has_audio:
            return RenderResult(success=False, error="Output has no audio stream")

        video_stream = next(s for s in streams if s.get("codec_type") == "video")
        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))

        if width != self.config.width or height != self.config.height:
            logger.warning("Output dimensions %dx%d differ from target %dx%d",
                           width, height, self.config.width, self.config.height)

        duration = float(probe.get("format", {}).get("duration", 0))

        # Compute file hash
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
        file_hash = sha256.hexdigest()

        return RenderResult(
            success=True,
            output_path=path,
            duration_seconds=duration,
            file_size_bytes=file_size,
            file_hash=file_hash,
            ffprobe_data=probe,
        )

    def _run(self, cmd: list[str], label: str) -> None:
        """Run an FFmpeg command, raising on failure."""
        logger.debug("FFmpeg [%s]: %s", label, " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"FFmpeg failed [{label}]:\n{result.stderr[-800:]}"
            )


def _seconds_to_ass(seconds: float) -> str:
    """Convert float seconds to ASS timestamp H:MM:SS.cc"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _ffprobe(path: Path) -> dict | None:
    """Run FFprobe and return parsed JSON, or None on failure."""
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
