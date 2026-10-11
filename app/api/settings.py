"""API router: settings and diagnostics."""
from fastapi import APIRouter
from app.core.diagnostics import run_diagnostics
from app.core.settings import get_settings, reload_settings

router = APIRouter()

@router.get("/")
async def get_current_settings():
    s = get_settings()
    return {
        "llm_provider": s.llm.provider,
        "tts_provider": s.tts.provider,
        "visual_provider": s.visuals.provider,
        "youtube_enabled": s.youtube.enabled,
        "safe_mode": s.safe_mode,
        "require_approval": s.content.require_human_approval,
        "daily_limit": s.content.daily_video_limit,
        "timezone": s.content.timezone,
    }

@router.get("/diagnostics")
async def diagnostics():
    return run_diagnostics()
