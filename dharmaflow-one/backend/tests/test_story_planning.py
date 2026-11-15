from unittest.mock import AsyncMock
import pytest
from backend.providers.local_providers import LocalLLMProvider
from backend.services.media_engine import scene_duration_ms
from backend.schemas.api_schemas import CreateProjectRequest

@pytest.mark.asyncio
async def test_storyboard_preserves_twelve_approved_beats_and_continuity():
    lines=[f'Approved beat {i} has exact words.' for i in range(12)]
    provider=LocalLLMProvider()
    provider._generate=AsyncMock(return_value={'continuity':'Red fox, white tail tip, green forest.', 'shots':[
        {'line_index':i,'visual_prompt':f'Fox takes action {i}.'} for i in range(12)]})
    scenes=await provider.parse_scenes('\n'.join(lines))
    assert [s['dialogue_or_lyrics'] for s in scenes] == lines
    assert all('white tail tip' in s['visual_prompt'] for s in scenes)
    assert len({s['visual_prompt'] for s in scenes}) == 12

@pytest.mark.asyncio
async def test_rejects_incomplete_storyboard_before_rendering():
    provider=LocalLLMProvider()
    provider._generate=AsyncMock(return_value={'continuity':'fox','shots':[]})
    with pytest.raises(ValueError,match='missing or reordered'):
        await provider.parse_scenes('First beat.\nSecond beat.')

@pytest.mark.asyncio
async def test_script_retries_short_story_for_minute_target():
    provider=LocalLLMProvider()
    lines=[f'The fox explores another forest path number {i}.' for i in range(12)]
    provider._generate=AsyncMock(side_effect=[{'lines':lines[:3]},{'lines':lines}])
    script=await provider.generate_script_and_metadata('fox','cinematic',60)
    assert script['raw_script'].splitlines()==lines
    assert provider._generate.await_count==2

def test_minute_timeline_preserves_long_narration():
    durations=[scene_duration_ms(4000,60,12) for _ in range(12)]
    assert sum(durations)==60000
    assert scene_duration_ms(6300,60,12)==6300
    assert CreateProjectRequest(topic='fox').target_duration_seconds==60
    with pytest.raises(ValueError):
        CreateProjectRequest(topic='fox',target_duration_seconds=600)

@pytest.mark.asyncio
async def test_existing_database_migration_preserves_project(tmp_path, monkeypatch):
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text
    from backend.db import database
    engine=create_async_engine('sqlite+aiosqlite:///' + (tmp_path/'legacy.db').as_posix())
    async with engine.begin() as conn:
        await conn.execute(text('CREATE TABLE projects (id TEXT PRIMARY KEY, topic TEXT)'))
        await conn.execute(text("INSERT INTO projects VALUES ('old','Keep this story')"))
    monkeypatch.setattr(database,'engine',engine)
    try:
        await database.init_db()
        await database.init_db()
        async with engine.connect() as conn:
            row=(await conn.execute(text('SELECT topic,target_duration_seconds FROM projects'))).one()
            assert tuple(row)==('Keep this story',15)
    finally:
        await engine.dispose()
