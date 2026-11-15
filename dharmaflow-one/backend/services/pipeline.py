import asyncio
import logging
import uuid
import json
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.db.models import Project, Scene, ProjectStatus, ExecutionMode
from backend.core.ws_manager import ws_manager
from backend.core.vram_guard import vram_guard
from backend.providers.mock_providers import MockLLMProvider, MockTTSProvider, MockVisualProvider
from backend.providers.local_providers import LocalLLMProvider, LocalTTSProvider, LocalVisualProvider
from backend.services.media_engine import get_audio_duration_ms, mux_scene, concat_scenes, inspect_av_sync, scene_duration_ms

logger = logging.getLogger(__name__)

class PipelineOrchestrator:
    def __init__(self):
        self._running: set[str] = set()

    def _get_providers(self):
        if settings.DHARMAFLOW_MOCK_AI:
            return MockLLMProvider(), MockTTSProvider(), MockVisualProvider()
        return LocalLLMProvider(), LocalTTSProvider(), LocalVisualProvider()

    async def _broadcast_state(self, project: Project):
        await ws_manager.broadcast({
            "event": "STATE_CHANGED",
            "project_id": project.id,
            "status": project.status.value,
        })

    async def run(self, project_id: str, session: AsyncSession):
        if project_id in self._running:
            return
        self._running.add(project_id)
        try:
            await self._run(project_id, session)
        finally:
            self._running.discard(project_id)

    async def _run(self, project_id: str, session: AsyncSession):
        stmt = select(Project).where(Project.id == project_id)
        result = await session.execute(stmt)
        project = result.scalar_one_or_none()
        if not project:
            logger.error("Project %s not found", project_id)
            return

        llm_provider, tts_provider, visual_provider = self._get_providers()
        project_media_dir = settings.MEDIA_DIR / project.id
        project_media_dir.mkdir(parents=True, exist_ok=True)

        try:
            # ── 1. SCRIPT GENERATION ──
            if project.status == ProjectStatus.IDLE:
                project.status = ProjectStatus.GENERATING_SCRIPT
                await session.commit()
                await self._broadcast_state(project)

                async with vram_guard.acquire_model("LLM", lambda: llm_provider):
                    script_data = await llm_provider.generate_script_and_metadata(project.topic + (' Write first-person spoken character dialogue, not third-person narration. One visible speaker throughout.' if project.lip_sync else ''), project.style, project.target_duration_seconds)

                project.raw_script = script_data["raw_script"]
                project.yt_title = script_data.get("yt_title")
                project.yt_description = script_data.get("yt_description")
                project.yt_tags = script_data.get("yt_tags")

                if project.mode == ExecutionMode.REVIEW:
                    project.status = ProjectStatus.WAIT_SCRIPT_REVIEW
                    await session.commit()
                    await self._broadcast_state(project)
                    return  # Halt and wait for user approval

                project.status = ProjectStatus.GENERATING_SCENES
                await session.commit()
                await self._broadcast_state(project)

            # ── 2. SCENE GENERATION ──
            if project.status == ProjectStatus.GENERATING_SCENES:
                async with vram_guard.acquire_model("LLM", lambda: llm_provider):
                    scenes_data = await llm_provider.parse_scenes(project.raw_script or project.topic)

                # Clear existing scenes if any
                for sc in list(project.scenes):
                    await session.delete(sc)
                await session.flush()

                for sc_data in scenes_data:
                    scene = Scene(
                        id=str(uuid.uuid4()),
                        project_id=project.id,
                        scene_index=sc_data["scene_index"],
                        dialogue_or_lyrics=sc_data["dialogue_or_lyrics"],
                        visual_prompt=sc_data['visual_prompt'] + (' Single character speaking directly to camera, frontal close-up, face and mouth clearly visible, subtle head motion, no other faces, no hands or objects covering the mouth.' if project.lip_sync else ''),
                    )
                    session.add(scene)
                await session.commit()
                await session.refresh(project)

                if project.mode == ExecutionMode.REVIEW:
                    project.status = ProjectStatus.WAIT_SCENE_REVIEW
                    await session.commit()
                    await self._broadcast_state(project)
                    return  # Halt and wait for scene review

                project.status = ProjectStatus.GENERATING_AUDIO
                await session.commit()
                await self._broadcast_state(project)

            # ── 3. AUDIO GENERATION ──
            if project.status == ProjectStatus.GENERATING_AUDIO:
                stmt_scenes = select(Scene).where(Scene.project_id == project.id).order_by(Scene.scene_index)
                scenes_res = await session.execute(stmt_scenes)
                scenes = list(scenes_res.scalars().all())

                async with vram_guard.acquire_model("TTS", lambda: tts_provider, lambda p: getattr(p, 'close', lambda: None)()):
                    for sc in scenes:
                        if sc.audio_path and sc.duration_ms and Path(sc.audio_path).is_file():
                            continue
                        audio_path = project_media_dir / f"scene_{sc.scene_index}.wav"
                        await tts_provider.synthesize(sc.dialogue_or_lyrics, audio_path)
                        duration_ms = await get_audio_duration_ms(str(audio_path))
                        # Give every story beat its share of the requested runtime.
                        # Longer speech extends the film instead of being cut off.
                        if not settings.DHARMAFLOW_MOCK_AI:
                            duration_ms = scene_duration_ms(duration_ms, project.target_duration_seconds, len(scenes))
                        sc.audio_path = str(audio_path)
                        sc.duration_ms = duration_ms
                        await session.commit()

                await session.commit()
                project.status = ProjectStatus.GENERATING_VISUALS
                await session.commit()
                await self._broadcast_state(project)

            # ── 4. VISUAL GENERATION ──
            if project.status == ProjectStatus.GENERATING_VISUALS:
                stmt_scenes = select(Scene).where(Scene.project_id == project.id).order_by(Scene.scene_index)
                scenes_res = await session.execute(stmt_scenes)
                scenes = list(scenes_res.scalars().all())

                async with vram_guard.acquire_model("VIDEO", lambda: visual_provider, lambda p: getattr(p, 'close', lambda: None)()):
                    for sc in scenes:
                        if sc.visual_path and Path(sc.visual_path).is_file():
                            continue
                        await ws_manager.broadcast({'event': 'GENERATION_PROGRESS', 'project_id': project.id,
                            'message': f'Rendering scene {sc.scene_index + 1} of {len(scenes)} with {settings.VIDEO_PROVIDER}.'})
                        dur_sec = (sc.duration_ms or 3000) / 1000.0
                        vis_path = project_media_dir / f"scene_{sc.scene_index}.mp4"
                        res_vis = await visual_provider.generate_visual(f"{project.style} style. {sc.visual_prompt}", vis_path, dur_sec, dialogue=sc.dialogue_or_lyrics)
                        sc.visual_path = str(res_vis)
                        await session.commit()

                await session.commit()
                project.status = ProjectStatus.MUXING_VIDEO
                await session.commit()
                await self._broadcast_state(project)

            # ── 5. MUXING VIDEO ──
            if project.status == ProjectStatus.MUXING_VIDEO:
                stmt_scenes = select(Scene).where(Scene.project_id == project.id).order_by(Scene.scene_index)
                scenes_res = await session.execute(stmt_scenes)
                scenes = list(scenes_res.scalars().all())

                muxed_paths = []
                for sc in scenes:
                    muxed_out = project_media_dir / f"muxed_{sc.scene_index}.mp4"
                    sub_cand = Path(sc.visual_path).with_name(f"{Path(sc.visual_path).stem}_sub.png")
                    sub_file = str(sub_cand) if sub_cand.exists() else None
                    scene_visual = sc.visual_path
                    if project.lip_sync:
                        from backend.services.lipsync_service import animate_speech
                        await ws_manager.broadcast({'event': 'GENERATION_PROGRESS', 'project_id': project.id,
                            'message': f'Animating speech for scene {sc.scene_index+1} of {len(scenes)}'})
                        async with vram_guard.acquire_model('LIPSYNC', lambda: None):
                            scene_visual = str(await animate_speech(sc.visual_path, sc.audio_path,
                                project_media_dir / f'speaking_{sc.scene_index}.mp4', sc.duration_ms))
                    await mux_scene(
                        scene_visual,
                        sc.audio_path,
                        sc.duration_ms,
                        str(muxed_out),
                        scene_index=sc.scene_index,
                        subtitle_overlay_path=sub_file,
                    )
                    sc.muxed_scene_path = str(muxed_out)
                    muxed_paths.append(str(muxed_out))

                final_out = project_media_dir / "final_video.mp4"
                await concat_scenes(muxed_paths, str(final_out))
                report = await inspect_av_sync(str(final_out))
                report['synthetic_test'] = settings.DHARMAFLOW_MOCK_AI
                report['target_duration_seconds'] = project.target_duration_seconds
                report['lip_sync'] = 'generated_not_independently_scored' if project.lip_sync else 'not_evaluated'
                report['scenes'] = []
                for sc in scenes:
                    provenance = Path(sc.visual_path).with_suffix('.provenance.json')
                    report['scenes'].append({'scene_index': sc.scene_index,
                        'timing': await inspect_av_sync(sc.muxed_scene_path),
                        'generation': json.loads(provenance.read_text(encoding='utf-8')) if provenance.exists() else {'provider': 'test' if settings.DHARMAFLOW_MOCK_AI else 'unknown'}})
                (project_media_dir / 'quality_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')

                project.final_video_path = str(final_out)
                project.status = ProjectStatus.WAIT_VIDEO_REVIEW
                await session.commit()
                await self._broadcast_state(project)

        except Exception as e:
            logger.error("Pipeline failure for project %s: %s", project_id, e, exc_info=True)
            project.status = ProjectStatus.FAILED
            project.error_message = f"{type(e).__name__}: {e}"
            await session.commit()
            await self._broadcast_state(project)
            await ws_manager.broadcast({'event': 'ERROR', 'project_id': project.id, 'message': str(e)})

pipeline_orchestrator = PipelineOrchestrator()
