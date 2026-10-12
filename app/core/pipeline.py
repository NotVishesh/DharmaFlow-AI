"""
DharmaFlow AI — Main Pipeline Orchestrator
Coordinates the full content-to-MP4 pipeline:
  idea → research → script → visuals → audio → render → QC → save
"""
from __future__ import annotations

import logging
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.content.originality import check_originality
from app.content.schema_validator import validate_script_data
from app.content.schemas import ScriptSchema
from app.content.script_generator import generate_script
from app.core.settings import get_settings
from app.database.models import (
    ApprovalStatus, Approval, JobStatus, MediaAsset, QCResult,
    RenderJob, Script, VerificationStatus,
)
from app.providers.llm import get_llm_provider
from app.providers.tts import get_tts_provider
from app.providers.visual import get_visual_provider
from app.quality.checker import QCReport, run_quality_checks
from app.video.renderer import RenderConfig, RenderResult, SceneAssets, VideoRenderer

logger = logging.getLogger(__name__)


class PipelineResult:
    def __init__(self):
        self.job_id: str = ""
        self.success: bool = False
        self.script: Optional[ScriptSchema] = None
        self.render_result: Optional[RenderResult] = None
        self.qc_report: Optional[QCReport] = None
        self.error: Optional[str] = None
        self.video_path: Optional[Path] = None
        self.db_render_job_id: Optional[str] = None


def run_pipeline(
    topic: str,
    category: str = "scripture_explainer",
    language: str = "hi",
    target_duration_seconds: int = 45,
    render_preset: str = "standard",
    demo_mode: bool = False,
    db: Optional[Session] = None,
) -> PipelineResult:
    """
    Run the full video generation pipeline.

    Args:
        topic: Video topic.
        category: Content category.
        language: 'hi', 'en', or 'hi-en'.
        target_duration_seconds: Target length in seconds.
        render_preset: 'draft', 'standard', or 'archival'.
        demo_mode: Use mock providers (no GPU, no internet needed).
        db: SQLAlchemy session. If None, creates a new one.

    Returns:
        PipelineResult with all outcomes.
    """
    result = PipelineResult()
    result.job_id = str(uuid.uuid4())

    settings = get_settings()
    output_base = settings.get_output_dir() / result.job_id
    output_base.mkdir(parents=True, exist_ok=True)

    logger.info("=== Pipeline START: job=%s topic='%s' ===", result.job_id[:8], topic[:60])
    pipeline_start = time.time()

    # Use injected db or create one
    own_db = False
    if db is None:
        from app.database.session import get_session_factory
        SessionLocal = get_session_factory()
        db = SessionLocal()
        own_db = True

    try:
        # ── Step 1: Generate Script ─────────────────────────────────────────
        logger.info("[1/6] Generating script...")
        try:
            script = generate_script(
                topic=topic,
                category=category,
                language=language,
                target_duration_seconds=target_duration_seconds,
                demo_mode=demo_mode,
                max_attempts=settings.content.max_regeneration_attempts,
            )
        except Exception as e:
            result.error = f"Script generation failed: {e}"
            return result

        result.script = script

        # ── Step 1b: Religious Fact-Checking & Source Verification ──────────
        logger.info("[2/7] Verifying sources and theological claims...")
        from app.content.research import ResearchEngine
        from app.content.source_verifier import SourceVerifier

        # If missing source references, enrich from authoritative registry
        if not script.source_references:
            script.source_references = ResearchEngine.identify_references_for_topic(
                script.topic, script.category
            )

        # If claims and evidence missing, extract from narration
        if not script.claims_and_evidence:
            script.claims_and_evidence = ResearchEngine.extract_claims_from_narration(
                script.narration, script.topic
            )

        # Verify claims against source registry
        new_status, verification_reasons = SourceVerifier.verify_script(script)
        script.verification_status = new_status

        if new_status == "SOURCES_PENDING" and not demo_mode:
            logger.warning("Script source verification failed: %s", "; ".join(verification_reasons))
            result.error = f"Source verification failed: {'; '.join(verification_reasons)}"
            return result

        # ── Step 2: Originality check ───────────────────────────────────────
        logger.info("[3/7] Checking originality...")
        originality = check_originality(script, db)
        script.originality_report = originality
        if not originality.passed and not demo_mode:
            result.error = f"Originality check failed: duplicate content detected"
            return result

        # ── Step 3: Save script to DB ───────────────────────────────────────
        db_script = _save_script(script, db, result.job_id)

        # ── Step 4: Create render job record ────────────────────────────────
        render_job = RenderJob(
            id=result.job_id,
            script_id=db_script.id,
            status=JobStatus.RUNNING,
            render_preset=render_preset,
            started_at=datetime.now(timezone.utc),
        )
        db.add(render_job)
        db.commit()
        result.db_render_job_id = render_job.id

        # ── Step 5: Generate Visuals ────────────────────────────────────────
        logger.info("[4/7] Generating visual assets...")
        visual_provider = get_visual_provider("placeholder" if demo_mode else None)
        scene_images: list[Path] = []

        for scene in script.scenes:
            img_path = output_base / f"scene_{scene.scene_number:03d}.png"
            try:
                visual_provider.generate_image(
                    prompt=scene.visual_prompt,
                    output_path=img_path,
                    scene_number=scene.scene_number,
                )
                scene.asset_path = str(img_path)
                scene.asset_generation_status = "complete"
            except Exception as e:
                logger.warning("Visual generation failed for scene %d: %s", scene.scene_number, e)
                # Create a basic placeholder
                from app.providers.visual.providers import PlaceholderVisualProvider
                PlaceholderVisualProvider().generate_image(
                    prompt=scene.visual_prompt,
                    output_path=img_path,
                    scene_number=scene.scene_number,
                )
                scene.asset_path = str(img_path)
                scene.asset_generation_status = "placeholder_fallback"

            scene_images.append(img_path)
            # Save asset record
            asset = MediaAsset(
                render_job_id=result.job_id,
                asset_type="image",
                file_path=str(img_path),
                provider=type(visual_provider).__name__,
                prompt=scene.visual_prompt,
                scene_number=scene.scene_number,
                is_placeholder=("placeholder" in scene.asset_generation_status),
            )
            db.add(asset)
        db.commit()

        # ── Step 6: Generate Audio ──────────────────────────────────────────
        logger.info("[5/7] Generating voiceover...")
        tts_provider = get_tts_provider("silent" if demo_mode else None, language=script.language)
        scene_audio: list[Path] = []

        for scene in script.scenes:
            audio_path = output_base / f"audio_{scene.scene_number:03d}.wav"
            try:
                tts_provider.synthesize(
                    text=scene.narration_text,
                    output_path=audio_path,
                    speed=settings.tts.speed,
                )
                # Re-estimate duration from actual audio
                from app.providers.tts.providers import validate_audio_file
                probe = validate_audio_file(audio_path)
                actual_dur = float(probe.get("format", {}).get("duration", scene.approximate_duration_seconds))
                scene.approximate_duration_seconds = actual_dur
            except Exception as e:
                logger.warning("TTS failed for scene %d: %s — using silence", scene.scene_number, e)
                from app.providers.tts.providers import _generate_silence_wav
                _generate_silence_wav(audio_path, duration=scene.approximate_duration_seconds)

            scene_audio.append(audio_path)
            db.add(MediaAsset(
                render_job_id=result.job_id,
                asset_type="audio",
                file_path=str(audio_path),
                provider=type(tts_provider).__name__,
                scene_number=scene.scene_number,
                is_placeholder=isinstance(tts_provider, type(None)),
            ))
        db.commit()

        # ── Step 7: Render Video ────────────────────────────────────────────
        logger.info("[6/7] Rendering video...")
        preset_cfg = settings.video.render_presets.get(render_preset, settings.video.render_presets["standard"])
        render_cfg = RenderConfig(
            width=preset_cfg.width,
            height=preset_cfg.height,
            fps=settings.video.fps,
            codec=settings.video.codec,
            audio_codec=settings.video.audio_codec,
            preset=preset_cfg.preset,
            crf=preset_cfg.crf,
            audio_bitrate=settings.video.audio_bitrate,
            subtitle_font_size=settings.video.subtitle_font_size,
            subtitle_safe_margin=settings.video.subtitle_safe_margin,
            ken_burns_enabled=settings.video.ken_burns_enabled and not demo_mode,
        )

        scene_assets = [
            SceneAssets(
                scene_number=scene.scene_number,
                image_path=scene_images[i],
                audio_path=scene_audio[i],
                subtitle_text=scene.subtitle_text,
                duration_seconds=scene.approximate_duration_seconds,
                narration_text=scene.narration_text,
            )
            for i, scene in enumerate(script.scenes)
        ]

        renderer = VideoRenderer(render_cfg, temp_dir=settings.get_temp_dir())
        output_video = output_base / "final_video.mp4"

        render_result = renderer.render(scene_assets, output_video, result.job_id)
        result.render_result = render_result

        if not render_result.success:
            render_job.status = JobStatus.FAILED
            render_job.error_detail = render_result.error
            render_job.completed_at = datetime.now(timezone.utc)
            db.commit()
            result.error = f"Render failed: {render_result.error}"
            return result

        result.video_path = output_video
        render_job.output_path = str(output_video)
        render_job.output_hash = render_result.file_hash
        render_job.duration_seconds = render_result.duration_seconds
        render_job.file_size_bytes = render_result.file_size_bytes
        render_job.compute_seconds = time.time() - pipeline_start

        # ── Step 7b: Provenance Manifest (Section 18) ────────────────────────
        provenance = {
            "job_id": result.job_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "original_script": script.model_dump(),
            "research_references": [r.model_dump() for r in script.source_references],
            "script_model": {
                "provider": script.generation_metadata.llm_provider if script.generation_metadata else "unknown",
                "model": script.generation_metadata.llm_model if script.generation_metadata else "unknown",
            },
            "visual_model": {
                "provider": type(visual_provider).__name__,
                "checkpoint": settings.visuals.comfyui.checkpoint if not demo_mode else "procedural-pillow",
                "prompts": [s.visual_prompt for s in script.scenes],
            },
            "audio_engine": {
                "provider": type(tts_provider).__name__,
                "voice": settings.tts.edge_tts_voice if settings.tts.provider == "edge_tts" else "default",
            },
            "music_source": "none (licensed silence / background disabled)" if not settings.video.background_music_enabled else str(settings.video.background_music_enabled),
            "media_hashes": {
                "final_video_sha256": render_result.file_hash,
            },
            "render_config": {
                "width": render_cfg.width,
                "height": render_cfg.height,
                "fps": render_cfg.fps,
                "codec": render_cfg.codec,
                "crf": render_cfg.crf,
            },
            "ai_disclosure_required": script.ai_disclosure_required,
        }
        render_job.provenance_manifest = provenance

        # Record cost tracking
        try:
            from app.core.cost_tracker import CostTracker
            tracker = CostTracker(db)
            tracker.record_usage(
                provider=type(visual_provider).__name__,
                operation="render_pipeline",
                job_id=result.job_id,
                compute_seconds=render_job.compute_seconds,
                notes=f"Rendered {len(script.scenes)} scenes"
            )
        except Exception as cost_err:
            logger.debug("Cost tracking note: %s", cost_err)

        # ── Step 8: Quality Control ─────────────────────────────────────────
        logger.info("[7/7] Running quality checks...")
        qc = run_quality_checks(
            video_path=output_video,
            script=script,
            render_job_id=result.job_id,
            expected_duration=target_duration_seconds,
            demo_mode=demo_mode,
        )
        result.qc_report = qc

        db.add(QCResult(
            render_job_id=result.job_id,
            passed=qc.passed,
            score=qc.score,
            checks=qc.checks,
            blocking_errors=qc.blocking_errors,
            warnings=qc.warnings,
            ffprobe_data=qc.ffprobe_data,
            duration_actual=qc.duration_actual,
            duration_expected=qc.duration_expected,
        ))

        if qc.passed:
            render_job.status = JobStatus.COMPLETED
            # Auto-create approval record in PENDING state
            db.add(Approval(
                render_job_id=result.job_id,
                status=ApprovalStatus.PENDING,
            ))
        else:
            render_job.status = JobStatus.FAILED
            render_job.error_detail = "; ".join(qc.blocking_errors)
            result.error = f"QC failed: {'; '.join(qc.blocking_errors)}"

        render_job.completed_at = datetime.now(timezone.utc)
        db.commit()

        result.success = qc.passed

        elapsed = time.time() - pipeline_start
        logger.info(
            "=== Pipeline %s: job=%s in %.1fs ===",
            "SUCCESS" if result.success else "FAILED",
            result.job_id[:8], elapsed
        )

    except Exception as e:
        logger.error("Pipeline unexpected error: %s", e, exc_info=True)
        result.error = f"Unexpected pipeline error: {e}"
        if result.db_render_job_id:
            try:
                job = db.get(RenderJob, result.db_render_job_id)
                if job:
                    job.status = JobStatus.FAILED
                    job.error_detail = str(e)
                    db.commit()
            except Exception:
                pass
    finally:
        if own_db:
            db.close()

    return result


def _save_script(script: ScriptSchema, db: Session, job_id: str) -> Script:
    """Persist a ScriptSchema to the database and return the ORM object."""
    db_script = Script(
        topic=script.topic,
        category=script.category,
        language=script.language,
        target_duration_seconds=script.target_duration_seconds,
        title_options=script.title_options,
        opening_hook=script.opening_hook,
        narration=script.narration,
        scenes=[s.model_dump() for s in script.scenes],
        closing_line=script.closing_line,
        call_to_action=script.call_to_action,
        source_references=[s.model_dump() for s in script.source_references],
        claims_and_evidence=[c.model_dump() for c in script.claims_and_evidence],
        copyright_notes=script.copyright_notes,
        ai_disclosure_required=script.ai_disclosure_required,
        verification_status=script.verification_status,
        originality_report=script.originality_report.model_dump() if script.originality_report else None,
        generation_metadata=script.generation_metadata.model_dump() if script.generation_metadata else None,
        fingerprint=script.originality_report.fingerprint if script.originality_report else None,
        llm_provider=script.generation_metadata.llm_provider if script.generation_metadata else None,
        llm_model=script.generation_metadata.llm_model if script.generation_metadata else None,
    )
    db.add(db_script)
    db.commit()
    db.refresh(db_script)
    return db_script
