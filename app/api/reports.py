"""API endpoints for exporting investigation reports."""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse

from app.database.db import get_investigation

router = APIRouter(prefix="/api/reports", tags=["Reports"])


def _generate_markdown_report(report) -> str:
    """Format investigation report into human-readable GitHub Flavored Markdown."""
    top_h = report.top_hypothesis
    fix_status = report.fix_proposal.status if report.fix_proposal else "none"

    md = f"""# BugScope Investigation Report

**Investigation ID:** `{report.investigation_id}`  
**Created At:** {report.created_at}  
**Final Verdict:** `{report.verdict}`  
**Total Duration:** {report.total_duration_seconds}s  
**Total Estimated Cost:** ${report.total_cost_usd:.6f}  

---

## 1. Observed Failure
- **Error Type:** `{report.failure_report.error_type}`
- **Failing Location:** `{report.failure_report.file}:{report.failure_report.line}` in `{report.failure_report.function}`
- **Message:** `{report.failure_report.message}`
- **Category:** {report.failure_report.category} (Severity: {report.failure_report.severity})

---

## 2. Root Cause Hypothesis
"""
    if top_h:
        md += f"""- **Title:** {top_h.title}
- **Rank:** #{top_h.rank} (Verified Score: {top_h.score}, Label: `{top_h.label}`)
- **Upstream Root Cause:** {top_h.is_upstream}
- **Explanation:** {top_h.explanation}

### Mechanically Verified Code Evidence:
"""
        for ev in top_h.evidence:
            check = "PASS" if ev.verified else "REJECTED (Quote Mismatch / Hallucination)"
            md += f"""- `[{check}]` `{ev.file}:{ev.line_start}-{ev.line_end}` ({ev.stance.upper()}):
  > *"{ev.quote}"*  
  **Reason:** {ev.reason}  
"""
    else:
        md += "No hypothesis was supported by mechanically verified evidence.\n"

    md += "\n---\n\n## 3. Proposed Fix & Validation\n"
    if report.fix_proposal:
        if report.fix_proposal.status == "needs_human_decision":
            md += f"""**STATUS: NEEDS HUMAN DECISION**  
*Reason:* {report.fix_proposal.human_decision_reason}  
*Options:*  
"""
            for opt in report.fix_proposal.decision_options:
                md += f"- **{opt.choice}:** {opt.description}\n"
        else:
            md += f"""**Fix Explanation:** {report.fix_proposal.explanation}  

```diff
{report.fix_proposal.diff}
```
"""

    if report.validation_report:
        v = report.validation_report
        md += f"""
### 3-Phase Sandbox Validation:
1. **Pre-patch Reproduction:** {'PASS (Reproduced)' if v.reproduced_before else 'FAIL (Could not reproduce)'}
2. **Patch Applies Cleanly:** {'PASS' if v.patch_applies else 'FAIL'}
3. **Regression Test Passes:** {'PASS' if v.regression_passes_after else 'FAIL'}
4. **Existing Suite Regressions:** {'NONE (Safe)' if v.existing_suite_passes_after else 'REGRESSIONS DETECTED'}
"""

    return md


@router.get("/{investigation_id}")
def get_report(
    investigation_id: str,
    format: str = Query(default="json", pattern="^(json|markdown)$"),
):
    """Export investigation report as JSON or human-readable Markdown."""
    report = get_investigation(investigation_id)
    if not report:
        raise HTTPException(status_code=404, detail="Investigation not found.")

    if format == "markdown":
        md_text = _generate_markdown_report(report)
        return PlainTextResponse(content=md_text, media_type="text/markdown")

    return report
