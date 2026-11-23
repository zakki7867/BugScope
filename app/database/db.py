"""SQLAlchemy and SQLite persistence layer for BugScope investigations and execution traces.

Stores full investigation reports alongside indexed relational metadata
for rapid querying and dashboard history rendering.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import desc
from app.config import get_settings
from app.database.session import Base, SessionLocal, engine
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import (
    Investigation,
    Hypothesis as HypothesisModel,
    Evidence as EvidenceModel,
    Experiment as ExperimentModel,
    Patch as PatchModel,
    ValidationResult as ValidationResultModel,
    TraceLog as TraceLogModel,
)
from app.schemas.report import InvestigationReport, TraceEntry


def _get_engine_and_session(db_path: Optional[str] = None):
    if db_path:
        eng = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        sess = sessionmaker(autocommit=False, autoflush=False, bind=eng)
        return eng, sess
    return engine, SessionLocal


def init_db(db_path: Optional[str] = None) -> None:
    """Initialize database tables using SQLAlchemy Base metadata."""
    eng, _ = _get_engine_and_session(db_path)
    Base.metadata.create_all(bind=eng)


def save_investigation(
    report: InvestigationReport, db_path: Optional[str] = None
) -> str:
    """Persist an investigation report, its relational models, and node traces.

    Returns:
        The investigation_id of the saved record.
    """
    init_db(db_path)
    report_json_str = report.model_dump_json()

    eng, sess_cls = _get_engine_and_session(db_path)
    with sess_cls() as session:
        inv = session.query(Investigation).filter_by(id=report.investigation_id).first()
        if not inv:
            inv = Investigation(id=report.investigation_id)
            session.add(inv)

        inv.repository_name = Path(report.failure_report.file).parts[0] if report.failure_report.file else "unknown"
        inv.repository_path = report.failure_report.file or ""
        inv.error_type = report.failure_report.error_type
        inv.error_message = report.failure_report.message
        inv.stack_trace = getattr(report.failure_report, "raw_traceback", None) or ""
        inv.status = "COMPLETED"
        inv.verdict = report.verdict
        inv.summary = getattr(report.failure_report, "one_sentence_summary", None) or f"{report.failure_report.error_type}: {report.failure_report.message}"
        inv.root_cause_summary = report.top_hypothesis.title if report.top_hypothesis else None
        inv.total_duration_seconds = report.total_duration_seconds
        inv.total_cost_usd = report.total_cost_usd
        inv.report_json = report_json_str

        # Wipe previous children if re-saving
        session.query(HypothesisModel).filter_by(investigation_id=report.investigation_id).delete()
        session.query(EvidenceModel).filter_by(investigation_id=report.investigation_id).delete()
        session.query(ExperimentModel).filter_by(investigation_id=report.investigation_id).delete()
        session.query(PatchModel).filter_by(investigation_id=report.investigation_id).delete()
        session.query(ValidationResultModel).filter_by(investigation_id=report.investigation_id).delete()
        session.query(TraceLogModel).filter_by(investigation_id=report.investigation_id).delete()

        # Add hypotheses & evidence
        for hyp in report.hypotheses:
            hyp_id = str(hyp.id)
            h_obj = HypothesisModel(
                id=f"{report.investigation_id}_hyp_{hyp_id}",
                investigation_id=report.investigation_id,
                rank=getattr(hyp, "rank", 1),
                title=hyp.title,
                description=getattr(hyp, "explanation", hyp.title),
                likelihood_score=float(getattr(hyp, "score", 0.0)),
                is_upstream=getattr(hyp, "is_upstream", False),
                status="SELECTED" if (report.top_hypothesis and report.top_hypothesis.id == hyp.id) else "CANDIDATE",
            )
            session.add(h_obj)

            for ev in hyp.evidence:
                ev_id = f"ev_{uuid.uuid4().hex[:8]}"
                e_obj = EvidenceModel(
                    id=ev_id,
                    investigation_id=report.investigation_id,
                    hypothesis_id=h_obj.id,
                    file_path=ev.file,
                    line_start=ev.line_start,
                    line_end=ev.line_end,
                    code_quote=ev.quote,
                    stance=ev.stance,
                    reason=ev.reason,
                    is_verified=ev.verified,
                    verification_notes=getattr(ev, "verification_note", None),
                )
                session.add(e_obj)

        # Add patch if present
        patch_id = None
        if report.fix_proposal:
            patch_id = f"patch_{uuid.uuid4().hex[:8]}"
            p_obj = PatchModel(
                id=patch_id,
                investigation_id=report.investigation_id,
                hypothesis_id=f"{report.investigation_id}_hyp_{report.top_hypothesis.id}" if report.top_hypothesis else None,
                diff=report.fix_proposal.diff,
                explanation=report.fix_proposal.explanation,
                modified_files=json.dumps(getattr(report.fix_proposal, "modified_files", [report.failure_report.file])),
                is_minimal=True,
                needs_human_decision=(report.fix_proposal.status == "needs_human_decision"),
                human_decision_reason=report.fix_proposal.human_decision_reason,
            )
            session.add(p_obj)

        # Add validation if present
        if report.validation_report:
            v_obj = ValidationResultModel(
                id=f"val_{uuid.uuid4().hex[:8]}",
                investigation_id=report.investigation_id,
                patch_id=patch_id,
                pre_patch_reproduced=report.validation_report.reproduced_before,
                post_patch_passed=report.validation_report.patch_applies and report.validation_report.regression_passes_after,
                regression_suite_passed=report.validation_report.existing_suite_passes_after,
                status=report.validation_report.verdict,
                details=json.dumps({"failure_log": report.validation_report.failure_log}),
            )
            session.add(v_obj)

        # Add traces
        for tr in report.traces:
            t_obj = TraceLogModel(
                id=f"tr_{uuid.uuid4().hex[:8]}",
                investigation_id=report.investigation_id,
                node=tr.node,
                input_summary=tr.input_summary,
                output_summary=tr.output_summary,
                duration_ms=tr.duration_ms,
                tokens_in=tr.tokens_in,
                tokens_out=tr.tokens_out,
                cost_usd=tr.cost_usd,
            )
            session.add(t_obj)

        session.commit()

    return report.investigation_id


def get_investigation(
    investigation_id: str, db_path: Optional[str] = None
) -> Optional[InvestigationReport]:
    """Retrieve an investigation report by ID."""
    init_db(db_path)
    _, sess_cls = _get_engine_and_session(db_path)
    with sess_cls() as session:
        inv = session.query(Investigation).filter_by(id=investigation_id).first()
        if inv and inv.report_json:
            data = json.loads(inv.report_json)
            return InvestigationReport.model_validate(data)
    return None


def list_investigations(
    limit: int = 50, db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """List recent investigations metadata."""
    init_db(db_path)
    _, sess_cls = _get_engine_and_session(db_path)
    with sess_cls() as session:
        records = (
            session.query(Investigation)
            .order_by(desc(Investigation.created_at))
            .limit(limit)
            .all()
        )
        results = []
        for r in records:
            results.append({
                "id": r.id,
                "created_at": r.created_at.isoformat() if r.created_at else "",
                "verdict": r.verdict,
                "error_type": r.error_type or r.summary or "Unknown",
                "message": r.error_message or "",
                "file": r.repository_path or "",
                "line": 0,
                "total_duration_seconds": r.total_duration_seconds or 0.0,
                "total_cost_usd": r.total_cost_usd or 0.0,
            })
        return results
