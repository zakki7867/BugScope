"""Schemas for 3-phase sandbox validation and final verdicts."""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field, computed_field

VerdictType = Literal[
    "validated",
    "partially_validated",
    "not_validated",
    "could_not_reproduce",
    "needs_human_decision",
    "sandbox_unavailable",
    "analysis_only",
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

    # Computed fields for frontend API serialization and backwards compatibility
    @computed_field
    @property
    def reproduced_before(self) -> bool:
        """Alias for regression_fails_before."""
        return self.regression_fails_before

    @computed_field
    @property
    def patch_applies(self) -> bool:
        """Whether the patch was cleanly applied and tested."""
        return self.regression_passes_after or (self.verdict == "validated")

    @computed_field
    @property
    def existing_suite_passes_after(self) -> bool:
        """Whether the existing suite passed without new regressions."""
        return self.existing_suite_result == "passed"

    @computed_field
    @property
    def retries_attempted(self) -> int:
        """Alias for retries_used."""
        return self.retries_used

