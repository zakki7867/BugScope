"""Unit tests for Docker sandbox execution service."""

from unittest.mock import MagicMock, patch
import pytest

from app.services.sandbox import (
    is_docker_available,
    run_command_in_sandbox,
    SandboxExecutionResult,
)


def test_docker_available_when_daemon_responds():
    """Test is_docker_available returns True when docker client pings successfully."""
    with patch("docker.from_env") as mock_from_env:
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_from_env.return_value = mock_client

        assert is_docker_available() is True


def test_docker_unavailable_when_daemon_down():
    """Test is_docker_available returns False when docker client raises exception."""
    with patch("docker.from_env") as mock_from_env:
        mock_from_env.side_effect = Exception("Docker daemon not running")

        assert is_docker_available() is False


def test_run_command_refuses_when_docker_unavailable(tmp_path):
    """Test that command execution is rejected when Docker is unavailable."""
    with patch("docker.from_env") as mock_from_env:
        mock_from_env.side_effect = Exception("Docker unavailable")

        result = run_command_in_sandbox(str(tmp_path), "pytest")
        assert result.docker_available is False
        assert result.exit_code == -1
        assert "refused for safety" in result.error


def test_run_command_with_mock_container(tmp_path):
    """Test container lifecycle (volumes, limits, ro binding) with a mock client."""
    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_container.wait.return_value = {"StatusCode": 0}
    mock_container.logs.side_effect = [b"Test Output", b""]
    mock_client.containers.run.return_value = mock_container

    result = run_command_in_sandbox(
        project_dir=str(tmp_path),
        command="python -m pytest",
        custom_docker_client=mock_client,
    )

    assert result.docker_available is True
    assert result.exit_code == 0
    assert result.stdout == "Test Output"

    # Verify containers.run parameters
    mock_client.containers.run.assert_called_once()
    _, kwargs = mock_client.containers.run.call_args
    assert kwargs["network_mode"] == "none"
    assert kwargs["mem_limit"] == "512m"
    assert kwargs["image"] == "python:3.11-slim"
    # Verify original project is mounted read-only
    volumes = kwargs["volumes"]
    assert str(tmp_path) in volumes
    assert volumes[str(tmp_path)]["mode"] == "ro"
