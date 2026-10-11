"""API router: analytics."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.database.models import AnalyticsSnapshot, PublishJob

router = APIRouter()

@router.get("/summary")
async def analytics_summary(db: Session = Depends(get_db)):
    """Return aggregate stats for published videos."""
    pub_jobs = db.query(PublishJob).filter(PublishJob.platform_video_id != None).all()
    total = len(pub_jobs)
    total_views = sum((s.views or 0) for j in pub_jobs for s in j.analytics)
    return {
        "total_published": total,
        "total_views": total_views,
        "platform_breakdown": {"youtube": total},
    }
