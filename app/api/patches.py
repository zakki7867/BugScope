"""API endpoints for patch inspection and diff rendering."""

from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.database.db import get_investigation
from app.schemas.fix import FixProposal
from app.services.patcher import apply_unified_diff

router = APIRouter(prefix="/api/patches", tags=["Patches"])


class PatchPreviewRequest(BaseModel):
    """Payload to preview diff applied against original source."""
    original_code: str = Field(..., description="Original file source code")
    diff: str = Field(..., description="Unified diff string")


@router.get("", response_model=Optional[FixProposal])
def get_patch(investigation_id: str = Query(..., description="ID of investigation")):
    """Get the proposed minimal patch and regression test for an investigation."""
    report = get_investigation(investigation_id)
    if not report:
        raise HTTPException(status_code=404, detail="Investigation not found.")
    return report.fix_proposal


@router.post("/preview")
def preview_patch(payload: PatchPreviewRequest):
    """Simulate applying a unified diff against given original source code."""
    res = apply_unified_diff(payload.original_code, payload.diff)
    return {
        "success": res.success,
        "patched_code": res.patched_content if res.success else payload.original_code,
        "error": res.error_message,
        "hunks_applied": res.applied_hunks,
    }
