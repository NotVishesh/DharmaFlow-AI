"""Database engine, session factory, and initialization."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import get_settings
from app.database.models import Base

_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        db_url = settings.storage.database_url
        # Ensure data directory exists for SQLite
        if db_url.startswith("sqlite"):
            db_path_str = db_url.replace("sqlite:///", "")
            db_path = Path(db_path_str)
            db_path.parent.mkdir(parents=True, exist_ok=True)

        _engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False} if "sqlite" in db_url else {},
            echo=False,
        )

        # Enable WAL mode for SQLite for better concurrency
        if "sqlite" in db_url:
            @event.listens_for(_engine, "connect")
            def set_sqlite_pragma(dbapi_conn, _):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA busy_timeout=30000")
                cursor.close()

    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=get_engine()
        )
    return _SessionLocal


def get_db() -> Session:
    """FastAPI dependency: yields a database session."""
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. Safe to call multiple times."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)


def reset_db() -> None:
    """Drop and recreate all tables. DESTRUCTIVE — only for testing."""
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
