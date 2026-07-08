"""
ETL pipeline - syncs operational PostgreSQL data into DuckDB analytics tables.

Runs every 15 minutes via Celery beat (run_etl_sync"). 
Postgres is the sole source of truth for every operational entity 
(reviews, tickets, github activity, jira issues, product events, competitor updates, workspaces, insights, recommendations). 
This job mirrors each of those tables into DuckDB so the analytical workloads (KPI engine, anomaly detector, dashboards, agents) 
can run cheap columnar queries without touching the OLTP database.

All transformations go through Polars in-memory frames so type coercion stays consistent regardless of source. 
All writes use DuckDB's 'INSERT OR REPLACE for idempotency re-running the task is always safe.

"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import polars as pl
import structlog
from sqlalchemy import select

from app.analytics.duckdb_manager import get_cursor, initialize_schema
from app.database import AsyncSessionLocal
from app.models.competitor_update import CompetitorUpdate
from app.models.github_activity import GitHubActivity
from app.models.insight import Insight
from app.models.jira_issue import JiraIssue
from app.models.product_event import ProductEvent
from app.models.recommendation import Recommendation
from app.models.review import Review
from app.models.support_ticket import SupportTicket
from app.models.workspace import Workspace

log=structlog.get_logger()

_DIM_TABLES=[
    """CREATE TABLE IF NOT EXISTS dim_workspace (
        id VARCHAR PRIMARY KEY,
        name VARCHAR,
        workspace_type VARCHAR,
        is_active BOOLEAN,
        created_at TIMESTAMP,
        synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS fact_insights (
        id VARCHAR PRIMARY KEY,
        workspace_id VARCHAR,
        insight_type VARCHAR,
        severity VARCHAR,
        status VARCHAR,
        confidence_score FLOAT,
        affected_users INTEGER,
        created_at TIMESTAMP,
        synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS fact_recommendations (
        id VARCHAR PRIMARY KEY,
        workspace_id VARCHAR,
        recommendation_type VARCHAR,
        status VARCHAR,
        impact_score FLOAT,
        effort_score FLOAT,
        roi score FLOAT,
        priority_rank INTEGER,
        created_at TIMESTAMP,
        synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
]

def _ensure_dim_tables() -> None:
    with get_cursor() as cursor:
        for stmt in _DIM_TABLES:
            cursor.execute(stmt)

def _rows_to_frame (rows: list[dict[str, Any]], schema: dict[str, pl.DataType]) -> pl.DataFrame:
    """Build a typed Polars frame, tolerating missing columns / nulls."""

    if not rows:
        return pl.DataFrame(schema=schema)
    return pl.DataFrame(rows, schema=schema, strict=False)

def _upsert_frame (df: pl.DataFrame, table: str) -> int:
    if df.is_empty():
        return 0
    columns=df.columns
    col_list=", ".join(columns)
    placeholders= ", ".join(["?"] * len(columns))
    sql=f"INSERT OR REPLACE INTO {table} ({col_list}) VALUES ({placeholders})"
    payload=df.rows()
    with get_cursor() as cursor:
        cursor.executemany(sql, payload)
    return len(payload)

async def _sync_workspaces()-> int:
    async with AsyncSessionLocal() as db:
        result=await db.execute(select(Workspace))
        rows=[
            {
                "id": w.id,
                "name": w.name,
                "workspace_type": w.workspace_type,
                "is_active": w.is_active,
                "created_at": w.created_at,
            }
            for w in result.scalars().all()
        ]
    df = _rows_to_frame(
        rows,
        {
            "id": pl.Utf8,
            "name": pl.Utf8,
            "workspace_type": pl.Utf8,
            "is_active": pl.Boolean,
            "created_at": pl.Datetime,
        },
    )
    return _upsert_frame(df, "dim_workspace")

async def _sync_insights() -> int:
    async with AsyncSessionLocal() as db:
        result=await db.execute(select(Insight))
        rows = [
            {
                "id": i.id,
                "workspace_id": i.workspace_id,
                "insight_type": i.insight_type,
                "severity": i.severity,
                "status": i.status,
                "confidence_score": float(i.confidence_score or 0),
                "affected_users": i.affected_users_estimate,
                "created_at": i.created_at,
            }
            for i in result.scalars().all()
        ]
    df = _rows_to_frame(
        rows,
        {
            "id": pl.Utf8,
            "workspace_id": pl.Utf8,
            "insight_type": pl.Utf8,
            "severity": pl.Utf8,
            "status": pl.Utf8,
            "confidence_score": pl. Float64,
            "affected_users": pl.Int64,
            "created_at": pl.Datetime,
        },
    )
    return _upsert_frame(df, "fact_insights")

async def _sync_recommendations() ->int:
    async with AsyncSessionLocal() as db:
        result=await db.execute(select(Recommendation))
        rows = [
            {
                "id": r.id,
                "workspace_id": r.workspace_id,
                "recommendation_type": r.recommendation_type,
                "status": r.status,
                "impact_score": float(r.impact_score or 0),
                "effort_score": float(r.effort_score or 0),
                "roi_score": float(r.roi_score or 6),
                "priority_rank": int(r.priority_rank or 0),
                "created_at": r.created_at,
            }
            for r in result.scalars().all()
        ]

    df = _rows_to_frame (
        rows,
        {
            "id": pl.Utf8,
            "workspace_id": pl.Utf8,
            "recommendation_type": pl.Utf8,
            "status": pl.Utf8,
            "impact_score": pl.Float64,
            "effort_score": pl.Float64,
            "roi_score": pl.Float64,    
            "priority_rank": pl.Int64,
            "created_at": pl.Datetime,
        },
    )
    return _upsert_frame(df, "fact_recommendations")

async def _sync_reviews() -> int:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Review))
        rows = [
            {
                "id": r.id,
                "workspace_id": r.workspace_id,
                "source": r.source,
                "rating": float(r.rating) if r.rating is not None else None,
                "title": r.title,
                "text": r.text,
                "author": r.author,
                "version": r.version,
                "sentiment_score": float(r.sentiment_score) if r.sentiment_score is not None else None,
                "reviewed_at": r.reviewed_at,
            }
            for r in result.scalars().all()
        ]
    df = _rows_to_frame(
        rows,
        {
            "id": pl.Utf8,
            "workspace_id": pl.Utf8,
            "source": pl.Utfs,
            "rating": pl.Float64,
            "title": pl.Utf8,
            "text": pl.Utfs,
            "author": pl.Utfs,
            "version": pl.Utfs,
            "sentiment score": pl.Float64,
            "reviewed_at": pl.Datetime,
        },
    )
    return _upsert_frame(df, "reviews")

async def _sync_support_tickets() -> int:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(SupportTicket))
        rows = [
                {
                    "id": t.id,
                    "workspace_id": t.workspace_id,
                    "source": t.source,
                    "subject": t.subject,
                    "description": t.description,
                    "status": t.status, 
                    "priority": t.priority,
                    "tags": list(t.tags or []),
                    "created_at": t.ticket_created_at,
                    "updated_at": t.ticket_updated_at,
                    "resolved_at": t.resolved_at,
                }
                for t in result.scalars().all()
            ]
    df = _rows_to_frame(
        rows,
        {
            "id": pl.Utf8,
            "workspace_id": pl.Utf8,
            "source": pl.Utf8,
            "subject": pl.Utf8,
            "description": pl.Utf8,
            "status": pl.Utf8,
            "priority": pl.Utf8,
            "tags": pl.List(pl.Utf8),
            "created_at": pl.Datetime,
            "updated_at": pl.Datetime,
            "resolved_at": pl.Datetime,
        },
    )
    return _upsert_frame (df, "support_tickets")

async def _sync_github_activity() -> int:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(GitHubActivity))
        rows = [
            {
                "id": a.id,
                "workspace_id": a.workspace_id,
                "repo": a.repo,
                "activity_type": a.activity_type,
                "title": a.title,
                "body": a.body,
                "state": a.state,
                "author": a.author,
                "labels": list(a.labels or []),
                "created_at": a.activity_created_at,
                "updated_at": a.activity_updated_at,
                "closed_at": a.closed_at,
            }
            for a in result.scalars().all()
        ]
    
    df = _rows_to_frame(
        rows,
        {
            "id": pl.Utf8,
            "workspace_id": pl.Utf8,
            "repo": pl.Utf8,
            "activity_type": pl.Utf8,
            "title": pl.Utf8,
            "body": pl.Utf8,
            "state": pl.Utf8,
            "author": pl.Utf8,
            "labels": pl.List (pl.Utf8),
            "created_at": pl.Datetime,
            "updated_at": pl.Datetime,
            "closed_at": pl.Datetime,
        },
    )
    return _upsert_frame(df, "github_activity")

async def _sync_jira_issues() -> int:
    async with AsyncSessionLocal() as db:
        result=await db.execute(select(JiraIssue))
        rows = [
            {
                "id": j.id,
                "workspace_id": j.workspace_id,
                "project_key": j.project_key,
                "issue_type": j.issue_type,
                "summary": j.summary,
                "status": j.status,
                "priority": j.priority,
                "assignee": j.assignee,
                "reporter": j.reporter,
                "labels": list(j.labels or []),
                "created_at": j.issue_created_at,
                "updated_at": j.issue_updated_at,
                "resolved_at": j.resolved_at,
                "sprint_name": j.sprint_name,
            }
            for j in result.scalars().all()
        ]
    df = _rows_to_frame(
        rows,
        {
            "id": pl.Utf8,
            "workspace_id": pl.Utf8,
            "project_key": pl.Utf8,
            "issue_type": pl.Utf8,
            "summary": pl.Utf8,
            "status": pl.Utf8,
            "priority": pl.Utf8,
            "assignee": pl.Utf8,
            "reporter": pl.Utf8,
            "labels": pl.List(pl.Utf8),
            "created_at": pl.Datetime,
            "updated_at": pl.Datetime,
            "resolved_at": pl.Datetime,
            "sprint_name": pl.Utf8,
        },
    )
    return _upsert_frame(df, "jira_issues")

async def _sync_product_events()-> int:
    import json
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ProductEvent))
        rows = [
            {
                "id": e.id,
                "workspace_id": e.workspace_id,
                "user_id": e.user_id,
                "event_name": e.event_name,
                "properties": json.dumps(e.properties or {}),
                "platform": e.platform,
                "app_version": e.app_version,
                "event_at": e.event_at,
            }
            for e in result.scalars().all()
        ]

    df = _rows_to_frame(
        rows,
        {
            "id": pl.Utf8,
            "workspace_id": pl.Utf8,
            "user_id": pl.Utf8,
            "event_name": pl.Utf8,
            "properties": pl.Utf8,
            "platform": pl.Utf8,
            "app_version": pl.Utf8,
            "event_at": pl.Datetime,
        },
    )
    return _upsert_frame(df, "product_events")

async def _sync_competitor_updates() -> int:
    async with AsyncSessionLocal() as db:
        result=await db.execute(select(CompetitorUpdate))
        rows = [
            {
                "id": c.id,
                "workspace_id": c.workspace_id,
                "competitor_name": c.competitor_name,
                "update_type": c.update_type,
                "title": c.title,
                "description": c.description,
                "url": c.url,
                "published_at": c.published_at,
            }
            for c in result.scalars().all()
        ]

    df = _rows_to_frame(
        rows,
        {
            "id": pl.Utf8,
            "workspace_id": pl.Utf8,
            "competitor_name": pl.Utf8,
            "update_type": pl.Utf8,
            "title": pl.Utf8,
            "description": pl.Utf8,
            "url": pl.Utf8,
            "published_at": pl.Datetime,
        },
    )
    return _upsert_frame(df, "competitor updates")

async def run_sync() -> dict[str, int]:
    """Full PG -> DuckDB sync. Safe to re-run (idempotent upserts)."""
    initialize_schema()
    _ensure_dim_tables()
    
    workspaces=await _sync_workspaces()
    insights=await _sync_insights()
    recs=await _sync_recommendations()
    reviews=await _sync_reviews()
    tickets=await _sync_support_tickets()
    gh_activity=await _sync_github_activity()
    jira_issues=await _sync_jira_issues()
    events=await _sync_product_events()
    competitors=await _sync_competitor_updates()

    result = {
        "dim_workspace": workspaces,
        "fact_insights": insights,
        "fact_recommendations": recs,
        "reviews": reviews,
        "support_tickets": tickets,
        "github_activity": gh_activity,
        "jira_issues": jira_issues,
        "product_events": events,
        "competitor_updates": competitors,
        "completed_at": datetime.now(UTC).isoformat(),
    } 
    log.info("etl_sync_complete", **{k: v for k, v in result.items() if isinstance(v, int)})
    return result