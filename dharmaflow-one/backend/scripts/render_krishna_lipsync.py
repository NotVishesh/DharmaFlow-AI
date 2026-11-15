"""Apply landmark-aligned speech animation to the moving Krishna source."""
import asyncio,argparse
from pathlib import Path
from backend.services.lipsync_service import animate_speech
from backend.services.media_engine import get_audio_duration_ms
async def main(offset):
 root=Path('backend/media/krishna-motion-v2')
 source=root/'source-motion.mp4'
 if not source.exists(): raise RuntimeError('Generate moving footage first: python -m backend.scripts.render_krishna_motion')
 voice=Path('backend/media/krishna-lipsync-test/voice-motion.wav')
 duration=await get_audio_duration_ms(str(voice))
 out=await animate_speech(source,voice,root/f'krishna-speaking-offset{offset}.mp4',duration,audio_offset_frames=offset)
 print(out,flush=True)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--offset',type=int,default=0)
 asyncio.run(main(parser.parse_args().offset))
