"""Unit tests for SQLite persistence layer."""

import pytest
from pathlib import Path

from app.database.db import (
    init_db,
    save_investigation,
    get_investigation,
    list_investigations,
)
from app.schemas.failure import FailureReport
from app.schemas.report import InvestigationReport, TraceEntry


@pytest.fixture
def test_db_path(tmp_path):
    """Fixture providing isolated temporary database path."""
    return str(tmp_path / "test_bugscope.db")


@pytest.fixture
def sample_report():
    """Fixture providing a mock InvestigationReport."""
    return InvestigationReport(
        investigation_id="test-uuid-12345",
        failure_report=FailureReport(
            error_type="KeyError",
            message="'user_id'",
            file="app/main.py",
            line=42,
            function="get_user",
            category="KeyError",
            severity="medium",
        ),
        traces=[
            TraceEntry(
                node="failure_analyzer",
                duration_ms=15.0,
                tokens_in=0,
                tokens_out=0,
                cost_usd=0.0,
            ),
            TraceEntry(
                node="hypothesis_generator",
                duration_ms=500.0,
                tokens_in=300,
                tokens_out=150,
                cost_usd=0.00012,
            ),
        ],
        verdict="validated",
        total_duration_seconds=0.515,
        total_cost_usd=0.00012,
    )


def test_init_db_creates_tables(test_db_path):
    """Test initializing database creates expected schema."""
    init_db(test_db_path)
    assert Path(test_db_path).is_file()


def test_save_and_get_investigation(test_db_path, sample_report):
    """Test saving and retrieving an investigation report."""
    saved_id = save_investigation(sample_report, db_path=test_db_path)
    assert saved_id == "test-uuid-12345"

    retrieved = get_investigation("test-uuid-12345", db_path=test_db_path)
    assert retrieved is not None
    assert retrieved.investigation_id == "test-uuid-12345"
    assert retrieved.verdict == "validated"
    assert retrieved.failure_report.error_type == "KeyError"
    assert len(retrieved.traces) == 2


def test_list_investigations(test_db_path, sample_report):
    """Test listing recent investigations."""
    save_investigation(sample_report, db_path=test_db_path)
    items = list_investigations(limit=10, db_path=test_db_path)

    assert len(items) == 1
    assert items[0]["id"] == "test-uuid-12345"
    assert items[0]["verdict"] == "validated"
    assert items[0]["error_type"] == "KeyError"
