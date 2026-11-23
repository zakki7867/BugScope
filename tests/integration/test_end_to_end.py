"""End-to-end integration test for BugScope workflow.

Acceptance Criterion 1:
A pasted KeyError plus a sample project produces a full report end to end.
"""

import pytest
from pathlib import Path

from app.database.db import get_investigation
from app.schemas.context import ContextBundle
from app.schemas.failure import FailureReport
from app.schemas.hypothesis import Hypothesis, EvidenceItem
from app.workflow.nodes.evidence_verifier import evidence_verifier
from app.workflow.nodes.failure_analyzer import failure_analyzer
from app.workflow.nodes.report_builder import report_builder
from app.workflow.nodes.repo_investigator import repo_investigator


def test_end_to_end_key_error_investigation(tmp_path):
    """Test full investigation pipeline from pasted KeyError to persisted InvestigationReport."""
    # 1. Set up a sample project directory
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    code = (
        "def get_user_email(user_data):\n"
        "    name = user_data['name']\n"
        "    email = user_data['email']\n"
        "    return f'{name}: {email}'\n"
    )
    (app_dir / "service.py").write_text(code, encoding="utf-8")

    # 2. Input: Pasted KeyError traceback
    raw_trace = """
Traceback (most recent call last):
  File "app/service.py", line 3, in get_user_email
    email = user_data['email']
KeyError: 'email'
"""

    # 3. Step 1: Failure Analyzer
    failure_rep = failure_analyzer(raw_trace)
    assert failure_rep.error_type == "KeyError"
    assert failure_rep.file == "app/service.py"
    assert failure_rep.line == 3
    assert failure_rep.function == "get_user_email"

    # 4. Step 2: Repo Investigator
    context_bun = repo_investigator(str(tmp_path), failure_rep)
    assert "app/service.py" in context_bun.failing_file
    assert context_bun.failing_symbol == "get_user_email"
    assert len(context_bun.snippets) >= 1

    # 5. Step 3: Evidence Verification on candidate hypotheses
    hypotheses = [
        Hypothesis(
            id=1,
            title="Missing email dictionary key",
            explanation="user_data dictionary is missing 'email' key on line 3",
            evidence=[
                EvidenceItem(
                    file="app/service.py",
                    line_start=3,
                    line_end=3,
                    quote="email = user_data['email']",
                    stance="supports",
                    reason="Directly looks up missing key 'email'",
                )
            ],
            is_upstream=False,
        ),
        Hypothesis(
            id=2,
            title="Upstream caller failed to populate email in user_data",
            explanation="Upstream registration form did not require email",
            evidence=[],
            is_upstream=True,
        ),
        Hypothesis(
            id=3,
            title="Hallucinated hypothesis",
            explanation="Fake theory",
            evidence=[
                EvidenceItem(
                    file="app/service.py",
                    line_start=20,
                    line_end=25,
                    quote="database.query()",  # Hallucinated!
                    stance="supports",
                    reason="Fake line",
                )
            ],
            is_upstream=False,
        ),
    ]

    ranked = evidence_verifier(str(tmp_path), hypotheses)
    assert len(ranked) == 3
    assert ranked[0].id == 1
    assert ranked[0].score == 1
    assert ranked[0].label == "supported"
    assert ranked[0].evidence[0].verified is True

    # Hallucinated hypothesis should have 0 verified evidence and be labeled unsupported
    h3_ranked = [h for h in ranked if h.id == 3][0]
    assert h3_ranked.label == "unsupported"
    assert h3_ranked.discarded_evidence_count == 1
    assert len(h3_ranked.evidence) == 0

    # 6. Step 4: Assemble master InvestigationReport and persist to SQLite
    db_file = str(tmp_path / "e2e_test.db")
    state = {
        "raw_trace": raw_trace,
        "repo_dir": str(tmp_path),
        "failure_report": failure_rep,
        "context_bundle": context_bun,
        "hypotheses": hypotheses,
        "ranked_hypotheses": ranked,
        "top_hypothesis": ranked[0],
        "verdict": "validated",
        "traces": [
            {
                "node": "failure_analyzer",
                "duration_ms": 5.0,
                "tokens_in": 0,
                "tokens_out": 0,
                "cost_usd": 0.0,
            },
            {
                "node": "repo_investigator",
                "duration_ms": 10.0,
                "tokens_in": 0,
                "tokens_out": 0,
                "cost_usd": 0.0,
            },
            {
                "node": "evidence_verifier",
                "duration_ms": 8.0,
                "tokens_in": 0,
                "tokens_out": 0,
                "cost_usd": 0.0,
            },
        ],
    }

    result = report_builder(state, db_path=db_file)
    master_report = result["investigation_report"]

    assert master_report.investigation_id is not None
    assert master_report.failure_report.error_type == "KeyError"
    assert master_report.verdict == "validated"
    assert len(master_report.hypotheses) == 3

    # 7. Verify persistent storage in SQLite
    loaded_report = get_investigation(master_report.investigation_id, db_path=db_file)
    assert loaded_report is not None
    assert loaded_report.investigation_id == master_report.investigation_id
    assert loaded_report.failure_report.error_type == "KeyError"
    assert loaded_report.failure_report.line == 3
