"""Restore local models without generation API keys."""
import asyncio
import subprocess
from huggingface_hub import snapshot_download
from backend.config import settings
from backend.services.setup_service import local_weights_ready, download_video_weights
from backend.services.lipsync_service import lipsync_ready
from backend.scripts.install_lipsync import main as install_lipsync
from backend.scripts.install_syncnet import main as install_syncnet
from backend.db.database import init_db, engine

async def database():
    await init_db()
    await engine.dispose()

def main():
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError('Local video requires an NVIDIA CUDA GPU and driver. Install the NVIDIA driver and retry.')
    subprocess.run(['ollama', 'pull', settings.OLLAMA_MODEL], check=True)
    if not local_weights_ready():
        download_video_weights()
    if not lipsync_ready():
        install_lipsync()
    install_syncnet()
    snapshot_download('Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice')
    asyncio.run(database())
    print('Models and database ready. Subsequent starts reuse downloaded files.')

if __name__ == '__main__':
    main()
