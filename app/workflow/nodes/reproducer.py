"""Deterministic reproducer node.

Executes tests in the isolated Docker sandbox prior to proposing any patch.
Validates that the reported failure actually reproduces in an isolated container.
If the failure cannot be reproduced or Docker is unavailable, flags the run with
trust_level='low' so the user is informed honestly.
No LLM calls are made in this node.
"""

from typing import List, Optional

from app.schemas.context import ContextBundle
from app.schemas.failure import FailureReport
from app.schemas.reproduction import ReproductionResult
from app.services.sandbox import run_command_in_sandbox


def determine_reproduction_command(
    context_bundle: ContextBundle, failure_report: FailureReport
) -> str:
    """Determine the most targeted pytest command to reproduce the failure."""
    # 1. If related tests were identified, run the top related test
    if context_bundle.related_tests:
        target_test = context_bundle.related_tests[0]
        return f"python -m pytest {target_test} -v"

    # 2. If any test file exists in the repo tree, run pytest
    has_tests = any(
        "test" in p.lower() and p.endswith(".py")
        for p in context_bundle.file_tree
    )
    if has_tests:
        return "python -m pytest -v"

    # 3. Fallback: run the failing file directly with python
    return f"python {failure_report.file}"


def reproducer(
    repo_dir: str,
    failure_report: FailureReport,
    context_bundle: ContextBundle,
    custom_docker_client=None,
) -> ReproductionResult:
    """Run failing test or command in the sandbox before proposing any fix.

    Args:
        repo_dir: Absolute path of project repository.
        failure_report: Parsed failure information.
        context_bundle: Context bundle with file tree and related tests.
        custom_docker_client: Optional injected Docker client (for tests).

    Returns:
        ReproductionResult detailing whether the bug reproduced.
    """
    cmd = determine_reproduction_command(context_bundle, failure_report)
    sandbox_res = run_command_in_sandbox(
        project_dir=repo_dir,
        command=cmd,
        custom_docker_client=custom_docker_client,
    )

    # 1. Handle Docker unavailable
    if not sandbox_res.docker_available:
        return ReproductionResult(
            reproduced=False,
            exit_code=sandbox_res.exit_code,
            stdout=sandbox_res.stdout,
            stderr=sandbox_res.stderr,
            command=cmd,
            error=sandbox_res.error or "Docker unavailable. Running analysis-only mode.",
            duration_seconds=sandbox_res.duration_seconds,
            docker_available=False,
            trust_level="low",
        )

    # 2. Check if error reproduced (exit code non-zero and error markers present)
    out_all = f"{sandbox_res.stdout}\n{sandbox_res.stderr}".lower()
    err_type_lower = failure_report.error_type.lower()
    has_error_signature = (
        err_type_lower in out_all
        or "failed" in out_all
        or "error" in out_all
        or "traceback" in out_all
    )

    if sandbox_res.exit_code != 0 and has_error_signature:
        return ReproductionResult(
            reproduced=True,
            exit_code=sandbox_res.exit_code,
            stdout=sandbox_res.stdout,
            stderr=sandbox_res.stderr,
            command=cmd,
            error=None,
            duration_seconds=sandbox_res.duration_seconds,
            docker_available=True,
            trust_level="high",
        )

    # 3. If exit code was 0 or signature wasn't found, mark lower trust
    return ReproductionResult(
        reproduced=False,
        exit_code=sandbox_res.exit_code,
        stdout=sandbox_res.stdout,
        stderr=sandbox_res.stderr,
        command=cmd,
        error="Failure could not be reproduced; test exited cleanly or error signature was absent.",
        duration_seconds=sandbox_res.duration_seconds,
        docker_available=True,
        trust_level="low",
    )
