"""Unit tests for deterministic mechanical evidence verifier node."""

import pytest
from pathlib import Path

from app.schemas.hypothesis import EvidenceItem, Hypothesis
from app.workflow.nodes.evidence_verifier import (
    evidence_verifier,
    verify_quote_on_disk,
)


@pytest.fixture
def repo_with_code(tmp_path):
    """Create a temporary repo with known source lines for verification."""
    src_dir = tmp_path / "app"
    src_dir.mkdir()
    code = """
def process_order(user_id, items):
    if not items:
        raise ValueError("Empty items")
    total = sum(item['price'] for item in items)
    return {"user": user_id, "total": total}
"""
    (src_dir / "orders.py").write_text(code.strip(), encoding="utf-8")
    return tmp_path


def test_verify_quote_exact_match(repo_with_code):
    """Test verification passes for exact quote matching file on disk."""
    item = EvidenceItem(
        file="app/orders.py",
        line_start=3,
        line_end=4,
        quote='raise ValueError("Empty items")',
        stance="supports",
        reason="Checks for empty items and raises error",
    )
    assert verify_quote_on_disk(repo_with_code, item) is True


def test_verify_quote_whitespace_tolerance(repo_with_code):
    """Test verification normalizes whitespace differences."""
    item = EvidenceItem(
        file="app/orders.py",
        line_start=4,
        line_end=5,
        quote="total  =   sum( item['price']   for item in items )",
        stance="supports",
        reason="Calculates total with whitespace variation",
    )
    assert verify_quote_on_disk(repo_with_code, item) is True


def test_verify_quote_hallucination_rejection(repo_with_code):
    """Test fake or hallucinated quote is rejected."""
    item = EvidenceItem(
        file="app/orders.py",
        line_start=1,
        line_end=5,
        quote="def calculate_discount(discount_code):",
        stance="supports",
        reason="This function does not exist in the file",
    )
    assert verify_quote_on_disk(repo_with_code, item) is False


def test_verify_quote_mismatched_lines_rejection(repo_with_code):
    """Test quote that appears at lines 1-2 is rejected when claimed at lines 50-60."""
    item = EvidenceItem(
        file="app/orders.py",
        line_start=50,
        line_end=60,
        quote='raise ValueError("Empty items")',
        stance="supports",
        reason="Wrong line numbers",
    )
    assert verify_quote_on_disk(repo_with_code, item) is False


def test_evidence_verifier_ranking_and_discarding(repo_with_code):
    """Test mechanical scoring, evidence filtering, and ranking."""
    # Hypothesis 1: 2 verified supports, 0 contradicts -> Score = 2
    h1 = Hypothesis(
        id=1,
        title="Valid items check",
        explanation="Empty check raises ValueError",
        evidence=[
            EvidenceItem(
                file="app/orders.py",
                line_start=2,
                line_end=3,
                quote="if not items:",
                stance="supports",
                reason="Checks for empty list",
            ),
            EvidenceItem(
                file="app/orders.py",
                line_start=3,
                line_end=4,
                quote='raise ValueError("Empty items")',
                stance="supports",
                reason="Raises ValueError",
            ),
        ],
    )

    # Hypothesis 2: 1 verified support, 1 fake hallucinated quote -> Score = 1 (1 discarded)
    h2 = Hypothesis(
        id=2,
        title="Sum calculation",
        explanation="Sum iterates over dicts",
        evidence=[
            EvidenceItem(
                file="app/orders.py",
                line_start=4,
                line_end=5,
                quote="total = sum(item['price'] for item in items)",
                stance="supports",
                reason="Sums item prices",
            ),
            EvidenceItem(
                file="app/orders.py",
                line_start=10,
                line_end=12,
                quote="database.commit()",  # Hallucinated!
                stance="supports",
                reason="Fake database commit",
            ),
        ],
    )

    # Hypothesis 3: 0 verified supports -> Score = 0, label = unsupported
    h3 = Hypothesis(
        id=3,
        title="Hallucinated upstream bug",
        explanation="Upstream auth server crashed",
        evidence=[
            EvidenceItem(
                file="app/orders.py",
                line_start=1,
                line_end=2,
                quote="auth_token = verify_jwt()",  # Hallucinated!
                stance="supports",
                reason="Fake auth line",
            )
        ],
        is_upstream=True,
    )

    ranked = evidence_verifier(str(repo_with_code), [h2, h1, h3])

    assert len(ranked) == 3
    # h1 has score 2 -> rank 1
    assert ranked[0].id == 1
    assert ranked[0].score == 2
    assert ranked[0].label == "supported"
    assert ranked[0].rank == 1

    # h2 has score 1 -> rank 2, discarded count = 1
    assert ranked[1].id == 2
    assert ranked[1].score == 1
    assert ranked[1].label == "supported"
    assert ranked[1].discarded_evidence_count == 1
    assert len(ranked[1].evidence) == 1  # Hallucinated item was discarded!

    # h3 has score 0 -> rank 3, label = unsupported
    assert ranked[2].id == 3
    assert ranked[2].score == 0
    assert ranked[2].label == "unsupported"
    assert ranked[2].discarded_evidence_count == 1


def test_verify_quote_line_tolerance_correction(repo_with_code):
    """Test verification succeeds within +-2 lines tolerance and reports correction."""
    from app.workflow.nodes.evidence_verifier import verify_quote_details

    # Line 3 is: raise ValueError("Empty items")
    # LLM cited line_start=2, line_end=2 (off by 1 line)
    item = EvidenceItem(
        file="app/orders.py",
        line_start=2,
        line_end=2,
        quote='raise ValueError("Empty items")',
        stance="supports",
        reason="Checks for empty items",
    )
    is_valid, start, end, corrected, note = verify_quote_details(repo_with_code, item)
    assert is_valid is True
    assert corrected is True
    assert start == 3
    assert end == 3
    assert "tolerance" in note.lower()
