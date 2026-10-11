"""
DharmaFlow AI — Analytics Engine
Polls official YouTube Analytics / Data API v3 and records performance snapshots.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.database.models import AnalyticsSnapshot, PublishJob
from app.publishing.youtube import YouTubeUploader

logger = logging.getLogger(__name__)


class AnalyticsEngine:
    """Collects and stores video performance snapshots."""

    def __init__(self, db: Session):
        self.db = db

    def sync_youtube_metrics(self) -> int:
        """
        Polls statistics for all published YouTube videos and saves snapshots.
        Returns count of synced videos.
        """
        from app.core.settings import get_settings
        settings = get_settings()

        uploader = YouTubeUploader(
            client_secrets_file=settings.youtube.client_secrets_file,
            token_file=settings.youtube.token_file,
        )

        if not uploader.is_authenticated():
            logger.info("YouTube not authenticated; skipping analytics sync.")
            return 0

        published_jobs = self.db.query(PublishJob).filter(
            PublishJob.platform == "youtube",
            PublishJob.platform_video_id != None,
        ).all()

        synced = 0
        today_str = datetime.now(timezone.utc).date().isoformat()

        for job in published_jobs:
            try:
                stats_info = uploader.get_video_status(job.platform_video_id)
                if not stats_info:
                    continue

                stats = stats_info.get("statistics", {})
                views = int(stats.get("viewCount", 0))
                likes = int(stats.get("likeCount", 0))
                comments = int(stats.get("commentCount", 0))

                snapshot = AnalyticsSnapshot(
                    publish_job_id=job.id,
                    snapshot_date=today_str,
                    views=views,
                    likes=likes,
                    comments=comments,
                    raw_data=stats,
                )
                self.db.add(snapshot)
                synced += 1
            except Exception as e:
                logger.warning("Could not sync metrics for video %s: %s", job.platform_video_id, e)

        self.db.commit()
        logger.info("Synced YouTube analytics for %d videos.", synced)
        return synced
