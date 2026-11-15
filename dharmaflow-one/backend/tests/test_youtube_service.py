from unittest.mock import MagicMock
import httplib2
import pytest
from googleapiclient.errors import HttpError
from sqlalchemy import select

from backend.db.database import AsyncSessionLocal
from backend.db.models import YouTubeChannel, Project, ProjectStatus, ExecutionMode
from backend.services.youtube_service import youtube_service

@pytest.mark.asyncio
async def test_multi_channel_discovery_and_selection(async_client, monkeypatch):
    mock_flow = MagicMock()
    mock_flow.run_local_server.return_value = MagicMock(to_json=lambda: "{}")
    monkeypatch.setattr(
        "google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file",
        lambda *args, **kwargs: mock_flow
    )

    mock_youtube = MagicMock()
    mock_channels = MagicMock()
    mock_channels.list.return_value.execute.return_value = {
        "items": [
            {
                "id": "channel_A",
                "snippet": {"title": "Channel A", "thumbnails": {"default": {"url": "http://img/a.jpg"}}},
                "statistics": {"subscriberCount": "1000"},
            },
            {
                "id": "channel_B",
                "snippet": {"title": "Channel B", "thumbnails": {"default": {"url": "http://img/b.jpg"}}},
                "statistics": {"subscriberCount": "5000"},
            },
        ]
    }
    mock_youtube.channels.return_value = mock_channels
    monkeypatch.setattr("backend.services.youtube_service.build", lambda *args, **kwargs: mock_youtube)

    # 1. Login & discover channels
    login_res = await async_client.post("/api/auth/youtube/login")
    assert login_res.status_code == 200
    channels = login_res.json()
    assert len(channels) == 2
    c_ids = [c["channel_id"] for c in channels]
    assert "channel_A" in c_ids and "channel_B" in c_ids

    # 2. Select channel_B
    select_res = await async_client.post("/api/auth/youtube/select-channel", json={"channel_id": "channel_B"})
    assert select_res.status_code == 200

    # 3. Assert channel_B is is_selected=True in SQLite
    async with AsyncSessionLocal() as session:
        stmt = select(YouTubeChannel).where(YouTubeChannel.channel_id == "channel_B")
        ch_b = (await session.execute(stmt)).scalar_one()
        assert ch_b.is_selected is True

        stmt_a = select(YouTubeChannel).where(YouTubeChannel.channel_id == "channel_A")
        ch_a = (await session.execute(stmt_a)).scalar_one()
        assert ch_a.is_selected is False

@pytest.mark.asyncio
async def test_resumable_upload_retry_on_503(tmp_path, monkeypatch):
    import uuid
    dummy_video = tmp_path / "final_video.mp4"
    dummy_video.write_bytes(b"FAKE_MP4_BYTES")
    proj_id = str(uuid.uuid4())

    async with AsyncSessionLocal() as session:
        project = Project(
            id=proj_id,
            topic="Upload Test Topic",
            style="cinematic",
            mode=ExecutionMode.TURBO,
            status=ProjectStatus.WAIT_VIDEO_REVIEW,
            final_video_path=str(dummy_video),
            yt_title="Uploaded Video",
            yt_description="Video description",
            yt_tags=["test", "upload"],
        )
        session.add(project)
        await session.commit()

    # Mock chunked upload with 503 error on first attempt
    mock_status_50 = MagicMock()
    mock_status_50.progress.return_value = 0.5

    mock_request = MagicMock()
    call_count = 0

    def mock_next_chunk():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            resp = httplib2.Response({"status": 503})
            raise HttpError(resp=resp, content=b"Service Unavailable")
        elif call_count == 2:
            return (mock_status_50, None)
        else:
            return (None, {"id": "yt_video_999"})

    mock_request.next_chunk.side_effect = mock_next_chunk

    mock_youtube = MagicMock()
    mock_videos = MagicMock()
    mock_videos.insert.return_value = mock_request
    mock_youtube.videos.return_value = mock_videos

    monkeypatch.setattr("backend.services.youtube_service.build", lambda *args, **kwargs: mock_youtube)
    monkeypatch.setattr("backend.services.youtube_service.MediaFileUpload", lambda *args, **kwargs: MagicMock())

    async with AsyncSessionLocal() as session:
        video_id = await youtube_service.upload_project_video(proj_id, session, creds=MagicMock())
        assert video_id == "yt_video_999"

        stmt = select(Project).where(Project.id == proj_id)
        proj = (await session.execute(stmt)).scalar_one()
        assert proj.youtube_video_id == "yt_video_999"
        assert proj.status == ProjectStatus.COMPLETED
