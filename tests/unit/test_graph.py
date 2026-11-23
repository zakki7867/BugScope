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
        "reproducer",
        "hypothesis_generator",
        "evidence_verifier",
        "fix_generator",
        "test_generator",
        "validator",
    ]
    for n in expected_nodes:
        assert n in nodes
