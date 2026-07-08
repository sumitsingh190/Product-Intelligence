"""
Slack connector = reads channel messages via Slack Web API

Config expected (all optional except 'bot_token and channel_ids`):
    {
        "bot_token": "xoxb=...",    #Bot User OAuth Token
        "channel_ids": ["C123", "C456"],    # Channels to poll
        "history_days": 7       #Only pull messages from the last N days
    }
Messages are persisted into the Postgres support_tickets table with 
source 'slack' so the customer intelligence agent picks them up alongside 
tickets from other sources. DuckDB is a downstream analytics mirror populated by the ETL job, never written to here. I
"""

from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy.dialects.postgresql import insert

from app.connectors.base import BaseConnector, SyncResult
from app.database import AsyncSessionLocal
from app.models.support_ticket import SupportTicket


SLACK_BASE="https://slack.com/api"

class SlackConnector (BaseConnector): 
    source_type="slack"

    def __init__(self, config: dict[str, Any]) -> None: 
        super()._init_(config) 
        self.token: str = self._get_config("bot_token", "") 
        self.channel_ids: list[str] = list(self._get_config("channel_ids", []) or []) 
        self.history_days: int = int(self._get_config("history_days", 7))

    def _headers(self) -> dict[str, str]: 
        return {"Authorization": f"Bearer {self.token}"}

    async def test_connection(self) -> bool:
        if not self.token:
            return False 
        
        async with httpx.AsyncClient(headers=self._headers(), timeout=15.0) as client:
            r=await client.get(f"{SLACK_BASE}/auth.test") 
            return r.status_code==200 and r.json().get("ok", False)

    async def fetch_raw(self, since: datetime | None=None) -> list[dict[str, Any]]: 
        if not self.token or not self.channel_ids: 
            return []

        cutoff=since or (datetime.now(timezone.utc) - timedelta(days=self.history_days)) 
        oldest_ts=cutoff.timestamp()

        messages: list[dict[str, Any]]=[]
        async with httpx.AsyncClient(headers=self._headers(), timeout=30.0) as client:
            for channel_id in self.channel_ids:
                try:
                    r=await client.get(
                        f"{SLACK_BASE}/conversations.history", 
                        params={
                            "channel": channel_id, 
                            "oldest": f"{oldest_ts:.6f}", 
                            "limit": 200, 
                        },
                    )
                    data=r.json()
                    if not data.get("ok"):
                        self.log.warning(
                            "slack_history_failed", 
                            channel=channel_id, 
                            error=data.get("error"),
                        )
                        continue
                    for msg in data.get("messages", []):
                        if msg.get("subtype") in {"channel_join", "channel_leave", "bot_message"}:
                            continue
                        msg["_channel"] = channel_id
                        messages.append(msg)
                except Exception as exc:#noqa: BLE001
                    self.log.warning("slack_channel_fetch_error", channel=channel_id, error=str(exc))
        return messages

    async def sync(self, workspace_id: str, since: datetime | None=None) -> SyncResult:
        result=SyncResult(source_type=self.source_type)
        try:
            messages=await self.fetch_raw(since)
            result.records_fetched=len(messages)
            await self._persist(workspace_id, messages)
        except Exception as exc: # noqa: BLE001
            result.success=False
            result.errors.append(str(exc))
        finally:
            result.finish()
        return result

    async def _persist(self, workspace_id: str, messages: list[dict[str, Any]]) -> None:
        if not messages:
            return
        
        rows: list[dict[str, Any]] = []
        for m in messages:
            ts=m.get("ts", "0")
            ticket_id = f"slack:{m.get('_channel')}:{ts}"
            try:
                created = datetime.fromtimestamp(float(ts), tz=timezone.utc)
            except (TypeError, ValueError):
                created = datetime.now(timezone.utc)

            text = (m.get("text") or "")[:8000]
            subject=text.splitlines()[0][:188] if text else "(no text)"
            rows.append({
                "id": ticket_id, 
                "workspace_id": workspace_id,
                "source": "slack",
                "subject": subject,
                "description": text,
                "status": "open",
                "priority": "normal",
                "tags": [m.get("_channel") or "unknown"],
                "ticket_created_at": created,
                "ticket_updated_at": created,
                "resolved_at": None,
            })
        async with AsyncSessionLocal() as db:
            stmt=insert(SupportTicket).values(rows)
            stmt=stmt.on_conflict_do_update(
                index_elements=["id"],
                set={ 
                    c.name: getattr(stmt.excluded, c.name) 
                    for c in SupportTicket._table_.columns 
                    if c.name not in {"id", "created_at"}
                },
            )
            await db.execute(stmt)
            await db.commit()