"""Deterministic mechanical evidence verifier node.

Verifies that code quotes cited by the LLM in root-cause hypotheses genuinely exist
on disk at the stated files and line numbers.

Rules:
1. Normalize whitespace when comparing quotes to on-disk code.
2. Mark verified quotes as verified=True; discard unverified/hallucinated items.
3. Score each hypothesis: count(verified supports) - count(verified contradicts).
4. Rank hypotheses descending by score.
5. If verified supports == 0, label as 'unsupported'.
6. Do NOT output percentages.
No LLM calls are made in this node.
"""

import re
from pathlib import Path
from typing import List, Tuple

from app.schemas.hypothesis import EvidenceItem, Hypothesis, RankedHypothesis


def _normalize_whitespace(text: str) -> str:
    """Normalize whitespace and strip whitespace around code syntax operators."""
    # 1. Collapse multiple spaces into one
    s = re.sub(r"\s+", " ", text).strip()
    # 2. Strip whitespace around syntax delimiters and operators
    s = re.sub(r"\s*([()\[\]{},:=+\-*/<>!&|])\s*", r"\1", s)
    return s


def verify_quote_on_disk(repo_path: Path, item: EvidenceItem) -> bool:
    """Mechanically verify whether item.quote appears at item.file between line_start and line_end."""
    clean_file = item.file.replace("\\", "/").strip().lstrip("/")
    target_file = (repo_path / clean_file).resolve()

    # If direct resolution fails, try finding matching file in repo
    if not target_file.is_file():
        candidates = list(repo_path.rglob(Path(clean_file).name))
        if candidates:
            target_file = candidates[0]
        else:
            return False

    try:
        content = target_file.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
    except Exception:
        return False

    # Guard line boundaries (1-indexed)
    if item.line_start < 1 or item.line_end < item.line_start or item.line_start > len(lines):
        return False

    # Extract target slice with small margin (+-1 line) to tolerate minor boundary offsets
    slice_start = max(1, item.line_start - 1)
    slice_end = min(len(lines), item.line_end + 1)
    actual_excerpt = "\n".join(lines[slice_start - 1 : slice_end])

    norm_excerpt = _normalize_whitespace(actual_excerpt)
    norm_quote = _normalize_whitespace(item.quote)

    if not norm_quote:
        return False

    # Check for containment
    return norm_quote in norm_excerpt or norm_excerpt in norm_quote


def evidence_verifier(
    repo_dir: str,
    hypotheses: List[Hypothesis],
) -> List[RankedHypothesis]:
    """Verify evidence items mechanically on disk and rank hypotheses by verified score.

    Args:
        repo_dir: Absolute path of project repository.
        hypotheses: List of candidate hypotheses from hypothesis_generator.

    Returns:
        List of RankedHypothesis sorted descending by score.
    """
    repo_path = Path(repo_dir).resolve()
    ranked_list: List[RankedHypothesis] = []

    for hyp in hypotheses:
        verified_items: List[EvidenceItem] = []
        discarded_count = 0

        for item in hyp.evidence:
            is_valid = verify_quote_on_disk(repo_path, item)
            if is_valid:
                verified_item = item.model_copy(update={"verified": True})
                verified_items.append(verified_item)
            else:
                discarded_count += 1

        v_supp = sum(1 for e in verified_items if e.stance == "supports")
        v_contra = sum(1 for e in verified_items if e.stance == "contradicts")
        score = v_supp - v_contra

        # A hypothesis with zero verified supporting evidence is strictly unsupported
        label = "supported" if v_supp > 0 else "unsupported"

        ranked_hyp = RankedHypothesis(
            id=hyp.id,
            title=hyp.title,
            explanation=hyp.explanation,
            evidence=verified_items,  # Discarded hallucinated items are removed
            score=score,
            label=label,
            is_upstream=hyp.is_upstream,
            verified_support_count=v_supp,
            verified_contradict_count=v_contra,
            discarded_evidence_count=discarded_count,
        )
        ranked_list.append(ranked_hyp)

    # Sort descending by score, tie-breaking by verified_support_count
    ranked_list.sort(key=lambda h: (h.score, h.verified_support_count), reverse=True)

    # Assign rank numbers 1, 2, ...
    for idx, rh in enumerate(ranked_list, start=1):
        rh.rank = idx

    return ranked_list
