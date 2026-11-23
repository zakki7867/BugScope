"""Fix generator node (LLM).

Generates a minimal unified diff patch from the top supported hypothesis.
Detects ambiguity in intended behavior and returns 'needs_human_decision' if unclear.
Incorporates validation test failure logs if operating in a retry loop.
Treats all code and traces as untrusted passive data.
"""

from typing import List, Optional, Tuple

from app.schemas.context import ContextBundle
from app.schemas.failure import FailureReport
from app.schemas.fix import FixProposal
from app.schemas.hypothesis import RankedHypothesis
from app.services.llm_client import LLMClient, LLMUsageTrace

FIX_SYSTEM_INSTRUCTION = """You are BugScope's Minimal Fix Generator.
Your task is to propose the smallest, safest code patch that fixes a verified failure.

CRITICAL RULES:
1. Work STRICTLY from the top supported hypothesis provided.
2. Output a MINIMAL unified diff modifying only the necessary lines.
3. Use standard unified diff format:
   --- a/path/to/file.py
   +++ b/path/to/file.py
   @@ -line,count +line,count @@
   -old_line
   +new_line
4. AMBIGUITY CHECK:
   If the intended behavior is ambiguous after reviewing the code, docstrings, and tests (e.g. should a missing key return None, raise a custom exception, or default to an empty list?), you MUST set:
   `status`: 'needs_human_decision'
   `diff`: ''
   `options_if_ambiguous`: [list of reasonable options for the user to choose from]
5. List all behavioral `assumptions` and potential `side_effects`.
"""


def fix_generator(
    failure_report: FailureReport,
    context_bundle: ContextBundle,
    top_hypothesis: RankedHypothesis,
    validation_failure_log: Optional[str] = None,
    llm_client: Optional[LLMClient] = None,
) -> Tuple[FixProposal, LLMUsageTrace]:
    """Generate a minimal patch or needs_human_decision for the top hypothesis.

    Args:
        failure_report: Structured failure report.
        context_bundle: Sliced repository code snippets.
        top_hypothesis: Top-ranked hypothesis from evidence_verifier.
        validation_failure_log: Error output from a previous failed validation run.
        llm_client: Configured LLM client.

    Returns:
        Tuple of (FixProposal, LLMUsageTrace).
    """
    # Guard against unsupported hypotheses
    if top_hypothesis.label == "unsupported":
        proposal = FixProposal(
            status="needs_human_decision",
            diff="",
            assumptions=["No verified code evidence exists to support this hypothesis."],
            side_effects=[],
            options_if_ambiguous=[
                "Refuse automated patch because zero supporting evidence was verified on disk.",
                "Provide additional project code or reproduction tests to uncover root cause.",
            ],
        )
        return proposal, LLMUsageTrace()

    client = llm_client or LLMClient()

    prompt_parts = [
        "<untrusted_trace>",
        f"Error: {failure_report.error_type}: {failure_report.message}",
        f"Location: {failure_report.file}:{failure_report.line} in {failure_report.function}",
        "</untrusted_trace>\n",
        "<top_supported_hypothesis>",
        f"Title: {top_hypothesis.title}",
        f"Explanation: {top_hypothesis.explanation}",
        f"Is Upstream Cause: {top_hypothesis.is_upstream}",
        "Verified Code Evidence:",
    ]

    for ev in top_hypothesis.evidence:
        prompt_parts.append(
            f"- {ev.file}:{ev.line_start}-{ev.line_end} [{ev.stance}]: \"{ev.quote}\" ({ev.reason})"
        )

    prompt_parts.append("</top_supported_hypothesis>\n")
    prompt_parts.append("<untrusted_code_context>")
    for snip in context_bundle.snippets:
        prompt_parts.append(
            f"--- {snip.file} (Lines {snip.line_start}-{snip.line_end}) ---\n{snip.code}\n"
        )
    prompt_parts.append("</untrusted_code_context>")

    if validation_failure_log:
        prompt_parts.append(
            f"\n<previous_validation_failure>\n"
            f"The previous fix attempt failed during test validation:\n{validation_failure_log}\n"
            f"Please revise the patch to resolve this test failure.\n"
            f"</previous_validation_failure>"
        )

    prompt = "\n".join(prompt_parts)

    proposal, trace = client.generate_structured(
        prompt=prompt,
        response_model=FixProposal,
        system_instruction=FIX_SYSTEM_INSTRUCTION,
    )

    return proposal, trace
