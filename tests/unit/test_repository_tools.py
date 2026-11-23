"""Unit tests for repository inspection and code search tools."""

from pathlib import Path
import pytest

from app.tools.code_search import search_code
from app.tools.repository_tools import (
    get_file_content,
    get_function_info,
    get_class_info,
    find_related_tests,
    dependency_analysis,
)


@pytest.fixture
def sample_repo(tmp_path):
    """Fixture providing a mock repository with python files."""
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    test_dir = tmp_path / "tests"
    test_dir.mkdir()

    calc_file = app_dir / "calculator.py"
    calc_file.write_text(
        '''"""Calculator module."""
import math
from typing import List

class Calculator:
    """Performs operations."""
    def add(self, a: int, b: int) -> int:
        return a + b

def multiply(x: int, y: int) -> int:
    """Multiply two integers."""
    return x * y
''',
        encoding="utf-8",
    )

    test_file = test_dir / "test_calculator.py"
    test_file.write_text(
        '''from app.calculator import Calculator, multiply

def test_add():
    c = Calculator()
    assert c.add(1, 2) == 3

def test_multiply():
    assert multiply(2, 3) == 6
''',
        encoding="utf-8",
    )

    return tmp_path


def test_search_code(sample_repo):
    """Test searching for symbols across the repo."""
    matches = search_code(sample_repo, "multiply")
    assert len(matches) >= 2
    files = [m["file"] for m in matches]
    assert any("calculator.py" in f for f in files)


def test_get_file_content(sample_repo):
    """Test retrieving line-numbered content."""
    res = get_file_content(sample_repo, "app/calculator.py", start_line=5, end_line=9)
    assert res["total_lines"] >= 10
    assert len(res["lines"]) == 5
    assert "class Calculator:" in res["content"]


def test_get_function_info(sample_repo):
    """Test extracting AST metadata for a function."""
    info = get_function_info(sample_repo, "app/calculator.py", "multiply")
    assert info["name"] == "multiply"
    assert info["arguments"] == ["x", "y"]
    assert "Multiply two integers." in info["docstring"]


def test_get_class_info(sample_repo):
    """Test extracting AST metadata for a class."""
    info = get_class_info(sample_repo, "app/calculator.py", "Calculator")
    assert info["name"] == "Calculator"
    assert "add" in info["methods"]
    assert "Performs operations." in info["docstring"]


def test_find_related_tests(sample_repo):
    """Test finding test functions referencing a symbol."""
    tests = find_related_tests(sample_repo, "calculator")
    assert len(tests) >= 1
    assert "test_calculator.py" in tests[0]["test_file"]


def test_dependency_analysis(sample_repo):
    """Test parsing internal vs external dependencies."""
    deps = dependency_analysis(sample_repo, "app/calculator.py")
    assert "math" in deps["external_dependencies"]
    assert "typing" in deps["external_dependencies"]
