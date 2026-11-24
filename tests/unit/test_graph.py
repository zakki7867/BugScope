"""Unit tests for LangGraph state machine structure and conditional edges."""

import pytest
from app.workflow.graph import create_bugscope_graph
from app.workflow.state import BugScopeState


def test_create_bugscope_graph_compilation():
    """Test that LangGraph StateGraph compiles cleanly with all required nodes."""
    compiled = create_bugscope_graph()
    assert compiled is not None
    # Verify nodes are registered in the compiled graph
    nodes = compiled.nodes
    expected_nodes = [
        "failure_analyzer",
        "repo_investigator",
        "code_context_extractor",
        "reproducer",
        "hypothesis_generator",
        "evidence_verifier",
        "hypothesis_ranker",
        "experiment_runner",
        "fix_generator",
        "patch_safety_checker",
        "test_generator",
        "validator",
        "report_builder",
    ]
    for n in expected_nodes:
        assert n in nodes
