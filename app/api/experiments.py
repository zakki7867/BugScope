"""API endpoints for controlled experiments."""

from typing import List
from fastapi import APIRouter, HTTPException, Query

from app.database.db import get_investigation
from app.schemas.experiment import ExperimentResult

router = APIRouter(prefix="/api/experiments", tags=["Experiments"])


@router.get("", response_model=List[ExperimentResult])
def get_experiments(investigation_id: str = Query(..., description="ID of investigation")):
    """Get all controlled experiment plans and sandbox results for an investigation."""
    report = get_investigation(investigation_id)
    if not report:
        raise HTTPException(status_code=404, detail="Investigation not found.")
    return report.experiments
