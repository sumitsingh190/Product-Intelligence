"""
Jira connector - ingests projects, sprints, issues and epics

Persists into Postgres ('jira_issues'). DuckDb is a downstream analytics
mirror populated by the ETL job, never written to here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
from base64 import b64encode
from sqlalchemy.dialects.postgresql import insert

from app.connectors.base import BaseConnector, SyncResult
from app.database import AsyncSessionLocal
from app.models.jira_issue import JiraIssue

def _parse_ts(value:Any) -> datetime |None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None

class JiraConnector (BaseConnector):
    source_type = "jira"

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.base_url=self._get_config("base_url", "").rstrip("/")
        self.email=self._get_config("email")
        self.api_token=self._get_config("api_token")
        self.project_keys=self._get_config("project_keys", [])

    def _headers(self) -> dict:
        credentials=b64encode(f"{self.email}:{self.api_token}".encode()).decode()
        return {
            "Authorization": f"Basic {credentials}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
    
    async def test_connection(self) -> bool:
        async with httpx.AsyncClient(headers=self._headers()) as client:
            r=await client.get(f"{self.base_url}/rest/api/3/myself")
            return r.status_code == 200

    async def fetch_raw(self, since: datetime | None=None) -> list[dict[str, Any]]: 
        records=[]
        async with httpx.AsyncClient(headers=self._headers(), timeout=30.0) as client:
            for project_key in self.project_keys:
                issues=await self._fetch_issues (client, project_key, since)
                sprints=await self._fetch_sprints(client, project_key)
                records.append({
                    "project_key": project_key,
                    "issues": issues,
                    "sprints": sprints,
                })
        return records

    async def sync(self, workspace_id: str, since: datetime | None=None) -> SyncResult:
        result=SyncResult(source_type=self.source_type)
        try:
            raw_data=await self.fetch_raw(since)
            for proj_data in raw_data:
                result.records_fetched += len(proj_data.get("issues", []))
            await self. persist(workspace_id, raw_data)
        except Exception as e:
            result.success=False
            result.errors.append(str(e))
        finally:
            result.finish()
        return result
        
    async def _persist(self, workspace_id: str, raw_data: list[dict[str, Any]]) ->None:
        rows: list[dict[str, Any]]=[]
        for proj in raw_data:
            project_key=proj.get("project_key", "UNK")
            for issue in proj.get("issues", []):
                fields=issue.get("fields",{}) or {}
                issue_id=f"jira:{issue.get('key', issue.get('id'))}"
                labels= fields.get("labels") or []
                if not isinstance(labels,list):
                    labels = []
                rows.append({
                    "id": issue_id,
                    "workspace_id": workspace_id,
                    "project_key": project_key,
                    "issue_type": (fields.get("issuetype") or {}).get("name"),
                    "summary": fields.get("summary"), 
                    "status": (fields.get("status") or {}).get("name"), 
                    "priority": (fields.get("priority") or {}).get("name"),
                    "assignee": (fields.get("assignee") or {}).get("displayName"),
                    "reporter": (fields.get("reporter") or ()).get("displayName"), 
                    "labels": labels,
                    "issue_created_at": _parse_ts(fields.get("created")),
                    "issue_updated_at": _parse_ts(fields.get("updated")),
                    "resolved_at": _parse_ts(fields.get("resolutiondate")),
                    "sprint_name": None,
                })
        if not rows:
            return
        
        async with AsyncSessionLocal() as db:
            stmt=insert(JiraIssue).values(rows)
            stmt=stmt.on_conflict_do_update(
                index_elements=["id"],
                set={
                    c.name: getattr(stmt.excluded, c.name) 
                    for c in JiraIssue.__table__.columns 
                    if c.name not in {"id", "created_at"}
                },
            )
            await db.execute(stmt)
            await db.commit()

    async def _fetch_issues(
        self, client: httpx.AsyncClient, project_key: str, since: datetime | None) -> list[dict]:
        jqlf=f"project={project_key} ORDER BY updated DESC"
        if since:
            jql=f"project = {project_key} AND updated >= '{since.strftime('%Y-%m-%d')}'"
        try:
            r=await client.post(
                f"{self.base_url}/rest/api/3/search", 
                json={"jql": jql, "maxResults": 100, "fields": [
                    "summary", "description", "status", "priority", "Issuetype", "assignee", 
                    "reporter", "created", "updated", "labels", "components", "fixVersions",
                    "sprint",]},
            )
            r.raise_for_status()
            return r.json().get("issues", [])
        except Exception as e:
            self.log.warning("jira_issues_fetch_failed", project=project_key, error=str(e))
            return []

    async def _fetch_sprints(self, client: httpx.AsyncClient, project_key: str) -> list[dict]: 
        try:
            boards_r = await client.get(
                f"{self.base_url}/rest/agile/1.0/board", params={"projectKeyOrId": project_key},
            )

            boards_r.raise_for_status() 
            boards=boards_r.json().get("values", []) 
            if not boards: 
                return [] 
            board_id = boards[0]["id"]

            sprints_r = await client.get(
                f"{self.base_url}/rest/agile/1.0/board/{board_id}/sprint", params={"state": "active,closed", "maxResults": 10},
            )
            sprints_r.raise_for_status()
            return sprints_r.json().get("values", []) 
        except Exception as e: 
            self.log.warning("jira_sprints_fetch_failed", project=project_key, error=str(e))
            return []