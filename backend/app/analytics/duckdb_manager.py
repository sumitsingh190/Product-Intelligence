"""DuckDB manager - connection pool and schema setup for analytics"""
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import duckdb
import structlog

from app.config import settings

log=structlog.get_logger()

_lock=threading.Lock()
_connection : duckdb.DuckDBPyConnection | None= None

def get_connection() -> duckdb.DuckDBPyConnection:
    global _connection
    with _lock:
        if _connection is None:
            Path(settings.duckdb_path).parent.mkdir(parents=True, exist_ok=True)
            _connection=duckdb.connect(settings.duckdb_path)
            _connection.execute(f"PRAGMA threads={settings.duckdb_threads}")
            _connection.execute(f"SET memory_limit='{settings.duckdb_memory_limit}'")
            log.info("duckdb_connected", path=settings.duckdb_path)
    return _connection

@contextmanager
def get_cursor():
    conn = get_connection()
    cursor = conn.cursor()

    try:
        yield cursor
    finally:
        cursor.close()

def initialize_schema() -> None:
    """Create all analytics tables if they don't exist."""

#BEFORE (broken executescript is SQLite-only; DuckDB raises AttributeError):

#with get_cursor() as cursor:

# cursor.executescript("""
#CREATE TABLE IF INOT EXISTS reviews (...);
#CREATE TABLE IF NOT EXISTS support_tickets (...);
#CREATE TABLE IF NOT EXISTS github_activity (...);
#CREATE TABLE IF NOT EXISTS jira_issues (...);
#CREATE TABLE IF NOT EXISTS product_events (...);
#CREATE TABLE IF NOT EXISTS kpi_snapshots (...);
#CREATE TABLE IF NOT EXISTS competitor_updates (...);
#AFTER: DuckDB only supports one statement per execute() call.

    statements=[
        """CREATE TABLE IF NOT EXISTS reviews (
            id VARCHAR PRIMARY KEY,
            workspace_id VARCHAR NOT NULL,
            source VARCHAR NOT NULL, 
            rating FLOAT, 
            title VARCHAR, 
            author VARCHAR, 
            version VARCHAR, 
            sentiment_score FLOAT,
            text TEXT,
            reviewed_at TIMESTAMP,
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP )""",

            """CREATE TABLE IF NOT EXISTS support_tickets (
            id VARCHAR PRIMARY KEY,
            workspace_id VARCHAR NOT NULL,
            source VARCHAR NOT NULL,
            subject VARCHAR,
            description TEXT,
            status VARCHAR, 
            priority VARCHAR,
            tags VARCHAR[],
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            resolved_at TIMESTAMP,
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",

            """CREATE TABLE IF NOT EXISTS github_activity (
            id VARCHAR PRIMARY KEY,
            workspace_id VARCHAR NOT NULL,
            repo VARCHAR NOT NULL,
            activity_type VARCHAR NOT NULL,
            title VARCHAR,
            body TEXT,
            state VARCHAR,
            author VARCHAR,
            labels VARCHAR[],
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            closed_at TIMESTAMP,
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ) """,

            """CREATE TABLE IF NOT EXISTS jira_issues (\
            id VARCHAR PRIMARY KEY,
            workspace_id VARCHAR NOT NULL,
            project_key VARCHAR NOT NULL,
            issue_type VARCHAR,
            summary VARCHAR,
            status VARCHAR,
            priority VARCHAR,
            assignee VARCHAR,
            reporter VARCHAR,
            labels VARCHAR[],
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            resolved_at TIMESTAMP,
            sprint_name VARCHAR,
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",

            """CREATE TABLE IF NOT EXISTS product_events (
            id VARCHAR PRIMARY KEY,
            workspace_id VARCHAR NOT NULL,
            user_id VARCHAR,
            event_name VARCHAR NOT NULL,
            properties JSON,
            platform VARCHAR,
            app_version VARCHAR,
            event_at TIMESTAMP NOT NULL,
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",

            """CREATE TABLE IF NOT EXISTS kpi_snapshots (
            id VARCHAR PRIMARY KEY,
            workspace_id VARCHAR NOT NULL,
            metric_name VARCHAR NOT NULL,
            metric_value FLOAT NOT NULL,
            dimension_key VARCHAR,
            dimension_value VARCHAR,
            snapshot_date DATE NOT NULL,
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS competitor_updates (
            id VARCHAR PRIMARY KEY,
            workspace_id VARCHAR NOT NULL,
            competitor_name VARCHAR NOT NULL,   
            update_type VARCHAR,
            title VARCHAR,
            description TEXT,
            url VARCHAR,
            published_at TIMESTAMP,
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
    ]

    with get_cursor() as cursor:
        for stmt in statements:
            cursor.execute(stmt)

    log.info("duckdb_schema_initialized")

def query(sql: str, params: list[Any] | None=  None) -> list[dict[str, Any]]:
    """Execute a SELECT query and return list of row dicts."""

    with get_cursor() as cursor:
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)

        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

def execute(sql: str, params: list [Any] | None = None) -> None:
    """Execute a non-SELECT statement."""
    with get_cursor() as cursor:
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)