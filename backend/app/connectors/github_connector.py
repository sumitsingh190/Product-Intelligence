"""GitHub connector - ingests repos, issues, PRs, releases, and commit activity.

Persists into Postgres ('github_activity' + 'support_tickets').
DuckDB is a downstream mirror populated by the ETL job, never written to here.

"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
from sqlalchemy.dialects.postgresql import insert

from app.connectors.base import BaseConnector,SyncResult
from app.database import AsyncSessionLocal
from app.models.github_activity import GitHubActivity
from app.models.support_ticket import SupportTicket

def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None

    if isinstance(value, datetime):
        return value
    
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None

def _label_names(labels: Any) -> list[str]:
    if not isinstance(labels, list):
        return []
    return [l.get("name") for l in labels if isinstance(l, dict) and l.get("name")]

class GitHubConnector (BaseConnector):
    source_type = "github"
    BASE_URL="https://api.github.com"

    def __init_(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.token=self._get_config("token")
        self.repos=self._get_config("repos", []) # ["owner/repo"]
        self._client: httpx.AsyncClient | None=None

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer (self.token)", 
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
    

    async def test_connection(self) -> bool:
        async with httpx.AsyncClient(headers=self._headers()) as client: 
            response=await client.get(f"{self.BASE_URL}/user")
            return response.status_code == 200

    async def fetch_raw(self, since: datetime | None=None) -> list[dict[str, Any]]: 
        records=[]

        async with httpx.AsyncClient(headers=self._headers(), timeout=30.0) as client:
            for repo in self.repos:
                issues=await self._fetch_issues(client, repo, since)
                prs=await self._fetch_pull_requests (client, repo, since)
                releases=await self._fetch_releases (client, repo)
                commits=await self._fetch_commits(client, repo, since)
                records.append({
                    "repo": repo,
                    "issues": issues,
                    "pull_requests": prs,
                    "releases": releases,
                    "commits": commits,
                })
        return records

    async def sync(self, workspace_id: str, since: datetime | None=None) -> SyncResult: 
        result=SyncResult(source_type=self.source_type) 
        try:
            raw_data=await self.fetch_raw(since)
            for repo_data in raw_data:
                result.records_fetched += (
                    len(repo_data.get("issues", []))
                    + len(repo_data.get("pull_requests", []))
                    + len(repo_data.get("releases", []))
                    + len(repo_data.get("commits", []))
                ) 
            await self._persist(workspace_id, raw_data)
        except Exception as e:
            result.success=False
            result.errors.append(str(e))
            self.log.error("github_sync_error", error=str(e))
        finally:
            result.finish()
        return result

    async def _persist(self, workspace_id: str, raw_data: list[dict[str, Any]]) -> None:
        activity_rows: list[dict[str, Any]]=[]
        ticket_rows: list[dict[str, Any]]=[]
        for repo_data in raw_data:
            repo=repo_data.get("repo", "unknown")
            for issue in repo_data.get("issues", []):
                if "pull_request" in issue:
                    continue
                issue_id=f"github: {repo}: issue:{issue.get('number')}"
                labels= _label_names(issue.get("labels"))
                created= _parse_ts(issue.get("created_at"))
                updated= _parse_ts(issue.get("updated_at"))
                closed= _parse_ts(issue.get("closed_at"))

                activity_rows.append({
                    "id": issue_id,
                    "workspace_id": workspace_id,
                    "repo": repo,
                    "activity_type": "issue",
                    "title": issue.get("title"),
                    "body": (issue.get("body") or "")[:8000],
                    "state": issue.get("state"),
                    "author": (issue.get("user") or {}).get("login"),
                    "labels": labels,
                    "activity_created_at": created,
                    "activity_updated_at": updated,
                    "closed_at": closed,
                })
                    #Also register the issue as a support ticket for the

                    #customer-intelligence agent.

                ticket_rows.append({
                    "id": issue_id,
                    "workspace_id": workspace_id,
                    "source": "github",
                    "subject": issue.get("title"),
                    "description": (issue.get("body") or "") [:8000],
                    "status": issue.get("state"),
                    "priority": "normal",
                    "tags": labels,
                    "ticket_created_at": created,
                    "ticket_updated_at": updated,
                    "resolved_at": closed,
                    })
            
            for pr in repo_data.get("pull_requests", []):
                pr_id=f"github: {repo}:pr: {pr.get('number')}"
                activity_rows.append({
                    "id": pr_id,
                    "workspace_id": workspace_id,
                    "repo": repo,
                    "activity_type": "pull_request",
                    "title": pr.get("title"),
                    "body": (pr.get("body") or "") [:8000],
                    "state": pr.get("state"),
                    "author": (pr.get("user") or {}).get("login"),
                    "labels": _label_names(pr.get("labels")),
                    "activity_created_at": _parse_ts(pr.get("created_at")),
                    "activity_updated_at": _parse_ts(pr.get("updated_at")),
                    "closed_at": _parse_ts(pr.get("closed_at")),
                })

        if not activity_rows and not ticket_rows:
            return

        async with AsyncSessionLocal() as db:
            if activity_rows:
                stmt=insert(GitHubActivity).values(activity_rows)
                stmt=stmt.on_conflict_do_update(
                    index_elements=["id"], 
                    set={
                        c.name: getattr(stmt.excluded, c.name)
                        for c in GitHubActivity.__table__.columns 
                        if c.name not in {"id", "created_at"}
                    },
                )
                await db.execute(stmt)

            
            if ticket_rows:
                stmt=insert(SupportTicket).values(ticket_rows)
                stmt=stmt.on_conflict_do_update(
                    index_elements=["id"],
                    set={
                        c.name: getattr(stmt.excluded, c.name)
                        for c in SupportTicket.__table__.columns
                        if c.name not in {"id", "created_at"}
                    },
                )
                await db.execute(stmt)

            await db.commit()

    async def _fetch_issues(
        self, client: httpx.AsyncClient, repo: str, since: datetime | None
    ) -> list[dict]:
        params={"state": "all", "per_page": 100}
        if since:
            params["since"] = since.isoformat()
        try:
            r=await client.get(f"{self.BASE_URL}/repos/{repo}/issues", params=params)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            self.log.warning("github_issues_fetch_failed", repo=repo, error=str(e))
            return []

    async def _fetch_pull_requests(
        self, client: httpx.AsyncClient, repo: str, since: datetime | None ) -> list[dict]:
        params={"state": "all", "per_page": 100}
        try:
            r=await client.get(f"{self.BASE_URL}/repos/{repo}/pulls", params=params)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            self.log.warning("github_prs_fetch_failed", repo=repo, error=str(e))
            return []

    async def _fetch_releases (self, client: httpx.AsyncClient, repo: str) -> list[dict]:
        try:
            r=await client.get(f"{self.BASE_URL}/repos/{repo}/releases", params={"per_page": 20})
            r.raise_for_status()
            return r.json()
        except Exception as e:
            self.log.warning("github_releases_fetch_failed", repo=repo, error=str(e))
            return []

    async def _fetch_commits(self, client: httpx.AsyncClient, repo: str, since: datetime | None) -> list[dict]:
        params = {"per_page": 100}
        if since:
            params["since"]=since.isoformat()
            try:
                r=await client.get(f"{self.BASE_URL}/repos/{repo}/commits", params=params)
                r.raise_for_status()
                return r.json()
            except Exception as e:
                self.log.warning("github commits fetch failed", repo=repo, error=str(e))
                return []