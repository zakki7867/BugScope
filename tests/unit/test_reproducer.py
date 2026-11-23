"""Unit tests for deterministic reproducer node."""

from unittest.mock import MagicMock
import pytest

from app.schemas.context import ContextBundle
from app.schemas.failure import FailureReport
from app.workflow.nodes.reproducer import (
    reproducer,
    determine_reproduction_command,
)


@pytest.fixture
def dummy_context():
    """Dummy ContextBundle fixture."""
    return ContextBundle(
        file_tree=["app/main.py", "tests/test_main.py"],
        failing_file="app/main.py",
        failing_symbol="process_data",
        callers=[],
        callees=[],
        snippets=[],
        related_tests=["tests/test_main.py"],
        total_lines_inspected=50,
    )


@pytest.fixture
def dummy_failure():
    """Dummy FailureReport fixture."""
    return FailureReport(
        error_type="KeyError",
        message="'user_id'",
        file="app/main.py",
        line=10,
        function="process_data",
        category="KeyError",
        severity="medium",
    )


def test_determine_reproduction_command_prefers_related_test(dummy_context, dummy_failure):
    """Test command targeting uses top related test."""
    cmd = determine_reproduction_command(dummy_context, dummy_failure)
    assert cmd == "python -m pytest tests/test_main.py -v"


def test_reproducer_successful_reproduction(tmp_path, dummy_context, dummy_failure):
    """Test when container exit code is non-zero and error signature matches."""
    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_container.wait.return_value = {"StatusCode": 1}
    mock_container.logs.side_effect = [b"FAILED tests/test_main.py - KeyError: 'user_id'", b""]
    mock_client.containers.run.return_value = mock_container

    result = reproducer(
        repo_dir=str(tmp_path),
        failure_report=dummy_failure,
        context_bundle=dummy_context,
        custom_docker_client=mock_client,
    )

    assert result.reproduced is True
    assert result.trust_level == "high"
    assert result.exit_code == 1
    assert "KeyError" in result.stdout


def test_reproducer_failure_not_reproduced(tmp_path, dummy_context, dummy_failure):
    """Test when container test unexpectedly passes (exit code 0)."""
    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_container.wait.return_value = {"StatusCode": 0}
    mock_container.logs.side_effect = [b"PASSED tests/test_main.py", b""]
    mock_client.containers.run.return_value = mock_container

    result = reproducer(
        repo_dir=str(tmp_path),
        failure_report=dummy_failure,
        context_bundle=dummy_context,
        custom_docker_client=mock_client,
    )

    assert result.reproduced is False
    assert result.trust_level == "low"
    assert "could not be reproduced" in result.error


def test_reproducer_docker_unavailable(tmp_path, dummy_context, dummy_failure):
    """Test reproducer handling when Docker daemon is not running."""
    from unittest.mock import patch

    with patch("docker.from_env") as mock_from_env:
        mock_from_env.side_effect = Exception("Docker daemon down")
        result = reproducer(
            repo_dir=str(tmp_path),
            failure_report=dummy_failure,
            context_bundle=dummy_context,
        )

        assert result.reproduced is False
        assert result.docker_available is False
        assert result.trust_level == "low"
        assert "unavailable" in result.error
