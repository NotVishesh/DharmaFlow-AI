import asyncio
from pathlib import Path
import pytest

async def wait_for_status(client, project_id: str, target_statuses: list[str], timeout: float = 15.0) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        res = await client.get(f"/api/projects/{project_id}")
        assert res.status_code == 200
        data = res.json()
        if data["status"] in target_statuses:
            return data
        if data["status"] == "FAILED":
            raise RuntimeError(f"Project failed: {data.get('error_message')}")
        await asyncio.sleep(0.1)
    raise TimeoutError(f"Project did not reach {target_statuses} within {timeout}s. Current: {data.get('status')}")

@pytest.mark.asyncio
async def test_review_mode_halts_and_persists_edits(async_client):
    # 1. Create project with mode="REVIEW"
    create_res = await async_client.post("/api/projects", json={
        "topic": "The Stoic Art of Inner Peace",
        "style": "cinematic",
        "mode": "REVIEW"
    })
    assert create_res.status_code == 200
    project = create_res.json()
    project_id = project["id"]

    # 2. Assert pipeline halts at WAIT_SCRIPT_REVIEW
    data = await wait_for_status(async_client, project_id, ["WAIT_SCRIPT_REVIEW"])
    assert data["status"] == "WAIT_SCRIPT_REVIEW"
    assert data["raw_script"] is not None

    # 3. Call POST /api/projects/{id}/approve-script with edited script
    edited_script = "EDITED SCRIPT CONTENT: Line 1 of deep reflection.\nLine 2 of actionable wisdom.\nLine 3 of peaceful completion."
    approve_script_res = await async_client.post(
        f"/api/projects/{project_id}/approve-script",
        json={"raw_script": edited_script}
    )
    assert approve_script_res.status_code == 200

    # 4. Assert pipeline advances and halts at WAIT_SCENE_REVIEW
    data = await wait_for_status(async_client, project_id, ["WAIT_SCENE_REVIEW"])
    assert data["status"] == "WAIT_SCENE_REVIEW"
    assert len(data["scenes"]) >= 3

    # 5. Call POST /api/projects/{id}/approve-scenes with updated scene 0 dialogue
    scenes = data["scenes"]
    updated_scenes = [
        {
            "id": scenes[0]["id"],
            "dialogue_or_lyrics": "Custom spoken line that is noticeably longer for duration testing",
            "visual_prompt": scenes[0]["visual_prompt"]
        }
    ]
    for sc in scenes[1:]:
        updated_scenes.append({
            "id": sc["id"],
            "dialogue_or_lyrics": sc["dialogue_or_lyrics"],
            "visual_prompt": sc["visual_prompt"]
        })

    approve_scenes_res = await async_client.post(
        f"/api/projects/{project_id}/approve-scenes",
        json={"scenes": updated_scenes}
    )
    assert approve_scenes_res.status_code == 200

    # 6. Assert pipeline advances through AUDIO -> VISUALS -> MUXING and halts at WAIT_VIDEO_REVIEW
    data = await wait_for_status(async_client, project_id, ["WAIT_VIDEO_REVIEW"], timeout=30.0)
    assert data["status"] == "WAIT_VIDEO_REVIEW"

    # 7. Assert final_video_path exists on disk and has size > 0
    final_video = data["final_video_path"]
    assert final_video is not None
    final_path = Path(final_video)
    assert final_path.exists()
    assert final_path.stat().st_size > 0

@pytest.mark.asyncio
async def test_turbo_mode_zero_touch_execution(async_client):
    # 1. Create project with mode="TURBO"
    create_res = await async_client.post("/api/projects", json={
        "topic": "The Science of Deep Focus",
        "style": "minimalist",
        "mode": "TURBO"
    })
    assert create_res.status_code == 200
    project = create_res.json()
    project_id = project["id"]

    # 2. Assert pipeline transitions automatically all the way to WAIT_VIDEO_REVIEW
    data = await wait_for_status(async_client, project_id, ["WAIT_VIDEO_REVIEW"], timeout=30.0)
    assert data["status"] == "WAIT_VIDEO_REVIEW"

    # 3. Assert yt_title, yt_description, and yt_tags are populated and final_video_path is valid MP4
    assert data["yt_title"] is not None and len(data["yt_title"]) > 0
    assert data["yt_description"] is not None and len(data["yt_description"]) > 0
    assert data["yt_tags"] is not None and len(data["yt_tags"]) > 0

    final_video = data["final_video_path"]
    assert final_video is not None
    final_path = Path(final_video)
    assert final_path.exists()
    assert final_path.stat().st_size > 0
    assert final_path.suffix.lower() == ".mp4"

@pytest.mark.asyncio
async def test_failed_project_can_retry_without_regenerating_completed_assets(async_client, monkeypatch):
    from backend.providers.mock_providers import MockVisualProvider
    from backend.config import settings
    from backend.providers.video_providers import VideoProvider
    from backend.services.pipeline import pipeline_orchestrator
    original = MockVisualProvider.generate_visual
    failed = False
    calls = []
    async def fail_once(self, prompt, out_path, duration_sec=3, **kwargs):
        nonlocal failed
        calls.append(out_path.name)
        if out_path.name == 'scene_1.mp4' and not failed:
            failed = True
            raise RuntimeError('temporary video generation failure')
        return await original(self,prompt,out_path,duration_sec,**kwargs)
    monkeypatch.setattr(MockVisualProvider,'generate_visual',fail_once)
    response = await async_client.post('/api/projects',json={'topic':'Fox runs','mode':'TURBO'})
    pid = response.json()['id']
    project = (await async_client.get(f'/api/projects/{pid}')).json()
    assert project['status'] == 'FAILED'
    retry = await async_client.post(f'/api/projects/{pid}/retry')
    assert retry.status_code == 200
    project = (await async_client.get(f'/api/projects/{pid}')).json()
    assert project['status'] == 'WAIT_VIDEO_REVIEW'
    assert calls.count('scene_0.mp4') == 1
    assert calls.count('scene_1.mp4') == 2
    report = (await async_client.get(f'/api/projects/{pid}/quality')).json()
    assert report['passed'] and report['max_offset_ms'] <= 50
    assert report['synthetic_test'] is True
    assert (await async_client.post(f'/api/projects/{pid}/retry')).status_code == 409
