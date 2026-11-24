"""FastAPI backend application for BugScope.

Exposes comprehensive REST API endpoints for investigations, repository analysis,
evidence verification, experiment execution, patch generation, validation, and evaluations.
"""

from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app import __version__
from app.api import (
    investigations_router,
    repositories_router,
    hypotheses_router,
    evidence_router,
    experiments_router,
    patches_router,
    validation_router,
    reports_router,
    evaluation_router,
)
from app.database.db import init_db, get_investigation, list_investigations
from app.schemas.context import ContextBundle
from app.schemas.failure import FailureReport
from app.schemas.report import InvestigationReport
from app.services.zip_handler import create_temp_repo_from_zip, ZipSecurityError
from app.workflow.graph import create_bugscope_graph
from app.workflow.nodes.failure_analyzer import failure_analyzer
from app.workflow.nodes.repo_investigator import repo_investigator

# Initialize database schema on startup
init_db()

app = FastAPI(
    title="BugScope API",
    description="Evidence-checked autonomous debugging agent for Python",
    version=__version__,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount modular REST routers
app.include_router(investigations_router)
app.include_router(repositories_router)
app.include_router(hypotheses_router)
app.include_router(evidence_router)
app.include_router(experiments_router)
app.include_router(patches_router)
app.include_router(validation_router)
app.include_router(reports_router)
app.include_router(evaluation_router)


# Root Web UI endpoint
@app.get("/", response_class=FileResponse)
def serve_dashboard_ui():
    """Serve the BugScope interactive dashboard application."""
    index_path = Path(__file__).parent / "static" / "index.html"
    return FileResponse(index_path)


# Root health and metadata endpoint
@app.get("/health")
@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "app": "BugScope",
        "version": __version__,
        "endpoints": [
            "/api/investigations",
            "/api/repositories",
            "/api/hypotheses",
            "/api/evidence",
            "/api/experiments",
            "/api/patches",
            "/api/validation",
            "/api/reports",
            "/api/evaluation",
        ],
    }


class AnalyzeFailureRequest(BaseModel):
    """Request payload for failure analysis."""
    raw_trace: str = Field(..., description="Pasted error message or Python traceback", min_length=1)


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


class InvestigateZipResponse(BaseModel):
    """Response returned after processing a zip upload and failure trace."""
    temp_repo_dir: str
    failure_report: FailureReport
    context_bundle: ContextBundle


@app.post("/api/investigate/upload-zip", response_model=InvestigateZipResponse)
async def upload_zip_and_investigate(
    file: UploadFile = File(...),
    raw_trace: str = Form(...),
):
    """Safely extract uploaded project ZIP and run deterministic repo investigation."""
    try:
        zip_bytes = await file.read()
        temp_dir = create_temp_repo_from_zip(zip_bytes)
    except ZipSecurityError as z_err:
        raise HTTPException(status_code=400, detail=f"ZIP security violation: {str(z_err)}") from z_err
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to process ZIP: {str(exc)}") from exc

    failure_rep = failure_analyzer(raw_trace)
    context_bun = repo_investigator(temp_dir, failure_rep)

    return InvestigateZipResponse(
        temp_repo_dir=temp_dir,
        failure_report=failure_rep,
        context_bundle=context_bun,
    )


class RunInvestigationRequest(BaseModel):
    """Request payload to execute full BugScope workflow."""
    raw_trace: str = Field(..., description="Pasted error trace", min_length=1)
    repo_dir: Optional[str] = Field(default=None, description="Optional local directory path")


@app.post("/api/investigate/run", response_model=InvestigationReport)
def run_investigation_endpoint(request: RunInvestigationRequest):
    """Execute end-to-end evidence-checked investigation graph."""
    repo_path = request.repo_dir or "."
    from app.api.repositories import _validate_safe_repo_dir
    safe_dir = _validate_safe_repo_dir(repo_path)

    graph = create_bugscope_graph()

    initial_state = {
        "raw_trace": request.raw_trace,
        "repo_dir": str(safe_dir),
        "traces": [],
        "retries_used": 0,
        "max_retries": 2,
    }

    final_state = graph.invoke(initial_state)
    report = final_state.get("investigation_report")
    if not report:
        raise HTTPException(status_code=500, detail="Workflow failed to generate an investigation report.")
    return report


if __name__ == "__main__":
    import uvicorn
    from app.config import get_settings

    settings = get_settings()
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
