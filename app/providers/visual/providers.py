"""
DharmaFlow AI — Visual Provider Interface
Supports placeholder (offline), ComfyUI (local SD), and future APIs.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class VisualProvider(ABC):
    """Abstract image generation interface."""

    @abstractmethod
    def generate_image(
        self,
        prompt: str,
        output_path: Path,
        width: int = 1080,
        height: int = 1920,
        **kwargs,
    ) -> Path:
        ...

    @abstractmethod
    def is_available(self) -> bool:
        ...


class PlaceholderVisualProvider(VisualProvider):
    """
    Generates placeholder images using Pillow.
    Used for offline development and testing.
    All images are clearly marked as placeholders.
    """

    def is_available(self) -> bool:
        try:
            from PIL import Image  # noqa
            return True
        except ImportError:
            return False

    def generate_image(
        self,
        prompt: str,
        output_path: Path,
        width: int = 1080,
        height: int = 1920,
        scene_number: int = 1,
        **kwargs,
    ) -> Path:
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            raise RuntimeError("Pillow not installed. Run: pip install Pillow")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Create a gradient-based placeholder with scene info
        import colorsys
        hue = (scene_number * 0.15) % 1.0
        rgb = colorsys.hsv_to_rgb(hue, 0.3, 0.25)
        bg_color = tuple(int(c * 255) for c in rgb)

        img = Image.new("RGB", (width, height), color=bg_color)
        draw = ImageDraw.Draw(img)

        # Draw border
        border_color = tuple(int(c * 255) for c in colorsys.hsv_to_rgb(hue, 0.6, 0.7))
        draw.rectangle([20, 20, width - 20, height - 20], outline=border_color, width=4)

        # Draw "PLACEHOLDER" watermark
        text_color = tuple(int(c * 255) for c in colorsys.hsv_to_rgb(hue, 0.1, 0.9))
        center_x, center_y = width // 2, height // 2

        try:
            font_large = ImageFont.truetype("arial.ttf", 80)
            font_small = ImageFont.truetype("arial.ttf", 32)
        except OSError:
            font_large = ImageFont.load_default()
            font_small = font_large

        # Om symbol placeholder
        draw.text((center_x, center_y - 200), "ॐ", fill=text_color, font=font_large, anchor="mm")
        draw.text((center_x, center_y), "[PLACEHOLDER]", fill=text_color, font=font_small, anchor="mm")
        draw.text((center_x, center_y + 80), f"Scene {scene_number}", fill=text_color, font=font_small, anchor="mm")

        # Truncate prompt for display
        short_prompt = (prompt[:60] + "...") if len(prompt) > 60 else prompt
        draw.text(
            (center_x, center_y + 160),
            short_prompt,
            fill=text_color,
            font=font_small,
            anchor="mm",
        )

        draw.text(
            (center_x, height - 80),
            "Test artifact — not for publishing",
            fill=(255, 100, 100),
            font=font_small,
            anchor="mm",
        )

        img.save(str(output_path), "PNG")
        logger.info("Placeholder image saved: %s (%dx%d)", output_path.name, width, height)
        return output_path


class ComfyUIProvider(VisualProvider):
    """
    ComfyUI local Stable Diffusion image generation.
    Connects to the ComfyUI API (http://127.0.0.1:8188 by default).
    """

    def __init__(
        self,
        url: str = "http://127.0.0.1:8188",
        workflow_file: str = "workflows/dharma_t2i.json",
        checkpoint: str = "v1-5-pruned-emaonly.safetensors",
        width: int = 768,
        height: int = 1344,
        steps: int = 25,
        cfg_scale: float = 7.0,
        timeout_seconds: int = 120,
        max_retries: int = 3,
    ):
        self.url = url.rstrip("/")
        self.workflow_file = Path(workflow_file)
        self.checkpoint = checkpoint
        self.width = width
        self.height = height
        self.steps = steps
        self.cfg_scale = cfg_scale
        self.timeout = timeout_seconds
        self.max_retries = max_retries

    def is_available(self) -> bool:
        try:
            import httpx
            r = httpx.get(f"{self.url}/system_stats", timeout=5.0)
            return r.status_code == 200
        except Exception:
            return False

    def generate_image(
        self,
        prompt: str,
        output_path: Path,
        width: int | None = None,
        height: int | None = None,
        negative_prompt: str = "blurry, low quality, text, watermark, signature, nsfw, violence",
        seed: int = -1,
        **kwargs,
    ) -> Path:
        import httpx
        import random

        w = width or self.width
        h = height or self.height
        if seed < 0:
            seed = random.randint(0, 2**32 - 1)

        # Build minimal API workflow
        workflow = self._build_workflow(prompt, negative_prompt, w, h, seed)
        client_id = str(uuid.uuid4())

        output_path.parent.mkdir(parents=True, exist_ok=True)

        for attempt in range(1, self.max_retries + 1):
            try:
                # Queue prompt
                resp = httpx.post(
                    f"{self.url}/prompt",
                    json={"prompt": workflow, "client_id": client_id},
                    timeout=30.0,
                )
                resp.raise_for_status()
                prompt_id = resp.json()["prompt_id"]
                logger.info("ComfyUI prompt queued: %s (attempt %d)", prompt_id[:8], attempt)

                # Poll for completion
                image_data = self._wait_for_output(client_id, prompt_id)
                output_path.write_bytes(image_data)
                logger.info("ComfyUI image saved: %s", output_path.name)
                return output_path

            except Exception as e:
                logger.warning("ComfyUI attempt %d failed: %s", attempt, e)
                if attempt == self.max_retries:
                    raise RuntimeError(f"ComfyUI generation failed after {self.max_retries} attempts: {e}")
                time.sleep(2 ** attempt)

        raise RuntimeError("ComfyUI generation exhausted retries")

    def _build_workflow(self, prompt: str, negative_prompt: str,
                        width: int, height: int, seed: int) -> dict:
        """Build a minimal ComfyUI API workflow for text-to-image."""
        return {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": seed,
                    "steps": self.steps,
                    "cfg": self.cfg_scale,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0],
                },
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": self.checkpoint},
            },
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {"batch_size": 1, "height": height, "width": width},
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": f"masterpiece, best quality, {prompt}, classical Indian art, spiritual, devotional",
                    "clip": ["4", 1],
                },
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": negative_prompt,
                    "clip": ["4", 1],
                },
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {"filename_prefix": "dharma", "images": ["8", 0]},
            },
        }

    def _wait_for_output(self, client_id: str, prompt_id: str) -> bytes:
        """Poll history until the image is ready, then fetch it."""
        import httpx

        deadline = time.time() + self.timeout
        while time.time() < deadline:
            resp = httpx.get(f"{self.url}/history/{prompt_id}", timeout=10.0)
            if resp.status_code == 200:
                history = resp.json()
                if prompt_id in history:
                    outputs = history[prompt_id].get("outputs", {})
                    for node_id, node_output in outputs.items():
                        images = node_output.get("images", [])
                        if images:
                            img_info = images[0]
                            img_resp = httpx.get(
                                f"{self.url}/view",
                                params={
                                    "filename": img_info["filename"],
                                    "subfolder": img_info.get("subfolder", ""),
                                    "type": img_info.get("type", "output"),
                                },
                                timeout=30.0,
                            )
                            img_resp.raise_for_status()
                            return img_resp.content
            time.sleep(2.0)

        raise TimeoutError(f"ComfyUI image generation timed out after {self.timeout}s")
