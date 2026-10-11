"""API router: job management."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.database.models import RenderJob, Approval, ApprovalStatus

router = APIRouter()


@router.get("/")
async def list_jobs(db: Session = Depends(get_db)):
    jobs = db.query(RenderJob).order_by(RenderJob.created_at.desc()).limit(20).all()
    return [
        {
            "id": j.id, "status": j.status,
            "topic": j.script.topic if j.script else "N/A",
            "created_at": str(j.created_at),
            "output_path": j.output_path,
            "duration_seconds": j.duration_seconds,
        }
        for j in jobs
    ]


@router.get("/{job_id}")
async def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(RenderJob, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return {
        "id": job.id, "status": job.status,
        "script": {"topic": job.script.topic, "verification_status": job.script.verification_status} if job.script else None,
        "output_path": job.output_path,
        "duration_seconds": job.duration_seconds,
        "error": job.error_detail,
        "qc": {"passed": job.qc_result.passed, "score": job.qc_result.score} if job.qc_result else None,
        "approval": {"status": job.approval.status} if job.approval else None,
    }


@router.post("/{job_id}/approve")
async def approve_job(job_id: str, notes: str = "", db: Session = Depends(get_db)):
    """Approve a video for publishing."""
    approval = db.query(Approval).filter(Approval.render_job_id == job_id).first()
    if not approval:
        raise HTTPException(404, "No approval record for this job")
    approval.status = ApprovalStatus.APPROVED
    approval.notes = notes
    from datetime import datetime, timezone
    approval.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "approved"}


@router.post("/{job_id}/reject")
async def reject_job(job_id: str, reason: str = "", db: Session = Depends(get_db)):
    """Reject a video."""
    approval = db.query(Approval).filter(Approval.render_job_id == job_id).first()
    if not approval:
        raise HTTPException(404, "No approval record")
    approval.status = ApprovalStatus.REJECTED
    approval.notes = reason
    from datetime import datetime, timezone
    approval.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "rejected"}
