"""A real one-shot acceptance render. No mocks or external paid API calls."""
import asyncio
import json
import uuid
from backend.config import settings
from backend.db.database import init_db, AsyncSessionLocal, engine
from backend.db.models import Project, Scene, ProjectStatus, ExecutionMode
from backend.services.pipeline import pipeline_orchestrator


async def main():
    if settings.DHARMAFLOW_MOCK_AI or settings.VIDEO_PROVIDER != 'local':
        raise RuntimeError('This acceptance render requires local production mode')
    await init_db()
    pid = str(uuid.uuid4())
    async with AsyncSessionLocal() as session:
        narration = 'A fox leaps over the log.'
        project = Project(id=pid, topic='A fox leaps over a mossy log in a sunlit forest',
            style='cinematic nature documentary', mode=ExecutionMode.REVIEW,
            status=ProjectStatus.GENERATING_AUDIO, raw_script=narration, yt_title='A Forest Leap')
        session.add(project)
        session.add(Scene(id=str(uuid.uuid4()), project_id=pid, scene_index=0,
            dialogue_or_lyrics=narration,
            visual_prompt='A small red fox with amber fur and a white-tipped tail runs from left to right through a sunlit woodland, '
            'bends its hind legs, leaps over a low moss-covered fallen log, and lands on the soft forest floor. '
            'Its four paws move naturally, its tail sways and autumn leaves scatter as it lands. '
            'Stable medium-wide side view, warm shafts of morning sunlight, detailed fur, soft green background, '
            'one continuous shot with realistic animal motion.'))
        await session.commit()
        print(f'Live project: {pid}', flush=True)
        await pipeline_orchestrator.run(pid, session)
        await session.refresh(project)
        if project.status != ProjectStatus.WAIT_VIDEO_REVIEW:
            raise RuntimeError(project.error_message)
        print(f'LIVE_VIDEO={project.final_video_path}', flush=True)
        report = settings.MEDIA_DIR / pid / 'quality_report.json'
        print(report.read_text(encoding='utf-8'), flush=True)
    await engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
