"""Quickstart CLI runner for BugScope investigations.

Usage:
    python run_investigation.py
    python run_investigation.py --bug sample_bugs/bug_01_key_error
    python run_investigation.py --trace "KeyError: 'user_id' at app/main.py:10"
"""

import argparse
import json
import sys
from pathlib import Path

from app.workflow.graph import create_bugscope_graph


def main():
    parser = argparse.ArgumentParser(description="Run a BugScope debugging investigation.")
    parser.add_argument(
        "--bug",
        type=str,
        default="sample_bugs/bug_01_key_error",
        help="Path to target project directory (default: sample_bugs/bug_01_key_error)",
    )
    parser.add_argument(
        "--trace",
        type=str,
        default=None,
        help="Optional raw traceback or error string (default: read from bug project tests)",
    )
    args = parser.parse_args()

    repo_path = Path(args.bug).resolve()
    if not repo_path.is_dir():
        print(f"Error: Directory '{args.bug}' does not exist.")
        sys.exit(1)

    raw_trace = args.trace
    if not raw_trace:
        # Default sample traceback for the bug
        raw_trace = """
Traceback (most recent call last):
  File "app/user.py", line 4, in format_user_profile
    email = user_dict['email']
KeyError: 'email'
""".strip()

    print("\n" + "=" * 60)
    print("  🔬 BugScope — Evidence-Checked Debugging Agent")
    print(f"  Target Repository: {repo_path}")
    print("=" * 60 + "\n")

    print("Running investigation pipeline through LangGraph...")
    from app.config import get_settings
    settings = get_settings()

    if not settings.api_key:
        print("[Notice] BUGSCOPE_API_KEY is not set in .env. Running in offline evidence-check demo mode.")
        from app.workflow.nodes.failure_analyzer import failure_analyzer
        from app.workflow.nodes.repo_investigator import repo_investigator
        from app.workflow.nodes.evidence_verifier import evidence_verifier
        from app.workflow.nodes.report_builder import report_builder
        from app.schemas.hypothesis import Hypothesis, EvidenceItem
        from app.schemas.fix import FixProposal, RegressionTest
        from app.schemas.validation import ValidationReport

        fail_rep = failure_analyzer(raw_trace)
        bundle = repo_investigator(str(repo_path), fail_rep)

        # Extract authentic code quote from file
        target_f = repo_path / fail_rep.file
        real_quote = "email = user_dict['email']"
        if target_f.is_file():
            flines = target_f.read_text(encoding="utf-8").splitlines()
            if fail_rep.line <= len(flines):
                real_quote = flines[fail_rep.line - 1].strip()

        hypotheses = [
            Hypothesis(
                id=1,
                title=f"Missing key in dictionary at {fail_rep.file}:{fail_rep.line}",
                explanation=f"Directly indexing key without validation raises {fail_rep.error_type}",
                evidence=[
                    EvidenceItem(
                        file=fail_rep.file,
                        line_start=fail_rep.line,
                        line_end=fail_rep.line,
                        quote=real_quote,
                        stance="supports",
                        reason=f"Code directly indexes missing key at line {fail_rep.line}",
                    )
                ],
                is_upstream=False,
            ),
            Hypothesis(
                id=2,
                title="Upstream caller failed to pass complete dictionary",
                explanation="Caller function constructed user_dict without required keys",
                evidence=[],
                is_upstream=True,
            ),
            Hypothesis(
                id=3,
                title="Corrupted session cache state",
                explanation="Session cache returned partial object",
                evidence=[
                    EvidenceItem(
                        file=fail_rep.file,
                        line_start=999,
                        line_end=1000,
                        quote="cache.get_unverified()",  # Hallucinated!
                        stance="supports",
                        reason="Fake cache line",
                    )
                ],
                is_upstream=False,
            ),
        ]

        ranked = evidence_verifier(str(repo_path), hypotheses)
        fix = FixProposal(
            status="proposed",
            diff=f"--- a/{fail_rep.file}\n+++ b/{fail_rep.file}\n@@ -{fail_rep.line},1 +{fail_rep.line},1 @@\n-{real_quote}\n+email = user_dict.get('email', 'N/A')\n",
            assumptions=["Missing email key should default to 'N/A'"],
            side_effects=["Consumers must handle 'N/A' placeholder value"],
        )
        reg_test = RegressionTest(
            test_code="def test_regression():\n    assert format_user_profile({'name': 'Bob'}) == 'Bob <N/A>'\n",
            target_path="tests/test_regression.py",
        )
        val = ValidationReport(
            regression_fails_before=True,
            regression_passes_after=True,
            existing_suite_result="passed",
            retries_used=0,
            duration_seconds=1.2,
            verdict="validated",
        )

        state = {
            "raw_trace": raw_trace,
            "repo_dir": str(repo_path),
            "failure_report": fail_rep,
            "context_bundle": bundle,
            "hypotheses": hypotheses,
            "ranked_hypotheses": ranked,
            "top_hypothesis": ranked[0],
            "fix_proposal": fix,
            "regression_test": reg_test,
            "validation_report": val,
            "traces": [
                {"node": "failure_analyzer", "duration_ms": 12.0, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0},
                {"node": "repo_investigator", "duration_ms": 45.0, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0},
                {"node": "evidence_verifier", "duration_ms": 18.0, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0},
                {"node": "validator", "duration_ms": 250.0, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0},
            ],
        }
        res = report_builder(state)
        report = res["investigation_report"]
    else:
        graph = create_bugscope_graph()
        initial_state = {
            "raw_trace": raw_trace,
            "repo_dir": str(repo_path),
            "traces": [],
            "retries_used": 0,
            "max_retries": 2,
        }
        result = graph.invoke(initial_state)
        report = result.get("investigation_report")

    if not report:
        print("Error: Workflow completed without generating an investigation report.")
        sys.exit(1)

    print("\n" + "-" * 60)
    print(f"  INVESTIGATION REPORT: {report.investigation_id}")
    print(f"  VERDICT: [{report.verdict.upper()}]")
    print("-" * 60)

    f = report.failure_report
    print(f"\n[1] Failure Analysis:")
    print(f"    - Error Type : {f.error_type} ({f.category})")
    print(f"    - Message    : {f.message}")
    print(f"    - Location   : {f.file}:{f.line} in {f.function}()")

    if report.reproduction_result:
        r = report.reproduction_result
        print(f"\n[2] Pre-Fix Sandbox Baseline:")
        print(f"    - Reproduced : {'YES' if r.reproduced else 'NO'}")
        print(f"    - Command    : {r.command}")
        print(f"    - Trust Level: {r.trust_level}")

    print(f"\n[3] Mechanically Ranked Hypotheses ({len(report.hypotheses)} total):")
    for h in report.hypotheses:
        tag = "TOP RANKED" if report.top_hypothesis and report.top_hypothesis.id == h.id else f"Rank #{h.rank}"
        label_icon = "[SUPPORTED]" if h.label == "supported" else "[UNSUPPORTED]"
        upstream_info = " (Upstream Cause)" if h.is_upstream else ""
        print(f"    • {tag}: {h.title}{upstream_info}")
        print(f"      Score: {h.score} {label_icon} | Verified Supports: {h.verified_support_count} | Hallucinations Discarded: {h.discarded_evidence_count}")
        for ev in h.evidence:
            print(f"        - Verified quote at {ev.file}:{ev.line_start}-{ev.line_end} [{ev.stance.upper()}]: \"{ev.quote}\"")

    if report.fix_proposal:
        fp = report.fix_proposal
        print(f"\n[4] Proposed Patch Status: [{fp.status.upper()}]")
        if fp.diff:
            print("    Unified Diff:")
            for line in fp.diff.strip().splitlines():
                print(f"      {line}")
        if fp.options_if_ambiguous:
            print("    Human Decision Options:")
            for opt in fp.options_if_ambiguous:
                print(f"      - {opt}")

    if report.validation_report:
        vr = report.validation_report
        print(f"\n[5] 3-Phase Mechanical Validation:")
        print(f"    - Phase 1 (Regression Fails Before Patch) : {'PASS' if vr.regression_fails_before else 'FAIL'}")
        print(f"    - Phase 2 (Regression Passes After Patch) : {'PASS' if vr.regression_passes_after else 'FAIL'}")
        print(f"    - Phase 3 (Existing Test Suite Regressions): {vr.existing_suite_result.upper()}")

    print(f"\n[6] Telemetry & Costs:")
    print(f"    - Wall-Clock Runtime : {report.total_duration_seconds}s")
    print(f"    - LLM Prompt Tokens  : {report.total_tokens_in}")
    print(f"    - LLM Output Tokens  : {report.total_tokens_out}")
    print(f"    - Estimated Run Cost : ${report.total_cost_usd:.6f}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
