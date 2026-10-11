"""
DharmaFlow AI — Visual Generation Manager
Coordinates scene image generation, fallback handling, and asset provenance records.
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Optional

from app.content.schemas import SceneSchema
from app.providers.visual import VisualProvider, get_visual_provider

logger = logging.getLogger(__name__)


class VisualManager:
    """Manages visual assets creation for scenes."""

    def __init__(self, provider: Optional[VisualProvider] = None):
        self.provider = provider or get_visual_provider()

    def generate_scene_image(
        self,
        scene: SceneSchema,
        output_dir: Path,
        width: int = 1080,
        height: int = 1920,
    ) -> Path:
        """Generates visual asset for a single scene."""
        output_dir.mkdir(parents=True, exist_ok=True)
        img_path = output_dir / f"scene_{scene.scene_number:03d}.png"

        try:
            self.provider.generate_image(
                prompt=scene.visual_prompt,
                output_path=img_path,
                width=width,
                height=height,
                scene_number=scene.scene_number,
            )
            scene.asset_path = str(img_path)
            scene.asset_generation_status = "completed"
        except Exception as e:
            logger.warning("Visual provider failed for scene %d: %s. Using procedural placeholder.", scene.scene_number, e)
            from app.providers.visual.providers import PlaceholderVisualProvider
            PlaceholderVisualProvider().generate_image(
                prompt=scene.visual_prompt,
                output_path=img_path,
                width=width,
                height=height,
                scene_number=scene.scene_number,
            )
            scene.asset_path = str(img_path)
            scene.asset_generation_status = "placeholder_fallback"

        return img_path

    @staticmethod
    def compute_file_hash(path: Path) -> str:
        """Compute SHA-256 hash of generated image asset."""
        sha = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha.update(chunk)
        return sha.hexdigest()
