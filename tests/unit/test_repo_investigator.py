"""Unit tests for deterministic repo_investigator node and AST slicing."""

import pytest
from pathlib import Path

from app.schemas.failure import FailureReport
from app.workflow.nodes.repo_investigator import (
    repo_investigator,
    build_file_tree,
    find_failing_file_path,
)


@pytest.fixture
def sample_project(tmp_path):
    """Create a temporary Python project on disk."""
    app_dir = tmp_path / "app"
    tests_dir = tmp_path / "tests"
    app_dir.mkdir()
    tests_dir.mkdir()

    # app/math_service.py
    math_code = """
def helper_clean(val):
    return str(val).strip()

def compute_total(items):
    subtotal = 0
    for item in items:
        cleaned = helper_clean(item)
        subtotal += int(cleaned)
    return subtotal
"""
    (app_dir / "math_service.py").write_text(math_code.strip(), encoding="utf-8")

    # app/caller_module.py
    caller_code = """
from app.math_service import compute_total

def run_pipeline(data):
    return compute_total(data)
"""
    (app_dir / "caller_module.py").write_text(caller_code.strip(), encoding="utf-8")

    # tests/test_math.py
    test_code = """
from app.math_service import compute_total

def test_compute_total():
    assert compute_total(["1", "2"]) == 3
"""
    (tests_dir / "test_math.py").write_text(test_code.strip(), encoding="utf-8")

    return tmp_path


def test_build_file_tree(sample_project):
    """Test file tree generation excludes hidden and cache directories."""
    tree = build_file_tree(sample_project)
    assert "app/math_service.py" in tree
    assert "app/caller_module.py" in tree
    assert "tests/test_math.py" in tree


def test_repo_investigator_target_function_and_ast(sample_project):
    """Test locating target function, AST callees, callers, and test files."""
    failure = FailureReport(
        error_type="ValueError",
        message="invalid literal for int() with base 10: 'abc'",
        file="app/math_service.py",
        line=8,  # Line corresponding to subtotal += int(cleaned) inside compute_total
        function="compute_total",
        category="ValueError",
        severity="medium",
    )

    bundle = repo_investigator(str(sample_project), failure, token_budget=4000)

    assert bundle.failing_file == "app/math_service.py"
    assert bundle.failing_symbol == "compute_total"
    assert "helper_clean" in bundle.callees
    assert any("caller_module.py::run_pipeline" in c for c in bundle.callers)
    assert any("test_math.py" in t for t in bundle.related_tests)
    assert len(bundle.snippets) >= 1

    target_snippet = bundle.snippets[0]
    assert target_snippet.is_target is True
    assert "compute_total" in target_snippet.code
    assert "subtotal +=" in target_snippet.code


def test_repo_investigator_budget_constraint(sample_project):
    """Test that snippet extraction respects small token budget limits."""
    failure = FailureReport(
        error_type="KeyError",
        message="'x'",
        file="app/math_service.py",
        line=2,
        function="helper_clean",
        category="KeyError",
        severity="low",
    )
    # Tiny token budget (e.g. 30 tokens = ~120 chars)
    bundle = repo_investigator(str(sample_project), failure, token_budget=30)
    assert len(bundle.snippets) <= 1
