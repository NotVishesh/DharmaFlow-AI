import asyncio
import sys
from pathlib import Path
import pytest
from backend.core.process_runner import run_process
from backend.services.media_engine import get_audio_duration_ms, mux_scene, inspect_av_sync
from backend.providers.mock_providers import MockTTSProvider, MockVisualProvider


def test_media_pipeline_on_selector_loop(tmp_path):
    async def scenario():
        voice = tmp_path / 'voice with spaces.wav'
        await MockTTSProvider().synthesize('hello', voice)
        duration = await get_audio_duration_ms(str(voice))
        clip = await MockVisualProvider().generate_visual('motion', tmp_path/'motion.mp4', duration/1000)
        final = await mux_scene(str(clip), str(voice), duration, str(tmp_path/'output.mp4'))
        assert (await inspect_av_sync(final))['max_offset_ms'] <= 50
    # This is specifically the Windows loop that raised NotImplementedError before.
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(scenario())

@pytest.mark.asyncio
async def test_timeout_is_actionable():
    with pytest.raises(RuntimeError, match='exceeded its'):
        await run_process(sys.executable, '-c', 'import time; time.sleep(30)', timeout=.3)

@pytest.mark.asyncio
async def test_cancellation_reaps_worker(tmp_path):
    import psutil
    pid_file=tmp_path/'pid.txt'
    code=f'import os,time; from pathlib import Path; Path({str(pid_file)!r}).write_text(str(os.getpid())); time.sleep(30)'
    task=asyncio.create_task(run_process(sys.executable,'-c',code))
    for _ in range(200):
        if pid_file.exists(): break
        await asyncio.sleep(.01)
    assert pid_file.exists()
    pid=int(pid_file.read_text())
    task.cancel()
    with pytest.raises(asyncio.CancelledError): await task
    assert not psutil.pid_exists(pid)

@pytest.mark.asyncio
async def test_event_loop_remains_responsive():
    worker=asyncio.create_task(run_process(sys.executable,'-c','import time; time.sleep(.5); print("done")'))
    await asyncio.sleep(.05)
    assert not worker.done()
    result=await worker
    assert result.stdout.strip()==b'done'
