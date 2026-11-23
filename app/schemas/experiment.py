"""Schemas for hypothesis testing through controlled experiments."""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class ExperimentPlan(BaseModel):
    """Plan for a controlled experiment to test a specific root-cause hypothesis."""
    hypothesis_id: int = Field(..., description="Target hypothesis identifier (1, 2, or 3)")
    experiment_type: Literal[
        "assertion_check",
        "call_flow_check",
        "reproduction_test",
        "variable_inspection",
        "environment_probe",
    ] = Field(default="reproduction_test", description="Methodology of the experiment")
    code_change: Optional[str] = Field(
        default=None, description="Temporary probe, assertion, or logging patch applied for test"
    )
    command: str = Field(
        default="pytest", description="Sandbox command to execute"
    )
    expected_outcome: str = Field(
        ..., description="Expected observation if the hypothesis is true"
    )


class ExperimentResult(BaseModel):
    """Observed result and conclusion of a controlled experiment."""
    hypothesis_id: int = Field(..., description="Target hypothesis identifier")
    experiment_type: str = Field(default="reproduction_test")
    command: str = Field(...)
    exit_code: int = Field(default=0)
    stdout: str = Field(default="")
    stderr: str = Field(default="")
    success: bool = Field(default=False)
    conclusion: Literal["confirmed", "refuted", "inconclusive"] = Field(
        default="inconclusive", description="Empirical verdict on the hypothesis"
    )
    notes: Optional[str] = Field(default=None)
