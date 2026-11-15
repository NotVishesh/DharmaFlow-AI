import asyncio
import json
import logging
from pathlib import Path
from typing import Any
import keyring
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.db.models import YouTubeChannel, Project, ProjectStatus
from backend.core.ws_manager import ws_manager

logger = logging.getLogger(__name__)

KEYRING_SERVICE = "dharmaflow_one"
KEYRING_USER = "youtube_oauth_creds"
YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly"
]

class YouTubeService:
    def get_stored_credentials(self) -> Credentials | None:
        creds_json = keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
        if creds_json:
            try:
                data = json.loads(creds_json)
                return Credentials.from_authorized_user_info(data, YOUTUBE_SCOPES)
            except Exception as e:
                logger.warning("Could not parse stored credentials: %s", e)
        return None

    def store_credentials(self, creds: Credentials):
        keyring.set_password(KEYRING_SERVICE, KEYRING_USER, creds.to_json())

    async def start_oauth_flow(self, session: AsyncSession) -> list[YouTubeChannel]:
        client_secrets_path = settings.CLIENT_SECRETS_PATH
        if not client_secrets_path.exists():
            # Create a mock/stub client secrets file if missing for local setup
            client_secrets_path.parent.mkdir(parents=True, exist_ok=True)
            dummy_secrets = {
                "installed": {
                    "client_id": "dummy-client-id",
                    "client_secret": "dummy-client-secret",
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token"
                }
            }
            client_secrets_path.write_text(json.dumps(dummy_secrets))

        def _run_flow():
            flow = InstalledAppFlow.from_client_secrets_file(
                str(client_secrets_path),
                scopes=YOUTUBE_SCOPES
            )
            creds = flow.run_local_server(
                host="127.0.0.1",
                port=0,
                authorization_prompt_message=""
            )
            return creds

        creds = await asyncio.to_thread(_run_flow)
        self.store_credentials(creds)
        return await self.fetch_and_sync_channels(session, creds=creds)

    async def fetch_and_sync_channels(
        self,
        session: AsyncSession,
        creds: Credentials | None = None
    ) -> list[YouTubeChannel]:
        if creds is None:
            creds = self.get_stored_credentials()
        if creds is None:
            # Check if any cached channels already exist
            stmt = select(YouTubeChannel)
            res = await session.execute(stmt)
            return list(res.scalars().all())

        def _fetch():
            youtube = build("youtube", "v3", credentials=creds)
            return youtube.channels().list(part="snippet,statistics", mine=True).execute()

        resp = await asyncio.to_thread(_fetch)
        items = resp.get("items", [])

        # Fetch existing selection
        stmt_sel = select(YouTubeChannel).where(YouTubeChannel.is_selected == True)
        res_sel = await session.execute(stmt_sel)
        has_selection = res_sel.scalar_one_or_none() is not None

        synced_channels = []
        for idx, item in enumerate(items):
            cid = item["id"]
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})

            stmt = select(YouTubeChannel).where(YouTubeChannel.channel_id == cid)
            existing = (await session.execute(stmt)).scalar_one_or_none()

            title = snippet.get("title", f"Channel {cid}")
            thumb = snippet.get("thumbnails", {}).get("default", {}).get("url", "")
            subs = int(stats.get("subscriberCount", 0))

            if existing:
                existing.title = title
                existing.thumbnail_url = thumb
                existing.subscriber_count = subs
                synced_channels.append(existing)
            else:
                is_selected = False
                if not has_selection and idx == 0:
                    is_selected = True
                    has_selection = True
                ch = YouTubeChannel(
                    channel_id=cid,
                    account_email="primary@gmail.com",
                    title=title,
                    thumbnail_url=thumb,
                    subscriber_count=subs,
                    is_selected=is_selected,
                )
                session.add(ch)
                synced_channels.append(ch)

        await session.commit()
        return synced_channels

    async def select_channel(self, channel_id: str, session: AsyncSession) -> None:
        await session.execute(
            update(YouTubeChannel).values(is_selected=False)
        )
        await session.execute(
            update(YouTubeChannel).where(YouTubeChannel.channel_id == channel_id).values(is_selected=True)
        )
        await session.commit()

    async def upload_project_video(
        self,
        project_id: str,
        session: AsyncSession,
        creds: Credentials | None = None
    ) -> str:
        stmt = select(Project).where(Project.id == project_id)
        project = (await session.execute(stmt)).scalar_one_or_none()
        if not project or not project.final_video_path or not Path(project.final_video_path).exists():
            raise ValueError(f"Project {project_id} final video not found.")

        project.status = ProjectStatus.UPLOADING
        await session.commit()
        await ws_manager.broadcast({
            "event": "STATE_CHANGED",
            "project_id": project.id,
            "status": project.status.value,
        })

        if creds is None:
            creds = self.get_stored_credentials()

        def _execute_upload():
            youtube = build("youtube", "v3", credentials=creds)
            body = {
                "snippet": {
                    "title": project.yt_title or project.topic[:100],
                    "description": project.yt_description or "",
                    "tags": project.yt_tags or [],
                    "categoryId": "22",
                },
                "status": {
                    "privacyStatus": project.yt_privacy or "private",
                    "selfDeclaredMadeForKids": False,
                }
            }
            media = MediaFileUpload(
                project.final_video_path,
                chunksize=5 * 1024 * 1024,
                resumable=True,
                mimetype="video/mp4"
            )
            request = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media
            )
            return request

        request = await asyncio.to_thread(_execute_upload)

        response = None
        backoff = 1.0
        while response is None:
            try:
                def _next():
                    return request.next_chunk()

                status, response = await asyncio.to_thread(_next)
                if status:
                    pct = int(status.progress() * 100)
                    await ws_manager.broadcast({
                        "event": "UPLOAD_PROGRESS",
                        "project_id": project.id,
                        "percent": pct
                    })
                backoff = 1.0
            except HttpError as err:
                if err.resp.status in [500, 502, 503, 504]:
                    logger.warning("Transient HTTP %d during upload. Retrying in %.1fs", err.resp.status, backoff)
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2.0, 16.0)
                else:
                    project.status = ProjectStatus.FAILED
                    project.error_message = f"Upload error: {err}"
                    await session.commit()
                    raise

        video_id = response.get("id")
        project.youtube_video_id = video_id
        project.status = ProjectStatus.COMPLETED
        await session.commit()
        await ws_manager.broadcast({
            "event": "STATE_CHANGED",
            "project_id": project.id,
            "status": project.status.value,
            "youtube_video_id": video_id,
        })
        return video_id

youtube_service = YouTubeService()
