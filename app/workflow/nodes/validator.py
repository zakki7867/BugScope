"""Deterministic validator node.

Performs 3-phase verification in the isolated sandbox:
1. Phase 1: Run regression test on original unpatched code (MUST FAIL).
2. Phase 2: Apply unified diff to temporary clone, run regression test (MUST PASS).
3. Phase 3: Run full existing test suite on patched copy (MUST HAVE ZERO NEW FAILURES).

If validation fails and retries < 2, sets failure_log to enable patch repair.
No LLM calls are made in this node.
"""

import shutil
import tempfile
import time
from pathlib import Path
from typing import Optional, Tuple

from app.schemas.fix import FixProposal, RegressionTest
from app.schemas.validation import ValidationReport, VerdictType
from app.services.patcher import PatchError, apply_patch_to_directory
from app.services.sandbox import run_command_in_sandbox


def validator(
    repo_dir: str,
    fix_proposal: FixProposal,
    regression_test: RegressionTest,
    current_retries: int = 0,
    max_retries: int = 2,
    custom_docker_client=None,
) -> ValidationReport:
    """Execute 3-phase sandbox validation of proposed patch and regression test.

    Args:
        repo_dir: Absolute path of repository on host.
        fix_proposal: Proposed unified diff patch.
        regression_test: Synthesized pytest regression test.
        current_retries: Number of retries already used.
        max_retries: Maximum permitted retries (default 2).
        custom_docker_client: Optional injected Docker client (for tests).

    Returns:
        ValidationReport containing mechanical findings and verdict.
    """
    start_time = time.time()

    # 1. Check for ambiguous status
    if fix_proposal.status == "needs_human_decision":
        return ValidationReport(
            regression_fails_before=False,
            regression_passes_after=False,
            existing_suite_result="not_run",
            retries_used=current_retries,
            duration_seconds=round(time.time() - start_time, 2),
            limitations=["Intended behavior requires human decision; automated patching skipped."],
            verdict="needs_human_decision",
            failure_log=None,
        )

    # 2. Check for empty diff
    if not fix_proposal.diff.strip():
        return ValidationReport(
            regression_fails_before=False,
            regression_passes_after=False,
            existing_suite_result="not_run",
            retries_used=current_retries,
            duration_seconds=round(time.time() - start_time, 2),
            limitations=["Empty diff provided; patch cannot be validated."],
            verdict="not_validated",
            failure_log="Empty diff provided.",
        )

    orig_path = Path(repo_dir).resolve()

    # Setup isolated scratch directories
    work_dir_unpatched = tempfile.mkdtemp(prefix="bugscope_val_unpatched_")
    work_dir_patched = tempfile.mkdtemp(prefix="bugscope_val_patched_")

    try:
        # Mirror repository files to work directories
        shutil.copytree(orig_path, work_dir_unpatched, dirs_exist_ok=True)
        shutil.copytree(orig_path, work_dir_patched, dirs_exist_ok=True)

        # Write regression test file into unpatched clone
        target_rel = regression_test.target_path.replace("\\", "/").strip().lstrip("/")
        test_file_unpatched = Path(work_dir_unpatched) / target_rel
        test_file_unpatched.parent.mkdir(parents=True, exist_ok=True)
        test_file_unpatched.write_text(regression_test.test_code, encoding="utf-8")

        test_cmd = f"python -m pytest {target_rel} -v"

        # -------------------------------------------------------------
        # Phase 1: Run regression test on unpatched code (MUST FAIL)
        # -------------------------------------------------------------
        res_phase1 = run_command_in_sandbox(
            project_dir=work_dir_unpatched,
            command=test_cmd,
            custom_docker_client=custom_docker_client,
        )

        if not res_phase1.docker_available:
            return ValidationReport(
                regression_fails_before=False,
                regression_passes_after=False,
                existing_suite_result="not_run",
                retries_used=current_retries,
                duration_seconds=round(time.time() - start_time, 2),
                limitations=["Docker daemon unavailable. Sandbox execution refused for host security."],
                verdict="sandbox_unavailable",
                failure_log=res_phase1.error or "Sandbox unavailable.",
            )

        # Must exit with non-zero status to prove failure
        regression_fails_before = res_phase1.exit_code != 0

        if not regression_fails_before:
            # Test did not fail on original code!
            return ValidationReport(
                regression_fails_before=False,
                regression_passes_after=False,
                existing_suite_result="not_run",
                retries_used=current_retries,
                duration_seconds=round(time.time() - start_time, 2),
                limitations=["Synthesized regression test passed on original unpatched code."],
                verdict="not_validated",
                failure_log=f"Regression test did not reproduce failure:\n{res_phase1.stdout}\n{res_phase1.stderr}",
            )

        # -------------------------------------------------------------
        # Phase 2: Apply patch to patched clone and run regression test (MUST PASS)
        # -------------------------------------------------------------
        try:
            apply_patch_to_directory(work_dir_patched, fix_proposal.diff)
        except PatchError as p_err:
            return ValidationReport(
                regression_fails_before=True,
                regression_passes_after=False,
                existing_suite_result="not_run",
                retries_used=current_retries,
                duration_seconds=round(time.time() - start_time, 2),
                limitations=[f"Failed to apply patch diff cleanly: {str(p_err)}"],
                verdict="not_validated",
                failure_log=f"Patch application failed: {str(p_err)}",
            )

        # Write regression test into patched clone
        test_file_patched = Path(work_dir_patched) / target_rel
        test_file_patched.parent.mkdir(parents=True, exist_ok=True)
        test_file_patched.write_text(regression_test.test_code, encoding="utf-8")

        res_phase2 = run_command_in_sandbox(
            project_dir=work_dir_patched,
            command=test_cmd,
            custom_docker_client=custom_docker_client,
        )

        regression_passes_after = res_phase2.exit_code == 0

        if not regression_passes_after:
            return ValidationReport(
                regression_fails_before=True,
                regression_passes_after=False,
                existing_suite_result="not_run",
                retries_used=current_retries,
                duration_seconds=round(time.time() - start_time, 2),
                limitations=["Regression test still fails after applying proposed fix."],
                verdict="not_validated",
                failure_log=f"Post-patch regression test failure:\n{res_phase2.stdout}\n{res_phase2.stderr}",
            )

        # -------------------------------------------------------------
        # Phase 3: Run existing test suite on patched copy (NO REGRESSIONS)
        # -------------------------------------------------------------
        # Remove the new regression test temporarily to isolate existing suite
        try:
            test_file_patched.unlink(missing_ok=True)
        except Exception:
            pass

        suite_cmd = "python -m pytest -v"
        res_phase3 = run_command_in_sandbox(
            project_dir=work_dir_patched,
            command=suite_cmd,
            custom_docker_client=custom_docker_client,
        )

        existing_suite_passed = res_phase3.exit_code == 0
        existing_result_str = "passed" if existing_suite_passed else "failed"

        elapsed = round(time.time() - start_time, 2)

        if regression_fails_before and regression_passes_after and existing_suite_passed:
            return ValidationReport(
                regression_fails_before=True,
                regression_passes_after=True,
                existing_suite_result="passed",
                retries_used=current_retries,
                duration_seconds=elapsed,
                limitations=[],
                verdict="validated",
                failure_log=None,
            )
        else:
            return ValidationReport(
                regression_fails_before=regression_fails_before,
                regression_passes_after=regression_passes_after,
                existing_suite_result=existing_result_str,
                retries_used=current_retries,
                duration_seconds=elapsed,
                limitations=["Existing test suite failed after applying proposed fix."],
                verdict="not_validated",
                failure_log=f"Existing suite regressions detected:\n{res_phase3.stdout}\n{res_phase3.stderr}",
            )

    finally:
        shutil.rmtree(work_dir_unpatched, ignore_errors=True)
        shutil.rmtree(work_dir_patched, ignore_errors=True)
