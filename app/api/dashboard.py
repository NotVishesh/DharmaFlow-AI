"""API router: dashboard overview."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.database.models import ContentIdea, RenderJob, JobStatus, Approval, ApprovalStatus, PublishJob

router = APIRouter()

@router.get("/overview")
async def overview(db: Session = Depends(get_db)):
    total_ideas = db.query(ContentIdea).count()
    pending_approval = db.query(Approval).filter(Approval.status == ApprovalStatus.PENDING).count()
    published = db.query(PublishJob).filter(PublishJob.platform_video_id != None).count()
    failed = db.query(RenderJob).filter(RenderJob.status == JobStatus.FAILED).count()
    completed = db.query(RenderJob).filter(RenderJob.status == JobStatus.COMPLETED).count()
    recent = db.query(RenderJob).order_by(RenderJob.created_at.desc()).limit(5).all()
    return {
        "total_ideas": total_ideas,
        "jobs_completed": completed,
        "pending_approval": pending_approval,
        "published": published,
        "failed_jobs": failed,
        "recent_jobs": [{"id": j.id[:8], "status": j.status, "topic": j.script.topic[:40] if j.script else "N/A"} for j in recent],
    }
