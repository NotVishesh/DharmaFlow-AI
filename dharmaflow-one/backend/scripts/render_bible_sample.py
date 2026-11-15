"""Render a three-scene narrated David and Goliath test reel locally."""
import asyncio
import json
import uuid
from backend.config import settings
from backend.db.database import init_db, AsyncSessionLocal, engine
from backend.db.models import Project, Scene, ProjectStatus, ExecutionMode
from backend.services.pipeline import pipeline_orchestrator

async def main():
    settings.DHARMAFLOW_MOCK_AI=False
    settings.VIDEO_PROVIDER='local'
    settings.VIDEO_OFFLOAD='sequential'
    await init_db()
    lines=[
        'An army froze. One young shepherd stepped forward.',
        'Goliath laughed. David raised his sling, trusting God.',
        'One stone flew. The giant fell. Fear shattered.',
    ]
    continuity=('Biblical-era Valley of Elah, dry golden grass and dusty limestone hills, late afternoon amber sunlight. '
        'David is a young adult shepherd with olive skin, curly dark hair, plain cream linen tunic, brown leather belt and sandals, carrying a simple leather sling. '
        'Goliath is a towering adult warrior in bronze scale armor and a bronze helmet. Earthy ochre and bronze palette, realistic cinematic historical drama. ')
    shots=[
        'Wide low-angle view behind David as he walks steadily out from a line of frightened soldiers into the open valley. '
        'His tunic flutters in the wind; dust rises around his sandals. Goliath waits far ahead. One continuous forward walking action, stable camera.',
        'Medium close side view of David, determined eyes, as he swings his leather sling in a smooth circle above his shoulder. '
        'The sling cord moves visibly, curly hair and loose tunic stir in the wind, dust drifts behind him. Goliath is distant and out of focus. One continuous preparation action.',
        'Wide side view across the battlefield. Goliath loses balance, drops to his knees and falls forward into a cloud of dust in the distance. '
        'David remains standing in the foreground with the sling lowered. Wind moves the golden grass. Non-graphic, no blood, no wounds. One continuous fall, steady camera.',
    ]
    pid=str(uuid.uuid4())
    async with AsyncSessionLocal() as session:
        p=Project(id=pid,topic='David and Goliath: the shepherd who faced fear',style='cinematic biblical historical drama',
            target_duration_seconds=15,mode=ExecutionMode.TURBO,status=ProjectStatus.GENERATING_AUDIO,
            raw_script='\n'.join(lines),yt_title='One Stone. One Act of Faith.',
            yt_description='A dramatized AI-generated retelling of David and Goliath.')
        session.add(p)
        for i,(line,shot) in enumerate(zip(lines,shots)):
            session.add(Scene(id=str(uuid.uuid4()),project_id=pid,scene_index=i,dialogue_or_lyrics=line,visual_prompt=continuity+shot))
        await session.commit()
        settings.TEMP_DIR.joinpath('bible-sample-project.json').write_text(json.dumps({'project_id':pid,'script':lines},indent=2))
        print(f'PROJECT_ID={pid}',flush=True)
        print('\n'.join(lines),flush=True)
        await pipeline_orchestrator.run(pid,session)
        await session.refresh(p)
        print(f'STATUS={p.status.value}\nFINAL_VIDEO={p.final_video_path}\nERROR={p.error_message}',flush=True)
    await engine.dispose()

if __name__=='__main__':
    asyncio.run(main())
