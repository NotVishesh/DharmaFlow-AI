"""Visual provider factory."""
from __future__ import annotations

from app.core.settings import get_settings
from app.providers.visual.providers import (
    ComfyUIProvider, PlaceholderVisualProvider, VisualProvider,
)


def get_visual_provider(override: str | None = None) -> VisualProvider:
    settings = get_settings()
    name = override or settings.visuals.provider

    if name == "comfyui":
        c = settings.visuals.comfyui
        if not c.enabled:
            raise ValueError("ComfyUI is not enabled in config. Set visuals.comfyui.enabled=true.")
        return ComfyUIProvider(
            url=c.url,
            workflow_file=c.workflow_file,
            checkpoint=c.checkpoint,
            width=c.width,
            height=c.height,
            steps=c.steps,
            cfg_scale=c.cfg_scale,
            timeout_seconds=c.timeout_seconds,
            max_retries=c.max_retries,
        )
    elif name == "placeholder":
        return PlaceholderVisualProvider()
    else:
        raise ValueError(f"Unknown visual provider: {name}")
