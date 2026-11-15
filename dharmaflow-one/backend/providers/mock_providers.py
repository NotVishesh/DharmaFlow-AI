import asyncio
import logging
from backend.core.process_runner import run_process
from pathlib import Path
from typing import Any
from backend.providers.base import BaseLLMProvider, BaseTTSProvider, BaseVisualProvider

logger = logging.getLogger(__name__)

class MockLLMProvider(BaseLLMProvider):
    async def generate_script_and_metadata(self, topic: str, style: str, target_duration_seconds: int = 60) -> dict[str, Any]:
        await asyncio.sleep(0.05)
        raw_script = (
            f"Have you ever wondered what happens at the edge of the known universe? {topic} reveals secrets beyond imagination.\n"
            f"As gravity warps spacetime itself, reality bends into extraordinary geometries and time begins to stretch.\n"
            f"When we observe the cosmos, we are not just looking at stars, but witnessing the fabric of existence itself."
        )
        return {
            "raw_script": raw_script,
            "yt_title": f"{topic[:60]}",
            "yt_description": f"Exploring {topic}. A journey into the extraordinary cosmos and the laws of reality.\n\n#Shorts #Science #Cosmos",
            "yt_tags": ["shorts", "science", "cosmos", "mindblown"],
        }

    async def parse_scenes(self, raw_script: str) -> list[dict[str, Any]]:
        await asyncio.sleep(0.05)
        lines = [line.strip() for line in raw_script.splitlines() if line.strip()]
        if not lines:
            lines = [
                "Have you ever wondered what happens at the edge of the universe?",
                "Gravity bends spacetime itself into breathtaking geometric horizons.",
                "In the silence of the cosmos, we witness the deepest secrets of existence."
            ]
        visual_descriptors = [
            "glowing accretion disk around a supermassive black hole, gravitational lensing bending starfield, cinematic cosmic photography, 8k",
            "curved spacetime grid warping under immense mass, deep space nebula, neon ethereal glow, hyperrealistic",
            "majestic silhouette of an observer gazing at a spiraling vortex galaxy, golden cosmic dust, volumetric rays, masterpiece"
        ]
        scenes = []
        for i, line in enumerate(lines[:6]):
            prompt = visual_descriptors[i % len(visual_descriptors)]
            scenes.append({
                "scene_index": i,
                "dialogue_or_lyrics": line,
                "visual_prompt": prompt,
            })
        while len(scenes) < 3:
            idx = len(scenes)
            scenes.append({
                "scene_index": idx,
                "dialogue_or_lyrics": f"The journey through {idx + 1} continues to unveil profound mysteries.",
                "visual_prompt": visual_descriptors[idx % len(visual_descriptors)],
            })
        return scenes

class MockTTSProvider(BaseTTSProvider):
    async def synthesize(self, text: str, out_wav_path: Path) -> Path:
        out_wav_path.parent.mkdir(parents=True, exist_ok=True)
        duration = max(1.5, len(text) * 0.05)
        cmd = [
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"sine=frequency=440:duration={duration:.3f}",
            "-c:a", "pcm_s16le",
            str(out_wav_path)
        ]
        proc = await run_process(*cmd)
        stderr = proc.stderr
        if proc.returncode != 0:
            raise RuntimeError(f"Mock TTS ffmpeg failed: {stderr.decode(errors='replace')}")
        return out_wav_path

class MockVisualProvider(BaseVisualProvider):
    async def generate_visual(self, prompt: str, out_path: Path, duration_sec: float = 3.0, dialogue: str = None, **kwargs) -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if out_path.suffix.lower() == ".mp4":
            cmd = [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", f"testsrc2=s=480x832:r=30:d={duration_sec + 0.1:.3f}",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                str(out_path)
            ]
        else:
            cmd = [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", "color=c=darkslateblue:s=1920x1080:d=1",
                "-frames:v", "1",
                str(out_path)
            ]
        proc = await run_process(*cmd)
        stderr = proc.stderr
        if proc.returncode != 0:
            raise RuntimeError(f"Mock Visual ffmpeg failed: {stderr.decode(errors='replace')}")
        return out_path
