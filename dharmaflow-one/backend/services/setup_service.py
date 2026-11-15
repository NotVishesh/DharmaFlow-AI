"""Local video installation and truthful runtime readiness."""
import asyncio
import importlib.metadata
import json
import shutil
from pathlib import Path
import httpx
from backend.config import settings
from backend.core.ws_manager import ws_manager

install_state = {'status': 'idle', 'message': ''}
_install_lock = asyncio.Lock()

def local_weights_ready():
    marker = settings.VIDEO_MODEL_DIR / 'verified.json'
    try:
        manifest = json.loads(marker.read_text(encoding='utf-8'))
        return manifest['model_id'] == settings.VIDEO_MODEL_ID and all(
            (settings.VIDEO_MODEL_DIR / f['name']).is_file() and
            (settings.VIDEO_MODEL_DIR / f['name']).stat().st_size == f['size']
            for f in manifest['files']) and bool(manifest['files'])
    except (OSError, ValueError, KeyError):
        return False

async def runtime_status():
    issues = []
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        issues.append('Install FFmpeg and ffprobe and add them to PATH.')
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            result = await client.get(settings.OLLAMA_URL.rstrip('/') + '/api/tags')
            result.raise_for_status()
            names = [m['name'] for m in result.json()['models']]
            if settings.OLLAMA_MODEL not in names:
                issues.append(f'Run: ollama pull {settings.OLLAMA_MODEL}')
    except Exception:
        issues.append('Start Ollama for local script and storyboard generation.')
    video_issues = []
    try:
        from packaging.version import Version
        if Version(importlib.metadata.version('diffusers')) < Version('0.35.2'):
            video_issues.append('Install backend/requirements-video.txt with the app Python environment.')
    except importlib.metadata.PackageNotFoundError:
        video_issues.append('Install backend/requirements-video.txt with the app Python environment.')
    if not local_weights_ready():
        video_issues.append('Download and verify the local Wan video model (approximately 27 GiB).')
    if settings.VIDEO_PROVIDER == 'fal':
        if not settings.FAL_KEY.get_secret_value():
            issues.append('Set FAL_KEY in backend/.env and restart the backend to use the paid API.')
    elif settings.VIDEO_PROVIDER == 'local_then_fal' and settings.FAL_KEY.get_secret_value():
        pass
    else:
        issues.extend(video_issues)
    return {'provider': settings.VIDEO_PROVIDER, 'ready': not issues, 'issues': issues,
            'local_weights_ready': local_weights_ready(), 'local_issues': video_issues,
            'api_key_configured': bool(settings.FAL_KEY.get_secret_value()),
            'native_resolution': '480x832 local / 720p Wan API',
            'export_resolution': '1080x1920 (native detail depends on selected provider)',
            'download': dict(install_state), 'mock': False}


def download_video_weights():
    import hashlib
    from huggingface_hub import HfApi, snapshot_download
    install_state.update(status='downloading', message='Checking model files and resuming downloads…')
    info = HfApi().model_info(settings.VIDEO_MODEL_ID, revision=settings.VIDEO_MODEL_REVISION, files_metadata=True)
    files = [f for f in info.siblings if f.rfilename.endswith(('.json', '.safetensors', '.model', '.txt'))]
    required = sum(f.size or 0 for f in files)
    existing = sum((settings.VIDEO_MODEL_DIR/f.rfilename).stat().st_size for f in files if (settings.VIDEO_MODEL_DIR/f.rfilename).exists())
    settings.VIDEO_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(settings.VIDEO_MODEL_DIR).free < max(0, required-existing) + 12*1024**3:
        raise RuntimeError('Insufficient disk space for the local video model plus 12 GiB working space.')
    snapshot_download(settings.VIDEO_MODEL_ID, revision=info.sha, local_dir=str(settings.VIDEO_MODEL_DIR),
                      allow_patterns=[f.rfilename for f in files], max_workers=2)
    install_state.update(status='verifying', message='Verifying downloaded model weights…')
    manifest = []
    for file in files:
        path = settings.VIDEO_MODEL_DIR/file.rfilename
        if file.size is not None and path.stat().st_size != file.size:
            raise ValueError(f'Model size mismatch: {file.rfilename}')
        if file.lfs:
            with path.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            if digest != file.lfs.sha256:
                raise ValueError(f'Model checksum mismatch: {file.rfilename}')
        manifest.append({'name': file.rfilename, 'size': path.stat().st_size})
    (settings.VIDEO_MODEL_DIR/'verified.json').write_text(json.dumps({'model_id': settings.VIDEO_MODEL_ID,
        'revision': info.sha, 'files': manifest}), encoding='utf-8')
    install_state.update(status='complete', message='Local video model verified.')

async def install_video():
    if _install_lock.locked():
        return
    async with _install_lock:
        try:
            await asyncio.to_thread(download_video_weights)
            await ws_manager.broadcast({'event': 'MODEL_DOWNLOAD_PROGRESS', 'model_id': 'wan-video', 'percent': 100, 'is_ready': True})
        except Exception as exc:
            install_state.update(status='failed', message=str(exc))
            await ws_manager.broadcast({'event': 'ERROR', 'message': f'Video model download failed: {exc}'})

if __name__ == '__main__':
    download_video_weights()
