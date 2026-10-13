"""
DharmaFlow AI — Daily Scheduler
Runs the daily automation pipeline with locking, limits, and dry-run support.
"""
from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

LOCK_FILE = Path("temp/dharmaflow_daily.lock")


def run_daily_job(dry_run: bool = False, limit: int = 1) -> int:
    """
    Execute the daily video generation and optional publishing run.
    Returns 0 on success, 1 on failure.
    """
    from app.core.settings import get_settings
    from app.database.models import AutomationRun, JobStatus, ContentIdea
    from app.database.session import get_session_factory, init_db
    from app.core.pipeline import run_pipeline

    settings = get_settings()
    init_db()
    SessionLocal = get_session_factory()
    db = SessionLocal()

    run_id = None
    try:
        # ── Lock check ──────────────────────────────────────────────────────
        LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        if LOCK_FILE.exists():
            lock_age = time.time() - LOCK_FILE.stat().st_mtime
            if lock_age < 3600:  # Consider stale after 1 hour
                logger.error("Another daily run is in progress (lock age: %.0fs). Aborting.", lock_age)
                return 1
            else:
                logger.warning("Stale lock file found (%.0f hours old) — removing.", lock_age / 3600)
                LOCK_FILE.unlink()

        LOCK_FILE.write_text(str(os.getpid()))

        # ── Record automation run ───────────────────────────────────────────
        run = AutomationRun(
            status=JobStatus.RUNNING,
            dry_run=dry_run,
            trigger="cli",
            started_at=datetime.now(timezone.utc),
            lock_file=str(LOCK_FILE),
        )
        db.add(run)
        db.commit()
        run_id = run.id

        logger.info("Daily run started (dry_run=%s, limit=%d)", dry_run, limit)

        # ── Preflight checks ────────────────────────────────────────────────
        from app.core.diagnostics import run_diagnostics
        diagnostics = run_diagnostics()
        required_failures = [d for d in diagnostics if not d["ok"] and d.get("required", True)]
        if required_failures:
            msg = f"Preflight check failures: {[d['name'] for d in required_failures]}"
            logger.error(msg)
            run.status = JobStatus.FAILED
            run.error_detail = msg
            run.completed_at = datetime.now(timezone.utc)
            db.commit()
            return 1

        # ── Check daily limit ───────────────────────────────────────────────
        today = datetime.now(timezone.utc).date().isoformat()
        from app.database.models import RenderJob
        from sqlalchemy import func as sqlfunc, cast, Date
        today_jobs = db.query(RenderJob).filter(
            RenderJob.status == JobStatus.COMPLETED,
            sqlfunc.date(RenderJob.created_at) == today,
        ).count()

        effective_limit = min(limit, settings.content.daily_video_limit)
        remaining = effective_limit - today_jobs
        if remaining <= 0:
            logger.info("Daily limit reached (%d/%d). Skipping.", today_jobs, effective_limit)
            run.status = JobStatus.COMPLETED
            run.completed_at = datetime.now(timezone.utc)
            db.commit()
            return 0

        # ── Select topic ────────────────────────────────────────────────────
        from app.content.planner import ContentPlanner
        planner = ContentPlanner(db)
        idea = planner.get_or_create_next_idea()
        topic = idea.topic
        category = idea.category
        language = idea.language

        if dry_run:
            logger.info("[DRY RUN] Would generate: '%s' (%s, %s)", topic, category, language)
            run.status = JobStatus.COMPLETED
            run.completed_at = datetime.now(timezone.utc)
            db.commit()
            print(f"[DRY RUN] Would have generated: '{topic}'")
            return 0

        # ── Run pipeline ────────────────────────────────────────────────────
        pipeline_result = run_pipeline(
            topic=topic,
            category=category,
            language=language,
            target_duration_seconds=settings.content.target_duration_seconds,
            render_preset="standard",
            demo_mode=False,
            db=db,
        )

        if pipeline_result.success and idea:
            idea.used = True
            db.commit()

        run.videos_generated = 1 if pipeline_result.success else 0
        run.status = JobStatus.COMPLETED if pipeline_result.success else JobStatus.FAILED
        run.error_detail = pipeline_result.error
        run.completed_at = datetime.now(timezone.utc)
        db.commit()

        return 0 if pipeline_result.success else 1

    except Exception as e:
        logger.error("Daily run error: %s", e, exc_info=True)
        if run_id:
            try:
                run = db.get(AutomationRun, run_id)
                if run:
                    run.status = JobStatus.FAILED
                    run.error_detail = str(e)
                    run.completed_at = datetime.now(timezone.utc)
                    db.commit()
            except Exception:
                pass
        return 1
    finally:
        LOCK_FILE.unlink(missing_ok=True)
        db.close()


def seed_content_ideas(db) -> None:
    """Populate the content idea queue with initial topics."""
    from app.database.models import ContentIdea

    initial_ideas = [
        ("कर्मयोग — निष्काम कर्म का सिद्धांत | Bhagavad Gita 3:19", "scripture_explainer", "hi"),
        ("सत्य हरिश्चन्द्र की कथा — सत्य का पालन", "epic_storytelling", "hi"),
        ("हनुमान चालीसा का अर्थ — श्लोक 1-5", "devotional_reflection", "hi"),
        ("कृष्ण जन्माष्टमी — श्री कृष्ण का जन्म और उद्देश्य", "festival_cultural", "hi"),
        ("तिरुपति बालाजी मंदिर — इतिहास और महत्व", "temple_historical", "hi"),
        ("द्रौपदी का चीरहरण — एक नैतिक विश्लेषण", "epic_storytelling", "hi"),
        ("Bhagavad Gita 2:20 — The Immortal Soul", "scripture_explainer", "en"),
        ("The significance of Om — Pranava Mantra", "devotional_reflection", "en"),
        ("Rama and Sita — exile and purpose", "epic_storytelling", "en"),
        ("Holi — festival of colors and its Puranic origin", "festival_cultural", "en"),
        ("शिव के पंचाक्षर मंत्र का रहस्य — ॐ नमः शिवाय", "devotional_reflection", "hi"),
        ("महाभारत में विदुर नीति — wise counsel of Vidura", "epic_storytelling", "hi-en"),
    ]

    existing = db.query(ContentIdea).count()
    if existing > 0:
        return

    for topic, category, language in initial_ideas:
        db.add(ContentIdea(topic=topic, category=category, language=language))
    db.commit()
    logger.info("Seeded %d content ideas", len(initial_ideas))
