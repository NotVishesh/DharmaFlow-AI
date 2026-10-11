"""
DharmaFlow AI — Instagram Reels Publishing Integration
Uses the official Meta / Instagram Graph API for Professional & Creator Accounts.
Reference: https://developers.facebook.com/docs/instagram-platform/reference/instagram-media
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v20.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


class InstagramUploader:
    """
    Publishes video Reels to Instagram Professional accounts using the official Graph API.

    Requirements:
    1. An Instagram Business or Creator account connected to a Facebook Page.
    2. A Facebook App with `instagram_basic` and `instagram_content_publish` permissions.
    3. A User Access Token or Page Access Token saved in environment/config.
    4. Video hosted at an accessible public URL (or local tunneling via ngrok/Cloudflare for testing).
    """

    def __init__(
        self,
        access_token: str = "",
        business_account_id: str = "",
        max_retries: int = 3,
    ):
        self.access_token = access_token
        self.business_account_id = business_account_id
        self.max_retries = max_retries

    def is_configured(self) -> bool:
        """Check if access token and account ID are provided."""
        return bool(self.access_token and self.business_account_id)

    def check_connection(self) -> dict:
        """Verify token validity and account permissions against Graph API."""
        if not self.is_configured():
            return {
                "connected": False,
                "error": "Instagram credentials missing. Set INSTAGRAM_ACCESS_TOKEN and INSTAGRAM_BUSINESS_ACCOUNT_ID in .env",
            }

        try:
            import httpx
            resp = httpx.get(
                f"{GRAPH_API_BASE}/{self.business_account_id}",
                params={
                    "fields": "id,username,name",
                    "access_token": self.access_token,
                },
                timeout=10.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "connected": True,
                    "account_id": data.get("id"),
                    "username": data.get("username"),
                    "name": data.get("name"),
                }
            else:
                return {
                    "connected": False,
                    "status_code": resp.status_code,
                    "error": resp.json().get("error", {}).get("message", resp.text),
                }
        except Exception as e:
            return {"connected": False, "error": str(e)}

    def publish_reel(
        self,
        video_url: str,
        caption: str,
        cover_url: Optional[str] = None,
        share_to_feed: bool = True,
    ) -> dict:
        """
        Executes the official 3-step Reels publishing flow:
        1. Initialize Media Container: POST /{ig-user-id}/media (media_type=REELS)
        2. Poll container processing status until FINISHED
        3. Publish Media: POST /{ig-user-id}/media_publish
        """
        if not self.is_configured():
            raise RuntimeError("Instagram integration is not configured with access token and business account ID.")

        import httpx

        # Step 1: Create Container
        logger.info("Initializing Instagram Reel media container...")
        container_payload = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "share_to_feed": share_to_feed,
            "access_token": self.access_token,
        }
        if cover_url:
            container_payload["cover_url"] = cover_url

        create_resp = httpx.post(
            f"{GRAPH_API_BASE}/{self.business_account_id}/media",
            data=container_payload,
            timeout=30.0,
        )
        if create_resp.status_code != 200:
            err = create_resp.json().get("error", {}).get("message", create_resp.text)
            raise RuntimeError(f"Failed to create Instagram media container: {err}")

        container_id = create_resp.json().get("id")
        logger.info("Container created: %s. Polling processing status...", container_id)

        # Step 2: Poll container status
        poll_start = time.time()
        timeout = 180.0
        while time.time() - poll_start < timeout:
            status_resp = httpx.get(
                f"{GRAPH_API_BASE}/{container_id}",
                params={
                    "fields": "status_code,status",
                    "access_token": self.access_token,
                },
                timeout=15.0,
            )
            if status_resp.status_code == 200:
                data = status_resp.json()
                code = data.get("status_code")
                if code == "FINISHED":
                    logger.info("Media container %s finished processing.", container_id)
                    break
                elif code == "ERROR":
                    raise RuntimeError(f"Instagram media processing failed: {data.get('status')}")
                elif code in ("IN_PROGRESS", "PUBLISHED"):
                    logger.debug("Container status: %s", code)
            time.sleep(5.0)
        else:
            raise TimeoutError(f"Instagram media processing timed out after {timeout} seconds.")

        # Step 3: Publish container
        logger.info("Publishing container %s to Instagram feed...", container_id)
        publish_resp = httpx.post(
            f"{GRAPH_API_BASE}/{self.business_account_id}/media_publish",
            data={
                "creation_id": container_id,
                "access_token": self.access_token,
            },
            timeout=30.0,
        )
        if publish_resp.status_code != 200:
            err = publish_resp.json().get("error", {}).get("message", publish_resp.text)
            raise RuntimeError(f"Instagram media_publish failed: {err}")

        media_id = publish_resp.json().get("id")
        reel_url = f"https://www.instagram.com/reel/{media_id}/"
        logger.info("Reel published successfully: %s", reel_url)

        return {
            "media_id": media_id,
            "url": reel_url,
            "platform": "instagram",
            "published_at": time.time(),
        }
