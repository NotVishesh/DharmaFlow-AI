"""
DharmaFlow AI — Integration Tests: Pipeline & State Lifecycle
"""
from __future__ import annotations

import os
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.pipeline import run_pipeline
from app.database.models import Base, JobStatus, RenderJob, Script


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_pipeline.db"
    engine = create_engine(f"sqlite:///{db_file.as_posix()}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_pipeline_demo_mode_execution(test_db):
    """Test full offline vertical slice execution in demo mode."""
    result = run_pipeline(
        topic="Karma Yoga from Bhagavad Gita 2:47",
        category="scripture_explainer",
        language="hi",
        target_duration_seconds=25,
        render_preset="draft",
        demo_mode=True,
        db=test_db,
    )

    assert result.job_id is not None
    assert result.success is True, f"Pipeline failed: {result.error}"
    assert result.video_path is not None
    assert result.video_path.exists()
    assert result.video_path.stat().st_size > 5000

    # Verify database persistence
    job = test_db.get(RenderJob, result.job_id)
    assert job is not None
    assert job.status == JobStatus.COMPLETED
    assert job.duration_seconds > 0
    assert job.output_path == str(result.video_path)
    assert job.provenance_manifest is not None
    assert "job_id" in job.provenance_manifest
    assert job.provenance_manifest["script_model"]["provider"] is not None

    # Verify QC result in DB
    assert job.qc_result is not None
    assert job.qc_result.passed is True
    assert job.qc_result.score > 80.0

    # Verify approval state created in PENDING
    assert job.approval is not None
    assert job.approval.status == "PENDING"
