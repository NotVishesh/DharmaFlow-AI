from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from backend.config import settings
from backend.db.models import Base

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Additive migration preserves existing projects and generated media.
        from sqlalchemy import inspect, text
        columns = await conn.run_sync(lambda sync: {c['name'] for c in inspect(sync).get_columns('projects')})
        if 'lip_sync' not in columns:
            await conn.execute(text('ALTER TABLE projects ADD COLUMN lip_sync BOOLEAN NOT NULL DEFAULT 0'))
        if 'target_duration_seconds' not in columns:
            await conn.execute(text('ALTER TABLE projects ADD COLUMN target_duration_seconds INTEGER NOT NULL DEFAULT 15'))

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
