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
from app.services.zip_handler import create_temp_repo_from_zip, ZipSecurityError
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


if __name__ == "__main__":
    import uvicorn
    from app.config import get_settings

    settings = get_settings()
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
