"""API endpoints for mechanically verified code evidence."""

from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, Query

from app.database.db import get_investigation

router = APIRouter(prefix="/api/evidence", tags=["Evidence"])


@router.get("")
def get_evidence(investigation_id: str = Query(..., description="ID of investigation")):
    """Get all code evidence items across all hypotheses for an investigation."""
    report = get_investigation(investigation_id)
    if not report:
        raise HTTPException(status_code=404, detail="Investigation not found.")

    all_evidence = []
    for hyp in report.hypotheses:
        for ev in hyp.evidence:
            all_evidence.append({
                "hypothesis_id": hyp.id,
                "hypothesis_title": hyp.title,
                "file": ev.file,
                "line_start": ev.line_start,
                "line_end": ev.line_end,
                "quote": ev.quote,
                "stance": ev.stance,
                "reason": ev.reason,
                "verified": ev.verified,
            })
    return {"investigation_id": investigation_id, "evidence": all_evidence}
