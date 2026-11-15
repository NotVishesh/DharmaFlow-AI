"""Real text-to-video providers; no image/stock/test fallback in production."""
import asyncio
import hashlib
import json
import math
import time
import sys
from pathlib import Path
import httpx
from backend.config import settings
from backend.core.process_runner import run_process
from backend.providers.base import BaseVisualProvider
from backend.services.media_engine import run_media, validate_motion_clip

NEGATIVE = 'still image, static scene, slideshow, frozen subject, text, subtitles, watermark, blurry, low quality, distorted anatomy, flicker, jump cuts'


def shot_lengths(duration: float) -> list[float]:
    if not math.isfinite(duration) or not 0 < duration <= 120:
        raise ValueError('Scene duration must be between 0 and 120 seconds')
    count = math.ceil(duration / 5)
    return [duration/count] * count


class LocalVideoProvider(BaseVisualProvider):
    def __init__(self):
        self.pipe = None

    def load(self):
        if self.pipe is not None:
            return
        import torch
        try:
            from diffusers import WanPipeline, AutoencoderKLWan
        except ImportError as exc:
            raise RuntimeError('Install backend/requirements-video.txt to enable the local Wan video model.') from exc
        if not torch.cuda.is_available():
            raise RuntimeError('Local Wan generation requires CUDA. Configure the API option on this computer.')
        from backend.services.setup_service import local_weights_ready
        if not local_weights_ready():
            raise RuntimeError('Local video weights are missing. Download the video model in Setup first.')
        vae = AutoencoderKLWan.from_pretrained(str(settings.VIDEO_MODEL_DIR), subfolder='vae', torch_dtype=torch.float32, local_files_only=True)
        self.pipe = WanPipeline.from_pretrained(str(settings.VIDEO_MODEL_DIR), vae=vae,
            text_encoder=None, tokenizer=None, torch_dtype=torch.bfloat16, local_files_only=True)
        # Sequential offload avoids putting the entire text encoder on a 6 GB GPU.
        if settings.VIDEO_OFFLOAD == 'sequential':
            self.pipe.enable_sequential_cpu_offload()
        else:
            self.pipe.to('cuda')
        self.pipe.vae.enable_tiling()

    def close(self):
        self.pipe = None
        import gc
        gc.collect()
        torch = sys.modules.get('torch')
        if torch is not None:
            torch.cuda.empty_cache()

    def _encode(self, prompt: str, embeddings: Path):
        import torch
        from diffusers import WanPipeline
        from transformers import UMT5EncoderModel
        from diffusers.utils import export_to_video
        from backend.services.setup_service import local_weights_ready
        if not local_weights_ready():
            raise RuntimeError('Download and verify the local video weights in Setup first.')
        # The large text encoder and video transformer must not coexist in 16 GB RAM.
        self.close()
        # Execute encoder layers on CUDA, streaming overflow from disk. Avoid CPU
        # layer execution and large resident CPU weights on this 16 GB machine.
        text_encoder = UMT5EncoderModel.from_pretrained(str(settings.VIDEO_MODEL_DIR),
            subfolder='text_encoder', torch_dtype=torch.bfloat16, local_files_only=True,
            device_map='auto', max_memory={0: '4GiB', 'cpu': 0},
            offload_folder=str(settings.TEMP_DIR / 'wan-text-offload'),
            offload_state_dict=True, low_cpu_mem_usage=True)
        encoder = WanPipeline.from_pretrained(str(settings.VIDEO_MODEL_DIR), transformer=None,
            vae=None, text_encoder=text_encoder, torch_dtype=torch.bfloat16, local_files_only=True)
        try:
            with torch.inference_mode():
                positive, negative = encoder.encode_prompt(prompt, NEGATIVE,
                    device=torch.device('cuda'), max_sequence_length=226)
                positive, negative = positive.cpu(), negative.cpu()
        finally:
            del encoder, text_encoder
            self.close()
        if not torch.isfinite(positive).all() or not torch.isfinite(negative).all():
            raise RuntimeError('Encoder produced non-finite prompt embeddings')
        temporary = embeddings.with_suffix('.tmp.pt')
        torch.save({'positive': positive, 'negative': negative}, temporary)
        temporary.replace(embeddings)
        print('Encoder completed; finite embeddings saved.', flush=True)

    def _render(self, prompt: str, out: Path, seconds: float, seed: int, embeddings: Path | None = None):
        import torch
        from diffusers.utils import export_to_video
        embeddings = embeddings or out.with_suffix('.embeddings.pt')
        if not embeddings.exists():
            self._encode(prompt, embeddings)
        tensors = torch.load(embeddings, map_location='cpu', weights_only=True)
        positive, negative = tensors['positive'], tensors['negative']
        self.load()
        frames = max(17, math.ceil((seconds*16 - 1)/4)*4 + 1)
        # The pipeline normalizes supplied embedding dtypes, not their devices.
        # Move both embeddings explicitly for classifier-free guidance.
        result = self.pipe(prompt_embeds=positive.to('cuda'), negative_prompt_embeds=negative.to('cuda'), width=480, height=832,
                           num_frames=frames, num_inference_steps=settings.VIDEO_STEPS,
                           guidance_scale=5.0, generator=torch.Generator('cpu').manual_seed(seed)).frames[0]
        export_to_video(result, str(out), fps=16, quality=9)

    async def generate_visual(self, prompt: str, out_path: Path, duration_sec: float = 3, **kwargs) -> Path:
        return await render_shots(self._render_async, prompt, out_path, duration_sec, 'local-wan-2.1-1.3b')

    async def _render_async(self, *args):
        # Isolate native/CUDA crashes so the desktop backend survives and API fallback works.
        prompt, out, seconds, seed = args
        request = out.with_suffix('.request.json')
        log_path = out.with_suffix('.render.log')
        # Separate encoder and diffusion processes: exiting releases native allocations,
        # CUDA contexts and disk mappings before the next large model is loaded.
        import logging
        logger = logging.getLogger(__name__)
        embeddings = out.with_suffix('.embeddings.pt')
        receipt = embeddings.with_suffix('.cache.json')
        identity = hashlib.sha256(json.dumps([prompt, NEGATIVE, str(settings.VIDEO_MODEL_DIR.resolve()),
            settings.VIDEO_MODEL_ID, 'cuda-encoder-v2']).encode()).hexdigest()
        cached = False
        if embeddings.exists() and receipt.exists():
            try:
                cached = json.loads(receipt.read_text()).get('identity') == identity and embeddings.stat().st_size > 1024
            except (ValueError, OSError):
                pass
        for stage in (('render',) if cached else ('encode', 'render')):
            for attempt in range(2):
                offload = settings.VIDEO_OFFLOAD if attempt == 0 else 'sequential'
                stage_log = out.with_suffix(f'.{stage}.{attempt+1}.render.log')
                request.write_text(json.dumps({'prompt': prompt, 'out': str(out.resolve()), 'seconds': seconds,
                    'seed': seed, 'steps': settings.VIDEO_STEPS, 'model_dir': str(settings.VIDEO_MODEL_DIR.resolve()),
                    'temp_dir': str(settings.TEMP_DIR.resolve()), 'offload': offload,
                    'stage': stage, 'embeddings': str(embeddings.resolve())}), encoding='utf-8')
                process = await run_process(sys.executable, '-u', '-m',
                    'backend.providers.video_worker', str(request.resolve()),
                    cwd=str(Path(__file__).resolve().parents[2]), log_path=stage_log,
                    timeout=settings.VIDEO_TIMEOUT_SECONDS)
                if not process.returncode:
                    if stage == 'encode' and embeddings.exists():
                        receipt.write_text(json.dumps({'identity': identity}), encoding='utf-8')
                    break
                tail = stage_log.read_text(encoding='utf-8', errors='replace')[-3000:]
                native_crash = (process.returncode & 0xffffffff) in (0xc0000005, 0xc0000017, 0xc0000409)
                memory_failure = 'out of memory' in tail.lower()
                if attempt == 0 and (native_crash or memory_failure):
                    logger.warning('%s worker failed (%s). Retrying once in a fresh process with sequential offload. Log: %s', stage, process.returncode, stage_log)
                    await asyncio.sleep(3)
                    continue
                raise RuntimeError(f'Local video worker exited ({process.returncode}) during {stage}. See {stage_log.name}. Completed shots are preserved. {tail}')


class FalVideoProvider(BaseVisualProvider):
    endpoint = 'https://queue.fal.run/fal-ai/wan/v2.2-a14b/text-to-video'

    async def _render_async(self, prompt: str, out: Path, seconds: float, seed: int):
        payload = {'prompt': prompt, 'negative_prompt': NEGATIVE, 'num_frames': max(17, math.ceil((seconds*16-1)/4)*4+1),
                   'frames_per_second': 16, 'resolution': '720p', 'aspect_ratio': '9:16', 'seed': seed,
                   'num_inference_steps': 27, 'video_quality': 'high', 'enable_safety_checker': True}
        await self._submit_payload(payload, out)

    async def _submit_payload(self, payload: dict, out: Path):
        key = settings.FAL_KEY.get_secret_value()
        if not key:
            raise RuntimeError('The API option requires FAL_KEY in backend/.env. No paid request was submitted.')
        headers = {'Authorization': f'Key {key}'}
        # A persisted queue job avoids duplicate paid submissions when a retry resumes.
        job_path = out.with_suffix('.job.json')
        fingerprint = hashlib.sha256(json.dumps([self.endpoint, payload], sort_keys=True).encode()).hexdigest()
        async with httpx.AsyncClient(timeout=60) as client:
            saved = json.loads(job_path.read_text()) if job_path.exists() else {}
            if saved.get('fingerprint') == fingerprint:
                job = saved['job']
            else:
                response = await client.post(self.endpoint, headers=headers, json=payload)
                response.raise_for_status()
                job = response.json()
                job_path.write_text(json.dumps({'fingerprint': fingerprint, 'job': job}), encoding='utf-8')
            from urllib.parse import urlparse
            for field in ('status_url', 'response_url'):
                url = urlparse(job[field])
                if url.scheme != 'https' or url.hostname != 'queue.fal.run':
                    raise RuntimeError('Unexpected API queue URL')
            deadline = time.monotonic() + settings.VIDEO_TIMEOUT_SECONDS
            while time.monotonic() < deadline:
                response = await client.get(job['status_url'], headers=headers)
                response.raise_for_status()
                state = response.json()['status']
                if state == 'COMPLETED':
                    break
                if state not in ('IN_QUEUE', 'IN_PROGRESS'):
                    raise RuntimeError(f'Video API job ended with status {state}')
                await asyncio.sleep(3)
            else:
                raise RuntimeError('Video API timed out. The queue job was saved; retry resumes it without resubmission.')
            response = await client.get(job['response_url'], headers=headers)
            response.raise_for_status()
            url = response.json()['video']['url']
            if urlparse(url).scheme != 'https':
                raise RuntimeError('The API returned an invalid video download URL')
        # Never send the API key to a media host.
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            async with client.stream('GET', url) as response:
                response.raise_for_status()
                temporary = out.with_suffix('.download.mp4')
                with temporary.open('wb') as file:
                    async for chunk in response.aiter_bytes():
                        file.write(chunk)
                temporary.replace(out)

    async def generate_visual(self, prompt: str, out_path: Path, duration_sec: float = 3, **kwargs) -> Path:
        return await render_shots(self._render_async, prompt, out_path, duration_sec, 'fal-wan-2.2-720p')


async def render_shots(render, prompt: str, out_path: Path, duration: float, provider: str) -> Path:
    out_path = out_path.with_suffix('.mp4')
    out_path.parent.mkdir(parents=True, exist_ok=True)
    shots = []
    reports = []
    for index, seconds in enumerate(shot_lengths(duration)):
        shot = out_path.with_name(f'{out_path.stem}_shot_{index}.mp4')
        shot_prompt = f'{prompt}. Continuous natural subject movement and environmental motion, coherent anatomy, cinematic lighting, clear composition. Shot {index+1}: a single uninterrupted action, no text or montage.'
        identity = hashlib.sha256(json.dumps([shot_prompt, seconds, settings.VIDEO_SEED + index,
            settings.VIDEO_STEPS, provider, settings.VIDEO_MODEL_ID], sort_keys=True).encode()).hexdigest()
        receipt = shot.with_suffix('.complete.json')
        reusable = False
        if shot.exists() and receipt.exists():
            try:
                reusable = json.loads(receipt.read_text())['identity'] == identity
                if reusable:
                    await validate_motion_clip(str(shot), seconds)
            except (ValueError, KeyError, RuntimeError):
                reusable = False
        if not reusable:
            await render(shot_prompt, shot, seconds + .04, settings.VIDEO_SEED + index)
        reports.append(await validate_motion_clip(str(shot), seconds))
        receipt.write_text(json.dumps({'identity': identity}), encoding='utf-8')
        shots.append(shot)
    # Normalize and trim each shot so none of the narration requires repeated footage.
    inputs = [arg for shot in shots for arg in ('-i', str(shot))]
    filters = []
    # Divide the integer scene frame budget, not fractional seconds per shot.
    # Independent duration trims can lose a frame at each concat boundary.
    total_frames = max(1, round(duration * 30))
    frames_per_shot, extra = divmod(total_frames, len(shots))
    for i in range(len(shots)):
        frames = frames_per_shot + (1 if i < extra else 0)
        filters.append(f'[{i}:v]fps=30,trim=end_frame={frames},settb=1/30,setpts=N,setsar=1[v{i}]')
    filters.append(''.join(f'[v{i}]' for i in range(len(shots))) + f'concat=n={len(shots)}:v=1:a=0[v]')
    await run_media('ffmpeg', '-y', *inputs, '-filter_complex', ';'.join(filters), '-map', '[v]',
                    '-r', '30', '-fps_mode', 'cfr', '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(out_path))
    await validate_motion_clip(str(out_path), duration)
    out_path.with_suffix('.provenance.json').write_text(json.dumps({'provider': provider, 'shots': reports,
        'native_resolution': f"{reports[0]['width']}x{reports[0]['height']}", 'synthetic_test': False}, indent=2), encoding='utf-8')
    return out_path


class VideoProvider(BaseVisualProvider):
    def __init__(self):
        self.local = LocalVideoProvider()

    def close(self):
        self.local.close()

    async def generate_visual(self, prompt, out_path, duration_sec=3, **kwargs):
        if settings.VIDEO_PROVIDER == 'fal':
            return await FalVideoProvider().generate_visual(prompt, out_path, duration_sec, **kwargs)
        try:
            return await self.local.generate_visual(prompt, out_path, duration_sec, **kwargs)
        except Exception as exc:
            self.local.close()
            if settings.VIDEO_PROVIDER != 'local_then_fal' or not settings.FAL_KEY.get_secret_value():
                raise RuntimeError(f'Local video generation failed: {exc}. The optional API fallback needs VIDEO_PROVIDER=local_then_fal and FAL_KEY.') from exc
            return await FalVideoProvider().generate_visual(prompt, out_path, duration_sec, **kwargs)
