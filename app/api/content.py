"""API router: content generation endpoints."""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.database.models import ContentIdea, Script

router = APIRouter()


class GenerateRequest(BaseModel):
    topic: str
    category: str = "scripture_explainer"
    language: str = "hi"
    duration_seconds: int = 45
    preset: str = "standard"
    demo_mode: bool = False


class GenerateResponse(BaseModel):
    job_id: str
    status: str
    message: str


@router.post("/generate", response_model=GenerateResponse)
async def generate_video(
    req: GenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Start a video generation pipeline in the background."""
    from app.core.pipeline import run_pipeline

    job_id = str(uuid.uuid4())

    def _run():
        run_pipeline(
            topic=req.topic,
            category=req.category,
            language=req.language,
            target_duration_seconds=req.duration_seconds,
            render_preset=req.preset,
            demo_mode=req.demo_mode,
        )

    background_tasks.add_task(_run)
    return GenerateResponse(
        job_id=job_id,
        status="queued",
        message=f"Pipeline started for topic: {req.topic[:60]}",
    )


@router.get("/ideas")
async def list_ideas(db: Session = Depends(get_db)):
    """List all content ideas."""
    ideas = db.query(ContentIdea).order_by(ContentIdea.created_at.desc()).limit(50).all()
    return [{"id": i.id, "topic": i.topic, "category": i.category, "language": i.language, "used": i.used} for i in ideas]


@router.post("/ideas")
async def create_idea(topic: str, category: str = "scripture_explainer", language: str = "hi", db: Session = Depends(get_db)):
    """Add a new content idea to the queue."""
    idea = ContentIdea(topic=topic, category=category, language=language)
    db.add(idea)
    db.commit()
    return {"id": idea.id, "topic": idea.topic}


@router.get("/scripts")
async def list_scripts(db: Session = Depends(get_db)):
    """List recent generated scripts."""
    scripts = db.query(Script).order_by(Script.created_at.desc()).limit(20).all()
    return [{"id": s.id, "topic": s.topic, "category": s.category, "status": s.verification_status} for s in scripts]
