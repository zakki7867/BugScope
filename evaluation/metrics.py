"""Evaluation metrics calculations and markdown reporting for BugScope benchmark."""

from pathlib import Path
from typing import Any, Dict, List
from pydantic import BaseModel, Field


class EvaluationMetrics(BaseModel):
    """Aggregated benchmark evaluation metrics."""
    mode: str = Field(..., description="Evaluation mode: 'bugscope' or 'baseline_single_prompt'")
    total_bugs: int = Field(default=0, description="Total benchmark bug projects evaluated")
    top1_root_cause_accuracy: float = Field(
        default=0.0, description="Fraction of runs where top hypothesis matched ground truth (0.0 to 1.0)"
    )
    top3_root_cause_accuracy: float = Field(
        default=0.0, description="Fraction of runs where ground truth was in top 3 hypotheses (0.0 to 1.0)"
    )
    evidence_verified_rate: float = Field(
        default=0.0, description="Ratio of verified evidence items to total generated evidence items"
    )
    regression_test_executes_rate: float = Field(
        default=0.0, description="Fraction of synthesized regression tests that executed cleanly"
    )
    fix_validated_rate: float = Field(
        default=0.0, description="Fraction of runs reaching final 'validated' verdict"
    )
    avg_seconds: float = Field(default=0.0, description="Mean end-to-end execution latency per bug")
    avg_cost_usd: float = Field(default=0.0, description="Mean dollar cost per bug")
    verdict_counts: Dict[str, int] = Field(
        default_factory=dict, description="Count of occurrences for each verdict"
    )


def compute_metrics(
    mode: str,
    results: List[Dict[str, Any]],
) -> EvaluationMetrics:
    """Compute aggregate metrics from individual bug evaluation results."""
    if not results:
        return EvaluationMetrics(mode=mode)

    n = len(results)
    top1_matches = 0
    top3_matches = 0
    total_evidence_generated = 0
    total_evidence_verified = 0
    regression_executed_count = 0
    validated_count = 0
    total_seconds = 0.0
    total_cost = 0.0
    verdict_counts: Dict[str, int] = {
        "validated": 0,
        "partially_validated": 0,
        "not_validated": 0,
        "could_not_reproduce": 0,
        "needs_human_decision": 0,
    }

    for item in results:
        gt = item.get("ground_truth", {})
        gt_category = gt.get("root_cause_category", "").lower()
        gt_file = gt.get("file", "").lower()

        # Check hypotheses matching
        hypotheses = item.get("hypotheses", [])
        if hypotheses:
            top = hypotheses[0]
            top_text = f"{top.get('title', '')} {top.get('explanation', '')}".lower()
            if gt_category in top_text or Path(gt_file).name.lower() in top_text:
                top1_matches += 1

            in_top3 = False
            for h in hypotheses[:3]:
                h_text = f"{h.get('title', '')} {h.get('explanation', '')}".lower()
                if gt_category in h_text or Path(gt_file).name.lower() in h_text:
                    in_top3 = True
                    break
            if in_top3:
                top3_matches += 1

            for h in hypotheses:
                ev_list = h.get("evidence", [])
                total_evidence_generated += len(ev_list) + h.get("discarded_evidence_count", 0)
                total_evidence_verified += len(ev_list)

        # Check regression test execution
        if item.get("regression_test_executed"):
            regression_executed_count += 1

        # Check verdicts
        v = item.get("verdict", "not_validated")
        verdict_counts[v] = verdict_counts.get(v, 0) + 1
        if v == "validated":
            validated_count += 1

        total_seconds += item.get("duration_seconds", 0.0)
        total_cost += item.get("cost_usd", 0.0)

    ev_rate = (
        round(total_evidence_verified / total_evidence_generated, 3)
        if total_evidence_generated > 0
        else 1.0
    )

    return EvaluationMetrics(
        mode=mode,
        total_bugs=n,
        top1_root_cause_accuracy=round(top1_matches / n, 3),
        top3_root_cause_accuracy=round(top3_matches / n, 3),
        evidence_verified_rate=ev_rate,
        regression_test_executes_rate=round(regression_executed_count / n, 3),
        fix_validated_rate=round(validated_count / n, 3),
        avg_seconds=round(total_seconds / n, 2),
        avg_cost_usd=round(total_cost / n, 6),
        verdict_counts=verdict_counts,
    )


def format_markdown_table(
    bugscope_metrics: EvaluationMetrics,
    baseline_metrics: EvaluationMetrics,
) -> str:
    """Format side-by-side comparison markdown table."""
    return f"""| Metric | BugScope (Evidence-Checked) | Baseline (Single-Prompt LLM) |
| :--- | :---: | :---: |
| **Total Sample Size** | {bugscope_metrics.total_bugs} bugs | {baseline_metrics.total_bugs} bugs |
| **Top-1 Root Cause Accuracy** | **{bugscope_metrics.top1_root_cause_accuracy * 100:.1f}%** | {baseline_metrics.top1_root_cause_accuracy * 100:.1f}% |
| **Top-3 Root Cause Accuracy** | **{bugscope_metrics.top3_root_cause_accuracy * 100:.1f}%** | {baseline_metrics.top3_root_cause_accuracy * 100:.1f}% |
| **Evidence Verified Rate** | **{bugscope_metrics.evidence_verified_rate * 100:.1f}%** (mechanical disk check) | N/A (unverified quotes) |
| **Regression Test Execution Rate** | **{bugscope_metrics.regression_test_executes_rate * 100:.1f}%** | {baseline_metrics.regression_test_executes_rate * 100:.1f}% |
| **Fix Validated Rate (3-Phase Pass)** | **{bugscope_metrics.fix_validated_rate * 100:.1f}%** | {baseline_metrics.fix_validated_rate * 100:.1f}% |
| **Average Latency per Bug** | {bugscope_metrics.avg_seconds:.2f}s | {baseline_metrics.avg_seconds:.2f}s |
| **Average Cost per Bug** | ${bugscope_metrics.avg_cost_usd:.5f} | ${baseline_metrics.avg_cost_usd:.5f} |
"""
