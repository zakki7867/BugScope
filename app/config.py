"""Application configuration loaded from environment variables and .env file."""

import os
from functools import lru_cache
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load .env file from project root if present
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_env_path, override=False)


class Settings(BaseModel):
    """BugScope application settings.
    
    All values are configurable via environment variables prefixed with BUGSCOPE_
    or standard names, falling back to safe defaults for local execution.
    """

    api_key: str = Field(
        default_factory=lambda: os.getenv("BUGSCOPE_API_KEY", "")
    )
    model: str = Field(
        default_factory=lambda: os.getenv("BUGSCOPE_MODEL", "gemini-2.0-flash")
    )
    api_base: str = Field(
        default_factory=lambda: os.getenv(
            "BUGSCOPE_API_BASE",
            "https://generativelanguage.googleapis.com/v1beta/openai/",
        )
    )
    host: str = Field(
        default_factory=lambda: os.getenv("BUGSCOPE_HOST", "127.0.0.1")
    )
    port: int = Field(
        default_factory=lambda: int(os.getenv("BUGSCOPE_PORT", "8000"))
    )
    db_path: str = Field(
        default_factory=lambda: os.getenv("BUGSCOPE_DB_PATH", "bugscope.db")
    )
    max_retries: int = Field(
        default_factory=lambda: int(os.getenv("BUGSCOPE_MAX_RETRIES", "2"))
    )
    docker_timeout: int = Field(
        default_factory=lambda: int(os.getenv("BUGSCOPE_DOCKER_TIMEOUT", "30"))
    )
    memory_limit: str = Field(
        default_factory=lambda: os.getenv("BUGSCOPE_MEMORY_LIMIT", "512m")
    )
    cpu_limit: str = Field(
        default_factory=lambda: os.getenv("BUGSCOPE_CPU_LIMIT", "1.0")
    )
    token_budget: int = Field(
        default_factory=lambda: int(os.getenv("BUGSCOPE_TOKEN_BUDGET", "8000"))
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton instance of Settings."""
    return Settings()
