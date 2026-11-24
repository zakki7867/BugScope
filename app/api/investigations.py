"""API endpoints for managing and executing debugging investigations."""

import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field

from app.database.db import get_investigation, list_investigations
from app.database.session import SessionLocal
from app.models import Investigation, Hypothesis, Evidence, Experiment, Patch, ValidationResult, TraceLog
from app.schemas.report import InvestigationReport
from app.workflow.graph import create_bugscope_graph

router = APIRouter(prefix="/api/investigations", tags=["Investigations"])


class CreateInvestigationRequest(BaseModel):
    """Payload to trigger an investigation."""
    raw_trace: str = Field(..., description="Error message, stack trace, or failing test log")
    repo_dir: Optional[str] = Field(default=None, description="Local path to repository or extracted zip folder")
    test_command: Optional[str] = Field(default=None, description="Optional failing test command")


class InvestigationSummary(BaseModel):
    """Summary record of an investigation."""
    id: str
    created_at: str
    verdict: str
    error_type: str
    message: str
    file: str
    total_duration_seconds: float
    total_cost_usd: float


@router.post("", response_model=InvestigationReport)
def create_investigation(payload: CreateInvestigationRequest):
    """Start and run an end-to-end evidence-checked debugging investigation."""
    repo_path = payload.repo_dir or "."
    graph = create_bugscope_graph()

    initial_state = {
        "raw_trace": payload.raw_trace,
        "repo_dir": repo_path,
        "traces": [],
        "retries_used": 0,
        "max_retries": 2,
    }

    try:
        final_state = graph.invoke(initial_state)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Investigation workflow execution error: {str(exc)}"
        ) from exc

    report = final_state.get("investigation_report")
    if not report:
        raise HTTPException(
            status_code=500, detail="Investigation completed without generating a report."
        )
    return report


@router.get("", response_model=List[InvestigationSummary])
def get_all_investigations(limit: int = Query(default=50, ge=1, le=200)):
    """List recent investigations ordered by newest first."""
    items = list_investigations(limit=limit)
    return [InvestigationSummary(**item) for item in items]


@router.get("/{investigation_id}", response_model=InvestigationReport)
def get_investigation_by_id(investigation_id: str):
    """Retrieve complete investigation report and metadata."""
    report = get_investigation(investigation_id)
    if not report:
        raise HTTPException(status_code=404, detail="Investigation not found.")
    return report


@router.get("/{investigation_id}/graph")
def get_investigation_graph_state(investigation_id: str):
    """Return LangGraph workflow execution graph state and node telemetry."""
    report = get_investigation(investigation_id)
    if not report:
        raise HTTPException(status_code=404, detail="Investigation not found.")

    # Nodes in the 13-step workflow topology
    standard_nodes = [
        {"id": "failure_analyzer", "label": "Failure Analyzer", "type": "deterministic"},
        {"id": "repo_investigator", "label": "Repo Investigator", "type": "deterministic"},
        {"id": "code_context_extractor", "label": "Context Extractor", "type": "deterministic"},
        {"id": "reproducer", "label": "Sandbox Reproducer", "type": "deterministic"},
        {"id": "hypothesis_generator", "label": "Hypothesis Generator", "type": "llm"},
        {"id": "evidence_verifier", "label": "Evidence Verifier", "type": "deterministic"},
        {"id": "hypothesis_ranker", "label": "Hypothesis Ranker", "type": "deterministic"},
        {"id": "experiment_runner", "label": "Experiment Runner", "type": "deterministic"},
        {"id": "fix_generator", "label": "Fix Generator", "type": "llm"},
        {"id": "patch_safety_checker", "label": "Patch Safety Guard", "type": "deterministic"},
        {"id": "test_generator", "label": "Test Generator", "type": "llm"},
        {"id": "validator", "label": "3-Phase Validator", "type": "deterministic"},
        {"id": "report_builder", "label": "Report Builder", "type": "deterministic"},
    ]

    executed_nodes = {t.node: t for t in report.traces}

    nodes_status = []
    for node in standard_nodes:
        node_id = node["id"]
        trace = executed_nodes.get(node_id)
        status = "COMPLETED" if trace else "SKIPPED"
        nodes_status.append({
            "id": node_id,
            "label": node["label"],
            "type": node["type"],
            "status": status,
            "duration_ms": trace.duration_ms if trace else 0.0,
            "tokens_in": trace.tokens_in if trace else 0,
            "tokens_out": trace.tokens_out if trace else 0,
            "cost_usd": trace.cost_usd if trace else 0.0,
            "input_summary": trace.input_summary if trace else "",
            "output_summary": trace.output_summary if trace else "",
        })

    edges = [
        {"source": "failure_analyzer", "target": "repo_investigator"},
        {"source": "repo_investigator", "target": "code_context_extractor"},
        {"source": "code_context_extractor", "target": "reproducer"},
        {"source": "reproducer", "target": "hypothesis_generator"},
        {"source": "hypothesis_generator", "target": "evidence_verifier"},
        {"source": "evidence_verifier", "target": "hypothesis_ranker"},
        {"source": "hypothesis_ranker", "target": "experiment_runner"},
        {"source": "experiment_runner", "target": "fix_generator"},
        {"source": "fix_generator", "target": "patch_safety_checker"},
        {"source": "patch_safety_checker", "target": "test_generator"},
        {"source": "test_generator", "target": "validator"},
        {"source": "validator", "target": "report_builder"},
    ]

    return {
        "investigation_id": investigation_id,
        "verdict": report.verdict,
        "nodes": nodes_status,
        "edges": edges,
        "traces": [t.model_dump() for t in report.traces],
    }
