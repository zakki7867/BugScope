"""Unit tests for fix_generator node."""

from unittest.mock import MagicMock
import pytest

from app.schemas.context import ContextBundle
from app.schemas.failure import FailureReport
from app.schemas.fix import FixProposal
from app.schemas.hypothesis import RankedHypothesis, EvidenceItem
from app.services.llm_client import LLMUsageTrace
from app.workflow.nodes.fix_generator import fix_generator


def test_fix_generator_needs_human_decision_when_unsupported():
    """Test that an unsupported top hypothesis automatically returns needs_human_decision."""
    failure = FailureReport(
        error_type="KeyError",
        message="'x'",
        file="app/main.py",
        line=10,
        function="f",
        category="KeyError",
        severity="low",
    )
    context = ContextBundle(failing_file="app/main.py")
    top_hyp = RankedHypothesis(
        id=1,
        title="Hypothesis with zero evidence",
        explanation="Fake explanation",
        evidence=[],
        score=0,
        label="unsupported",
    )

    proposal, trace = fix_generator(failure, context, top_hyp)

    assert proposal.status == "needs_human_decision"
    assert proposal.diff == ""
    assert len(proposal.options_if_ambiguous) >= 1
    assert trace.tokens_in == 0


def test_fix_generator_success_with_mock():
    """Test generating a proposed fix diff with a mock LLM."""
    mock_client = MagicMock()
    mock_proposal = FixProposal(
        status="proposed",
        diff="--- a/app/main.py\n+++ b/app/main.py\n@@ -10,1 +10,1 @@\n-data['x']\n+data.get('x', 0)",
        assumptions=["Missing key should default to 0"],
        side_effects=[],
    )
    mock_trace = LLMUsageTrace(tokens_in=150, tokens_out=80, duration_ms=300.0, cost_usd=0.0001)
    mock_client.generate_structured.return_value = (mock_proposal, mock_trace)

    failure = FailureReport(
        error_type="KeyError",
        message="'x'",
        file="app/main.py",
        line=10,
        function="f",
        category="KeyError",
        severity="low",
    )
    context = ContextBundle(failing_file="app/main.py")
    top_hyp = RankedHypothesis(
        id=1,
        title="Missing key",
        explanation="Accessing x",
        evidence=[
            EvidenceItem(
                file="app/main.py",
                line_start=10,
                line_end=11,
                quote="data['x']",
                stance="supports",
                reason="Indexes key x",
                verified=True,
            )
        ],
        score=1,
        label="supported",
    )

    proposal, trace = fix_generator(
        failure,
        context,
        top_hyp,
        validation_failure_log="AssertionError on test 1",
        llm_client=mock_client,
    )

    assert proposal.status == "proposed"
    assert "data.get('x', 0)" in proposal.diff
    assert trace.tokens_in == 150
