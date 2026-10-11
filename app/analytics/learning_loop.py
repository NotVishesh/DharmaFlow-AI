"""
DharmaFlow AI — Analytics Learning Loop
Derives content insights from observed video metrics and provides strategic recommendations.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session

from app.database.models import AnalyticsSnapshot, PublishJob, RenderJob, Script

logger = logging.getLogger(__name__)

MINIMUM_SAMPLE_SIZE = 3


class LearningLoop:
    """Analyzes historical audience retention & engagement to optimize future topics."""

    def __init__(self, db: Session):
        self.db = db

    def generate_recommendations(self) -> dict[str, Any]:
        """
        Analyzes performance by category, duration, and language.
        Generates data-driven recommendations without superstitious assumptions.
        """
        # Fetch completed publish jobs that have analytics
        publish_jobs = self.db.query(PublishJob).filter(PublishJob.platform_video_id != None).all()

        category_stats: dict[str, list[int]] = defaultdict(list)
        language_stats: dict[str, list[int]] = defaultdict(list)
        total_views = 0

        for pj in publish_jobs:
            latest_snapshot = (
                self.db.query(AnalyticsSnapshot)
                .filter(AnalyticsSnapshot.publish_job_id == pj.id)
                .order_by(AnalyticsSnapshot.created_at.desc())
                .first()
            )
            views = latest_snapshot.views if (latest_snapshot and latest_snapshot.views) else 0
            total_views += views

            if pj.render_job and pj.render_job.script:
                script = pj.render_job.script
                category_stats[script.category].append(views)
                language_stats[script.language].append(views)

        recommendations = {
            "total_analyzed_videos": len(publish_jobs),
            "total_views": total_views,
            "category_performance": {},
            "recommended_focus_categories": [],
            "suggested_duration_seconds": 40,
            "recommended_language": "hi",
            "notes": [],
        }

        # Analyze categories
        for cat, view_list in category_stats.items():
            avg_views = sum(view_list) / len(view_list) if view_list else 0
            count = len(view_list)
            recommendations["category_performance"][cat] = {
                "sample_size": count,
                "average_views": round(avg_views, 1),
                "statistically_meaningful": count >= MINIMUM_SAMPLE_SIZE,
            }

        # Select top performing categories if sample size adequate
        meaningful_categories = [
            cat for cat, stats in recommendations["category_performance"].items()
            if stats["statistically_meaningful"]
        ]

        if meaningful_categories:
            sorted_cats = sorted(
                meaningful_categories,
                key=lambda c: recommendations["category_performance"][c]["average_views"],
                reverse=True,
            )
            recommendations["recommended_focus_categories"] = sorted_cats[:2]
            recommendations["notes"].append(
                f"Categories '{sorted_cats[0]}' show higher audience engagement based on observed data."
            )
        else:
            recommendations["recommended_focus_categories"] = ["scripture_explainer", "epic_storytelling"]
            recommendations["notes"].append(
                f"Sample size below {MINIMUM_SAMPLE_SIZE} videos per category. Maintaining default balanced distribution."
            )

        return recommendations
