"""Unit tests for deterministic validator node and 3-phase verification."""

from unittest.mock import MagicMock
import pytest

from app.schemas.fix import FixProposal, RegressionTest
from app.workflow.nodes.validator import validator


@pytest.fixture
def dummy_project(tmp_path):
    """Set up temporary project on disk."""
    app_dir = tmp_path / "app"
    tests_dir = tmp_path / "tests"
    app_dir.mkdir()
    tests_dir.mkdir()

    (app_dir / "calc.py").write_text(
        "def compute(a, b):\n    return a / b\n", encoding="utf-8"
    )
    (tests_dir / "test_calc.py").write_text(
        "from app.calc import compute\ndef test_normal():\n    assert compute(4, 2) == 2\n",
        encoding="utf-8",
    )
    return tmp_path


def test_validator_needs_human_decision_handling(dummy_project):
    """Test validator immediately returns needs_human_decision without sandbox execution."""
    proposal = FixProposal(
        status="needs_human_decision",
        diff="",
        options_if_ambiguous=["Option A", "Option B"],
    )
    reg_test = RegressionTest(test_code="def test_x(): pass")

    report = validator(str(dummy_project), proposal, reg_test)
    assert report.verdict == "needs_human_decision"
    assert "human decision" in report.limitations[0].lower()


def test_validator_three_phases_success(dummy_project):
    """Test 3-phase validation success: phase 1 fails, phase 2 passes, phase 3 passes."""
    mock_client = MagicMock()
    mock_container = MagicMock()

    # Simulate container results:
    # 1. Phase 1 (regression before): exit code 1 (fails as required)
    # 2. Phase 2 (regression after): exit code 0 (passes)
    # 3. Phase 3 (existing suite): exit code 0 (passes)
    mock_container.wait.side_effect = [
        {"StatusCode": 1},
        {"StatusCode": 0},
        {"StatusCode": 0},
    ]
    mock_container.logs.side_effect = [
        b"ZeroDivisionError",
        b"",
        b"1 passed",
        b"",
        b"1 passed",
        b"",
    ]
    mock_client.containers.run.return_value = mock_container

    diff = """
--- a/app/calc.py
+++ b/app/calc.py
@@ -1,2 +1,3 @@
 def compute(a, b):
+    if b == 0: return 0
     return a / b
"""
    proposal = FixProposal(status="proposed", diff=diff)
    reg_test = RegressionTest(
        test_code="from app.calc import compute\ndef test_zero(): assert compute(1, 0) == 0",
        target_path="tests/test_regression.py",
    )

    report = validator(
        str(dummy_project),
        proposal,
        reg_test,
        custom_docker_client=mock_client,
    )

    assert report.verdict == "validated"
    assert report.regression_fails_before is True
    assert report.regression_passes_after is True
    assert report.existing_suite_result == "passed"


def test_validator_phase1_does_not_fail(dummy_project):
    """Test validator rejects if regression test fails to reproduce the error (passes before fix)."""
    mock_client = MagicMock()
    mock_container = MagicMock()

    # Phase 1 passes unexpectedly (StatusCode 0)
    mock_container.wait.return_value = {"StatusCode": 0}
    mock_container.logs.side_effect = [b"1 passed", b""]
    mock_client.containers.run.return_value = mock_container

    proposal = FixProposal(status="proposed", diff="some diff")
    reg_test = RegressionTest(test_code="def test_bogus(): pass")

    report = validator(
        str(dummy_project),
        proposal,
        reg_test,
        custom_docker_client=mock_client,
    )

    assert report.verdict == "not_validated"
    assert report.regression_fails_before is False
    assert "passed on original" in report.limitations[0]
