"""Optional audio-driven mouth animation, isolated from the video generator."""
import json,sys,hashlib
from pathlib import Path
from backend.config import settings
from backend.core.process_runner import run_process
from backend.services.media_engine import run_media,inspect_av_sync,probe_media

ROOT=Path(__file__).resolve().parents[1]

def lipsync_ready():
    import importlib.util
    if any(importlib.util.find_spec(name) is None for name in ('cv2','librosa','einops','torch','torchvision','diffusers','transformers','filelock','mediapipe')):
        return False
    root=settings.MODELS_DIR/'lipsync'
    required=[root/'face_landmarker.task',root/'musetalk/musetalkV15/unet.pth',root/'musetalk/musetalkV15/musetalk.json',
        root/'vae/config.json',root/'vae/diffusion_pytorch_model.bin',root/'whisper/config.json',root/'whisper/model.safetensors',root/'whisper/preprocessor_config.json']
    return (ROOT/'vendor/MuseTalk/musetalk/models/unet.py').is_file() and all(p.is_file() and p.stat().st_size > 0 for p in required)

async def animate_speech(source, audio, output, duration_ms, *, portrait=False, face_box=None, audio_offset_frames=0):
    if face_box is not None:
        raise ValueError('Manual face boxes are no longer used; landmark tracking is required for aligned speech.')
    if not lipsync_ready():
        raise RuntimeError('Lip-sync is not installed. Run python -m backend.scripts.install_lipsync first.')
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    frames=max(1,round(duration_ms*30/1000));seconds=frames/30
    source=Path(source);audio=Path(audio)
    identity=hashlib.sha256(json.dumps([str(source.resolve()),source.stat().st_size,source.stat().st_mtime_ns,
        str(audio.resolve()),audio.stat().st_size,audio.stat().st_mtime_ns,frames,portrait,face_box,audio_offset_frames,'musetalk-v15-landmarks-v2']).encode()).hexdigest()
    cached_report=output.with_suffix('.lipsync.json')
    if output.exists() and cached_report.exists():
        try:
            if json.loads(cached_report.read_text()).get('identity')==identity:
                await inspect_av_sync(str(output))
                return output
        except (ValueError,RuntimeError):
            pass
    voice=output.with_suffix('.speech.wav')
    await run_media('ffmpeg','-v','error','-y','-i',str(audio),'-af',f'apad,atrim=duration={seconds:.9f}',
        '-ar','16000','-ac','1',str(voice))
    prepared=Path(source)
    if not portrait:
        prepared=output.with_suffix('.input.mp4')
        await run_media('ffmpeg','-v','error','-y','-i',str(source),'-vf','fps=30','-an','-c:v','libx264','-crf','18',str(prepared))
        info=await probe_media(str(prepared))
        if int(info['streams'][0].get('nb_frames',0))<frames:
            raise ValueError('Lip-sync source is shorter than the scene; provide more generated footage')
    silent=output.with_suffix('.silent.mp4');report=output.with_suffix('.lipsync.json')
    request=output.with_suffix('.lipsync-request.json')
    request.write_text(json.dumps({'source':str(prepared.resolve()),'audio':str(voice.resolve()),
        'silent_output':str(silent.resolve()),'report':str(report.resolve()),'frames':frames,'portrait':portrait,
        'face_box':face_box,'audio_offset_frames':audio_offset_frames,'vendor':str(ROOT/'vendor/MuseTalk'),'models':str(settings.MODELS_DIR/'lipsync')}))
    log=output.with_suffix('.lipsync.log')
    proc=await run_process(sys.executable,'-u','-m','backend.providers.lipsync_worker',str(request.resolve()),
        cwd=str(ROOT.parent),log_path=log,timeout=3600)
    if proc.returncode:
        raise RuntimeError(f'Lip-sync worker failed ({proc.returncode}): {log.read_text(errors="replace")[-1800:]}')
    await run_media('ffmpeg','-v','error','-y','-i',str(silent),'-i',str(voice),'-map','0:v','-map','1:a',
        '-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',str(output))
    timing=await inspect_av_sync(str(output))
    data=json.loads(report.read_text());data['timing']=timing;data['identity']=identity;report.write_text(json.dumps(data,indent=2))
    return output
