import asyncio
import json
import logging
import subprocess
import sys
import uuid
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir.parent))

from backend.db.database import AsyncSessionLocal, init_db
from backend.db.models import Project, ExecutionMode, ProjectStatus
from backend.services.pipeline import pipeline_orchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sample_generator")

async def generate_random_topic_video():
    logger.info("Initializing database...")
    await init_db()

    topic = "The Quantum Universe: Why Observation Changes Everything"
    style = "cinematic, deep documentary, engaging narration"
    project_id = f"sample_{uuid.uuid4().hex[:8]}"

    logger.info("Creating project: %s | Topic: '%s'", project_id, topic)
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

        logger.info("Starting pipeline execution in TURBO mode...")
        await pipeline_orchestrator.run(project_id, session)

        await session.refresh(project)
        logger.info("Project run completed with status: %s", project.status.value)
        if project.error_message:
            logger.error("Project error: %s", project.error_message)

        final_video = project.final_video_path
        logger.info("Final video path: %s", final_video)

        if not final_video or not Path(final_video).exists():
            raise RuntimeError(f"Final video was not generated at: {final_video}")

        # Probe video using ffprobe
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,duration",
            "-of", "json",
            final_video,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        probe_data = json.loads(res.stdout)
        stream_info = probe_data.get("streams", [{}])[0]
        width = stream_info.get("width")
        height = stream_info.get("height")
        fps = stream_info.get("r_frame_rate")
        dur = stream_info.get("duration")

        file_size_kb = Path(final_video).stat().st_size / 1024

        print("\n" + "=" * 60)
        print("SAMPLE VIDEO GENERATION SUCCESSFUL!")
        print("=" * 60)
        print(f"Topic:        {project.topic}")
        print(f"Status:       {project.status.value}")
        print(f"YouTube Title: {project.yt_title}")
        print(f"YouTube Desc:  {project.yt_description}")
        print(f"YouTube Tags:  {project.yt_tags}")
        print(f"Output Path:  {final_video}")
        print(f"Resolution:   {width}x{height} (Vertical 9:16)")
        print(f"Frame Rate:   {fps}")
        print(f"Duration (s): {dur}")
        print(f"File Size:    {file_size_kb:.1f} KB")
        print("=" * 60 + "\n")

if __name__ == "__main__":
    asyncio.run(generate_random_topic_video())
