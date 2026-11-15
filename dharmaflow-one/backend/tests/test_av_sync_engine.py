import json
from pathlib import Path
import pytest
from backend.services.media_engine import get_audio_duration_ms, mux_scene, concat_scenes, inspect_av_sync, validate_motion_clip, run_media

async def audio(path, seconds):
    await run_media('ffmpeg','-y','-f','lavfi','-i',f'sine=frequency=440:duration={seconds}', '-c:a','pcm_s16le',str(path))

async def video(path, seconds, static=False):
    source = 'color=c=navy:s=480x832:r=30' if static else 'testsrc2=s=480x832:r=30'
    await run_media('ffmpeg','-y','-f','lavfi','-i',f'{source}:d={seconds}', '-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p',str(path))

@pytest.mark.asyncio
async def test_audio_first_scene_mux_duration_precision(tmp_path):
    outputs=[]
    expected=0
    for index, seconds in enumerate((2.15,3.42)):
        wav=tmp_path/f'a{index}.wav'
        clip=tmp_path/f'v{index}.mp4'
        out=tmp_path/f'm{index}.mp4'
        await audio(wav,seconds)
        duration=await get_audio_duration_ms(str(wav))
        assert seconds+.3 <= duration/1000+.001 <= seconds+.335
        expected+=round(duration*30/1000)/30
        await video(clip,duration/1000+.1)
        await mux_scene(str(clip),str(wav),duration,str(out))
        report=await inspect_av_sync(str(out))
        assert report['max_offset_ms'] <= 50
        outputs.append(str(out))
    final=tmp_path/'final.mp4'
    await concat_scenes(outputs,str(final))
    report=await inspect_av_sync(str(final))
    assert report['max_offset_ms'] <= 50
    assert abs(report['video_seconds']-expected) <= .05
    assert (report['width'],report['height']) == (1080,1920)
    # Check actual decoded narration at both sides of the first scene boundary.
    import array
    raw=await run_media('ffmpeg','-v','error','-i',str(final),'-vn','-ac','1','-ar','48000','-f','f32le','-')
    samples=array.array('f'); samples.frombytes(raw)
    boundary=round((2.15+.3)*30)/30
    def rms(start,end):
        window=samples[int(start*48000):int(end*48000)]
        return (sum(x*x for x in window)/len(window))**.5
    assert rms(.2,.4) > .01
    assert rms(2.25,2.4) < .003
    assert rms(boundary+.15,boundary+.35) > .01

@pytest.mark.asyncio
async def test_rejects_still_and_frozen_video(tmp_path):
    with pytest.raises(ValueError,match='Still-image'):
        await mux_scene('still.png','voice.wav',2000,str(tmp_path/'out.mp4'))
    frozen=tmp_path/'frozen.mp4'
    await video(frozen,1,static=True)
    with pytest.raises(ValueError,match='static'):
        await validate_motion_clip(str(frozen))

@pytest.mark.asyncio
async def test_rejects_short_clip_instead_of_looping(tmp_path):
    clip=tmp_path/'short.mp4'
    await video(clip,1)
    with pytest.raises(ValueError,match='too short'):
        await mux_scene(str(clip),'unused.wav',3000,str(tmp_path/'out.mp4'))

@pytest.mark.asyncio
async def test_detects_misaligned_audio(tmp_path):
    path=tmp_path/'bad.mp4'
    await run_media('ffmpeg','-y','-f','lavfi','-i','testsrc2=s=320x240:r=30:d=2',
        '-f','lavfi','-i','sine=frequency=440:duration=1','-c:v','libx264','-c:a','aac',str(path))
    with pytest.raises(ValueError,match='timing check failed'):
        await inspect_av_sync(str(path))
