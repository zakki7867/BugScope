"""LangGraph workflow graph assembly for BugScope.

Orchestrates deterministic nodes and LLM nodes into an evidence-checked state machine
with mechanical retry edges and verdict routing.
"""

import time
from typing import Any, Dict, Literal
from langgraph.graph import END, StateGraph

from app.schemas.validation import VerdictType
from app.workflow.nodes.evidence_verifier import evidence_verifier
from app.workflow.nodes.experiment_runner import experiment_runner
from app.workflow.nodes.failure_analyzer import failure_analyzer
from app.workflow.nodes.fix_generator import fix_generator
from app.workflow.nodes.hypothesis_generator import hypothesis_generator
from app.workflow.nodes.repo_investigator import repo_investigator
from app.workflow.nodes.report_builder import report_builder
from app.workflow.nodes.reproducer import reproducer
from app.workflow.nodes.test_generator import test_generator
from app.workflow.nodes.validator import validator
from app.workflow.state import BugScopeState


def node_report_builder(state: BugScopeState) -> Dict[str, Any]:
    """Node 9: Assemble final investigation report and save to database."""
    return report_builder(state)


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


def node_code_context_extractor(state: BugScopeState) -> Dict[str, Any]:
    """Node 3: Deterministic code context extractor."""
    start_t = time.time()
    bundle = state.get("context_bundle")
    snippet_count = len(bundle.snippets) if bundle else 0
    total_lines = sum(len(s.code.splitlines()) for s in bundle.snippets) if bundle else 0
    elapsed_ms = round((time.time() - start_t) * 1000, 2)

    trace_entry = {
        "node": "code_context_extractor",
        "input_summary": f"{snippet_count} snippets from {bundle.failing_file if bundle else 'unknown'}",
        "output_summary": f"Extracted {total_lines} lines within token budget",
        "duration_ms": elapsed_ms,
        "tokens_in": 0,
        "tokens_out": 0,
        "cost_usd": 0.0,
    }
    traces = state.get("traces", []) + [trace_entry]
    return {"traces": traces}


def node_reproducer(state: BugScopeState) -> Dict[str, Any]:
    """Node 4: Deterministic sandbox reproducer."""
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
    """Node 5: LLM hypothesis generator."""
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
    """Node 6: Deterministic mechanical evidence verifier."""
    start_t = time.time()
    ranked = evidence_verifier(
        repo_dir=state["repo_dir"],
        hypotheses=state["hypotheses"],
    )
    elapsed_ms = round((time.time() - start_t) * 1000, 2)

    top = ranked[0] if ranked else None
    trace_entry = {
        "node": "evidence_verifier",
        "input_summary": f"Verifying quotes across {len(state['hypotheses'])} hypotheses",
        "output_summary": f"Mechanical verification complete: top score +{top.score if top else 0}",
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


def node_hypothesis_ranker(state: BugScopeState) -> Dict[str, Any]:
    """Node 7: Deterministic hypothesis ranker."""
    start_t = time.time()
    ranked = state.get("ranked_hypotheses", [])
    top = state.get("top_hypothesis")
    elapsed_ms = round((time.time() - start_t) * 1000, 2)

    trace_entry = {
        "node": "hypothesis_ranker",
        "input_summary": f"Ranked {len(ranked)} hypotheses by verified evidence score",
        "output_summary": f"Top #{top.id if top else 'none'}: {top.title if top else 'none'} ({top.label if top else 'none'})",
        "duration_ms": elapsed_ms,
        "tokens_in": 0,
        "tokens_out": 0,
        "cost_usd": 0.0,
    }
    traces = state.get("traces", []) + [trace_entry]
    return {"traces": traces}


def node_experiment_runner(state: BugScopeState) -> Dict[str, Any]:
    """Node 8: Deterministic controlled experiment runner."""
    start_t = time.time()
    results = experiment_runner(
        repo_dir=state["repo_dir"],
        failure_report=state["failure_report"],
        ranked_hypotheses=state.get("ranked_hypotheses", []),
        reproduction_result=state.get("reproduction_result"),
    )
    elapsed_ms = round((time.time() - start_t) * 1000, 2)
    confirmed_count = sum(1 for r in results if r.conclusion == "confirmed")
    trace_entry = {
        "node": "experiment_runner",
        "input_summary": f"Testing {len(results)} candidate hypotheses",
        "output_summary": f"{confirmed_count}/{len(results)} confirmed by controlled sandbox experiment",
        "duration_ms": elapsed_ms,
        "tokens_in": 0,
        "tokens_out": 0,
        "cost_usd": 0.0,
    }
    traces = state.get("traces", []) + [trace_entry]
    return {"experiments": results, "traces": traces}


def node_fix_generator(state: BugScopeState) -> Dict[str, Any]:
    """Node 9: LLM fix generator."""
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


def node_patch_safety_checker(state: BugScopeState) -> Dict[str, Any]:
    """Node 10: Deterministic patch safety checker."""
    start_t = time.time()
    proposal = state.get("fix_proposal")
    is_safe = True
    error_msg = None

    if proposal and proposal.diff.strip():
        try:
            from app.services.patcher import validate_patch_safety
            validate_patch_safety(proposal.diff)
        except Exception as exc:
            is_safe = False
            error_msg = str(exc)
            proposal = proposal.model_copy(
                update={
                    "status": "needs_human_decision",
                    "human_decision_reason": f"Patch safety invariant violated: {error_msg}",
                    "options_if_ambiguous": [
                        "Review proposed diff manually for forbidden test edits or unsafe code execution.",
                        "Reject automated patch and inspect alternative hypotheses.",
                    ],
                }
            )

    elapsed_ms = round((time.time() - start_t) * 1000, 2)
    trace_entry = {
        "node": "patch_safety_checker",
        "input_summary": f"Diff length {len(proposal.diff) if proposal else 0} chars",
        "output_summary": "Passed all safety invariants" if is_safe else f"Rejected: {error_msg}",
        "duration_ms": elapsed_ms,
        "tokens_in": 0,
        "tokens_out": 0,
        "cost_usd": 0.0,
    }
    traces = state.get("traces", []) + [trace_entry]
    return {"fix_proposal": proposal, "traces": traces}


def node_test_generator(state: BugScopeState) -> Dict[str, Any]:
    """Node 11: LLM test generator."""
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
    """Node 12: Deterministic sandbox validator."""
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
def route_after_evidence(state: BugScopeState) -> Literal["fix_generator", "report_builder"]:
    """Route after evidence verification."""
    top = state.get("top_hypothesis")
    if not top or top.label == "unsupported":
        return "report_builder"
    return "fix_generator"


def route_after_fix(state: BugScopeState) -> Literal["test_generator", "report_builder"]:
    """Route after fix proposal."""
    proposal = state.get("fix_proposal")
    if not proposal or proposal.status == "needs_human_decision":
        return "report_builder"
    return "test_generator"


def route_after_validator(state: BugScopeState) -> Literal["fix_generator", "report_builder"]:
    """Route after validator: retry fix if validation failed and retries remain."""
    val_rep = state.get("validation_report")
    retries = state.get("retries_used", 0)
    max_retries = state.get("max_retries", 2)

    if val_rep and val_rep.verdict != "validated" and retries < max_retries:
        state["retries_used"] = retries + 1
        return "fix_generator"
    return "report_builder"


def create_bugscope_graph() -> StateGraph:
    """Build and compile the BugScope LangGraph workflow."""
    workflow = StateGraph(BugScopeState)

    # Register all 13 workflow nodes
    workflow.add_node("failure_analyzer", node_failure_analyzer)
    workflow.add_node("repo_investigator", node_repo_investigator)
    workflow.add_node("code_context_extractor", node_code_context_extractor)
    workflow.add_node("reproducer", node_reproducer)
    workflow.add_node("hypothesis_generator", node_hypothesis_generator)
    workflow.add_node("evidence_verifier", node_evidence_verifier)
    workflow.add_node("hypothesis_ranker", node_hypothesis_ranker)
    workflow.add_node("experiment_runner", node_experiment_runner)
    workflow.add_node("fix_generator", node_fix_generator)
    workflow.add_node("patch_safety_checker", node_patch_safety_checker)
    workflow.add_node("test_generator", node_test_generator)
    workflow.add_node("validator", node_validator)
    workflow.add_node("report_builder", node_report_builder)

    # Linear deterministic chain
    workflow.set_entry_point("failure_analyzer")
    workflow.add_edge("failure_analyzer", "repo_investigator")
    workflow.add_edge("repo_investigator", "code_context_extractor")
    workflow.add_edge("code_context_extractor", "reproducer")
    workflow.add_edge("reproducer", "hypothesis_generator")
    workflow.add_edge("hypothesis_generator", "evidence_verifier")
    workflow.add_edge("evidence_verifier", "hypothesis_ranker")
    workflow.add_edge("hypothesis_ranker", "experiment_runner")

    # Conditional routing after experiment runner
    workflow.add_conditional_edges(
        "experiment_runner",
        route_after_evidence,
        {"fix_generator": "fix_generator", "report_builder": "report_builder"},
    )

    # Fix generator leads directly to patch safety checker
    workflow.add_edge("fix_generator", "patch_safety_checker")

    # Conditional routing after patch safety verification
    workflow.add_conditional_edges(
        "patch_safety_checker",
        route_after_fix,
        {"test_generator": "test_generator", "report_builder": "report_builder"},
    )

    # Test generator proceeds directly to validator
    workflow.add_edge("test_generator", "validator")

    # Conditional retry loop from validator back to fix_generator or forward to report_builder
    workflow.add_conditional_edges(
        "validator",
        route_after_validator,
        {"fix_generator": "fix_generator", "report_builder": "report_builder"},
    )

    # Report builder terminates the workflow
    workflow.add_edge("report_builder", END)

    return workflow.compile()
