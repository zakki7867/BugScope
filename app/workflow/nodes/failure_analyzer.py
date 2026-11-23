"""Deterministic failure analyzer node.

Parses pasted Python tracebacks, pytest failure output, or standalone exception
messages into a structured FailureReport using regex and pattern matching.
No LLM calls are made in this node.
"""

import re
from typing import List, Optional, Tuple
from app.schemas.failure import CallFrame, FailureCategory, FailureReport


# Regex for standard Python traceback frame:
# File "path/to/file.py", line 42, in my_func
_FRAME_PATTERN = re.compile(
    r'File\s+["\'](?P<file>[^"\']+)["\'],\s+line\s+(?P<line>\d+)(?:,\s+in\s+(?P<func>[^\n]+))?',
    re.IGNORECASE,
)

# Regex for final exception line:
# KeyError: 'user_id' or CustomError: something went wrong
_EXCEPTION_PATTERN = re.compile(
    r"^(?:(?:[a-zA-Z_]\w*\.)*(?P<error_type>[a-zA-Z_]\w*Error|[a-zA-Z_]\w*Exception|AssertionError|KeyboardInterrupt|SystemExit|StopIteration|GeneratorExit))\s*:\s*(?P<message>.*)$",
    re.MULTILINE,
)

# Pytest traceback line:
# path/to/file.py:42: in test_func or path/to/file.py:42: AssertionError
_PYTEST_FRAME_PATTERN = re.compile(
    r"^(?P<file>[a-zA-Z0-9_\-\./\\]+\.py):(?P<line>\d+):(?:\s+in\s+(?P<func>[^\n]+)|\s*(?P<trailer>[^\n]*))",
    re.MULTILINE,
)

# Pytest error prefix line:
# E   KeyError: 'item' or E   assert 100.0 == 150
_PYTEST_ERROR_PATTERN = re.compile(
    r"^E\s+(?:(?:[a-zA-Z_]\w*\.)*(?P<error_type>[a-zA-Z_]\w*))\s*:\s*(?P<message>.*)$",
    re.MULTILINE,
)
_PYTEST_ASSERT_LINE = re.compile(
    r"^E\s+(?P<message>assert\s+.*)$",
    re.MULTILINE,
)

# Fallback pattern for inline references:
# in foo at bar.py:123 or in bar.py, line 123
_INLINE_REF_PATTERN = re.compile(
    r"(?:at|in)\s+(?P<file>[a-zA-Z0-9_\-\./\\]+\.py)(?::|,\s+line\s+)(?P<line>\d+)",
    re.IGNORECASE,
)


def _normalize_path(path: str) -> str:
    """Normalize file path to use forward slashes and strip redundant prefixes."""
    normalized = path.replace("\\", "/").strip().strip('"').strip("'")
    return normalized


def _map_category(error_type: str, message: str) -> str:
    """Map raw error type and message to a standard FailureCategory."""
    err_lower = error_type.lower()
    if "key" in err_lower:
        return FailureCategory.KEY_ERROR.value
    if "type" in err_lower:
        return FailureCategory.TYPE_ERROR.value
    if "index" in err_lower:
        return FailureCategory.INDEX_ERROR.value
    if "attribute" in err_lower:
        return FailureCategory.ATTRIBUTE_ERROR.value
    if "import" in err_lower or "modulenotfound" in err_lower:
        return FailureCategory.IMPORT_ERROR.value
    if "value" in err_lower:
        return FailureCategory.VALUE_ERROR.value
    if "assert" in err_lower:
        return FailureCategory.ASSERTION_ERROR.value
    if "division" in err_lower or "zerodivision" in err_lower:
        return FailureCategory.ZERO_DIVISION.value
    if "filenotfound" in err_lower:
        return FailureCategory.FILE_NOT_FOUND.value
    if "syntax" in err_lower or "indentation" in err_lower:
        return FailureCategory.SYNTAX_ERROR.value
    return FailureCategory.UNKNOWN.value


def _extract_frames_standard(text: str) -> List[CallFrame]:
    """Extract call frames from standard Python traceback format."""
    frames: List[CallFrame] = []
    lines = text.splitlines()

    for idx, line in enumerate(lines):
        match = _FRAME_PATTERN.search(line)
        if match:
            file_path = _normalize_path(match.group("file"))
            line_no = int(match.group("line"))
            func_name = (match.group("func") or "<module>").strip()

            # Look ahead to see if the next non-empty line has code
            code_snippet = None
            if idx + 1 < len(lines):
                next_line = lines[idx + 1].strip()
                if not next_line.startswith("File ") and not _EXCEPTION_PATTERN.match(next_line):
                    code_snippet = next_line

            frames.append(
                CallFrame(
                    file=file_path,
                    line=line_no,
                    function=func_name,
                    code=code_snippet,
                )
            )
    return frames


def _extract_frames_pytest(text: str) -> List[CallFrame]:
    """Extract call frames from pytest failure logs."""
    frames: List[CallFrame] = []
    for match in _PYTEST_FRAME_PATTERN.finditer(text):
        file_path = _normalize_path(match.group("file"))
        line_no = int(match.group("line"))
        func_name = (match.group("func") or "<test>").strip()
        frames.append(
            CallFrame(
                file=file_path,
                line=line_no,
                function=func_name,
            )
        )
    return frames


def _extract_exception_details(text: str) -> Tuple[str, str]:
    """Find the exception class and message from text."""
    # 1. Try pytest 'E   Exception: ...' format first
    pytest_match = None
    for match in _PYTEST_ERROR_PATTERN.finditer(text):
        pytest_match = match
    if pytest_match:
        return (
            pytest_match.group("error_type").strip(),
            pytest_match.group("message").strip(),
        )

    # 2. Check for pytest 'E   assert ...' lines
    pytest_assert = None
    for match in _PYTEST_ASSERT_LINE.finditer(text):
        pytest_assert = match
    if pytest_assert:
        return "AssertionError", pytest_assert.group("message").strip()

    # 3. Check for trailing pytest 'file.py:line: AssertionError' lines
    for match in _PYTEST_FRAME_PATTERN.finditer(text):
        trailer = (match.group("trailer") or "").strip()
        if trailer and ("Error" in trailer or "Exception" in trailer):
            return trailer, f"Failed at {match.group('file')}:{match.group('line')}"

    # 4. Try standard exception pattern (find the last occurrence in traceback)
    std_match = None
    for match in _EXCEPTION_PATTERN.finditer(text):
        std_match = match
    if std_match:
        return (
            std_match.group("error_type").strip(),
            std_match.group("message").strip(),
        )

    # 5. Fallback: check for standalone 'ErrorName: message' anywhere
    generic = re.search(r"^([a-zA-Z_]\w*)\s*:\s*(.*)$", text.strip(), re.MULTILINE)
    if generic:
        return generic.group(1).strip(), generic.group(2).strip()

    # 6. Unknown fallback
    first_line = text.strip().splitlines()[0] if text.strip() else "Unknown error"
    return "RuntimeError", first_line[:200]


def failure_analyzer(raw_trace: str) -> FailureReport:
    """Parse raw traceback or error string deterministically into a FailureReport.
    
    Args:
        raw_trace: The raw text of a traceback, pytest log, or error message.

    Returns:
        FailureReport containing parsed fields and categorization.
    """
    clean_text = raw_trace.strip()

    # 1. Extract error type and message
    error_type, message = _extract_exception_details(clean_text)

    # 2. Extract call frames
    frames = _extract_frames_standard(clean_text)
    if not frames:
        frames = _extract_frames_pytest(clean_text)

    # 3. Determine the primary crash location
    if frames:
        primary_frame = frames[-1]
        file_path = primary_frame.file
        line_no = primary_frame.line
        func_name = primary_frame.function
    else:
        # Check for inline location hints (e.g. at foo.py:45)
        inline_match = _INLINE_REF_PATTERN.search(clean_text)
        if inline_match:
            file_path = _normalize_path(inline_match.group("file"))
            line_str = inline_match.group("line")
            line_no = int(line_str) if line_str else 1
            func_name = "<unknown>"
            frames.append(CallFrame(file=file_path, line=line_no, function=func_name))
        else:
            file_path = "unknown.py"
            line_no = 1
            func_name = "<unknown>"

    # 4. Categorize and evaluate severity
    category = _map_category(error_type, message)
    severity = "high" if len(frames) > 5 or category in ("ZeroDivisionError", "SyntaxError") else "medium"

    return FailureReport(
        error_type=error_type,
        message=message,
        file=file_path,
        line=line_no,
        function=func_name,
        call_chain=frames,
        category=category,
        severity=severity,
    )
