"""LangGraph State definition for BugScope investigation workflow."""

from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict

from app.schemas.context import ContextBundle
from app.schemas.experiment import ExperimentResult
from app.schemas.failure import FailureReport
from app.schemas.fix import FixProposal, RegressionTest
from app.schemas.hypothesis import Hypothesis, RankedHypothesis
from app.schemas.reproduction import ReproductionResult
from app.schemas.validation import ValidationReport


class BugScopeState(TypedDict, total=False):
    """The central state dictionary passed across all LangGraph nodes."""
    # Inputs
    raw_trace: str
    repo_dir: str

    # Node outputs
    failure_report: Optional[FailureReport]
    context_bundle: Optional[ContextBundle]
    reproduction_result: Optional[ReproductionResult]
    hypotheses: Optional[List[Hypothesis]]
    ranked_hypotheses: Optional[List[RankedHypothesis]]
    experiments: Optional[List[ExperimentResult]]
    top_hypothesis: Optional[RankedHypothesis]
    fix_proposal: Optional[FixProposal]
    regression_test: Optional[RegressionTest]
    validation_report: Optional[ValidationReport]

    # Retry loop telemetry
    retries_used: int
    max_retries: int
    validation_failure_log: Optional[str]

    # Telemetry and traces
    traces: List[Dict[str, Any]]
    verdict: str
