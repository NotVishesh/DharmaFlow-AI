"""Generate genuine body/head motion for the speaking Krishna acceptance test."""
import asyncio
from pathlib import Path
from backend.config import settings
from backend.providers.video_providers import LocalVideoProvider
from backend.services.media_engine import get_audio_duration_ms
async def main():
 settings.VIDEO_OFFLOAD='sequential'
 root=Path('backend/media/krishna-motion-v2');root.mkdir(exist_ok=True)
 voice=Path('backend/media/krishna-lipsync-test/voice-motion.wav')
 duration=await get_audio_duration_ms(str(voice))
 prompt=('A respectful cinematic realistic 3D animated scene of child Lord Krishna, a charming little boy with gentle light blue skin, '
 'curly black hair, a small peacock feather in his hair, gold earrings and a yellow silk tunic, seated in a sunlit Vrindavan courtyard. '
 'Medium close-up showing his head, shoulders, both arms and a clay butter pot held against his chest. '
 'He gently tilts his head, blinks naturally and lifts his right hand in a small pleading gesture while his left arm hugs the pot. '
 'His eyes look toward the viewer, his face stays frontal and clearly visible, lips relaxed. '
 'Soft golden light, natural human facial proportions, warm affectionate expression, moving fabric and peacock feather, fixed camera, '
 'one continuous natural action, no cuts, no text, no other people, no hands near the face.')
 (root/'prompt.txt').write_text(prompt)
 print('Generating source motion:',duration,'ms',flush=True)
 await LocalVideoProvider().generate_visual(prompt,root/'source-motion.mp4',duration/1000)
 print('SOURCE_READY',flush=True)
asyncio.run(main())
