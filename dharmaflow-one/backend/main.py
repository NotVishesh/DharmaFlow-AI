import asyncio
import logging
import uuid
import json
from backend.services.setup_service import runtime_status, install_video
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.config import settings
from backend.db.database import get_db, init_db, AsyncSessionLocal
from backend.db.models import (
    ModelArtifact,
    YouTubeChannel,
    Project,
    Scene,
    ProjectStatus,
    ExecutionMode,
    HardwareTier,
)
from backend.schemas.api_schemas import (
    HardwareProfileResponse,
    YouTubeChannelSchema,
    SelectChannelRequest,
    CreateProjectRequest,
    ProjectResponse,
    ApproveScriptRequest,
    ApproveScenesRequest,
    UpdateMetadataRequest,
)
from backend.core.ws_manager import ws_manager
from backend.core.hardware import detect_hardware_profile
from backend.core.downloader import download_model_artifact
from backend.services.pipeline import pipeline_orchestrator
from backend.services.youtube_service import youtube_service

logger = logging.getLogger("dharmaflow")
logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # Populate default mock model artifacts if table is empty
    async with AsyncSessionLocal() as session:
        stmt = select(ModelArtifact)
        res = await session.execute(stmt)
        if settings.DHARMAFLOW_MOCK_AI and not res.scalars().first():
            hw = detect_hardware_profile()
            tier = hw["hardware_tier"]
            artifacts = [
                ModelArtifact(
                    id="llm_default",
                    role="LLM",
                    tier=tier,
                    url="https://mock.local/llm.gguf",
                    filename="llm.gguf",
                    sha256="d5b1b46327b9c7cf8fb93e2b4fef00527376c6df9fb6786c67ef8874136e4b95",
                    size_bytes=1024 * 1024 * 10,
                    downloaded_bytes=1024 * 1024 * 10 if settings.DHARMAFLOW_MOCK_AI else 0,
                    is_ready=True if settings.DHARMAFLOW_MOCK_AI else False,
                ),
                ModelArtifact(
                    id="tts_default",
                    role="TTS",
                    tier=tier,
                    url="https://mock.local/tts.onnx",
                    filename="tts.onnx",
                    sha256="8b1a9953c4611296a827abf8c47804d70034a742888cf311352e8d350c3886f4",
                    size_bytes=1024 * 1024 * 5,
                    downloaded_bytes=1024 * 1024 * 5 if settings.DHARMAFLOW_MOCK_AI else 0,
                    is_ready=True if settings.DHARMAFLOW_MOCK_AI else False,
                )
            ]
            session.add_all(artifacts)
            await session.commit()
    yield

app = FastAPI(title="DharmaFlow One API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

settings.MEDIA_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(settings.MEDIA_DIR)), name="media")

# ── WEBSOCKET ────────────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)

# ── SYSTEM ENDPOINTS ─────────────────────────────────────────────────────────
@app.get("/api/system/status", response_model=HardwareProfileResponse)
async def get_system_status(db: AsyncSession = Depends(get_db)):
    hw = detect_hardware_profile()
    stmt = select(ModelArtifact)
    res = await db.execute(stmt)
    models = list(res.scalars().all())

    matching_models = [m for m in models if m.tier == hw["hardware_tier"]]
    models_ready = bool(matching_models and all(m.is_ready for m in matching_models))
    if not matching_models and models:
        models_ready = all(m.is_ready for m in models)

    generation = {'ready': True, 'mock': True, 'provider': 'test', 'issues': []} if settings.DHARMAFLOW_MOCK_AI else await runtime_status()
    models_ready = generation['ready']
    return {
        "generation": generation,
        "hardware_tier": hw["hardware_tier"],
        "vram_gb": hw["vram_gb"],
        "ram_gb": hw["ram_gb"],
        "models_ready": models_ready,
        "models": models,
    }

@app.post("/api/system/models/download")
async def start_models_download(background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    if not settings.DHARMAFLOW_MOCK_AI:
        background_tasks.add_task(install_video)
        return {'status': 'started', 'artifact_count': 1}
    hw = detect_hardware_profile()
    stmt = select(ModelArtifact).where(ModelArtifact.tier == hw["hardware_tier"])
    res = await db.execute(stmt)
    artifacts = list(res.scalars().all())
    if not artifacts:
        # Fallback to any unready artifacts
        stmt_all = select(ModelArtifact)
        artifacts = list((await db.execute(stmt_all)).scalars().all())

    async def _download_all():
        async with AsyncSessionLocal() as bg_db:
            for art in artifacts:
                try:
                    await download_model_artifact(art, settings.MODELS_DIR, session=bg_db)
                except Exception as e:
                    logger.error("Download failed for artifact %s: %s", art.id, e)

    background_tasks.add_task(_download_all)
    return {"status": "started", "artifact_count": len(artifacts)}

# ── YOUTUBE AUTH ENDPOINTS ───────────────────────────────────────────────────
@app.post("/api/auth/youtube/login", response_model=list[YouTubeChannelSchema])
async def youtube_login(db: AsyncSession = Depends(get_db)):
    channels = await youtube_service.start_oauth_flow(db)
    return channels

@app.get("/api/auth/youtube/channels", response_model=list[YouTubeChannelSchema])
async def get_youtube_channels(db: AsyncSession = Depends(get_db)):
    stmt = select(YouTubeChannel)
    res = await db.execute(stmt)
    return list(res.scalars().all())

@app.post("/api/auth/youtube/select-channel")
async def select_youtube_channel(req: SelectChannelRequest, db: AsyncSession = Depends(get_db)):
    await youtube_service.select_channel(req.channel_id, db)
    return {"status": "selected", "channel_id": req.channel_id}

# ── PROJECT ENDPOINTS ────────────────────────────────────────────────────────
@app.post("/api/projects", response_model=ProjectResponse)
async def create_project(
    req: CreateProjectRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    if not settings.DHARMAFLOW_MOCK_AI:
        status = await runtime_status()
        if not status['ready']:
            raise HTTPException(503, detail=' '.join(status['issues']))
    if req.lip_sync:
        from backend.services.lipsync_service import lipsync_ready
        if not lipsync_ready():
            raise HTTPException(503, 'Install the lip-sync model before starting a speaking-character project.')
    project_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        topic=req.topic,
        lip_sync=req.lip_sync,
        target_duration_seconds=req.target_duration_seconds,
        style=req.style,
        mode=req.mode,
        status=ProjectStatus.IDLE,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    async def _run_pipeline(pid: str):
        async with AsyncSessionLocal() as bg_db:
            await pipeline_orchestrator.run(pid, bg_db)

    background_tasks.add_task(_run_pipeline, project_id)
    return project

@app.get("/api/projects/{id}", response_model=ProjectResponse)
async def get_project(id: str, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Project)
        .options(selectinload(Project.scenes))
        .where(Project.id == id)
    )
    res = await db.execute(stmt)
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@app.post("/api/projects/{id}/approve-script", response_model=ProjectResponse)
async def approve_script(
    id: str,
    req: ApproveScriptRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Project)
        .options(selectinload(Project.scenes))
        .where(Project.id == id)
    )
    res = await db.execute(stmt)
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.status != ProjectStatus.WAIT_SCRIPT_REVIEW:
        raise HTTPException(409, 'Project is not waiting for script review')
    project.raw_script = req.raw_script
    project.status = ProjectStatus.GENERATING_SCENES
    await db.commit()
    await db.refresh(project)

    async def _run_pipeline(pid: str):
        async with AsyncSessionLocal() as bg_db:
            await pipeline_orchestrator.run(pid, bg_db)

    background_tasks.add_task(_run_pipeline, id)
    return project

@app.post("/api/projects/{id}/approve-scenes", response_model=ProjectResponse)
async def approve_scenes(
    id: str,
    req: ApproveScenesRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Project)
        .options(selectinload(Project.scenes))
        .where(Project.id == id)
    )
    res = await db.execute(stmt)
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.status != ProjectStatus.WAIT_SCENE_REVIEW:
        raise HTTPException(409, 'Project is not waiting for scene review')
    if len({s.id for s in req.scenes}) != len(req.scenes) or {s.id for s in req.scenes} != {s.id for s in project.scenes}:
        raise HTTPException(422, 'Submit every scene exactly once')
    # Update scene rows
    for update_req in req.scenes:
        stmt_sc = select(Scene).where(Scene.id == update_req.id, Scene.project_id == id)
        sc = (await db.execute(stmt_sc)).scalar_one_or_none()
        if sc:
            sc.dialogue_or_lyrics = update_req.dialogue_or_lyrics
            sc.visual_prompt = update_req.visual_prompt
            sc.audio_path = sc.visual_path = sc.muxed_scene_path = None
            sc.duration_ms = None

    project.status = ProjectStatus.GENERATING_AUDIO
    await db.commit()
    await db.refresh(project)

    async def _run_pipeline(pid: str):
        async with AsyncSessionLocal() as bg_db:
            await pipeline_orchestrator.run(pid, bg_db)

    background_tasks.add_task(_run_pipeline, id)
    return project

@app.patch("/api/projects/{id}/metadata", response_model=ProjectResponse)
async def update_metadata(
    id: str,
    req: UpdateMetadataRequest,
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Project)
        .options(selectinload(Project.scenes))
        .where(Project.id == id)
    )
    res = await db.execute(stmt)
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if req.yt_title is not None:
        project.yt_title = req.yt_title
    if req.yt_description is not None:
        project.yt_description = req.yt_description
    if req.yt_tags is not None:
        project.yt_tags = req.yt_tags
    if req.yt_privacy is not None:
        project.yt_privacy = req.yt_privacy
    if req.target_channel_id is not None:
        project.target_channel_id = req.target_channel_id

    await db.commit()
    await db.refresh(project)
    return project

@app.post("/api/projects/{id}/upload")
async def upload_project(
    id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Project).where(Project.id == id)
    res = await db.execute(stmt)
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    async def _do_upload(pid: str):
        async with AsyncSessionLocal() as bg_db:
            await youtube_service.upload_project_video(pid, bg_db)

    background_tasks.add_task(_do_upload, id)
    return {"status": "upload_started", "project_id": id}

@app.get('/api/projects/{id}/quality')
async def project_quality(id: str, db: AsyncSession = Depends(get_db)):
    project = await get_project(id, db)
    report = settings.MEDIA_DIR / project.id / 'quality_report.json'
    if not report.exists():
        raise HTTPException(404, 'No verified export report exists for this project')
    return json.loads(report.read_text(encoding='utf-8'))

@app.post('/api/projects/{id}/retry', response_model=ProjectResponse)
async def retry_project(id: str, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    project = await get_project(id, db)
    if project.status != ProjectStatus.FAILED:
        raise HTTPException(409, 'Only failed projects can be retried')
    if not project.raw_script:
        project.status = ProjectStatus.IDLE
    elif not project.scenes:
        project.status = ProjectStatus.GENERATING_SCENES
    elif any(not sc.audio_path or not Path(sc.audio_path).is_file() for sc in project.scenes):
        project.status = ProjectStatus.GENERATING_AUDIO
    elif any(not sc.visual_path or not Path(sc.visual_path).is_file() for sc in project.scenes):
        project.status = ProjectStatus.GENERATING_VISUALS
    else:
        project.status = ProjectStatus.MUXING_VIDEO
    project.error_message = None
    await db.commit()
    async def resume():
        async with AsyncSessionLocal() as session:
            await pipeline_orchestrator.run(id, session)
    background_tasks.add_task(resume)
    return project
