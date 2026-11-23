"""Schemas for root-cause hypotheses, code evidence items, and ranking."""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    """A mechanically verifiable code excerpt supporting or contradicting a hypothesis."""
    file: str = Field(..., description="File path containing the code evidence")
    line_start: int = Field(..., description="1-indexed starting line number")
    line_end: int = Field(..., description="1-indexed ending line number")
    quote: str = Field(..., description="Exact code quote copied from repository")
    stance: Literal["supports", "contradicts"] = Field(
        ..., description="Whether evidence supports or contradicts the hypothesis"
    )
    reason: str = Field(..., description="One-sentence explanation of relevance")
    verified: bool = Field(default=False, description="True if quote was mechanically verified on disk")


class Hypothesis(BaseModel):
    """A candidate explanation for the root cause of the observed failure."""
    id: int = Field(..., description="Hypothesis identifier (1, 2, or 3)")
    title: str = Field(..., description="Short descriptive title of hypothesis")
    explanation: str = Field(..., description="Detailed technical explanation of root cause")
    evidence: List[EvidenceItem] = Field(default_factory=list, description="Code evidence items")
    score: int = Field(default=0, description="Verified supporting minus verified contradicting items")
    label: Literal["supported", "unsupported"] = Field(
        default="unsupported", description="Label based on verified support count"
    )
    is_upstream: bool = Field(
        default=False, description="True if hypothesis targets cause upstream of crash line"
    )


class RankedHypothesis(Hypothesis):
    """Hypothesis with mechanical ranking metrics."""
    rank: int = Field(default=1, description="Rank position (1 is best supported)")
    verified_support_count: int = Field(default=0, description="Count of verified supporting evidence")
    verified_contradict_count: int = Field(default=0, description="Count of verified contradicting evidence")
    discarded_evidence_count: int = Field(default=0, description="Count of hallucinated/unverified evidence items discarded")


class HypothesesResponse(BaseModel):
    """Structured response required from hypothesis_generator LLM."""
    hypotheses: List[Hypothesis] = Field(
        ..., min_length=3, max_length=3, description="Exactly 3 root cause hypotheses"
    )
