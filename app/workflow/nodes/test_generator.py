"""Test generator node (LLM).

Synthesizes a focused pytest regression test designed to:
1. Fail on the unpatched codebase.
2. Pass cleanly once the proposed fix is applied.
Treats all repository code as untrusted passive data.
"""

from typing import Optional, Tuple

from app.schemas.context import ContextBundle
from app.schemas.failure import FailureReport
from app.schemas.fix import FixProposal, RegressionTest
from app.schemas.hypothesis import RankedHypothesis
from app.services.llm_client import LLMClient, LLMUsageTrace

TEST_SYSTEM_INSTRUCTION = """You are BugScope's Regression Test Synthesizer.
Your goal is to write a standalone, deterministic pytest regression test.

CRITICAL REQUIREMENTS:
1. The test MUST FAIL when executed against the original, unpatched codebase.
2. The test MUST PASS when executed against the codebase after applying the proposed fix.
3. Keep the test focused and self-contained. Import necessary functions or classes directly.
4. Do NOT use network calls, sleep commands, or external services.
5. Provide the test code in `test_code`, targeting a path like `tests/test_regression_bugscope.py`.
"""


def test_generator(
    failure_report: FailureReport,
    context_bundle: ContextBundle,
    top_hypothesis: RankedHypothesis,
    fix_proposal: FixProposal,
    llm_client: Optional[LLMClient] = None,
) -> Tuple[RegressionTest, LLMUsageTrace]:
    """Invoke LLM to write a pytest regression test.

    Args:
        failure_report: Structured failure report.
        context_bundle: Sliced repository code snippets.
        top_hypothesis: Top supported hypothesis.
        fix_proposal: Proposed fix patch.
        llm_client: Configured LLM client.

    Returns:
        Tuple of (RegressionTest, LLMUsageTrace).
    """
    client = llm_client or LLMClient()

    prompt_parts = [
        "<untrusted_trace>",
        f"Error: {failure_report.error_type}: {failure_report.message}",
        f"Location: {failure_report.file}:{failure_report.line}",
        "</untrusted_trace>\n",
        "<hypothesis>",
        f"Title: {top_hypothesis.title}",
        f"Explanation: {top_hypothesis.explanation}",
        "</hypothesis>\n",
        "<proposed_fix_diff>",
        fix_proposal.diff,
        "</proposed_fix_diff>\n",
        "<untrusted_code_context>",
    ]

    for snip in context_bundle.snippets:
        prompt_parts.append(
            f"--- {snip.file} (Lines {snip.line_start}-{snip.line_end}) ---\n{snip.code}\n"
        )
    prompt_parts.append("</untrusted_code_context>")
    prompt_parts.append(
        "\nGenerate a pytest regression test that reproduces this exact failure on the original code "
        "and verifies the proposed patch."
    )

    prompt = "\n".join(prompt_parts)

    test_item, trace = client.generate_structured(
        prompt=prompt,
        response_model=RegressionTest,
        system_instruction=TEST_SYSTEM_INSTRUCTION,
    )

    return test_item, trace
