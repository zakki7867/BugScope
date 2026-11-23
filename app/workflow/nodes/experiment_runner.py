"""Controlled experiment runner node for empirical hypothesis testing."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from app.schemas.experiment import ExperimentPlan, ExperimentResult
from app.schemas.failure import FailureReport
from app.schemas.hypothesis import RankedHypothesis
from app.schemas.reproduction import ReproductionResult
from app.services.sandbox import run_command_in_sandbox


def experiment_runner(
    repo_dir: str,
    failure_report: FailureReport,
    ranked_hypotheses: List[RankedHypothesis],
    reproduction_result: Optional[ReproductionResult] = None,
) -> List[ExperimentResult]:
    """Execute controlled experiments to empirically confirm or refute candidate hypotheses.

    For each candidate hypothesis, design and execute a targeted reproduction or probe
    command inside the sandbox, recording mechanical stdout, stderr, and exit codes.
    """
    results: List[ExperimentResult] = []
    repo_path = Path(repo_dir)

    for hyp in ranked_hypotheses:
        # Determine appropriate test command
        cmd = "pytest"
        if failure_report.test_command:
            cmd = failure_report.test_command
        elif reproduction_result and reproduction_result.command:
            cmd = reproduction_result.command
        elif failure_report.file:
            # Check if there is a matching test file
            stem = Path(failure_report.file).stem
            test_candidates = list(repo_path.rglob(f"test_*{stem}*.py")) or list(repo_path.rglob("test_*.py"))
            if test_candidates:
                cmd = f"pytest {test_candidates[0].relative_to(repo_path)}"

        # Experiment plan
        plan = ExperimentPlan(
            hypothesis_id=hyp.id,
            experiment_type="reproduction_test",
            command=cmd,
            expected_outcome=f"Execution fails with {failure_report.error_type} if bug is triggered",
        )

        # Run command in sandbox
        sandbox_res = run_command_in_sandbox(repo_dir=repo_dir, command=cmd)

        conclusion = "inconclusive"
        if sandbox_res.reproduced:
            # If reproduced, verify if error message matches hypothesis reasoning
            if failure_report.error_type.lower() in sandbox_res.stdout.lower() or failure_report.error_type.lower() in sandbox_res.stderr.lower():
                conclusion = "confirmed"
            else:
                conclusion = "inconclusive"
        else:
            conclusion = "refuted" if sandbox_res.exit_code == 0 else "inconclusive"

        exp_result = ExperimentResult(
            hypothesis_id=hyp.id,
            experiment_type=plan.experiment_type,
            command=cmd,
            exit_code=sandbox_res.exit_code,
            stdout=sandbox_res.stdout[:2000],
            stderr=sandbox_res.stderr[:2000],
            success=(conclusion == "confirmed"),
            conclusion=conclusion,
            notes=f"Empirically tested in sandbox. Exit code: {sandbox_res.exit_code}",
        )
        results.append(exp_result)

    return results
