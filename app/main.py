"""FastAPI backend application for BugScope.

Exposes endpoints for health checks, failure analysis, and debugging workflow runs.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app import __version__
from app.schemas.failure import FailureReport
from app.workflow.nodes.failure_analyzer import failure_analyzer

app = FastAPI(
    title="BugScope API",
    description="Evidence-checked debugging agent for Python",
    version=__version__,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeFailureRequest(BaseModel):
    """Request payload for failure analysis."""
    raw_trace: str = Field(..., description="Pasted error message or Python traceback", min_length=1)


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "app": "BugScope",
        "version": __version__,
    }


@app.post("/api/analyze-failure", response_model=FailureReport)
def analyze_failure_endpoint(request: AnalyzeFailureRequest):
    """Deterministically parse and categorize a pasted traceback or error message."""
    try:
        report = failure_analyzer(request.raw_trace)
        return report
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to parse failure trace: {str(exc)}",
        ) from exc


if __name__ == "__main__":
    import uvicorn
    from app.config import get_settings

    settings = get_settings()
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
