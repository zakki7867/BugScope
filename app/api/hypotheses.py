"""API endpoints for hypotheses and ranking data."""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query

from app.database.db import get_investigation
from app.schemas.hypothesis import RankedHypothesis

router = APIRouter(prefix="/api/hypotheses", tags=["Hypotheses"])


@router.get("", response_model=List[RankedHypothesis])
def get_hypotheses(investigation_id: str = Query(..., description="ID of investigation")):
    """Get candidate root-cause hypotheses with verified evidence for an investigation."""
    report = get_investigation(investigation_id)
    if not report:
        raise HTTPException(status_code=404, detail="Investigation not found.")
    return report.hypotheses
