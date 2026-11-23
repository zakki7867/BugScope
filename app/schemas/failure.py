"""Schemas representing parsed failure reports and call traces."""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class FailureCategory(str, Enum):
    """Categorized root failure types for deterministic routing."""
    KEY_ERROR = "KeyError"
    TYPE_ERROR = "TypeError"
    INDEX_ERROR = "IndexError"
    ATTRIBUTE_ERROR = "AttributeError"
    IMPORT_ERROR = "ImportError"
    VALUE_ERROR = "ValueError"
    ASSERTION_ERROR = "AssertionError"
    ZERO_DIVISION = "ZeroDivisionError"
    FILE_NOT_FOUND = "FileNotFoundError"
    SYNTAX_ERROR = "SyntaxError"
    LOGIC_ERROR = "LogicError"
    UNKNOWN = "Unknown"


class CallFrame(BaseModel):
    """A single frame in the execution call chain."""
    file: str = Field(..., description="File path of the call frame")
    line: int = Field(..., description="Line number where call occurred")
    function: str = Field(..., description="Function or method name")
    code: Optional[str] = Field(default=None, description="Source line preview if available")


class FailureReport(BaseModel):
    """Structured report extracted deterministically from raw error or traceback."""
    error_type: str = Field(..., description="Exception class name, e.g. KeyError")
    message: str = Field(..., description="Exception message details")
    file: str = Field(..., description="Primary failing file path")
    line: int = Field(..., description="Primary failing line number")
    function: str = Field(..., description="Primary failing function or method name")
    call_chain: List[CallFrame] = Field(default_factory=list, description="Frames from outermost to innermost")
    category: str = Field(..., description="Failure category string")
    severity: str = Field(default="medium", description="Estimated severity: low, medium, high")
