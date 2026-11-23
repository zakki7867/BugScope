"""LangGraph workflow graph assembly for BugScope.

Orchestrates deterministic nodes and LLM nodes into an evidence-checked state machine
with mechanical retry edges and verdict routing.
"""

import time
from typing import Any, Dict, Literal
from langgraph.graph import END, StateGraph

from app.schemas.validation import VerdictType
from app.workflow.nodes.evidence_verifier import evidence_verifier
from app.workflow.nodes.failure_analyzer import failure_analyzer
from app.workflow.nodes.fix_generator import fix_generator
from app.workflow.nodes.hypothesis_generator import hypothesis_generator
from app.workflow.nodes.repo_investigator import repo_investigator
from app.workflow.nodes.reproducer import reproducer
from app.workflow.nodes.test_generator import test_generator
from app.workflow.nodes.validator import validator
from app.workflow.state import BugScopeState


def node_failure_analyzer(state: BugScopeState) -> Dict[str, Any]:
    """Node 1: Deterministic failure analyzer."""
    start_t = time.time()
    report = failure_analyzer(state["raw_trace"])
    elapsed_ms = round((time.time() - start_t) * 1000, 2)

    trace_entry = {
        "node": "failure_analyzer",
        "input_summary": f"Trace of length {len(state['raw_trace'])} chars",
        "output_summary": f"{report.error_type} in {report.file}:{report.line}",
        "duration_ms": elapsed_ms,
        "tokens_in": 0,
        "tokens_out": 0,
        "cost_usd": 0.0,
    }
    traces = state.get("traces", []) + [trace_entry]
    return {"failure_report": report, "traces": traces}


def node_repo_investigator(state: BugScopeState) -> Dict[str, Any]:
    """Node 2: Deterministic repository investigator."""
    start_t = time.time()
    bundle = repo_investigator(
        repo_dir=state["repo_dir"],
        failure_report=state["failure_report"],
    )
    elapsed_ms = round((time.time() - start_t) * 1000, 2)

    trace_entry = {
        "node": "repo_investigator",
        "input_summary": f"Repo {state['repo_dir']}, failing file {state['failure_report'].file}",
        "output_summary": f"Tree {len(bundle.file_tree)} files, {len(bundle.snippets)} snippets, {len(bundle.related_tests)} tests",
        "duration_ms": elapsed_ms,
        "tokens_in": 0,
        "tokens_out": 0,
        "cost_usd": 0.0,
    }
    traces = state.get("traces", []) + [trace_entry]
    return {"context_bundle": bundle, "traces": traces}


def node_reproducer(state: BugScopeState) -> Dict[str, Any]:
    """Node 3: Deterministic sandbox reproducer."""
    start_t = time.time()
    repro = reproducer(
        repo_dir=state["repo_dir"],
        failure_report=state["failure_report"],
        context_bundle=state["context_bundle"],
    )
    elapsed_ms = round((time.time() - start_t) * 1000, 2)

    trace_entry = {
        "node": "reproducer",
        "input_summary": f"Command: {repro.command}",
        "output_summary": f"Reproduced: {repro.reproduced}, trust: {repro.trust_level}",
        "duration_ms": elapsed_ms,
        "tokens_in": 0,
        "tokens_out": 0,
        "cost_usd": 0.0,
    }
    traces = state.get("traces", []) + [trace_entry]
    return {"reproduction_result": repro, "traces": traces}


def node_hypothesis_generator(state: BugScopeState) -> Dict[str, Any]:
    """Node 4: LLM hypothesis generator."""
    start_t = time.time()
    hypotheses, usage = hypothesis_generator(
        failure_report=state["failure_report"],
        context_bundle=state["context_bundle"],
    )
    elapsed_ms = round((time.time() - start_t) * 1000, 2)

    trace_entry = {
        "node": "hypothesis_generator",
        "input_summary": f"Failure: {state['failure_report'].error_type}",
        "output_summary": f"Generated {len(hypotheses)} hypotheses",
        "duration_ms": elapsed_ms,
        "tokens_in": usage.tokens_in,
        "tokens_out": usage.tokens_out,
        "cost_usd": usage.cost_usd,
    }
    traces = state.get("traces", []) + [trace_entry]
    return {"hypotheses": hypotheses, "traces": traces}


def node_evidence_verifier(state: BugScopeState) -> Dict[str, Any]:
    """Node 5: Deterministic mechanical evidence verifier."""
    start_t = time.time()
    ranked = evidence_verifier(
        repo_dir=state["repo_dir"],
        hypotheses=state["hypotheses"],
    )
    elapsed_ms = round((time.time() - start_t) * 1000, 2)

    top = ranked[0] if ranked else None
    trace_entry = {
        "node": "evidence_verifier",
        "input_summary": f"Verifying {len(state['hypotheses'])} hypotheses",
        "output_summary": f"Top hypothesis #{top.id if top else 'none'} score {top.score if top else 0} ({top.label if top else 'none'})",
        "duration_ms": elapsed_ms,
        "tokens_in": 0,
        "tokens_out": 0,
        "cost_usd": 0.0,
    }
    traces = state.get("traces", []) + [trace_entry]
    return {
        "ranked_hypotheses": ranked,
        "top_hypothesis": top,
        "traces": traces,
    }


def node_fix_generator(state: BugScopeState) -> Dict[str, Any]:
    """Node 6: LLM fix generator."""
    start_t = time.time()
    proposal, usage = fix_generator(
        failure_report=state["failure_report"],
        context_bundle=state["context_bundle"],
        top_hypothesis=state["top_hypothesis"],
        validation_failure_log=state.get("validation_failure_log"),
    )
    elapsed_ms = round((time.time() - start_t) * 1000, 2)

    trace_entry = {
        "node": "fix_generator",
        "input_summary": f"Top hypothesis #{state['top_hypothesis'].id}, retry {state.get('retries_used', 0)}",
        "output_summary": f"Status: {proposal.status}, diff len: {len(proposal.diff)} chars",
        "duration_ms": elapsed_ms,
        "tokens_in": usage.tokens_in,
        "tokens_out": usage.tokens_out,
        "cost_usd": usage.cost_usd,
    }
    traces = state.get("traces", []) + [trace_entry]
    return {"fix_proposal": proposal, "traces": traces}


def node_test_generator(state: BugScopeState) -> Dict[str, Any]:
    """Node 7: LLM test generator."""
    start_t = time.time()
    reg_test, usage = test_generator(
        failure_report=state["failure_report"],
        context_bundle=state["context_bundle"],
        top_hypothesis=state["top_hypothesis"],
        fix_proposal=state["fix_proposal"],
    )
    elapsed_ms = round((time.time() - start_t) * 1000, 2)

    trace_entry = {
        "node": "test_generator",
        "input_summary": f"Proposal status: {state['fix_proposal'].status}",
        "output_summary": f"Test for {reg_test.target_path}",
        "duration_ms": elapsed_ms,
        "tokens_in": usage.tokens_in,
        "tokens_out": usage.tokens_out,
        "cost_usd": usage.cost_usd,
    }
    traces = state.get("traces", []) + [trace_entry]
    return {"regression_test": reg_test, "traces": traces}


def node_validator(state: BugScopeState) -> Dict[str, Any]:
    """Node 8: Deterministic sandbox validator."""
    start_t = time.time()
    current_retries = state.get("retries_used", 0)
    val_report = validator(
        repo_dir=state["repo_dir"],
        fix_proposal=state["fix_proposal"],
        regression_test=state["regression_test"],
        current_retries=current_retries,
        max_retries=state.get("max_retries", 2),
    )
    elapsed_ms = round((time.time() - start_t) * 1000, 2)

    trace_entry = {
        "node": "validator",
        "input_summary": f"Validating patch attempt {current_retries + 1}",
        "output_summary": f"Verdict: {val_report.verdict}, regression pass: {val_report.regression_passes_after}",
        "duration_ms": elapsed_ms,
        "tokens_in": 0,
        "tokens_out": 0,
        "cost_usd": 0.0,
    }
    traces = state.get("traces", []) + [trace_entry]
    return {
        "validation_report": val_report,
        "validation_failure_log": val_report.failure_log,
        "verdict": val_report.verdict,
        "traces": traces,
    }


# Router conditionals
def route_after_evidence(state: BugScopeState) -> Literal["fix_generator", "__end__"]:
    """Route after evidence verification."""
    top = state.get("top_hypothesis")
    if not top or top.label == "unsupported":
        return "__end__"
    return "fix_generator"


def route_after_fix(state: BugScopeState) -> Literal["test_generator", "__end__"]:
    """Route after fix proposal."""
    proposal = state.get("fix_proposal")
    if not proposal or proposal.status == "needs_human_decision":
        return "__end__"
    return "test_generator"


def route_after_validator(state: BugScopeState) -> Literal["fix_generator", "__end__"]:
    """Route after validator: retry fix if validation failed and retries remain."""
    val_rep = state.get("validation_report")
    retries = state.get("retries_used", 0)
    max_retries = state.get("max_retries", 2)

    if val_rep and val_rep.verdict != "validated" and retries < max_retries:
        state["retries_used"] = retries + 1
        return "fix_generator"
    return "__end__"


def create_bugscope_graph() -> StateGraph:
    """Build and compile the BugScope LangGraph workflow."""
    workflow = StateGraph(BugScopeState)

    # Register nodes
    workflow.add_node("failure_analyzer", node_failure_analyzer)
    workflow.add_node("repo_investigator", node_repo_investigator)
    workflow.add_node("reproducer", node_reproducer)
    workflow.add_node("hypothesis_generator", node_hypothesis_generator)
    workflow.add_node("evidence_verifier", node_evidence_verifier)
    workflow.add_node("fix_generator", node_fix_generator)
    workflow.add_node("test_generator", node_test_generator)
    workflow.add_node("validator", node_validator)

    # Linear deterministic chain
    workflow.set_entry_point("failure_analyzer")
    workflow.add_edge("failure_analyzer", "repo_investigator")
    workflow.add_edge("repo_investigator", "reproducer")
    workflow.add_edge("reproducer", "hypothesis_generator")
    workflow.add_edge("hypothesis_generator", "evidence_verifier")

    # Conditional routing after evidence verification
    workflow.add_conditional_edges(
        "evidence_verifier",
        route_after_evidence,
        {"fix_generator": "fix_generator", "__end__": END},
    )

    # Conditional routing after fix generation
    workflow.add_conditional_edges(
        "fix_generator",
        route_after_fix,
        {"test_generator": "test_generator", "__end__": END},
    )

    # Test generator proceeds directly to validator
    workflow.add_edge("test_generator", "validator")

    # Conditional retry loop from validator back to fix_generator
    workflow.add_conditional_edges(
        "validator",
        route_after_validator,
        {"fix_generator": "fix_generator", "__end__": END},
    )

    return workflow.compile()
