"""Schemas for code context snippets and repository investigation bundles."""

from typing import List, Optional
from pydantic import BaseModel, Field


class Snippet(BaseModel):
    """A sliced, numbered code snippet from the repository."""
    file: str = Field(..., description="File path relative to repository root")
    line_start: int = Field(..., description="1-indexed starting line number")
    line_end: int = Field(..., description="1-indexed ending line number")
    code: str = Field(..., description="Source code excerpt with line numbers")
    is_target: bool = Field(default=False, description="Whether this snippet contains the crash location")


class ContextBundle(BaseModel):
    """Mechanically gathered context bundle within a fixed token/size budget."""
    file_tree: List[str] = Field(default_factory=list, description="Repository directory layout")
    failing_file: str = Field(..., description="Primary file where error occurred")
    failing_symbol: Optional[str] = Field(default=None, description="Enclosing function or class name")
    callers: List[str] = Field(default_factory=list, description="Functions calling the failing symbol")
    callees: List[str] = Field(default_factory=list, description="Functions called by the failing symbol")
    snippets: List[Snippet] = Field(default_factory=list, description="Extracted code snippets within budget")
    related_tests: List[str] = Field(default_factory=list, description="Test files relevant to the failure")
    total_lines_inspected: int = Field(default=0, description="Total source lines analyzed")
