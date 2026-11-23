"""SQLite persistence layer for BugScope investigations and execution traces.

Stores full investigation reports in JSON format alongside indexed relational metadata
for rapid querying and dashboard history rendering.
"""

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import get_settings
from app.schemas.report import InvestigationReport, TraceEntry


def _get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Open a SQLite database connection with row factory enabled."""
    settings = get_settings()
    path_str = db_path or settings.db_path
    conn = sqlite3.connect(path_str)
    conn.row_factory = sqlite3.Row
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """Initialize database tables if they do not exist."""
    with _get_connection(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS investigations (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                verdict TEXT NOT NULL,
                error_type TEXT NOT NULL,
                message TEXT NOT NULL,
                file TEXT NOT NULL,
                line INTEGER NOT NULL,
                total_duration_seconds REAL NOT NULL,
                total_cost_usd REAL NOT NULL,
                report_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                investigation_id TEXT NOT NULL,
                node TEXT NOT NULL,
                input_summary TEXT NOT NULL,
                output_summary TEXT NOT NULL,
                duration_ms REAL NOT NULL,
                tokens_in INTEGER NOT NULL,
                tokens_out INTEGER NOT NULL,
                cost_usd REAL NOT NULL,
                FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_investigations_created_at ON investigations(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_traces_investigation_id ON traces(investigation_id);
            """
        )
        conn.commit()


def save_investigation(
    report: InvestigationReport, db_path: Optional[str] = None
) -> str:
    """Persist an investigation report and its node traces into SQLite.

    Returns:
        The investigation_id of the saved record.
    """
    init_db(db_path)
    report_json_str = report.model_dump_json()

    with _get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO investigations (
                id, created_at, verdict, error_type, message, file, line,
                total_duration_seconds, total_cost_usd, report_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report.investigation_id,
                report.created_at,
                report.verdict,
                report.failure_report.error_type,
                report.failure_report.message,
                report.failure_report.file,
                report.failure_report.line,
                report.total_duration_seconds,
                report.total_cost_usd,
                report_json_str,
            ),
        )

        for tr in report.traces:
            conn.execute(
                """
                INSERT INTO traces (
                    investigation_id, node, input_summary, output_summary,
                    duration_ms, tokens_in, tokens_out, cost_usd
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report.investigation_id,
                    tr.node,
                    tr.input_summary,
                    tr.output_summary,
                    tr.duration_ms,
                    tr.tokens_in,
                    tr.tokens_out,
                    tr.cost_usd,
                ),
            )
        conn.commit()

    return report.investigation_id


def get_investigation(
    investigation_id: str, db_path: Optional[str] = None
) -> Optional[InvestigationReport]:
    """Retrieve an investigation report by ID."""
    init_db(db_path)
    with _get_connection(db_path) as conn:
        cursor = conn.execute(
            "SELECT report_json FROM investigations WHERE id = ?",
            (investigation_id,),
        )
        row = cursor.fetchone()
        if row:
            data = json.loads(row["report_json"])
            return InvestigationReport.model_validate(data)
    return None


def list_investigations(
    limit: int = 50, db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """List recent investigations metadata."""
    init_db(db_path)
    with _get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            SELECT id, created_at, verdict, error_type, message, file, line,
                   total_duration_seconds, total_cost_usd
            FROM investigations
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]
