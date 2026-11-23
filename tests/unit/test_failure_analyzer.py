"""Unit tests for failure_analyzer node and FastAPI failure endpoint."""

import pytest

from app.main import app, health_check, analyze_failure_endpoint, AnalyzeFailureRequest
from app.schemas.failure import FailureCategory
from app.workflow.nodes.failure_analyzer import failure_analyzer


def test_standard_python_traceback_key_error():
    """Test standard multi-frame Python traceback ending with KeyError."""
    trace = """
Traceback (most recent call last):
  File "app/server.py", line 45, in handle_request
    response = process_item(item_data)
  File "app/services/processor.py", line 112, in process_item
    user_id = item_data["user_id"]
KeyError: 'user_id'
"""
    report = failure_analyzer(trace)

    assert report.error_type == "KeyError"
    assert "'user_id'" in report.message
    assert report.file == "app/services/processor.py"
    assert report.line == 112
    assert report.function == "process_item"
    assert report.category == FailureCategory.KEY_ERROR.value
    assert len(report.call_chain) == 2
    assert report.call_chain[0].file == "app/server.py"
    assert report.call_chain[0].line == 45
    assert report.call_chain[0].function == "handle_request"


def test_pytest_failure_block_type_error():
    """Test parsing a pytest style failure output."""
    trace = """
________________________________ test_calculate_discount ________________________________

    def test_calculate_discount():
>       calc(100, "invalid")

tests/test_pricing.py:24: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
app/pricing.py:15: in calc
    return price * (1.0 - rate)
E   TypeError: unsupported operand type(s) for -: 'float' and 'str'
"""
    report = failure_analyzer(trace)

    assert report.error_type == "TypeError"
    assert "unsupported operand type" in report.message
    assert report.file == "app/pricing.py"
    assert report.line == 15
    assert report.function == "calc"
    assert report.category == FailureCategory.TYPE_ERROR.value


def test_pytest_assertion_error():
    """Test pytest assertion failure block."""
    trace = """
____________________________________ test_tax_bracket ___________________________________

    def test_tax_bracket():
>       assert compute_tax(1000) == 150
E       assert 100.0 == 150

tests/test_tax.py:32: AssertionError
"""
    report = failure_analyzer(trace)

    assert "AssertionError" in report.error_type
    assert report.file == "tests/test_tax.py"
    assert report.line == 32
    assert report.category == FailureCategory.ASSERTION_ERROR.value


def test_standalone_attribute_error_without_traceback():
    """Test raw error string without Python 'Traceback' header."""
    trace = "AttributeError: 'NoneType' object has no attribute 'get_token'"
    report = failure_analyzer(trace)

    assert report.error_type == "AttributeError"
    assert "object has no attribute 'get_token'" in report.message
    assert report.category == FailureCategory.ATTRIBUTE_ERROR.value
    assert report.file == "unknown.py"
    assert report.line == 1


def test_inline_location_reference():
    """Test error string containing inline file and line reference."""
    trace = "IndexError: list index out of range at app/parsers/csv_parser.py:54"
    report = failure_analyzer(trace)

    assert report.error_type == "IndexError"
    assert report.file == "app/parsers/csv_parser.py"
    assert report.line == 54
    assert report.category == FailureCategory.INDEX_ERROR.value


def test_import_error_parsing():
    """Test ModuleNotFoundError / ImportError categorization."""
    trace = """
Traceback (most recent call last):
  File "app/main.py", line 3, in <module>
    import missing_dependency
ModuleNotFoundError: No module named 'missing_dependency'
"""
    report = failure_analyzer(trace)

    assert report.error_type == "ModuleNotFoundError"
    assert report.category == FailureCategory.IMPORT_ERROR.value
    assert report.file == "app/main.py"
    assert report.line == 3


def test_health_endpoint():
    """Test FastAPI /health endpoint handler directly."""
    data = health_check()
    assert data["status"] == "ok"
    assert data["app"] == "BugScope"


def test_analyze_failure_api_endpoint():
    """Test POST /api/analyze-failure endpoint handler directly."""
    req = AnalyzeFailureRequest(
        raw_trace="ZeroDivisionError: division by zero at app/math_ops.py:12"
    )
    report = analyze_failure_endpoint(req)
    assert report.error_type == "ZeroDivisionError"
    assert report.file == "app/math_ops.py"
    assert report.line == 12
    assert report.category == FailureCategory.ZERO_DIVISION.value
