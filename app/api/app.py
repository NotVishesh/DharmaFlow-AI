"""
DharmaFlow AI — FastAPI Application
Provides REST API for dashboard and CLI clients.
"""
from __future__ import annotations

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pathlib import Path
from sqlalchemy.orm import Session

from app.database.session import get_db, init_db
from app.api import content, jobs, publishing, analytics, settings as settings_router, dashboard

app = FastAPI(
    title="DharmaFlow AI",
    description="Hindu Devotional Shorts Factory API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url=None,
)

# CORS: only allow localhost by default (never expose to public internet)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(content.router, prefix="/api/content", tags=["content"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(publishing.router, prefix="/api/publishing", tags=["publishing"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["settings"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])

# Serve static frontend
STATIC_DIR = Path(__file__).resolve().parent.parent / "dashboard" / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.on_event("startup")
async def startup_event():
    init_db()


@app.get("/", response_class=HTMLResponse)
async def root():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return HTMLResponse("<h1>DharmaFlow AI</h1><p>Dashboard loading... visit <a href='/api/docs'>API docs</a></p>")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "DharmaFlow AI"}
