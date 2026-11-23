"""FastAPI backend application for BugScope.

Exposes endpoints for health checks, failure analysis, and debugging workflow runs.
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional

from app import __version__
from app.schemas.failure import FailureReport
from app.schemas.context import ContextBundle
from app.schemas.report import InvestigationReport
from app.database.db import get_investigation, list_investigations, save_investigation
from app.services.zip_handler import create_temp_repo_from_zip, ZipSecurityError
from app.workflow.graph import create_bugscope_graph
from app.workflow.nodes.failure_analyzer import failure_analyzer
from app.workflow.nodes.repo_investigator import repo_investigator

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
    graph = create_bugscope_graph()

    initial_state = {
        "raw_trace": request.raw_trace,
        "repo_dir": repo_path,
        "traces": [],
        "retries_used": 0,
        "max_retries": 2,
    }

    final_state = graph.invoke(initial_state)
    report = final_state.get("investigation_report")
    if not report:
        raise HTTPException(status_code=500, detail="Workflow failed to generate an investigation report.")
    return report


@app.get("/api/investigations")
def list_investigations_endpoint(limit: int = 50):
    """List recent investigations."""
    return list_investigations(limit=limit)


@app.get("/api/investigations/{investigation_id}", response_model=InvestigationReport)
def get_investigation_endpoint(investigation_id: str):
    """Retrieve full investigation report by ID."""
    report = get_investigation(investigation_id)
    if not report:
        raise HTTPException(status_code=404, detail="Investigation not found.")
    return report


if __name__ == "__main__":
    import uvicorn
    from app.config import get_settings

    settings = get_settings()
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
