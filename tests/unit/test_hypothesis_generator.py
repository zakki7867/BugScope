"""Unit tests for hypothesis_generator prompt construction and structured output."""

from unittest.mock import MagicMock
import pytest

from app.schemas.context import ContextBundle, Snippet
from app.schemas.failure import FailureReport
from app.schemas.hypothesis import HypothesesResponse, Hypothesis, EvidenceItem
from app.services.llm_client import LLMUsageTrace
from app.workflow.nodes.hypothesis_generator import (
    hypothesis_generator,
    format_context_for_prompt,
)


@pytest.fixture
def mock_llm_response():
    """Mock HypothesesResponse with 3 hypotheses."""
    return HypothesesResponse(
        hypotheses=[
            Hypothesis(
                id=1,
                title="Missing key in dict",
                explanation="Accessing non-existent key user_id raises KeyError",
                evidence=[
                    EvidenceItem(
                        file="app/main.py",
                        line_start=10,
                        line_end=11,
                        quote="return data['user_id']",
                        stance="supports",
                        reason="Directly indexes dictionary with user_id key",
                    )
                ],
                is_upstream=False,
            ),
            Hypothesis(
                id=2,
                title="Empty dictionary input",
                explanation="Dictionary was initialized as empty dict",
                evidence=[],
                is_upstream=False,
            ),
            Hypothesis(
                id=3,
                title="Upstream parser omitted user_id field",
                explanation="Upstream JSON parser failed to populate user_id",
                evidence=[],
                is_upstream=True,
            ),
        ]
    )


def test_format_context_for_prompt_tags():
    """Test that context formatting encloses repo data in untrusted delimiters."""
    failure = FailureReport(
        error_type="KeyError",
        message="'user_id'",
        file="app/main.py",
        line=10,
        function="get_user",
        category="KeyError",
        severity="medium",
    )
    context = ContextBundle(
        file_tree=["app/main.py"],
        failing_file="app/main.py",
        failing_symbol="get_user",
        callers=["api/routes.py::handler"],
        callees=[],
        snippets=[
            Snippet(
                file="app/main.py",
                line_start=8,
                line_end=12,
                code="0010 | return data['user_id']",
                is_target=True,
            )
        ],
        related_tests=["tests/test_user.py"],
        total_lines_inspected=20,
    )

    prompt = format_context_for_prompt(failure, context)
    assert "<untrusted_trace>" in prompt
    assert "</untrusted_trace>" in prompt
    assert "<untrusted_code_context>" in prompt
    assert "</untrusted_code_context>" in prompt
    assert "return data['user_id']" in prompt


def test_hypothesis_generator_enforces_upstream_constraint(mock_llm_response):
    """Test that hypothesis_generator ensures at least one hypothesis has is_upstream=True."""
    mock_client = MagicMock()
    trace = LLMUsageTrace(tokens_in=100, tokens_out=50, duration_ms=250.0, cost_usd=0.0001)
    mock_client.generate_structured.return_value = (mock_llm_response, trace)

    failure = FailureReport(
        error_type="KeyError",
        message="'user_id'",
        file="app/main.py",
        line=10,
        function="get_user",
        category="KeyError",
        severity="medium",
    )
    context = ContextBundle(failing_file="app/main.py")

    hypotheses, out_trace = hypothesis_generator(failure, context, llm_client=mock_client)

    assert len(hypotheses) == 3
    assert any(h.is_upstream for h in hypotheses)
    assert out_trace.tokens_in == 100
