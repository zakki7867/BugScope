"""Deterministic mechanical evidence verifier node.

Verifies that code quotes cited by the LLM in root-cause hypotheses genuinely exist
on disk at the stated files and line numbers.

Rules:
1. Normalize whitespace when comparing quotes to on-disk code.
2. If quote matches exactly at stated lines: mark verified=True.
3. If quote matches within +-2 lines tolerance: accept and adjust range (range_corrected=True).
4. Discard unverified or hallucinated items.
5. Score each hypothesis: count(verified supports) - count(verified contradicts).
6. Rank hypotheses descending by score; if verified supports == 0, label as 'unsupported'.
No LLM calls are made in this node.
"""

import re
from pathlib import Path
from typing import List, Optional, Tuple

from app.schemas.hypothesis import EvidenceItem, Hypothesis, RankedHypothesis

LINE_TOLERANCE = 2
MIN_QUOTE_CHARS = 4


def _normalize_whitespace(text: str) -> str:
    """Normalize whitespace and strip whitespace around code syntax operators."""
    s = re.sub(r"\s+", " ", text).strip()
    s = re.sub(r"\s*([()\[\]{},:=+\-*/<>!&|])\s*", r"\1", s)
    return s


def verify_quote_details(
    repo_path: Path, item: EvidenceItem
) -> Tuple[bool, int, int, bool, Optional[str]]:
    """Mechanically verify whether item.quote appears at item.file.

    Returns:
        (is_verified, actual_line_start, actual_line_end, range_corrected, note)
    """
    clean_file = item.file.replace("\\", "/").strip().lstrip("/")
    target_file = (repo_path / clean_file).resolve()

    # If direct resolution fails, try finding matching file in repo
    if not target_file.is_file():
        candidates = list(repo_path.rglob(Path(clean_file).name))
        if candidates:
            target_file = candidates[0]
            clean_file = str(target_file.relative_to(repo_path)).replace("\\", "/")
        else:
            return False, item.line_start, item.line_end, False, f"File '{clean_file}' not found."

    norm_quote = _normalize_whitespace(item.quote)
    if len(norm_quote) < MIN_QUOTE_CHARS:
        return False, item.line_start, item.line_end, False, "Quote too short to verify."

    try:
        content = target_file.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
    except Exception as exc:
        return False, item.line_start, item.line_end, False, f"Read error: {exc}"

    if not lines:
        return False, item.line_start, item.line_end, False, "File is empty."

    # Guard against invalid or wildly out-of-range line claims
    if item.line_start > len(lines) + LINE_TOLERANCE or item.line_end < 1 - LINE_TOLERANCE:
        return False, item.line_start, item.line_end, False, "Stated line range is outside file bounds."

    start = max(1, min(len(lines), item.line_start))
    end = max(start, min(len(lines), item.line_end))

    # 1. Check exact stated slice
    actual_excerpt = "\n".join(lines[start - 1 : end])
    norm_excerpt = _normalize_whitespace(actual_excerpt)
    if norm_quote in norm_excerpt:
        return True, start, end, False, "Exact line match verified."

    # 2. Tolerance window search (+- LINE_TOLERANCE lines)
    lo = max(1, item.line_start - LINE_TOLERANCE)
    hi = min(len(lines), item.line_end + LINE_TOLERANCE)
    best_range = None

    if lo <= hi:
        for a in range(lo, hi + 1):
            for b in range(a, hi + 1):
                window_text = "\n".join(lines[a - 1 : b])
                norm_window = _normalize_whitespace(window_text)
                if norm_quote in norm_window:
                    if best_range is None or (b - a) < (best_range[1] - best_range[0]):
                        best_range = (a, b)
                    break

    if best_range:
        return (
            True,
            best_range[0],
            best_range[1],
            True,
            f"Quote located within +-2 lines tolerance at lines {best_range[0]}-{best_range[1]}.",
        )

    return False, item.line_start, item.line_end, False, "Quote not found on disk at stated lines."


def verify_quote_on_disk(repo_path: Path, item: EvidenceItem) -> bool:
    """Check if an evidence quote is verified on disk at the stated location.

    Returns boolean True if verified (with or without line tolerance), False otherwise.
    """
    is_valid, _, _, _, _ = verify_quote_details(repo_path, item)
    return is_valid


def evidence_verifier(
    repo_dir: str,
    hypotheses: List[Hypothesis],
) -> List[RankedHypothesis]:
    """Verify evidence items mechanically on disk and rank hypotheses by verified score."""
    repo_path = Path(repo_dir).resolve()
    ranked_list: List[RankedHypothesis] = []

    for hyp in hypotheses:
        verified_items: List[EvidenceItem] = []
        discarded_count = 0

        for item in hyp.evidence:
            is_valid, actual_start, actual_end, corrected, note = verify_quote_details(
                repo_path, item
            )
            if is_valid:
                verified_item = item.model_copy(
                    update={
                        "verified": True,
                        "line_start": actual_start,
                        "line_end": actual_end,
                        "range_corrected": corrected,
                        "verification_note": note,
                    }
                )
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
            evidence=verified_items,
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

    for idx, rh in enumerate(ranked_list, start=1):
        rh.rank = idx

    return ranked_list
