"""API endpoints for patch validation results."""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from app.database.db import get_investigation
from app.schemas.validation import ValidationReport

router = APIRouter(prefix="/api/validation", tags=["Validation"])


@router.get("", response_model=Optional[ValidationReport])
def get_validation(investigation_id: str = Query(..., description="ID of investigation")):
    """Get 3-phase sandbox validation report (reproduction, fix verification, suite regression check)."""
    report = get_investigation(investigation_id)
    if not report:
        raise HTTPException(status_code=404, detail="Investigation not found.")
    return report.validation_report
