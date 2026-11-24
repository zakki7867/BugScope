"""Unit tests for evaluation metrics and evaluation benchmark runner."""

import pytest
from evaluation.metrics import compute_metrics, format_markdown_table, EvaluationMetrics
from evaluation.run import evaluate_bug_baseline, evaluate_bug_bugscope, BASE_BUGS_DIR
import json


def test_compute_metrics_empty():
    m = compute_metrics("bugscope", [])
    assert m.total_bugs == 0
    assert m.top1_root_cause_accuracy == 0.0


def test_compute_metrics_aggregation():
    sample_results = [
        {
            "bug_id": "bug_01_off_by_one",
            "ground_truth": {
                "file": "calc.py",
                "line": 10,
                "root_cause_category": "off-by-one",
            },
            "hypotheses": [
                {
                    "id": 1,
                    "title": "Root cause: off-by-one in calc.py",
                    "explanation": "Loop boundary issue",
                    "evidence": [{"file": "calc.py", "quote": "for i in range(n):"}],
                    "discarded_evidence_count": 0,
                }
            ],
            "verdict": "validated",
            "regression_test_executed": True,
            "duration_seconds": 1.5,
            "cost_usd": 0.001,
        },
        {
            "bug_id": "bug_02_key_error",
            "ground_truth": {
                "file": "lookup.py",
                "line": 5,
                "root_cause_category": "missing key",
            },
            "hypotheses": [
                {
                    "id": 1,
                    "title": "Unrelated issue",
                    "explanation": "some other theory",
                    "evidence": [],
                    "discarded_evidence_count": 1,
                },
                {
                    "id": 2,
                    "title": "Missing key in lookup.py",
                    "explanation": "lookup error",
                    "evidence": [{"file": "lookup.py", "quote": "return d[k]"}],
                    "discarded_evidence_count": 0,
                },
            ],
            "verdict": "not_validated",
            "regression_test_executed": False,
            "duration_seconds": 2.0,
            "cost_usd": 0.001,
        },
    ]

    metrics = compute_metrics("bugscope", sample_results)
    assert metrics.total_bugs == 2
    assert metrics.top1_root_cause_accuracy == 0.5
    assert metrics.top3_root_cause_accuracy == 1.0
    assert metrics.fix_validated_rate == 0.5
    assert metrics.regression_test_executes_rate == 0.5
    assert metrics.verdict_counts["validated"] == 1
    assert metrics.verdict_counts["not_validated"] == 1


def test_format_markdown_table():
    m_bs = EvaluationMetrics(
        mode="bugscope",
        total_bugs=20,
        top1_root_cause_accuracy=0.85,
        top3_root_cause_accuracy=1.0,
        evidence_verified_rate=0.95,
        regression_test_executes_rate=0.90,
        fix_validated_rate=0.85,
        avg_seconds=4.2,
        avg_cost_usd=0.002,
        verdict_counts={"validated": 17, "could_not_reproduce": 2, "needs_human_decision": 1},
    )
    m_bl = EvaluationMetrics(
        mode="baseline_single_prompt",
        total_bugs=20,
        top1_root_cause_accuracy=0.60,
        top3_root_cause_accuracy=0.60,
        evidence_verified_rate=0.0,
        regression_test_executes_rate=0.0,
        fix_validated_rate=0.55,
        avg_seconds=3.0,
        avg_cost_usd=0.001,
        verdict_counts={"validated": 11, "not_validated": 9},
    )

    table = format_markdown_table(m_bs, m_bl)
    assert "| Metric | BugScope (Evidence-Checked) | Baseline (Single-Prompt LLM) |" in table
    assert "Top-1 Root Cause Accuracy" in table
    assert "85.0%" in table


def test_evaluate_bug_baseline_structure():
    bug_dir = BASE_BUGS_DIR / "bug_01_off_by_one"
    if bug_dir.is_dir():
        gt = json.loads((bug_dir / "ground_truth.json").read_text(encoding="utf-8"))
        res = evaluate_bug_baseline(bug_dir, gt)
        assert res["bug_id"] == "bug_01_off_by_one"
        assert len(res["hypotheses"]) > 0
        assert res["regression_test_executed"] is False
