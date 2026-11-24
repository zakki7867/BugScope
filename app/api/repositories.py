"""API endpoints for repository uploads, file navigation, and AST tools."""

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from app.services.zip_handler import create_temp_repo_from_zip, ZipSecurityError
from app.tools.code_search import search_code
from app.tools.repository_tools import (
    get_file_content,
    get_function_info,
    get_class_info,
    find_related_tests,
    dependency_analysis,
)

router = APIRouter(prefix="/api/repositories", tags=["Repositories"])


def _validate_safe_repo_dir(raw_path: str) -> Path:
    """Validate that repository path exists and does not escape allowed workspace/temp roots."""
    p = Path(raw_path).resolve()
    if not p.is_dir():
        raise HTTPException(status_code=404, detail="Repository path not found.")

    allowed_roots = [
        Path.cwd().resolve(),
        Path(tempfile.gettempdir()).resolve(),
    ]
    is_safe = False
    for root in allowed_roots:
        try:
            p.relative_to(root)
            is_safe = True
            break
        except ValueError:
            continue
    if not is_safe:
        raise HTTPException(
            status_code=403,
            detail="Access forbidden: Specified repository path is outside allowed workspace boundaries.",
        )
    return p


class CodeSearchRequest(BaseModel):
    """Payload for code search query."""
    repo_path: str = Field(..., description="Path to repository")
    query: str = Field(..., description="Search keyword or regex")
    file_pattern: Optional[str] = Field(default="*.py", description="Glob pattern")
    max_results: int = Field(default=20, ge=1, le=100)


@router.post("/upload")
async def upload_repository_zip(file: UploadFile = File(...)):
    """Upload and safely extract a ZIP archive of a Python repository."""
    try:
        zip_bytes = await file.read()
        extracted_dir = create_temp_repo_from_zip(zip_bytes)
        repo_path = Path(extracted_dir)

        # Build initial file tree
        files = []
        for p in repo_path.rglob("*"):
            if p.is_file():
                rel = str(p.relative_to(repo_path)).replace("\\", "/")
                files.append(rel)

        return {
            "repository_id": repo_path.name,
            "repository_path": str(repo_path),
            "filename": file.filename,
            "total_files": len(files),
            "files": sorted(files),
        }
    except ZipSecurityError as z_err:
        raise HTTPException(status_code=400, detail=f"ZIP security violation: {str(z_err)}") from z_err
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to process ZIP upload: {str(exc)}") from exc


@router.get("/list")
@router.get("/sample-bugs")
def list_repositories():
    """List seeded benchmark bug repositories and available sample projects."""
    sample_bugs_dir = Path(__file__).resolve().parent.parent.parent / "sample_bugs"
    if not sample_bugs_dir.is_dir():
        sample_bugs_dir = Path("sample_bugs")
    available = []
    if sample_bugs_dir.is_dir():
        for bug_dir in sorted(sample_bugs_dir.iterdir()):
            if bug_dir.is_dir():
                gt_path = bug_dir / "ground_truth.json"
                category = "Unknown"
                description = bug_dir.name
                sample_trace = ""
                if gt_path.is_file():
                    try:
                        data = json.loads(gt_path.read_text(encoding="utf-8"))
                        category = data.get("root_cause_category") or data.get("category", "General")
                        description = data.get("notes") or data.get("description", bug_dir.name)
                        failing_f = data.get("file", "app/main.py")
                        failing_l = data.get("line", 1)
                        sample_trace = (
                            f"Traceback (most recent call last):\n"
                            f'  File "{failing_f}", line {failing_l}, in run\n'
                            f"{category}: {description}"
                        )
                    except Exception:
                        pass
                available.append({
                    "id": bug_dir.name,
                    "name": bug_dir.name.replace("_", " ").title(),
                    "path": str(bug_dir.resolve()).replace("\\", "/"),
                    "category": category,
                    "description": description,
                    "sample_trace": sample_trace,
                })
    return {"repositories": available, "bugs": available}


@router.get("/tree")
def get_repository_tree(path: str = Query(..., description="Repository root path")):
    """Get recursive directory and file hierarchy of a repository."""
    repo_path = _validate_safe_repo_dir(path)

    tree = []
    for item in repo_path.rglob("*"):
        parts = item.parts
        if any(p.startswith(".") or p in ("__pycache__", "venv", "node_modules") for p in parts):
            continue
        rel = str(item.relative_to(repo_path)).replace("\\", "/")
        tree.append({
            "path": rel,
            "name": item.name,
            "is_dir": item.is_dir(),
            "size_bytes": item.stat().st_size if item.is_file() else 0,
        })
    return {"repository_path": str(repo_path), "tree": sorted(tree, key=lambda x: (not x["is_dir"], x["path"]))}


@router.get("/file")
def get_file(
    repo_path: str = Query(..., description="Repository root"),
    file_path: str = Query(..., description="Relative file path"),
    start_line: Optional[int] = Query(default=None),
    end_line: Optional[int] = Query(default=None),
):
    """Retrieve file content and numbered lines."""
    safe_repo = _validate_safe_repo_dir(repo_path)
    sl = start_line if isinstance(start_line, int) else None
    el = end_line if isinstance(end_line, int) else None
    res = get_file_content(
        repo_path=safe_repo,
        file_path=file_path,
        start_line=sl,
        end_line=el,
    )
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res


@router.post("/search")
def search_repository_code(payload: CodeSearchRequest):
    """Search code across files in repository using AST / regex."""
    repo_path = _validate_safe_repo_dir(payload.repo_path)
    matches = search_code(
        repo_path=repo_path,
        query=payload.query,
        file_pattern=payload.file_pattern,
        max_results=payload.max_results,
    )
    return {"query": payload.query, "matches_count": len(matches), "matches": matches}


@router.get("/function-info")
def inspect_function(
    repo_path: str = Query(...),
    file_path: str = Query(...),
    function_name: str = Query(...),
):
    """Extract AST docstring, arguments, decorators, and body for a function."""
    safe_repo = _validate_safe_repo_dir(repo_path)
    res = get_function_info(safe_repo, file_path, function_name)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res


@router.get("/related-tests")
def inspect_related_tests(
    repo_path: str = Query(...),
    symbol: str = Query(...),
):
    """Locate tests referencing a given module or symbol."""
    safe_repo = _validate_safe_repo_dir(repo_path)
    res = find_related_tests(safe_repo, symbol)
    return {"symbol": symbol, "tests": res}
