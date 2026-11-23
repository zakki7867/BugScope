"""Schemas for sandbox execution and failure reproduction results."""

from typing import Optional
from pydantic import BaseModel, Field


class ReproductionResult(BaseModel):
    """Result of running tests in the isolated Docker sandbox prior to patching."""
    reproduced: bool = Field(..., description="Whether the original failure was observed")
    exit_code: int = Field(default=-1, description="Process exit status code")
    stdout: str = Field(default="", description="Captured standard output")
    stderr: str = Field(default="", description="Captured standard error")
    command: str = Field(default="", description="Command executed inside the sandbox")
    error: Optional[str] = Field(default=None, description="Execution or environment error details")
    duration_seconds: float = Field(default=0.0, description="Execution wall-clock time in seconds")
    docker_available: bool = Field(default=True, description="Whether Docker sandbox was available")
    trust_level: str = Field(default="high", description="Investigation trust level: 'high' or 'low'")
