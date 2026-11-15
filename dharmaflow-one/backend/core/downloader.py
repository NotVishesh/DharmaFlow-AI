import os
import hashlib
import logging
from pathlib import Path
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db.models import ModelArtifact
from backend.core.ws_manager import ws_manager

logger = logging.getLogger(__name__)

async def compute_file_sha256(filepath: Path) -> str:
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            sha256.update(chunk)
    return sha256.hexdigest()

async def download_model_artifact(
    artifact: ModelArtifact,
    dest_dir: Path,
    session: AsyncSession | None = None,
    client: httpx.AsyncClient | None = None,
) -> bool:
    dest_dir.mkdir(parents=True, exist_ok=True)
    target_path = dest_dir / artifact.filename
    existing_bytes = target_path.stat().st_size if target_path.exists() else 0

    headers = {}
    if existing_bytes > 0:
        headers["Range"] = f"bytes={existing_bytes}-"

    close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=60.0, follow_redirects=True)
        close_client = True

    try:
        async with client.stream("GET", artifact.url, headers=headers) as resp:
            # Handle resume or full download
            if resp.status_code == 206:
                mode = "ab"
                total_bytes = artifact.size_bytes
            elif resp.status_code == 200:
                mode = "wb"
                existing_bytes = 0
                content_len = resp.headers.get("content-length")
                total_bytes = int(content_len) if content_len else artifact.size_bytes
            else:
                resp.raise_for_status()
                total_bytes = artifact.size_bytes
                mode = "wb"

            downloaded = existing_bytes
            with open(target_path, mode) as f:
                async for chunk in resp.aiter_bytes(chunk_size=1024 * 512):
                    f.write(chunk)
                    downloaded += len(chunk)
                    artifact.downloaded_bytes = downloaded
                    pct = round((downloaded / total_bytes) * 100, 2) if total_bytes > 0 else 0
                    await ws_manager.broadcast({
                        "event": "MODEL_DOWNLOAD_PROGRESS",
                        "model_id": artifact.id,
                        "percent": pct,
                        "downloaded_bytes": downloaded,
                        "total_bytes": total_bytes,
                    })

        # Verify SHA-256
        computed_hash = await compute_file_sha256(target_path)
        if computed_hash.lower() != artifact.sha256.lower():
            if target_path.exists():
                target_path.unlink()
            artifact.downloaded_bytes = 0
            artifact.is_ready = False
            if session:
                await session.commit()
            raise ValueError("Checksum mismatch")

        artifact.is_ready = True
        artifact.downloaded_bytes = target_path.stat().st_size
        if session:
            await session.commit()

        await ws_manager.broadcast({
            "event": "MODEL_DOWNLOAD_PROGRESS",
            "model_id": artifact.id,
            "percent": 100.0,
            "is_ready": True,
        })
        return True

    finally:
        if close_client:
            await client.aclose()
