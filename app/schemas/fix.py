"""Schemas for minimal fix proposals and regression test synthesis."""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class FixProposal(BaseModel):
    """Minimal patch proposal with behavioral assumptions and side-effect analysis."""
    status: Literal["proposed", "needs_human_decision"] = Field(
        ..., description="'proposed' if fix was synthesized, or 'needs_human_decision' if ambiguous"
    )
    diff: str = Field(
        default="", description="Minimal unified diff patch relative to repo root"
    )
    assumptions: List[str] = Field(
        default_factory=list, description="Explicit assumptions made about intended behavior"
    )
    side_effects: List[str] = Field(
        default_factory=list, description="Potential side effects or risks of this patch"
    )
    options_if_ambiguous: Optional[List[str]] = Field(
        default=None, description="Options for human decision if intended behavior is ambiguous"
    )


class RegressionTest(BaseModel):
    """Focused pytest regression test that reproduces the failure and guards against regression."""
    test_code: str = Field(
        ..., description="Executable Python pytest code defining test function"
    )
    target_path: str = Field(
        default="tests/test_regression_bugscope.py",
        description="Path where regression test should be placed",
    )
    description: str = Field(
        default="", description="Description of the failure mode this test guards against"
    )
