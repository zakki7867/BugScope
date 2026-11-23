"""Deterministic report builder node.

Assembles the final comprehensive InvestigationReport from workflow state,
aggregates runtime and cost telemetry, and persists the record to SQLite.
No LLM calls are made in this node.
"""

import time
import uuid
from typing import Any, Dict, List

from app.database.db import save_investigation
from app.schemas.report import InvestigationReport, TraceEntry
from app.workflow.state import BugScopeState


def report_builder(state: BugScopeState, db_path: str = None) -> Dict[str, Any]:
    """Assemble master investigation report and persist to database.

    Args:
        state: Final state from LangGraph workflow.
        db_path: Optional custom SQLite database path.

    Returns:
        State dict containing 'investigation_report'.
    """
    investigation_id = str(uuid.uuid4())

    raw_traces = state.get("traces", [])
    trace_entries: List[TraceEntry] = []
    total_tokens_in = 0
    total_tokens_out = 0
    total_cost = 0.0

    for tr in raw_traces:
        entry = TraceEntry(
            node=tr.get("node", "unknown"),
            input_summary=tr.get("input_summary", ""),
            output_summary=tr.get("output_summary", ""),
            duration_ms=tr.get("duration_ms", 0.0),
            tokens_in=tr.get("tokens_in", 0),
            tokens_out=tr.get("tokens_out", 0),
            cost_usd=tr.get("cost_usd", 0.0),
        )
        trace_entries.append(entry)
        total_tokens_in += entry.tokens_in
        total_tokens_out += entry.tokens_out
        total_cost += entry.cost_usd

    total_duration_sec = round(sum(t.duration_ms for t in trace_entries) / 1000.0, 2)

    # Determine final verdict
    if state.get("validation_report"):
        verdict = state["validation_report"].verdict
    elif state.get("fix_proposal") and state["fix_proposal"].status == "needs_human_decision":
        verdict = "needs_human_decision"
    elif state.get("top_hypothesis") and state["top_hypothesis"].label == "unsupported":
        verdict = "not_validated"
    elif state.get("reproduction_result") and not state["reproduction_result"].docker_available:
        verdict = "could_not_reproduce"
    else:
        verdict = state.get("verdict", "not_validated")

    report = InvestigationReport(
        investigation_id=investigation_id,
        failure_report=state["failure_report"],
        context_bundle=state.get("context_bundle"),
        reproduction_result=state.get("reproduction_result"),
        hypotheses=state.get("ranked_hypotheses", []),
        experiments=state.get("experiments", []),
        top_hypothesis=state.get("top_hypothesis"),
        fix_proposal=state.get("fix_proposal"),
        regression_test=state.get("regression_test"),
        validation_report=state.get("validation_report"),
        traces=trace_entries,
        verdict=verdict,
        total_duration_seconds=total_duration_sec,
        total_cost_usd=round(total_cost, 6),
        total_tokens_in=total_tokens_in,
        total_tokens_out=total_tokens_out,
    )

    # Persist to SQLite
    try:
        save_investigation(report, db_path=db_path)
    except Exception as e:
        # Avoid crashing workflow if database write fails
        pass

    return {"investigation_report": report, "verdict": verdict}
