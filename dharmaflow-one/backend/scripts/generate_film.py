"""Run a real local film from prompt through narration, video and final export."""
import argparse
import asyncio
import json
import logging
import uuid
from pathlib import Path
from backend.config import settings
from backend.db.database import init_db, AsyncSessionLocal, engine
from backend.db.models import Project, ProjectStatus, ExecutionMode
from backend.services.pipeline import pipeline_orchestrator
from backend.core.ws_manager import ws_manager


async def run(args):
    # This CLI is explicitly local-only and never submits paid requests.
    settings.DHARMAFLOW_MOCK_AI = False
    settings.VIDEO_PROVIDER = 'local'
    if args.lip_sync:
        from backend.services.lipsync_service import lipsync_ready
        if not lipsync_ready():
            raise RuntimeError('Install lip-sync first: python -m backend.scripts.install_lipsync')
    await init_db()
    pid = args.resume or str(uuid.uuid4())
    original_broadcast = ws_manager.broadcast

    async def progress(message):
        if message.get('project_id') == pid:
            print(message.get('message') or message.get('status') or message.get('event'), flush=True)
        await original_broadcast(message)

    async def worker_progress():
        previous = ''
        while True:
            folder = settings.MEDIA_DIR / pid
            logs = list(folder.glob('*.render.log'))
            if logs:
                latest = max(logs, key=lambda p: p.stat().st_mtime)
                lines = latest.read_text(encoding='utf-8', errors='replace').splitlines()
                line = next((s for s in reversed(lines) if s.strip()), '')
                update = f'{latest.name}: {line}'
                if update != previous:
                    print(update, flush=True)
                    previous = update
            await asyncio.sleep(10)

    ws_manager.broadcast = progress
    monitor = asyncio.create_task(worker_progress()) if not args.check else None
    try:
        async with AsyncSessionLocal() as session:
            if args.resume:
                project = await session.get(Project, pid)
                if project is None:
                    raise ValueError(f'Unknown project: {pid}')
                completed = sum(bool(sc.visual_path and Path(sc.visual_path).is_file()) for sc in project.scenes)
                print(f'Resume: {completed}/{len(project.scenes)} scene videos saved.', flush=True)
                if args.check:
                    print(f'Status: {project.status.value}. No generation started.')
                    return
                if project.status != ProjectStatus.FAILED:
                    raise ValueError('Only a failed project can be resumed; do not run concurrent renderers.')
                if not project.raw_script:
                    project.status = ProjectStatus.IDLE
                elif not project.scenes:
                    project.status = ProjectStatus.GENERATING_SCENES
                elif any(not sc.audio_path or not Path(sc.audio_path).is_file() for sc in project.scenes):
                    project.status = ProjectStatus.GENERATING_AUDIO
                elif completed < len(project.scenes):
                    project.status = ProjectStatus.GENERATING_VISUALS
                else:
                    project.status = ProjectStatus.MUXING_VIDEO
                if args.lip_sync:
                    project.lip_sync = True
                project.error_message = None
            else:
                project = Project(id=pid, topic=args.prompt, style=args.style,
                    target_duration_seconds=args.seconds, lip_sync=args.lip_sync, mode=ExecutionMode.TURBO,
                    status=ProjectStatus.IDLE)
                session.add(project)
            await session.commit()
            print(f'PROJECT_ID={pid}\nOUTPUT_DIRECTORY={settings.MEDIA_DIR / pid}', flush=True)
            print('Local generation only. Ctrl+C cancels. A one-minute film can take several hours.', flush=True)
            try:
                await pipeline_orchestrator.run(pid, session)
            except asyncio.CancelledError:
                project.status = ProjectStatus.FAILED
                project.error_message = 'CLI generation cancelled by user; completed scene assets preserved.'
                await session.commit()
                raise
            await session.refresh(project)
            if project.status != ProjectStatus.WAIT_VIDEO_REVIEW:
                raise RuntimeError(project.error_message or f'Unexpected status: {project.status}')
            print(f'FINAL_VIDEO={project.final_video_path}', flush=True)
            report = settings.MEDIA_DIR / pid / 'quality_report.json'
            print(f'QUALITY_REPORT={report}', flush=True)
            print(json.dumps(json.loads(report.read_text(encoding='utf-8')), indent=2), flush=True)
    finally:
        if monitor is not None:
            monitor.cancel()
            await asyncio.gather(monitor, return_exceptions=True)
        ws_manager.broadcast = original_broadcast
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--resume', help='Resume a failed project UUID without replacing completed scenes')
    parser.add_argument('--check', action='store_true', help='Inspect a resume project without starting generation')
    parser.add_argument('--offload', choices=('resident', 'sequential'), default='sequential')
    group.add_argument('--prompt', help='Film topic or story (up to 500 characters)')
    parser.add_argument('--seconds', type=int, choices=(15, 30, 60, 120), default=60)
    parser.add_argument('--style', default='cinematic')
    parser.add_argument('--lip-sync', action='store_true', help='Animate the visible character mouth from scene dialogue')
    args = parser.parse_args()
    if args.check and not args.resume:
        parser.error('--check requires --resume')
    settings.VIDEO_OFFLOAD = args.offload
    if args.prompt is not None and (not args.prompt.strip() or len(args.prompt) > 500):
        parser.error('--prompt must contain 1 to 500 characters')
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        print('Cancelled. Completed scene assets have been preserved.')
        raise SystemExit(130)
    except Exception as exc:
        logging.error('Generation failed: %s', exc)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
