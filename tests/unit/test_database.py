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


def test_save_report_with_validation_and_patch(test_db_path, sample_report):
    """Test saving a full report with fix proposal, validation result, and hypotheses."""
    from app.schemas.fix import FixProposal
    from app.schemas.validation import ValidationReport
    from app.schemas.hypothesis import Hypothesis, EvidenceItem

    sample_report.hypotheses = [
        Hypothesis(
            id=1,
            title="Fix missing key",
            explanation="Use get() with default",
            evidence=[
                EvidenceItem(
                    file="app/main.py",
                    line_start=42,
                    line_end=42,
                    quote="user_id = data['user_id']",
                    stance="supports",
                    reason="Direct key access",
                    verified=True,
                )
            ],
            score=1,
            label="supported",
            rank=1,
        )
    ]
    sample_report.top_hypothesis = sample_report.hypotheses[0]
    sample_report.fix_proposal = FixProposal(
        status="proposed",
        diff="--- a/app/main.py\n+++ b/app/main.py\n@@ -42,1 +42,1 @@\n-data['user_id']\n+data.get('user_id')\n",
        explanation="Safely look up user_id",
    )
    sample_report.validation_report = ValidationReport(
        regression_fails_before=True,
        regression_passes_after=True,
        existing_suite_result="passed",
        verdict="validated",
        retries_used=0,
        duration_seconds=1.2,
    )

    saved_id = save_investigation(sample_report, db_path=test_db_path)
    assert saved_id == sample_report.investigation_id

    retrieved = get_investigation(saved_id, db_path=test_db_path)
    assert retrieved is not None
    assert retrieved.fix_proposal is not None
    assert retrieved.fix_proposal.explanation == "Safely look up user_id"
    assert retrieved.validation_report is not None
    assert retrieved.validation_report.regression_fails_before is True
    assert retrieved.validation_report.regression_passes_after is True
    assert retrieved.validation_report.reproduced_before is True
    assert retrieved.validation_report.existing_suite_passes_after is True
