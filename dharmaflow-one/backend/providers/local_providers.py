import asyncio
import logging
from pathlib import Path
from typing import Any
import httpx
from backend.core.process_runner import run_process
from backend.providers.base import BaseLLMProvider, BaseTTSProvider, BaseVisualProvider

logger = logging.getLogger(__name__)

class LocalLLMProvider(BaseLLMProvider):
    def __init__(self):
        from backend.config import settings
        self.base_url = settings.OLLAMA_URL.rstrip('/')
        self.model_name = settings.OLLAMA_MODEL

    async def _generate(self, prompt: str, structured=False):
        import json
        payload = {'model': self.model_name, 'prompt': prompt, 'stream': False, 'keep_alive': 0}
        if structured:
            payload['format'] = 'json'
        async with httpx.AsyncClient(timeout=180) as client:
            try:
                res = await client.post(f'{self.base_url}/api/generate', json=payload)
                res.raise_for_status()
                text = res.json()['response'].strip()
                if not text:
                    raise ValueError('Empty model response')
                return json.loads(text) if structured else text
            except Exception as exc:
                raise RuntimeError('Script generation failed. Start Ollama and install the configured model; no canned script was substituted.') from exc

    async def generate_script_and_metadata(self, topic: str, style: str, target_duration_seconds: int = 60) -> dict[str, Any]:
        import math
        count = math.ceil(target_duration_seconds / 5)
        prompt = (
            f'Write a connected {target_duration_seconds}-second film about: {topic}. Style: {style}. '
            f'Return JSON {{"lines": ["spoken narration"]}} with exactly {count} strings. '
            'Each line is one five-second scene with 7-10 spoken words. '
            'Develop ONE story with a clear beginning, discovery, challenge, resolution and ending. '
            'Keep the same main character and connected setting. Each beat advances the story with '
            'a different concrete action and new visual detail; never repeat a summary. '
            'Use natural flowing narration, no headings, numbering, directions or labels.')
        for attempt in range(3):
            data = await self._generate(prompt, True)
            lines = data.get('lines', []) if isinstance(data, dict) else []
            if (len(lines) == count and all(isinstance(line, str) and 7 <= len(line.split()) <= 15
                                          and '\n' not in line for line in lines)):
                break
            prompt += f' Correction: your previous lines were too short or the count was wrong. Write exactly {count} complete sentences, each with AT LEAST SEVEN words and at most 15 words. Use richer action and sensory details.'
        else:
            raise ValueError(f'The script must contain {count} short story beats. Retry script generation.')
        return {'raw_script': '\n'.join(line.strip() for line in lines), 'yt_title': topic[:100],
                'yt_description': f'{topic} — {style} AI-generated short film.', 'yt_tags': ['shortfilm', 'aivideo']}

    async def parse_scenes(self, raw_script: str) -> list[dict[str, Any]]:
        import json
        lines = [line.strip() for line in raw_script.splitlines() if line.strip()]
        if not 1 <= len(lines) <= 30:
            raise ValueError('Use one narration line per scene, with 1 to 30 scenes.')
        prompt = (
            'Act as a film director. Create a connected storyboard for the numbered narration lines. '
            'Return JSON {"continuity": "shared visual description", '
            '"shots": [{"line_index": 0, "visual_prompt": "detailed action shot"}]}. '
            f'Return exactly {len(lines)} shots, one per line, in order. '
            'The continuity description must specify concrete stable character appearance '
            '(species, fur or hair, clothing and distinctive features), setting, palette and lighting. '
            'Do not use names alone as a visual description. Avoid conflicting character details. '
            'Each shot must develop its narration beat with one observable physical action, '
            'environment movement, foreground/background details, composition and camera distance. '
            'Vary wide, medium and close views purposefully; preserve the story location and direction. '
            'No still poses, image zooms, internal cuts, montage, text overlays or quality buzzwords. '
            'Narration lines: ' + json.dumps(list(enumerate(lines))))
        for attempt in range(3):
            data = await self._generate(prompt, True)
            shots = data.get('shots', []) if isinstance(data, dict) else []
            continuity = data.get('continuity', '') if isinstance(data, dict) else ''
            if (isinstance(continuity, str) and continuity.strip() and len(shots) == len(lines)
                and all(isinstance(shot, dict) and shot.get('line_index') == i
                        and isinstance(shot.get('visual_prompt'), str) and shot['visual_prompt'].strip()
                        for i, shot in enumerate(shots))):
                break
            prompt += f' Correction: include continuity and exactly {len(lines)} shots indexed 0 through {len(lines)-1}.'
        else:
            raise ValueError('Storyboard has missing or reordered shots. Retry before rendering.')
        # Assign approved text ourselves: the model cannot drop or rewrite narration.
        return [{'scene_index': i, 'dialogue_or_lyrics': line,
                 'visual_prompt': f"Visual continuity: {continuity.strip()}\nScene {i+1}: {shots[i]['visual_prompt'].strip()}"}
                for i, line in enumerate(lines)]

class LocalTTSProvider(BaseTTSProvider):
    def __init__(self, voice: str = "ryan", language: str = "auto"):
        self.voice = voice
        self.language = language
        self._qwen = None

    def _synthesize_qwen(self, text: str, out_wav_path: Path):
        import importlib.util
        if importlib.util.find_spec('qwen_tts') is None:
            return False
        import torch
        import soundfile as sf
        from huggingface_hub import snapshot_download
        from qwen_tts import Qwen3TTSModel
        if self._qwen is None:
            # Setup should own downloads; do not start an unannounced TTS download here.
            model_path = snapshot_download('Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice', local_files_only=True)
            self._qwen = Qwen3TTSModel.from_pretrained(model_path,
                device_map='cuda:0' if torch.cuda.is_available() else 'cpu',
                dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32)
        waves, sample_rate = self._qwen.generate_custom_voice(text=text, speaker=self.voice,
            language=self.language, instruct='Speak naturally and clearly, with warm cinematic narration.')
        sf.write(str(out_wav_path), waves[0], sample_rate)
        return True

    async def synthesize(self, text: str, out_wav_path: Path) -> Path:
        out_wav_path.parent.mkdir(parents=True, exist_ok=True)
        out_wav_path.unlink(missing_ok=True)
        try:
            if await asyncio.to_thread(self._synthesize_qwen, text, out_wav_path):
                return out_wav_path
        except Exception as exc:
            logger.warning('Local Qwen speech failed, trying installed system voice: %s', exc)
            self.close()

        # Windows offline voice keeps the local workflow usable without a network TTS service.
        import sys
        if sys.platform == 'win32':
            text_path = out_wav_path.with_suffix('.speech.txt')
            text_path.write_text(text, encoding='utf-8')
            script = Path(__file__).with_name('speak.ps1')
            try:
                proc = await run_process('powershell.exe', '-NoProfile', '-NonInteractive',
                    '-File', str(script), '-TextPath', str(text_path.resolve()), '-OutputPath', str(out_wav_path.resolve()))
                err = proc.stderr
                if proc.returncode == 0 and out_wav_path.exists():
                    return out_wav_path
                logger.warning('Offline speech failed: %s', err.decode(errors='replace'))
            finally:
                text_path.unlink(missing_ok=True)

        # 2. Secondary: Edge-TTS
        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, "en-US-GuyNeural")
            mp3_temp = out_wav_path.with_suffix(".edge.mp3")
            await communicate.save(str(mp3_temp))
            cmd = [
                "ffmpeg", "-y", "-i", str(mp3_temp),
                "-c:a", "pcm_s16le", str(out_wav_path)
            ]
            proc = await run_process(*cmd)
            if proc.returncode:
                raise RuntimeError(proc.stderr.decode(errors="replace")[-1000:])
            if mp3_temp.exists():
                mp3_temp.unlink()
            if out_wav_path.exists() and out_wav_path.stat().st_size > 1000:
                return out_wav_path
        except Exception as e:
            logger.info("Edge-TTS unavailable (%s), trying gTTS...", e)

        # 3. Tertiary: gTTS
        try:
            import gtts
            mp3_temp = out_wav_path.with_suffix(".gtts.mp3")
            def _synth():
                tts = gtts.gTTS(text=text, lang="en")
                tts.save(str(mp3_temp))
            await asyncio.to_thread(_synth)
            cmd = [
                "ffmpeg", "-y", "-i", str(mp3_temp),
                "-c:a", "pcm_s16le", str(out_wav_path)
            ]
            proc = await run_process(*cmd)
            if proc.returncode:
                raise RuntimeError(proc.stderr.decode(errors="replace")[-1000:])
            if mp3_temp.exists():
                mp3_temp.unlink()
            if out_wav_path.exists() and out_wav_path.stat().st_size > 1000:
                return out_wav_path
        except Exception as e:
            logger.warning("gTTS unavailable (%s); no speech provider succeeded.", e)

        raise RuntimeError('Speech synthesis failed. Configure Qwen TTS, Edge TTS, or gTTS. Test tones are disabled in production.')

    def close(self):
        if self._qwen is not None:
            self._qwen = None

# Backward-compatible import for the pipeline and sample scripts.
from backend.providers.video_providers import VideoProvider as LocalVisualProvider
