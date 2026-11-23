"""Schemas for 3-phase sandbox validation and final verdicts."""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field

VerdictType = Literal[
    "validated",
    "partially_validated",
    "not_validated",
    "could_not_reproduce",
    "needs_human_decision",
]


class ValidationReport(BaseModel):
    """Report detailing multi-phase mechanical validation in the sandbox."""
    regression_fails_before: bool = Field(
        default=False, description="Whether the regression test failed on the unpatched codebase"
    )
    regression_passes_after: bool = Field(
        default=False, description="Whether the regression test passed after applying the patch"
    )
    existing_suite_result: str = Field(
        default="not_run", description="Status of existing test suite (e.g. 'passed', 'failed', 'not_run')"
    )
    retries_used: int = Field(
        default=0, description="Number of patch repair retries consumed (max 2)"
    )
    duration_seconds: float = Field(
        default=0.0, description="Total seconds elapsed during validation"
    )
    limitations: List[str] = Field(
        default_factory=list, description="Explicit disclosures of validation constraints or limitations"
    )
    verdict: VerdictType = Field(
        default="not_validated", description="Honest mechanical verdict"
    )
    failure_log: Optional[str] = Field(
        default=None, description="Diagnostic test error output if validation failed"
    )
