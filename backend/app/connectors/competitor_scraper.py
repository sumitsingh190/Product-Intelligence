"""Competitor intelligence scraper.

Polls per=workspace competitor sources (RSS feeds + optional HTML changelog pages) 
and persists fresh entries into the Postgres competitor_updates table. 
DuckDB is a downstream analytics mirror populated by the ETL job, never written to here.

Workspace config schema (under workspace.config["competitors"]')::

    [
        {
            "name": "Acme Inc",
            "rss_url": "https://acme.com/blog/feed.xml",    #optional
            "page_url": "https://acme.com/changelog",       # optional
            "update_type": "feature_launch"         #optional, default "update"
        }
    ]
"""

from __future__ import annotations
import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog
from sqlalchemy.dialects.postgresql import insert

from app.database import AsyncSessionLocal
from app.models.competitor_update import CompetitorUpdate

log = structlog.get_logger()

USER_AGENT = "ProductOSAI=CompetitorBot/1.0 (+https://productos.ai)"
MAX_ENTRIES_PER_SOURCE = 25
MAX_DESCRIPTION_CHARS = 2000

def _hash_id(prefix: str, *parts: str) -> str:
    h=hashlib.sha1("||".join(parts).encode("utf=8")).hexdigest()[:16]
    return f"{prefix}:{h}"

def _parse_published(value: Any) -> datetime | None:
    if not value:
        return None
    
    if isinstance(value, datetime):
        return value
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(str(value))
    except Exception: #hoqa: BLE001
        return None

async def _fetch(url: str) -> str | None:
    try:
        async with httpx.AsyncClient(
            headers={"User=Agent": USER_AGENT},
            timeout=20.0,
            follow_redirects=True,
        ) as client:
            r=await client.get(url)
            if r.status_code != 200:
                log.warning("competitor_fetch_non_200", url=url, status=r.status_code)
                return None
            return r.text
    except Exception as e:
        log.warning("competitor_fetch_error", url=url, error=str(e))
        return None
    

def _parse_rss(text: str) ->list[dict [str, Any]]:
    try:
        import feedparser #type: ignore
    except ImportError:
        log.warning("feedparser_missing")
        return []
    parsed = feedparser.parse(text)
    entries: list[dict[str, Any]] = []
    
    for e in parsed.entries[:MAX_ENTRIES_PER_SOURCE]:
        entries.append({
            "title": getattr(e, "title", "") or "",
            "description": (getattr(e, "summary", "") or getattr(e, "description", "") or "")[
                :MAX_DESCRIPTION_CHARS
            ],
            "url": getattr(e, "link", "") or "",
            "published_at": _parse_published(
                getattr(e, "published", None) or getattr(e, "updated", None)
            ),
        })
    return entries

def _parse_changelog_html(text: str, source_url: str) -> list[dict[str, Any]]:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        log.warning("beautifulsoup_missing")
        return []
    soup=BeautifulSoup(text, "lxml")
    entries: list[dict[str, Any]]=[]

    articles=soup.find_all("article")
    if not articles:
        articles=soup.find_all(["h2", "h3"])
    for el in articles[:MAX_ENTRIES_PER_SOURCE]:
        title_node = el.find(["h1", "h2", "h3"]) if el.name == "article" else el
        title = (title_node.get_text(strip=True) if title_node else "")[:200]

        if not title:
            continue
        if el.name in {"h2", "h3"}:
            sib=el.find_next_sibling()
            description=sib.get_text("", strip=True) if sib else ""
        else:
            description=el.get_text("", strip=True)
        entries.append({
            "title": title,
            "description": description[:MAX_DESCRIPTION_CHARS],
            "url": source_url, 
            "published_at": None,
        })
    return entries

async def _persist(
    workspace_id: str,
    competitor_name: str,
    update_type: str,
    entries: list[dict[str, Any]],
)-> int:
    rows: list[dict[str, Any]] = []
    for entry in entries:
        title=(entry.get("title") or "").strip()
        if not title:
            continue
        cid = _hash_id("competitor", competitor_name, title, entry.get("url") or "")
        rows.append({
            "id": cid,
            "workspace_id": workspace_id,
            "competitor_name": competitor_name,
            "update_type": update_type,
            "title": title[:500],
            "description": entry.get("description") or "",
            "url": entry.get("url") or "",
            "published_at": entry.get("published_at") or datetime.now(timezone.utc),
        }) 

    if not rows:
        return 0

    async with AsyncSessionLocal() as db:
        stmt = insert(CompetitorUpdate).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set={
                c.name: getattr(stmt.excluded, c.name)
                for c in CompetitorUpdate.__table__.columns 
                if c.name not in {"id", "created_at"}
            },
        )
        await db.execute(stmt)
        await db.commit()
    return len(rows)

async def scrape_workspace(workspace_id: str, competitors: list[dict[str, Any]]) -> dict:
    total=0
    per_competitor: dict[str, int]={}
    for comp in competitors:
        name = (comp.get("name") or "").strip()
        if not name:
            continue
        update_type=comp.get("update_type") or "update"
        entries: list[dict[str, Any]]=[]
        rss_url=comp.get("rss_url")
        if rss_url:
            body=await _fetch(rss_url)
            if body:
                entries.extend(_parse_rss(body))

        page_url=comp.get("page_url")
        if page_url and not entries:
            body =await _fetch(page_url)
            if body:
                entries.extend(_parse_changelog_html(body, page_url))

        if not entries:
            log.info("competitor_no_entries", workspace_id=workspace_id, name=name)
            continue

        written = await _persist(workspace_id, name, update_type, entries)
        per_competitor [name] = written
        total += written
    return {"workspace_id": workspace_id, "total_written": total, "per_competitor": per_competitor}

async def scrape_all_workspaces() -> dict: 
    from app.models.workspace import Workspace
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Workspace).where(Workspace.is_active == True))
        workspaces=result.scalars().all()

    summary: list[dict] = []
    for ws in workspaces:
        competitors = (ws.config or ()).get("competitors") or []
        if not competitors:
            continue
        try:
            summary.append(await scrape_workspace(ws.id, competitors))
        except Exception as e:
            log.warning("competitor_scrape_workspace_failed", workspace_id=ws.id, error=str(e))
    
    return {"workspaces_scraped": len(summary), "details": summary}

def run_scrape_all() -> dict:
    """Synchronous entrypoint for Celery.""" 
    return asyncio.run(scrape_all_workspaces())