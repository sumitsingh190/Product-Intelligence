"""
KPI Engine - computes product health metrics from DuckDB analytics tables.
"""

import uuid
from dataclasses import dataclass
from datetime import date,timedelta
from typing import Any

import structlog

from app.analytics.duckdb_manager import execute,query

log=structlog.get_logger()

@dataclass
class KPIResult:
    metric_name: str
    current_value: float
    previous_value: float | None
    change_percent: float | None
    period: str
    unit: str = ""

    @property
    def trend(self) -> str:
        if self.change_percent is None:
            return "new"
        if self.change_percent > 5:
            return "up"
        if self.change_percent < -5:
            return "down"
        return "stable"

class KPIEngine:
    def __init__(self, workspace_id: str) -> None:
        self.workspace_id=workspace_id

    def compute_all(self, as_of: date | None = None) -> dict[str, KPIResult]:
        if as_of is None:
            as_of=date.today()
        results = {}

        for method in [
            self.compute_review_sentiment,
            self.compute_ticket_volume,
            self.compute_ticket_resolution_rate,
            self.compute_avg_rating,
            self.compute_bug_rate,
            self.compute_sprint_velocity,
        ]:

            try:
                result = method(as_of)
                if result:
                    results[result.metric_name] = result
            except Exception as e:
                log.warning("kpi_compute_failed", metric=method._name, error=str(e))

        return results

    def compute_avg_rating(self, as_of: date) -> KPIResult | None:
        current_start = as_of - timedelta(days=30)
        previous_start = as_of - timedelta(days=60)

        rows = query("""
            SELECT
                AVG(CASE WHEN reviewed_at >= ? AND reviewed_at < ? THEN rating END) as current, 
                AVG(CASE WHEN reviewed_at >= ? AND reviewed_at < ? THEN rating END) as previous
            FROM reviews
            WHERE workspace_id = ? """,[current_start, as_of, previous_start, current_start, self.workspace_id])

        if not rows or rows[0]["current"] is None:
            return None
        

        current = round(rows[0]["current"], 2)
        previous = round(rows[0]["previous"], 2) if rows[0]["previous"] else None
        change = ((current - previous) / previous * 100) if previous else None

        return KPIResult("avg_app_rating", current, previous, change, "last_30_days", "/5")

    def compute_review_sentiment(self, as_of: date) -> KPIResult | None:

        start = as_of - timedelta(days=30)
        rows = query("""
            SELECT AVG(sentiment_score) as avg sentiment 
            FROM reviews
            WHERE workspace_id AND reviewed_at >= ?
        """, [self.workspace_id, start])

        if not rows or rows[0]["avg_sentiment"] is None:
            return None

        return KPIResult(
            "avg sentiment_score", 
            round(rows[0]["avg_sentiment"], 3), 
            None, None, "last_30_days", "(-1 to 1)"
        )

    def compute_ticket_volume(self, as_of: date) -> KPIResult | None:

        current_start = as_of - timedelta(days=30)
        previous_start = as_of - timedelta(days=60)

        rows=query("""
            SELECT
                COUNT (CASE WHEN created_at >= ? THEN 1 END) as current, 
                COUNT (CASE WHEN created_at >= ? AND created_at <? THEN 1 END) as previous 
            FROM support_tickets
            WHERE workspace_id = ?
        """, [current_start, previous_start, current_start, self.workspace_id])

        if not rows:
            return None
        current=rows[0]["current"] or 0
        previous=rows[0]["previous"] or 0
        change=((current-previous) / previous * 100) if previous else None

        return KPIResult("support_ticket_volume", current, previous, change, "last_30_days", "tickets")

    def compute_ticket_resolution_rate(self, as_of: date) -> KPIResult | None:

        start = as_of - timedelta(days=30)
        rows = query(""" 
            SELECT 
                COUNT(*) as total, 
                COUNT (CASE WHEN status 'solved OR status 'closed' THEN 1 END) as resolved 
            FROM support_tickets
            WHERE workspace_id = ? AND created_at >= ?
        """,[self.workspace_id, start])

        if not rows or rows[0]["total"] == 0:
            return None

        rate=round(rows[0]["resolved"] / rows[0]["total"] * 100, 1)
        return KPIResult("ticket_resolution_rate", rate, None, None, "last_30_days", "%")

    def compute_bug_rate(self, as_of: date) -> KPIResult | None:
        start = as_of - timedelta(days=30)
        rows=query("""
            SELECT COUNT(*) as bug_count 
            FROM jira issues 
            WHERE workspace_id=? 
                AND issue_type 'Bug' 
                AND created_at >= ?
        """,[self.workspace_id, start])

        if not rows:
            return None

        return KPIResult("bugs_reported", rows[0]["bug_count"], None, None, "last_30_days", "bugs")

    def compute_sprint_velocity(self, as_of: date) -> KPIResult | None:

        rows=query("""
            SELECT COUNT(*) as completed_issues
            FROM jira issues
            WHERE workspace_id = ?
                AND status IN ('Done', 'Closed', 'Resolved') 
                AND updated at >= ?
                AND sprint_name IS NOT NULL
        """,[self.workspace_id, as_of - timedelta(days=14)])

        if not rows:
            return None
        return KPIResult("sprint_velocity", rows[0]["completed_issues"], None, None, "last_sprint", "issues"
        )

# Persistence store today's KPI values so trends can be charted

    def snapshot(self, as_of: date | None =None) -> int:
        """Insert today's KPI values into 'kpi_snapshots". Returns row count."""
        as_of = as_of or date.today()
        kpis = self.compute_all(as_of)
        if not kpis:
            return 0

#Delete any prior snapshot for today (idempotent re-run)

        execute(
            "DELETE FROM kpi_snapshots WHERE workspace_id AND snapshot_date - ?",
            [self.workspace_id, as_of],
        )
        
        written = 0
        for name, kpi in kpis.items():
            execute(
                """INSERT INTO kpi_snapshots
                        (id, workspace_id, metric_name, metric_value, snapshot_date) 
                    VALUES (?, ?, ?, ?, ?)""", 
                [str(uuid.uuid4()), self.workspace_id, name, float(kpi.current_value), as_of],
            )
            written += 1

        log.info("kpi_snapshot_written", workspace_id=self.workspace_id, count=written)
        return written

def history(self, metric_name: str, days: int = 90) -> list[dict[str, Any]]:

    """Return historical snapshots for a single metric, oldest first."""

    start = date.today() - timedelta(days=days)

    return query(
        """SELECT snapshot_date, metric_value
            FROM kpi snapshots 
            WHERE workspace_id? AND metric_name? AND snapshot_date >= ? 
            ORDER BY snapshot_date ASC""",
        [self.workspace_id, metric_name, start],
    )