"""
DharmaFlow AI — CLI Entry Point
python -m app <command> [options]
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

logger = logging.getLogger("dharmaflow.cli")


def cmd_doctor(args) -> int:
    """Check environment dependencies."""
    from app.core.diagnostics import run_diagnostics
    report = run_diagnostics()
    for item in report:
        status = "[OK]" if item["ok"] else "[X]"
        print(f"  {status}  {item['name']}: {item['message']}")
    failures = [i for i in report if not i["ok"] and i.get("required", True)]
    if failures:
        print(f"\n{len(failures)} required dependency/dependencies are missing.")
        return 1
    print("\nAll required dependencies OK.")
    return 0


def cmd_gpu(args) -> int:
    """Show GPU diagnostics."""
    try:
        import torch
        if torch.cuda.is_available():
            device = torch.cuda.get_device_properties(0)
            total_vram = device.total_memory / 1_073_741_824
            free_vram = (device.total_memory - torch.cuda.memory_allocated(0)) / 1_073_741_824
            print(f"GPU: {device.name}")
            print(f"VRAM Total: {total_vram:.1f} GB")
            print(f"VRAM Free:  {free_vram:.1f} GB")
            print(f"CUDA Version: {torch.version.cuda}")
            return 0
        else:
            print("CUDA not available.")
            return 1
    except ImportError:
        print("PyTorch not installed.")
        return 1


def cmd_generate(args) -> int:
    """Generate a script and optionally run the full pipeline."""
    import random
    from app.database.session import init_db, get_session_factory
    from app.core.pipeline import run_pipeline
    from app.content.planner import CURATED_TOPIC_POOL

    init_db()

    topic = getattr(args, "topic", None)
    category = getattr(args, "category", "general")
    language = getattr(args, "language", "en")

    if not topic or getattr(args, "random", False):
        universal_cats = [
            k for k in CURATED_TOPIC_POOL.keys()
            if k not in ("scripture_explainer", "epic_storytelling", "devotional_reflection", "festival_cultural", "temple_historical")
        ]
        if category and category != "general" and category in CURATED_TOPIC_POOL:
            chosen_cat = category
        else:
            chosen_cat = random.choice(universal_cats or list(CURATED_TOPIC_POOL.keys()))
        chosen_item = random.choice(CURATED_TOPIC_POOL[chosen_cat])
        topic = chosen_item["topic"]
        category = chosen_cat
        print(f"Selected random topic: '{topic}' (category={category}, lang={language})")

    print(f"Generating video: '{topic}' [{language}] {args.duration}s {args.preset} preset")
    print(f"Demo mode: {args.demo}")

    result = run_pipeline(
        topic=topic,
        category=category,
        language=language,
        target_duration_seconds=args.duration,
        render_preset=args.preset,
        demo_mode=args.demo,
    )

    if result.success:
        print(f"\n[OK] Pipeline succeeded!")
        print(f"  Job ID:   {result.job_id}")
        print(f"  Video:    {result.video_path}")
        if result.qc_report:
            print(f"  QC Score: {result.qc_report.score:.0f}%")
            if result.qc_report.warnings:
                print(f"  Warnings: {'; '.join(result.qc_report.warnings[:3])}")
        return 0
    else:
        print(f"\n[X] Pipeline failed: {result.error}")
        return 1


def cmd_validate(args) -> int:
    """Run QC on a rendered video."""
    from app.quality.checker import run_quality_checks
    from app.content.schemas import ScriptSchema

    video_path = Path(args.video)
    if not video_path.exists():
        print(f"Video not found: {video_path}")
        return 1

    # Load script from DB or create minimal mock
    script = _load_script_for_job(args.job_id)
    if not script:
        print(f"No script found for job {args.job_id}")
        return 1

    report = run_quality_checks(video_path, script, args.job_id)
    print(f"\nQC Report for {video_path.name}:")
    print(f"  Passed: {report.passed}")
    print(f"  Score:  {report.score:.0f}%")
    print(f"  Duration: {report.duration_actual:.1f}s / {report.duration_expected:.0f}s expected")
    if report.blocking_errors:
        print("  BLOCKING ERRORS:")
        for e in report.blocking_errors:
            print(f"    ✗ {e}")
    if report.warnings:
        print("  Warnings:")
        for w in report.warnings:
            print(f"    ⚠ {w}")
    return 0 if report.passed else 1


def cmd_upload(args) -> int:
    """Upload a video to YouTube."""
    from app.publishing.youtube import YouTubeUploader
    from app.core.settings import get_settings
    settings = get_settings()

    if not settings.youtube.enabled:
        print("YouTube publishing is disabled. Set youtube.enabled=true in config.yaml")
        return 1

    uploader = YouTubeUploader(
        client_secrets_file=settings.youtube.client_secrets_file,
        token_file=settings.youtube.token_file,
    )

    if not uploader.is_authenticated():
        print("Not authenticated. Run: python -m app youtube-auth")
        return 1

    video_path = Path(args.video) if hasattr(args, 'video') else None
    if not video_path or not video_path.exists():
        print("Provide --video path to the MP4 file")
        return 1

    try:
        resp = uploader.upload_video(
            video_path=video_path,
            title=args.title or "DharmaFlow AI Video",
            description=args.description or "",
            tags=args.tags.split(",") if hasattr(args, 'tags') and args.tags else [],
            privacy_status=args.privacy or "private",
        )
        print(f"[OK] Uploaded: {resp['url']}")
        print(f"  Video ID: {resp['id']}")
        print(f"  Privacy:  {resp['privacy']}")
        return 0
    except Exception as e:
        print(f"[X] Upload failed: {e}")
        return 1


def cmd_youtube_auth(args) -> int:
    """Complete YouTube OAuth authorization."""
    from app.publishing.youtube import YouTubeUploader
    from app.core.settings import get_settings
    settings = get_settings()

    uploader = YouTubeUploader(
        client_secrets_file=settings.youtube.client_secrets_file,
        token_file=settings.youtube.token_file,
    )
    try:
        uploader.authenticate()
        print(f"[OK] YouTube authentication complete. Token saved.")
        return 0
    except Exception as e:
        print(f"[X] Authentication failed: {e}")
        return 1


def cmd_run_daily(args) -> int:
    """Run the daily automation pipeline."""
    from app.scheduler.daily import run_daily_job
    return run_daily_job(dry_run=args.dry_run, limit=args.limit)


def cmd_list_jobs(args) -> int:
    """List recent pipeline jobs."""
    from app.database.session import init_db, get_session_factory
    from app.database.models import RenderJob
    init_db()
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        jobs = db.query(RenderJob).order_by(RenderJob.created_at.desc()).limit(20).all()
        if not jobs:
            print("No jobs found.")
            return 0
        print(f"{'ID':<10} {'Status':<12} {'Created':<20} {'Topic'}")
        print("-" * 80)
        for j in jobs:
            script_topic = j.script.topic[:40] if j.script else "N/A"
            print(f"{j.id[:8]:<10} {j.status:<12} {str(j.created_at)[:19]:<20} {script_topic}")
        return 0
    finally:
        db.close()


def cmd_retry(args) -> int:
    """Retry a failed job."""
    print(f"Retry not yet implemented for job {args.job_id}")
    return 0


def cmd_demo(args) -> int:
    """Run a full offline demo pipeline."""
    print("Running offline demo pipeline...")
    print("This uses placeholder visuals, silent audio, and mock LLM.")
    print("The output is a test artifact — NOT suitable for publishing.\n")

    # Override args for demo
    args.topic = "The Teaching of Equanimity from Bhagavad Gita Chapter 2"
    args.category = "scripture_explainer"
    args.language = "hi"
    args.duration = 40
    args.preset = "draft"
    args.demo = True
    return cmd_generate(args)


def _load_script_for_job(job_id: str):
    """Load a ScriptSchema from the DB for a given job ID."""
    try:
        from app.database.session import get_session_factory
        from app.database.models import RenderJob
        from app.content.schemas import ScriptSchema
        db = get_session_factory()()
        job = db.get(RenderJob, job_id)
        if not job or not job.script:
            return None
        s = job.script
        return ScriptSchema.model_validate({
            "topic": s.topic, "category": s.category, "language": s.language,
            "target_duration_seconds": s.target_duration_seconds,
            "title_options": s.title_options or ["Test Title"],
            "opening_hook": s.opening_hook or "", "narration": s.narration or "",
            "scenes": s.scenes or [], "closing_line": s.closing_line or "",
            "verification_status": s.verification_status,
            "generation_metadata": s.generation_metadata or {
                "llm_provider": "OllamaProvider",
                "llm_model": "llama3.2:3b",
                "generation_timestamp": str(s.created_at or ""),
            },
        })
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(
        prog="python -m app",
        description="Universal AI Short-Form Video Factory",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # doctor
    subparsers.add_parser("doctor", help="Check environment dependencies")

    # gpu
    subparsers.add_parser("gpu", help="Show GPU diagnostics")

    # generate
    gen = subparsers.add_parser("generate", help="Generate a video from any topic (or pick a random topic)")
    gen.add_argument("--topic", default="", help="Video topic (leave empty or pass --random for a random topic)")
    gen.add_argument("--random", action="store_true", help="Pick a random topic automatically")
    gen.add_argument("--category", default="general", help="Content category (e.g., general, tech_ai, science_space, motivation_mindset, history_culture, finance_business, storytelling, facts_trivia, health_psychology, philosophy_wisdom, scripture_explainer)")
    gen.add_argument("--language", default="en", choices=["hi", "en", "hi-en"])
    gen.add_argument("--duration", type=int, default=45, help="Target duration (seconds)")
    gen.add_argument("--preset", default="standard", choices=["draft", "standard", "archival"])
    gen.add_argument("--demo", action="store_true", help="Use offline demo mode")

    # validate
    val = subparsers.add_parser("validate", help="Run quality checks on a video")
    val.add_argument("--video", required=True, help="Path to video file")
    val.add_argument("--job-id", required=True, help="Job ID")

    # upload
    up = subparsers.add_parser("upload", help="Upload video to YouTube")
    up.add_argument("--video", required=True, help="Path to video file")
    up.add_argument("--title", default="", help="Video title")
    up.add_argument("--description", default="", help="Video description")
    up.add_argument("--tags", default="", help="Comma-separated tags")
    up.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"])

    # youtube-auth
    subparsers.add_parser("youtube-auth", help="Complete YouTube OAuth authorization")

    # run-daily
    daily = subparsers.add_parser("run-daily", help="Run the daily automation job")
    daily.add_argument("--dry-run", action="store_true", help="Simulate without publishing")
    daily.add_argument("--limit", type=int, default=1, help="Max videos to generate")

    # list-jobs
    subparsers.add_parser("list-jobs", help="List recent pipeline jobs")

    # retry
    retry = subparsers.add_parser("retry", help="Retry a failed job")
    retry.add_argument("--job-id", required=True)

    # demo
    subparsers.add_parser("demo", help="Run offline demo pipeline")

    args = parser.parse_args()

    # Initialize DB before any command
    try:
        from app.database.session import init_db
        init_db()
    except Exception as e:
        print(f"Database initialization failed: {e}")
        sys.exit(1)

    commands = {
        "doctor": cmd_doctor,
        "gpu": cmd_gpu,
        "generate": cmd_generate,
        "validate": cmd_validate,
        "upload": cmd_upload,
        "youtube-auth": cmd_youtube_auth,
        "run-daily": cmd_run_daily,
        "list-jobs": cmd_list_jobs,
        "retry": cmd_retry,
        "demo": cmd_demo,
    }

    handler = commands.get(args.command)
    if handler:
        sys.exit(handler(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
