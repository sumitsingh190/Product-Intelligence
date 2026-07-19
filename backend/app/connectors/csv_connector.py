"""CSV up) upload connector imports rows from a user=provided CSV file.

Config expected:
    {
        "kind": "reviews" | "support_tickets" | "product_events",
        "csv_text": "<raw csv text>"        #written when the file is uploaded
    }

The uploader endpoint (see `api/v1/endpoints/data_sources.py') writes the CSV 
text into the data source's config, then triggers a normal sync. This keeps 
the connector interface identical to the API=based ones. Persists into 
Postgres (`reviews', 'support_tickets', 'product_events'). DuckDB is a 
downstream analytics mirror populated by the ETL job, never written to here.

Supported columns (case=insensitive; extra columns are ignored):

* reviews:              id, source, rating, title, text, author, version, reviewed_at
* support_tickets:      id, source, subject, description, status, priority, created_at, updated_at
* product_events:       id, user_id event_name, properties, platform, app_version, event_at
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from app.connectors.base import BaseConnector, SyncResult
from app.database import AsyncSessionLocal
from app.models.product_event import ProductEvent
from app.models.review import Review
from app.models.support_ticket import SupportTicket

class CSVUploadConnector (BaseConnector):
    source_type="csv_upload"
    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.kind: str = str(self._get_config("kind", "reviews"))
        self.csv_text: str = str(self._get_config("csv_text", ""))

    async def test_connection(self) -> bool:
        return bool(self.csv_text.strip())

    async def fetch_raw(self, since: datetime | None = None) -> list[dict[str, Any]]:
        if not self.csv_text.strip():
            return []

        reader = csv.DictReader(io.StringIO(self.csv_text))
        return [
            {k.strip().lower(): (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
            for row in reader 
        ]

    async def sync(self, workspace_id: str, since: datetime | None=None) -> SyncResult:
        result = SyncResult(source_type=self.source_type)
        try:
            rows=await self.fetch_raw(since)
            result.records_fetched=len(rows)
            await self._persist(workspace_id, rows)
        except Exception as exc:
            result.success = False
            result.errors.append(str(exc))
        finally:
            result.finish()
        return result
    
    async def _persist(self, workspace_id: str, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return

        if self.kind == "reviews":
            await self._persist_reviews(workspace_id, rows)
        elif self.kind== "support_tickets":
            await self._persist_tickets(workspace_id, rows)
        elif self.kind== "product_events":
            await self._persist_events(workspace_id, rows)
        else:
            raise ValueError(f"Unsupported CSV kind: {self.kind}")

    @staticmethod
    def _parse_ts(value: Any) -> datetime | None:
        if not value:
            return None

        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    
    @staticmethod
    def _parse_properties(value: Any) -> dict:
        if isinstance(value, dict):
            return value
        if not value:
            return {}
        try:
            data=json.loads(str(value))
            return data if isinstance(data, dict) else {}
        except (ValueError, TypeError):
            return {}

    async def _persist_reviews(self, workspace_id: str, rows: list[dict[str, Any]]) -> None:
        payload: list[dict[str, Any]]=[]
        for row in rows:
            rid = row.get("id") or f"csv:{uuid.uuid4()}"
            payload.append({
                "id": str(rid),
                "workspace_id": workspace_id,
                "source": row.get("source") or "csv",
                "rating": float(row["rating"]) if row.get("rating") else None,
                "title": row.get("title"),
                "text": row.get("text"),
                "author": row.get("author"),
                "version": row.get("version"),
                "sentiment_score": None,
                "reviewed_at": self._parse_ts(row.get("reviewed_at")) or datetime.now(timezone.utc),
            })

        async with AsyncSessionLocal() as db:
            stmt=insert(Review).values(payload)
            stmt=stmt.on_conflict_do_update(
                index_elements=["id"],
                set_={
                    c.name: getattr(stmt.excluded, c.name)
                    for c in Review.__table__.columns
                    if c.name not in {"id","created_at"}
                },
            )
            await db.execute(stmt)
            await db.commit()

    async def _persist_tickets(self, workspace_id: str, rows: list[dict[str, Any]]) -> None:

        payload: list[dict[str, Any]]=[]
        for row in rows:
            tid = row.get("id") or f"csv:{uuid.uuid4()}"
            created = self._parse_ts(row.get("created_at")) or datetime.now(timezone.utc)
            updated = self._parse_ts(row.get("updated_at")) or created
            payload.append({
                "id": str(tid),
                "workspace_id": workspace_id,
                "source": row.get("source") or "csv",
                "subject": row.get("subject"),
                "description": row.get("description"),
                "status": row.get("status") or "open",
                "priority": row.get("priority") or "normal", 
                "tags": [],
                "ticket_created_at": created,
                "ticket_updated_at": updated,
                "resolved_at": None,
            })

        async with AsyncSessionLocal() as db:
            stmt=insert(SupportTicket).values(payload)
            stmt=stmt.on_conflict_do_update(
                index_elements=["id"],
                set_={
                    c.name: getattr(stmt.excluded, c.name)
                    for c in SupportTicket.__table__.columns
                    if c.name not in {"id", "created_at"}
                },
            )
            await db.execute(stmt)
            await db.commit()


    async def _persist_events(self, workspace_id: str, rows: list[dict[str, Any]]) -> None:
        payload: list[dict[str, Any]]=[]
        for row in rows:
            eid=row.get("id") or f"csv:{uuid.uuid4()}"
            event_at=self._parse_ts(row.get("event_at")) or datetime.now(timezone.utc)
            payload.append({
                "id": str(eid),
                "workspace_id": workspace_id,
                "user_id": row.get("user_id"),
                "event_name": row.get("event_name") or "unknown",
                "properties": self._parse_properties(row.get("properties")),
                "platform": row.get("platform"),
                "app_version": row.get("app_version"),
                "event_at": event_at,
            })

        async with AsyncSessionLocal() as db:
            stmt=insert(ProductEvent).values(payload)
            stmt=stmt.on_conflict_do_update(
                index_elements=["id"],
                set_={
                    c.name: getattr(stmt.excluded, c.name)
                    for c in ProductEvent.__table__.columns
                    if c.name not in {"id", "created_at"}
                },
            )
        await db.execute(stmt)
        await db.commit()