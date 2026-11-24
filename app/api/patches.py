"""API endpoints for patch inspection and diff rendering."""

from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.database.db import get_investigation
from app.schemas.fix import FixProposal
from app.services.patcher import (
    PatchError,
    apply_patch_to_directory,
    apply_unified_diff,
    validate_patch_safety,
)

router = APIRouter(prefix="/api/patches", tags=["Patches"])

# In-memory pre-patch backup registry for atomic rollback: key -> {rel_path: original_content}
_ROLLBACK_REGISTRY: Dict[str, Dict[str, str]] = {}


class PatchPreviewRequest(BaseModel):
    """Payload to preview diff applied against original source."""
    original_code: str = Field(..., description="Original file source code")
    diff: str = Field(..., description="Unified diff string")


class ApplyPatchRequest(BaseModel):
    """Payload to apply a verified patch to the user's project."""
    investigation_id: str = Field(..., description="ID of completed investigation")
    target_repo_dir: str = Field(..., description="Path to original project directory")
    user_approved: bool = Field(..., description="Explicit confirmation that user approves applying the patch")


class RollbackPatchRequest(BaseModel):
    """Payload to revert an applied patch."""
    investigation_id: str = Field(..., description="ID of investigation")
    target_repo_dir: str = Field(..., description="Path to original project directory")


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


@router.post("/apply")
def apply_patch_endpoint(payload: ApplyPatchRequest):
    """Apply a validated patch to the user's original project after explicit user approval.

    Enforces patch safety rules, backs up original files, and creates an atomic rollback point.
    """
    if not payload.user_approved:
        raise HTTPException(
            status_code=400,
            detail="User approval required: Patches will not be applied to original project without explicit approval.",
        )

    report = get_investigation(payload.investigation_id)
    if not report or not report.fix_proposal or not report.fix_proposal.diff.strip():
        raise HTTPException(
            status_code=404,
            detail="No valid patch found for this investigation.",
        )

    target_path = Path(payload.target_repo_dir).resolve() if payload.target_repo_dir else None
    if not target_path or not target_path.is_dir():
        from app.database.session import SessionLocal
        from app.models.investigation import Investigation
        with SessionLocal() as sess:
            inv = sess.query(Investigation).filter_by(id=payload.investigation_id).first()
            if inv and inv.repository_path and Path(inv.repository_path).is_dir():
                target_path = Path(inv.repository_path).resolve()
            elif inv and inv.file and Path(inv.file).is_file():
                target_path = Path(inv.file).resolve().parent

    if not target_path or not target_path.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Target repository directory does not exist: {payload.target_repo_dir}",
        )

    # Capture pre-patch file snapshots for user-initiated rollback
    diff = report.fix_proposal.diff
    try:
        from app.services.patcher import parse_unified_diff
        import json
        hunks_map = parse_unified_diff(diff)
        backups: Dict[str, str] = {}
        for rel_p in hunks_map.keys():
            t_f = (target_path / rel_p).resolve()
            if not t_f.is_file():
                candidates = list(target_path.rglob(Path(rel_p).name))
                if candidates:
                    t_f = candidates[0]
            if t_f.is_file():
                backups[str(t_f)] = t_f.read_text(encoding="utf-8", errors="replace")

        # Apply patch with atomic rollback on failure
        modified_files = apply_patch_to_directory(str(target_path), diff)

        # Store backup snapshot in memory registry and persistent disk storage for rollback
        registry_key = f"{payload.investigation_id}:{str(target_path)}"
        _ROLLBACK_REGISTRY[registry_key] = backups

        backup_dir = Path("scratch/rollback_snapshots")
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_file = backup_dir / f"{payload.investigation_id}.json"
        try:
            backup_file.write_text(json.dumps(backups), encoding="utf-8")
        except Exception:
            pass

        return {
            "status": "applied",
            "user_approved": True,
            "modified_files": modified_files,
            "rollback_available": True,
            "message": f"Successfully applied patch to {len(modified_files)} file(s).",
        }
    except PatchError as p_err:
        raise HTTPException(status_code=400, detail=f"Patch application failed: {str(p_err)}") from p_err
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal error applying patch: {str(exc)}") from exc


@router.post("/rollback")
def rollback_patch_endpoint(payload: RollbackPatchRequest):
    """Roll back an applied patch to its exact pre-patch state using stored backup snapshots."""
    target_path = Path(payload.target_repo_dir).resolve() if payload.target_repo_dir else None
    registry_key = f"{payload.investigation_id}:{str(target_path)}" if target_path else payload.investigation_id

    backups = _ROLLBACK_REGISTRY.get(registry_key)
    if not backups:
        # Check fallback by investigation_id prefix in registry
        for k, v in _ROLLBACK_REGISTRY.items():
            if k.startswith(f"{payload.investigation_id}:"):
                backups = v
                registry_key = k
                break

    # If not in memory registry, check persistent disk snapshot
    if not backups:
        import json
        backup_file = Path("scratch/rollback_snapshots") / f"{payload.investigation_id}.json"
        if backup_file.is_file():
            try:
                backups = json.loads(backup_file.read_text(encoding="utf-8"))
            except Exception:
                backups = None

    if not backups:
        raise HTTPException(
            status_code=404,
            detail="No rollback snapshot found for this investigation and repository.",
        )

    reverted_files = []
    for f_path_str, orig_content in backups.items():
        f_path = Path(f_path_str)
        try:
            f_path.write_text(orig_content, encoding="utf-8")
            reverted_files.append(f_path.name)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed reverting {f_path}: {exc}") from exc

    # Clean up from memory registry and disk
    if registry_key in _ROLLBACK_REGISTRY:
        del _ROLLBACK_REGISTRY[registry_key]
    backup_file = Path("scratch/rollback_snapshots") / f"{payload.investigation_id}.json"
    if backup_file.is_file():
        try:
            backup_file.unlink()
        except Exception:
            pass

    return {
        "status": "rolled_back",
        "reverted_files": reverted_files,
        "message": f"Successfully reverted {len(reverted_files)} file(s) to original pre-patch state.",
    }
