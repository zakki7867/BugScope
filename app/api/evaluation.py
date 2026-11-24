"""API endpoints for benchmark suites and evaluation harness."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field

from evaluation.metrics import compute_metrics, EvaluationMetrics

router = APIRouter(prefix="/api/evaluation", tags=["Evaluation"])


@router.get("/benchmarks")
def list_benchmarks():
    """List all seeded benchmark bugs, categories, and ground truth definitions."""
    benchmarks_dir = Path("sample_bugs")
    cases = []
    if benchmarks_dir.is_dir():
        for bug_folder in sorted(benchmarks_dir.iterdir()):
            if bug_folder.is_dir():
                gt_file = bug_folder / "ground_truth.json"
                if gt_file.is_file():
                    try:
                        gt_data = json.loads(gt_file.read_text(encoding="utf-8"))
                        cases.append({
                            "bug_id": bug_folder.name,
                            "category": gt_data.get("root_cause_category") or gt_data.get("category", "General"),
                            "description": gt_data.get("notes") or gt_data.get("description", bug_folder.name),
                            "failing_test": gt_data.get("failing_test", ""),
                            "is_upstream": gt_data.get("is_upstream", False),
                            "is_ambiguous": gt_data.get("is_ambiguous", False),
                            "expected_verdict": gt_data.get("expected_verdict", "validated"),
                        })
                    except Exception:
                        pass
    return {"total_cases": len(cases), "cases": cases}


@router.get("/results")
def get_evaluation_results():
    """Retrieve the latest benchmark evaluation results and baseline comparison metrics."""
    res_file = Path("evaluation/results.json")
    if not res_file.is_file():
        return {
            "status": "not_run",
            "message": "Evaluation has not yet been executed. Run POST /api/evaluation/run.",
        }

    try:
        data = json.loads(res_file.read_text(encoding="utf-8"))
        return data
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed reading evaluation results: {exc}")
