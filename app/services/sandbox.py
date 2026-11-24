"""Docker sandbox execution service.

Runs untrusted code strictly inside an ephemeral Docker container:
- Network disabled (--network none).
- 512 MB memory ceiling.
- 1.0 CPU allocation.
- 30-second strict timeout.
- Project mounted read-only (:ro); scratch directory mounted read-write (:rw).
- Refuses host-level execution if Docker is unavailable to prevent host compromise.
"""

import logging
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.config import get_settings

logger = logging.getLogger(__name__)


class SandboxExecutionResult:
    """Raw container execution output."""

    def __init__(
        self,
        exit_code: int,
        stdout: str,
        stderr: str,
        duration_seconds: float,
        docker_available: bool = True,
        error: Optional[str] = None,
    ):
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.duration_seconds = duration_seconds
        self.docker_available = docker_available
        self.error = error


def is_docker_available() -> bool:
    """Check whether the Docker daemon is accessible."""
    try:
        import docker
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


def run_command_in_sandbox(
    project_dir: str,
    command: List[str] | str,
    timeout: Optional[int] = None,
    custom_docker_client=None,
) -> SandboxExecutionResult:
    """Execute a command in an isolated Docker container.

    Args:
        project_dir: Absolute path of project on the host.
        command: Command string or argument list to execute inside container.
        timeout: Seconds before container execution is terminated (default 30s).
        custom_docker_client: Optional injected Docker client (useful for unit testing).

    Returns:
        SandboxExecutionResult with exit code, outputs, and status.
    """
    settings = get_settings()
    timeout_sec = timeout or settings.docker_timeout
    start_time = time.time()

    # Obtain or test Docker client
    client = custom_docker_client
    if client is None:
        try:
            import docker
            client = docker.from_env()
            client.ping()
        except Exception as exc:
            logger.warning("Docker daemon is unreachable: %s", exc)
            return SandboxExecutionResult(
                exit_code=-1,
                stdout="",
                stderr="",
                duration_seconds=0.0,
                docker_available=False,
                error="Docker daemon is unavailable. Untrusted code execution refused for safety.",
            )
    else:
        try:
            client.ping()
        except Exception as exc:
            logger.warning("Injected Docker client failed ping: %s", exc)
            return SandboxExecutionResult(
                exit_code=-1,
                stdout="",
                stderr="",
                duration_seconds=0.0,
                docker_available=False,
                error="Docker daemon is unavailable. Untrusted code execution refused for safety.",
            )

    proj_path = Path(project_dir).resolve()
    # Create isolated scratch directory on host for writable artifacts
    scratch_dir = tempfile.mkdtemp(prefix="bugscope_scratch_")

    try:
        if isinstance(command, list):
            cmd_str = " ".join(command)
        else:
            cmd_str = command

        # Wrapper script executes in scratch directory where project files are mirrored
        container_cmd = [
            "sh",
            "-c",
            f"cp -r /app/. /scratch/ && cd /scratch && {cmd_str}",
        ]

        volumes = {
            str(proj_path): {"bind": "/app", "mode": "ro"},
            scratch_dir: {"bind": "/scratch", "mode": "rw"},
        }

        # Determine container image: use configured sandbox image or fallback
        image_name = settings.docker_image or "python:3.11-slim"
        try:
            client.images.get(image_name)
        except Exception:
            # Fall back to standard python:3.11-slim if custom tag is not built locally
            image_name = "python:3.11-slim"

        # Run hardened ephemeral container
        container = client.containers.run(
            image=image_name,
            command=container_cmd,
            volumes=volumes,
            working_dir="/scratch",
            network_mode="none",
            mem_limit=settings.memory_limit,
            nano_cpus=int(float(settings.cpu_limit) * 1e9),
            pids_limit=settings.pids_limit,
            privileged=False,
            user="1000:1000",
            security_opt=["no-new-privileges:true"],
            cap_drop=["ALL"],
            detach=True,
        )

        try:
            # Wait for container completion with timeout
            result = container.wait(timeout=timeout_sec)
            exit_code = result.get("StatusCode", -1)
            stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
            stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")
            duration = round(time.time() - start_time, 2)
            return SandboxExecutionResult(
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                duration_seconds=duration,
                docker_available=True,
            )
        except Exception as wait_exc:
            # Handle timeout by forcibly killing container
            try:
                container.kill()
            except Exception:
                pass
            duration = round(time.time() - start_time, 2)
            return SandboxExecutionResult(
                exit_code=-1,
                stdout="",
                stderr=f"Execution timed out after {timeout_sec}s",
                duration_seconds=duration,
                docker_available=True,
                error=f"Timeout: {str(wait_exc)}",
            )
        finally:
            try:
                container.remove(v=True, force=True)
            except Exception:
                pass

    finally:
        shutil.rmtree(scratch_dir, ignore_errors=True)
