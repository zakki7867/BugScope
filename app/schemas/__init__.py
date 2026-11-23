"""Pydantic schemas for data contracts across workflow nodes."""

from app.schemas.failure import FailureCategory, CallFrame, FailureReport
from app.schemas.context import Snippet, ContextBundle
from app.schemas.reproduction import ReproductionResult
from app.schemas.hypothesis import (
    EvidenceItem,
    Hypothesis,
    RankedHypothesis,
    HypothesesResponse,
)
from app.schemas.fix import FixProposal, RegressionTest
from app.schemas.validation import ValidationReport, VerdictType

__all__ = [
    "FailureCategory",
    "CallFrame",
    "FailureReport",
    "Snippet",
    "ContextBundle",
    "ReproductionResult",
    "EvidenceItem",
    "Hypothesis",
    "RankedHypothesis",
    "HypothesesResponse",
    "FixProposal",
    "RegressionTest",
    "ValidationReport",
    "VerdictType",
]
