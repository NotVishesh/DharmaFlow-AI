"""API router: publishing endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.database.models import Approval, ApprovalStatus, PublishJob, RenderJob

router = APIRouter()


class PublishRequest(BaseModel):
    job_id: str
    platform: str = "youtube"
    privacy: str = "private"
    title: str = ""
    description: str = ""
    tags: list[str] = []


@router.post("/publish")
async def publish_video(req: PublishRequest, db: Session = Depends(get_db)):
    """Publish an approved video to a platform."""
    from app.core.settings import get_settings
    settings = get_settings()

    # Verify approval
    approval = db.query(Approval).filter(Approval.render_job_id == req.job_id).first()
    if not approval or approval.status != ApprovalStatus.APPROVED:
        raise HTTPException(400, "Video must be approved before publishing")

    # Verify QC
    job = db.get(RenderJob, req.job_id)
    if not job or not job.qc_result or not job.qc_result.passed:
        raise HTTPException(400, "Video must pass quality checks before publishing")

    if not job.output_path:
        raise HTTPException(400, "No output file for this job")

    # Check for existing publish job
    existing = db.query(PublishJob).filter(
        PublishJob.render_job_id == req.job_id,
        PublishJob.platform == req.platform,
    ).first()
    if existing and existing.platform_video_id:
        raise HTTPException(409, f"Already published: {existing.platform_url}")

    if req.platform == "youtube":
        if not settings.youtube.enabled:
            raise HTTPException(400, "YouTube publishing is disabled in config")
        return _publish_youtube(req, job, db, settings)
    else:
        raise HTTPException(400, f"Unsupported platform: {req.platform}")


def _publish_youtube(req, job, db, settings):
    from pathlib import Path
    from app.publishing.youtube import YouTubeUploader

    uploader = YouTubeUploader(
        client_secrets_file=settings.youtube.client_secrets_file,
        token_file=settings.youtube.token_file,
    )
    if not uploader.is_authenticated():
        raise HTTPException(401, "YouTube not authenticated. Run: python -m app youtube-auth")

    pub_job = PublishJob(
        render_job_id=req.job_id,
        platform="youtube",
        privacy=req.privacy,
        title=req.title or (job.script.title_options[0] if job.script and job.script.title_options else "DharmaFlow Video"),
        description=req.description,
        tags=req.tags,
    )
    db.add(pub_job)
    db.commit()

    try:
        resp = uploader.upload_video(
            video_path=Path(job.output_path),
            title=pub_job.title,
            description=pub_job.description,
            tags=pub_job.tags or [],
            privacy_status=req.privacy,
            ai_disclosure=job.script.ai_disclosure_required if job.script else True,
        )
        from datetime import datetime, timezone
        pub_job.platform_video_id = resp["id"]
        pub_job.platform_url = resp["url"]
        pub_job.published_at = datetime.now(timezone.utc)
        pub_job.status = "COMPLETED"
        pub_job.ai_disclosure_set = resp.get("ai_disclosure_set", False)
        db.commit()
        return {"status": "published", "url": resp["url"], "video_id": resp["id"]}
    except Exception as e:
        pub_job.status = "FAILED"
        pub_job.error_detail = str(e)
        db.commit()
        raise HTTPException(500, f"Upload failed: {str(e)[:200]}")


@router.get("/status")
async def publishing_status(db: Session = Depends(get_db)):
    """Get overview of publishing status."""
    from app.core.settings import get_settings
    settings = get_settings()
    from app.publishing.youtube import YouTubeUploader
    yt = YouTubeUploader(settings.youtube.client_secrets_file, settings.youtube.token_file)
    return {
        "youtube": {"enabled": settings.youtube.enabled, "authenticated": yt.is_authenticated()},
        "instagram": {"enabled": settings.instagram.enabled},
    }
