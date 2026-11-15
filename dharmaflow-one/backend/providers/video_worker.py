"""Process boundary for local inference: native model failures cannot crash FastAPI."""
import os
# Apply before torch loads its native thread pools.
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
import faulthandler
faulthandler.enable()
import json
import sys
from pathlib import Path
from backend.config import settings
from backend.providers.video_providers import LocalVideoProvider

if __name__ == '__main__':
    request = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    settings.VIDEO_MODEL_DIR = Path(request['model_dir'])
    settings.TEMP_DIR = Path(request['temp_dir'])
    settings.VIDEO_STEPS = request['steps']
    settings.VIDEO_OFFLOAD = request.get('offload', 'resident')
    import torch
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    torch.backends.mkldnn.enabled = False
    from filelock import FileLock, Timeout
    # Protect shared offload files and VRAM across CLI and web processes.
    lock = FileLock(str(settings.TEMP_DIR / 'local-video-worker.lock'))
    try:
        lock.acquire(timeout=0)
    except Timeout:
        raise RuntimeError('Another local video worker is running. Wait for it to finish before resuming.')
    from backend.core.safe_offload import install_owned_buffer_offload
    install_owned_buffer_offload()
    provider = LocalVideoProvider()
    try:
        embeddings = Path(request['embeddings']) if 'embeddings' in request else None
        print(f"Starting {request.get('stage', 'render')} with {settings.VIDEO_OFFLOAD} offload", flush=True)
        if request.get('stage') == 'encode':
            provider._encode(request['prompt'], embeddings)
        else:
            provider._render(request['prompt'], Path(request['out']), request['seconds'], request['seed'], embeddings)
    finally:
        provider.close()
        lock.release()
