"""Audio-led editing: no still animation, looping, or clipped narration."""
import asyncio
import json
import math
import tempfile
from pathlib import Path

from backend.core.process_runner import run_process

async def run_media(*args: str) -> bytes:
    result = await run_process(*args)
    if result.returncode:
        raise RuntimeError(f"{args[0]} failed: {result.stderr.decode(errors='replace')[-3000:]}")
    return result.stdout

async def probe_media(path: str) -> dict:
    return json.loads(await run_media('ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)))

async def get_audio_duration_ms(audio_path: str) -> int:
    info = await probe_media(audio_path)
    if not any(s['codec_type'] == 'audio' for s in info['streams']):
        raise ValueError('Narration file contains no audio')
    seconds = float(info['format']['duration'])
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError('Invalid narration duration')
    return round(math.ceil((seconds + .3) * 30) * 1000 / 30)

async def validate_motion_clip(path: str, minimum_seconds: float = 0) -> dict:
    info = await probe_media(path)
    video = next((s for s in info['streams'] if s['codec_type'] == 'video'), None)
    if not video or int(video.get('nb_frames', 0)) < 2:
        raise ValueError('Video generation must return a multi-frame video, not a still image')
    duration = float(video.get('duration') or info['format'].get('duration', 0))
    if duration + .02 < minimum_seconds:
        raise ValueError(f'Generated video is too short ({duration:.2f}s for {minimum_seconds:.2f}s narration). Generate more footage; looping is disabled.')
    samples = await run_media('ffmpeg', '-v', 'error', '-i', str(path), '-vf', 'fps=4,scale=64:64', '-pix_fmt', 'gray', '-f', 'rawvideo', '-')
    frames = [samples[i:i+4096] for i in range(0, len(samples), 4096) if len(samples[i:i+4096]) == 4096]
    changes = [sum(abs(x-y) for x,y in zip(a,b))/4096 for a,b in zip(frames, frames[1:])]
    if not changes or max(changes) < .25:
        raise ValueError('Generated clip appears static. Regenerate with explicit subject action.')
    return {'width': video['width'], 'height': video['height'], 'duration_seconds': duration,
            'motion_mean_pixel_change': round(sum(changes)/len(changes), 3)}

async def mux_scene(visual_path: str, audio_path: str, duration_ms: int, out_path: str,
                    scene_index: int = 0, subtitle_overlay_path: str | None = None) -> str:
    if Path(visual_path).suffix.lower() not in {'.mp4', '.mov', '.mkv', '.webm'}:
        raise ValueError('Still-image rendering is disabled. A generated motion video is required.')
    frames = max(1, round(duration_ms * 30 / 1000))
    seconds = frames / 30
    await validate_motion_clip(visual_path, seconds)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    filters = (f'[0:v]setpts=PTS-STARTPTS,scale=1080:1920:force_original_aspect_ratio=decrease:flags=lanczos,'
               f'pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,trim=end_frame={frames}[v];'
               f'[1:a]asetpts=PTS-STARTPTS,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000,'
               f'apad,atrim=duration={seconds:.9f}[a]')
    await run_media('ffmpeg', '-y', '-i', visual_path, '-i', audio_path,
                    '-filter_complex', filters, '-map', '[v]', '-map', '[a]',
                    '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-movflags', '+faststart', out_path)
    await inspect_av_sync(out_path)
    return out_path

async def inspect_av_sync(path: str, tolerance: float = .05) -> dict:
    info = await probe_media(path)
    video = next((s for s in info['streams'] if s['codec_type'] == 'video'), None)
    audio = next((s for s in info['streams'] if s['codec_type'] == 'audio'), None)
    if not video or not audio:
        raise ValueError('Export must contain both video and narration')
    vd, ad = float(video['duration']), float(audio['duration'])
    vs, ast = float(video.get('start_time', 0)), float(audio.get('start_time', 0))
    drift = max(abs(vs-ast), abs((vs+vd)-(ast+ad)))
    if not all(math.isfinite(n) for n in (vd, ad, vs, ast)) or drift > tolerance:
        raise ValueError(f'Audio/video timing check failed: {drift * 1000:.1f} ms offset')
    return {'passed': True, 'video_seconds': vd, 'audio_seconds': ad,
            'max_offset_ms': round(drift*1000, 2), 'tolerance_ms': tolerance*1000,
            'width': video['width'], 'height': video['height'],
            'lip_sync': 'not_evaluated', 'scope': 'stream start/end timing; narration over generated footage'}

async def concat_scenes(muxed_scene_paths: list[str], final_out_path: str) -> str:
    if not muxed_scene_paths:
        raise ValueError('No scenes to concatenate')
    Path(final_out_path).parent.mkdir(parents=True, exist_ok=True)
    inputs=[]
    filters=[]
    for i, path in enumerate(muxed_scene_paths):
        report = await inspect_av_sync(path)
        duration = report['video_seconds']
        inputs.extend(['-i', path])
        filters.append(f'[{i}:v]setpts=PTS-STARTPTS[v{i}]')
        filters.append(f'[{i}:a]aresample=48000,apad,atrim=duration={duration:.9f},asetpts=PTS-STARTPTS[a{i}]')
    filters.append(''.join(f'[v{i}][a{i}]' for i in range(len(muxed_scene_paths))) + f'concat=n={len(muxed_scene_paths)}:v=1:a=1[v][a]')
    # Decode away per-file AAC priming, then encode a single continuous timeline.
    await run_media('ffmpeg', '-y', *inputs, '-filter_complex', ';'.join(filters),
                    '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
                    '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-ar', '48000', '-b:a', '192k',
                    '-movflags', '+faststart', final_out_path)
    await inspect_av_sync(final_out_path)
    return final_out_path


def scene_duration_ms(audio_ms: int, target_seconds: int, scene_count: int) -> int:
    """Reserve each beat's runtime without cutting speech; align to 30 fps."""
    if scene_count < 1:
        raise ValueError('A film needs at least one scene')
    return max(audio_ms, round(math.ceil(target_seconds * 30 / scene_count) * 1000 / 30))
