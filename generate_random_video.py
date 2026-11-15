import asyncio
import json
import logging
import subprocess
import sys
import uuid
from pathlib import Path

# Setup paths
root_dir = Path(__file__).resolve().parent
dharmaflow_backend = root_dir / "dharmaflow-one" / "backend"
sys.path.insert(0, str(root_dir / "dharmaflow-one"))

from backend.db.database import AsyncSessionLocal, init_db
from backend.db.models import Project, Scene, ExecutionMode, ProjectStatus
from backend.services.pipeline import pipeline_orchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("video_generator")

async def run_random_video():
    logger.info("Initializing database...")
    await init_db()

    # Topic and style
    topic = "Life Inside a Cartoon Ant Colony: The Secret Underground Empire"
    style = "fun 3D Disney Pixar animated cartoon style, colorful, humorous, vibrant, lively narration"
    project_id = f"video_{uuid.uuid4().hex[:8]}"

    logger.info("=" * 60)
    logger.info("GENERATING CARTOON ANT COLONY VIDEO")
    logger.info("Project ID: %s", project_id)
    logger.info("Topic:      %s", topic)
    logger.info("Style:      %s", style)
    logger.info("=" * 60)

    async with AsyncSessionLocal() as session:
        project = Project(
            id=project_id,
            topic=topic,
            style=style,
            mode=ExecutionMode.TURBO,
            status=ProjectStatus.IDLE,
        )
        session.add(project)
        await session.commit()

        # Run pipeline orchestrator
        await pipeline_orchestrator.run(project_id, session)

        await session.refresh(project)

        if project.status == ProjectStatus.FAILED or project.error_message:
            raise RuntimeError(f"Pipeline failed: {project.error_message}")

        final_video_path = project.final_video_path
        if not final_video_path or not Path(final_video_path).exists():
            raise RuntimeError(f"Output video missing at: {final_video_path}")

        # Probe video details with ffprobe
        probe_cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,duration,codec_name",
            "-of", "json",
            final_video_path
        ]
        res = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
        probe_data = json.loads(res.stdout)
        video_stream = probe_data.get("streams", [{}])[0]

        # Probe audio details
        probe_audio = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=sample_rate,channels,codec_name",
            "-of", "json",
            final_video_path
        ]
        res_audio = subprocess.run(probe_audio, capture_output=True, text=True, check=True)
        audio_stream = json.loads(res_audio.stdout).get("streams", [{}])[0]

        file_size_mb = Path(final_video_path).stat().st_size / (1024 * 1024)

        print("\n" + "=" * 65)
        print(">>> VIDEO GENERATION COMPLETED SUCCESSFULLY! <<<")
        print("=" * 65)
        print(f"Project ID:      {project.id}")
        print(f"Status:          {project.status.value}")
        print(f"Topic:           {project.topic}")
        print(f"YouTube Title:   {project.yt_title}")
        print(f"YouTube Tags:    {', '.join(project.yt_tags or [])}")
        print(f"Description:\n{project.yt_description}")
        print("-" * 65)
        print("MEDIA SPECIFICATIONS:")
        print(f"File Path:       {final_video_path}")
        print(f"File Size:       {file_size_mb:.2f} MB")
        print(f"Resolution:      {video_stream.get('width')}x{video_stream.get('height')}")
        print(f"Video Codec:     {video_stream.get('codec_name')} @ {video_stream.get('r_frame_rate')} fps")
        print(f"Audio Codec:     {audio_stream.get('codec_name')} ({audio_stream.get('sample_rate')} Hz, {audio_stream.get('channels')} channels)")
        print(f"Total Duration:  {float(video_stream.get('duration', 0)):.2f} seconds")
        print("=" * 65 + "\n")

if __name__ == "__main__":
    asyncio.run(run_random_video())
