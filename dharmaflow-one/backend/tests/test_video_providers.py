import pytest
from pathlib import Path
from pydantic import SecretStr
from backend.config import settings
from backend.providers.video_providers import VideoProvider, LocalVideoProvider, FalVideoProvider, shot_lengths, render_shots
from backend.services.media_engine import run_media

@pytest.mark.parametrize('duration',[.5, 5, 5.5, 15.2])
def test_shots_cover_narration_without_looping(duration):
    lengths=shot_lengths(duration)
    assert sum(lengths)==pytest.approx(duration)
    assert max(lengths)<=5

@pytest.mark.asyncio
async def test_local_failure_does_not_silently_use_cloud(monkeypatch,tmp_path):
    monkeypatch.setattr(settings,'VIDEO_PROVIDER','local')
    async def fail(*args,**kwargs): raise RuntimeError('GPU memory exhausted')
    monkeypatch.setattr(LocalVideoProvider,'generate_visual',fail)
    monkeypatch.setattr(LocalVideoProvider,'close',lambda self: None)
    async def cloud(*args,**kwargs): pytest.fail('Paid fallback must be configured')
    monkeypatch.setattr(FalVideoProvider,'generate_visual',cloud)
    with pytest.raises(RuntimeError,match='GPU memory exhausted'):
        await VideoProvider().generate_visual('A bird flies',tmp_path/'out.mp4',3)

@pytest.mark.asyncio
async def test_explicit_cloud_fallback(monkeypatch,tmp_path):
    monkeypatch.setattr(settings,'VIDEO_PROVIDER','local_then_fal')
    monkeypatch.setattr(settings,'FAL_KEY',SecretStr('test-key'))
    async def fail(*args,**kwargs): raise RuntimeError('GPU memory exhausted')
    monkeypatch.setattr(LocalVideoProvider,'generate_visual',fail)
    monkeypatch.setattr(LocalVideoProvider,'close',lambda self: None)
    async def cloud(self,prompt,path,duration,**kwargs): return path
    monkeypatch.setattr(FalVideoProvider,'generate_visual',cloud)
    out=tmp_path/'out.mp4'
    assert await VideoProvider().generate_visual('A bird flies',out,3)==out

@pytest.mark.asyncio
async def test_multishot_render_preserves_duration(tmp_path):
    calls=[]
    async def render(prompt,path,seconds,seed):
        calls.append((seconds,seed))
        await run_media('ffmpeg','-y','-f','lavfi','-i',f'testsrc2=s=320x576:r=16:d={seconds+.1}',
                        '-c:v','libx264','-preset','ultrafast',str(path))
    path=await render_shots(render,'A fox runs',tmp_path/'out.mp4',5.6,'fixture')
    assert len(calls)==2
    assert path.exists()
    assert path.with_suffix('.provenance.json').exists()

@pytest.mark.asyncio
async def test_fal_queue_resume_and_credential_separation(monkeypatch, tmp_path):
    import httpx
    from backend.providers import video_providers as module
    monkeypatch.setattr(settings, 'FAL_KEY', SecretStr('private-test-key'))
    requests=[]
    def handler(request):
        requests.append(request)
        if request.method == 'POST':
            assert request.headers['authorization'] == 'Key private-test-key'
            return httpx.Response(200,json={'status_url':'https://queue.fal.run/job/status',
                'response_url':'https://queue.fal.run/job/result'})
        if request.url.path == '/job/status':
            return httpx.Response(200,json={'status':'COMPLETED'})
        if request.url.path == '/job/result':
            return httpx.Response(200,json={'video':{'url':'https://media.fal.media/result.mp4'}})
        assert 'authorization' not in request.headers
        return httpx.Response(200,content=b'mock-video-payload')
    original=httpx.AsyncClient
    monkeypatch.setattr(module.httpx,'AsyncClient',lambda **kwargs: original(transport=httpx.MockTransport(handler),**kwargs))
    provider=FalVideoProvider()
    out=tmp_path/'shot.mp4'
    await provider._render_async('fox runs',out,3,42)
    await provider._render_async('fox runs',out,3,42)
    assert sum(r.method=='POST' for r in requests)==1
    assert out.read_bytes()==b'mock-video-payload'
    assert 'private-test-key' not in out.with_suffix('.job.json').read_text()

@pytest.mark.asyncio
async def test_native_worker_failure_is_reported(monkeypatch, tmp_path):
    from backend.providers import video_providers as module
    class FailedProcess:
        returncode = 17
        async def wait(self): return 17
    async def spawn(*args, **kwargs):
        kwargs['log_path'].write_text('Native crash', encoding='utf-8')
        return FailedProcess()
    monkeypatch.setattr(module, 'run_process', spawn)
    with pytest.raises(RuntimeError, match='worker exited'):
        await LocalVideoProvider()._render_async('A fox leaps', tmp_path/'out.mp4', 2, 42)

@pytest.mark.asyncio
async def test_native_crash_retries_stage_in_fresh_low_memory_worker(monkeypatch,tmp_path):
    import json
    from types import SimpleNamespace
    from backend.providers import video_providers as module
    calls=[]
    async def spawn(*args,**kwargs):
        data=json.loads(__import__('pathlib').Path(args[-1]).read_text())
        calls.append((data['stage'],data['offload']))
        kwargs['log_path'].write_text('native failure')
        return SimpleNamespace(returncode=3221225477 if len(calls)==2 else 0)
    async def no_wait(*args): pass
    monkeypatch.setattr(module,'run_process',spawn)
    monkeypatch.setattr(module.asyncio,'sleep',no_wait)
    monkeypatch.setattr(settings,'VIDEO_OFFLOAD','resident')
    await LocalVideoProvider()._render_async('fox',tmp_path/'clip.mp4',3,42)
    assert calls==[('encode','resident'),('render','resident'),('render','sequential')]

@pytest.mark.asyncio
async def test_native_crash_retry_is_bounded(monkeypatch,tmp_path):
    from types import SimpleNamespace
    from backend.providers import video_providers as module
    calls=[]
    async def spawn(*args,**kwargs):
        calls.append(1)
        kwargs['log_path'].write_text('crash')
        return SimpleNamespace(returncode=3221225477)
    async def no_wait(*args): pass
    monkeypatch.setattr(module,'run_process',spawn)
    monkeypatch.setattr(module.asyncio,'sleep',no_wait)
    with pytest.raises(RuntimeError,match='Completed shots are preserved'):
        await LocalVideoProvider()._render_async('fox',tmp_path/'clip.mp4',3,42)
    assert len(calls)==2

@pytest.mark.asyncio
async def test_completed_shots_survive_retry(tmp_path):
    calls=[]
    async def render(prompt,path,seconds,seed):
        calls.append(seed)
        await run_media('ffmpeg','-y','-f','lavfi','-i',f'testsrc2=s=160x288:r=16:d={seconds+.1}',
            '-c:v','libx264','-preset','ultrafast',str(path))
    out=tmp_path/'resume.mp4'
    await render_shots(render,'fox',out,5.6,'fixture')
    await render_shots(render,'fox',out,5.6,'fixture')
    assert len(calls)==2

@pytest.mark.asyncio
async def test_prompt_cache_reused_only_for_matching_prompt(monkeypatch,tmp_path):
    import json
    from pathlib import Path
    from types import SimpleNamespace
    from backend.providers import video_providers as module
    stages=[]
    async def spawn(*args,**kwargs):
        data=json.loads(Path(args[-1]).read_text());stages.append(data['stage'])
        if data['stage']=='encode': Path(data['embeddings']).write_bytes(b'x'*2048)
        kwargs['log_path'].write_text('ok')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(module,'run_process',spawn)
    provider=LocalVideoProvider();out=tmp_path/'clip.mp4'
    await provider._render_async('fox',out,3,42)
    await provider._render_async('fox',out,3,42)
    assert stages==['encode','render','render']
    await provider._render_async('different fox',out,3,42)
    assert stages[-2:]==['encode','render']

@pytest.mark.asyncio
@pytest.mark.parametrize('duration,expected_frames',[(5.433,163),(5.467,164),(10.033,301)])
async def test_fractional_shot_joins_preserve_scene_frame_budget(tmp_path,duration,expected_frames):
    from backend.services.media_engine import probe_media
    async def render(prompt,path,seconds,seed):
        await run_media('ffmpeg','-y','-f','lavfi','-i',f'testsrc2=s=160x288:r=16:d={seconds+.1}',
            '-c:v','libx264','-preset','ultrafast',str(path))
    path=await render_shots(render,'moving subject',tmp_path/'joined.mp4',duration,'fixture')
    video=(await probe_media(str(path)))['streams'][0]
    assert int(video['nb_frames'])==expected_frames
    assert abs(float(video['duration'])-expected_frames/30)<.00001
