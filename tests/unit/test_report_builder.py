"""Unit tests for deterministic report_builder node."""

import pytest

from app.schemas.failure import FailureReport
from app.schemas.validation import ValidationReport
from app.workflow.nodes.report_builder import report_builder
from app.workflow.state import BugScopeState


def test_report_builder_telemetry_aggregation(tmp_path):
    """Test report_builder sums duration, tokens, and cost across traces."""
    db_file = str(tmp_path / "rep_test.db")

    state: BugScopeState = {
        "raw_trace": "KeyError: 'foo'",
        "repo_dir": str(tmp_path),
        "failure_report": FailureReport(
            error_type="KeyError",
            message="'foo'",
            file="app.py",
            line=5,
            function="foo_func",
            category="KeyError",
            severity="low",
        ),
        "validation_report": ValidationReport(
            regression_fails_before=True,
            regression_passes_after=True,
            existing_suite_result="passed",
            verdict="validated",
        ),
        "traces": [
            {
                "node": "failure_analyzer",
                "duration_ms": 100.0,
                "tokens_in": 50,
                "tokens_out": 20,
                "cost_usd": 0.00001,
            },
            {
                "node": "fix_generator",
                "duration_ms": 400.0,
                "tokens_in": 150,
                "tokens_out": 80,
                "cost_usd": 0.00004,
            },
        ],
    }

    result = report_builder(state, db_path=db_file)
    report = result["investigation_report"]

    assert report.verdict == "validated"
    assert report.total_tokens_in == 200
    assert report.total_tokens_out == 100
    assert report.total_duration_seconds == 0.50
    assert report.total_cost_usd == 0.00005
    assert len(report.traces) == 2
