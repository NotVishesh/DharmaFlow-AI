import os
import tempfile
import sys
from pathlib import Path
import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Keep tests out of the user's real project database and media directory.
_test_root = tempfile.TemporaryDirectory(prefix='dharmaflow-tests-')
os.environ['DHARMAFLOW_DATABASE_URL'] = 'sqlite+aiosqlite:///' + (Path(_test_root.name)/'test.db').as_posix()
os.environ['MEDIA_DIR'] = str(Path(_test_root.name)/'media')
# Enable Mock AI for tests
os.environ["DHARMAFLOW_MOCK_AI"] = "1"

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BASE_DIR.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.config import settings
settings.DHARMAFLOW_MOCK_AI = True

from backend.db.models import Base
from backend.main import app
from backend.db.database import init_db, engine

@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    await init_db()
    yield
    await engine.dispose()

@pytest_asyncio.fixture
async def test_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture
async def async_client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
