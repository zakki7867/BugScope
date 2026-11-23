"""Schemas for final investigation reports and per-node telemetry traces."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.context import ContextBundle
from app.schemas.experiment import ExperimentResult
from app.schemas.failure import FailureReport
from app.schemas.fix import FixProposal, RegressionTest
from app.schemas.hypothesis import RankedHypothesis
from app.schemas.reproduction import ReproductionResult
from app.schemas.validation import ValidationReport, VerdictType


class TraceEntry(BaseModel):
    """Telemetry record for a single workflow node execution."""
    node: str = Field(..., description="Name of the executed workflow node")
    input_summary: str = Field(default="", description="Summary of inputs received")
    output_summary: str = Field(default="", description="Summary of outputs produced")
    duration_ms: float = Field(default=0.0, description="Execution time in milliseconds")
    tokens_in: int = Field(default=0, description="Prompt tokens consumed")
    tokens_out: int = Field(default=0, description="Completion tokens consumed")
    cost_usd: float = Field(default=0.0, description="Estimated cost in USD")


class InvestigationReport(BaseModel):
    """Master report summarizing an evidence-checked debugging investigation."""
    investigation_id: str = Field(..., description="Unique investigation UUID")
    created_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z",
        description="ISO timestamp of investigation creation",
    )
    failure_report: FailureReport = Field(..., description="Parsed initial failure details")
    context_bundle: Optional[ContextBundle] = Field(
        default=None, description="Repository context sliced for investigation"
    )
    reproduction_result: Optional[ReproductionResult] = Field(
        default=None, description="Pre-fix baseline reproduction results"
    )
    hypotheses: List[RankedHypothesis] = Field(
        default_factory=list, description="All candidate hypotheses ranked mechanically"
    )
    experiments: List[ExperimentResult] = Field(
        default_factory=list, description="Controlled experiment executions"
    )
    top_hypothesis: Optional[RankedHypothesis] = Field(
        default=None, description="Top-ranked supported hypothesis (if any)"
    )
    fix_proposal: Optional[FixProposal] = Field(
        default=None, description="Proposed patch or human decision options"
    )
    regression_test: Optional[RegressionTest] = Field(
        default=None, description="Synthesized regression test"
    )
    validation_report: Optional[ValidationReport] = Field(
        default=None, description="3-phase mechanical sandbox validation results"
    )
    traces: List[TraceEntry] = Field(
        default_factory=list, description="Per-node execution traces"
    )
    verdict: VerdictType = Field(
        default="not_validated", description="Final honest verdict"
    )
    total_duration_seconds: float = Field(
        default=0.0, description="Total wall-clock duration of investigation in seconds"
    )
    total_cost_usd: float = Field(
        default=0.0, description="Total cumulative LLM cost in USD"
    )
    total_tokens_in: int = Field(default=0, description="Total prompt tokens")
    total_tokens_out: int = Field(default=0, description="Total completion tokens")
