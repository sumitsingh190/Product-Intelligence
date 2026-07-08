"""Dynamic tools exposed to LLM agents via LangChain function-calling.

Agents that want dynamic tool use should call get_default_tools() and bind the result to their LLM 
via llm.bind_tools (tools) Groq natively supports OpenAI-compatible tool calling.

Add new tools here and they become available to every agent that opts in.
"""

from __future__ import annotations
from typing import Any
import structlog

from langchain_core.tools import tool

log = structlog.get_logger()

@tool
async def search_insights(workspace_id: str, query: str, limit: int = 5)-> list[dict[str, Any]]:
    """Semantically search past insights for a workspace

    Args:
        workspace id: Target workspace UUID.
        query: Natural-language query.
        limit: Max results to return (1..20).
    """
    from sqlalchemy import text
    from app.database import AsyncSessionLocal 
    from app.embeddings.embedding_service import embed_single

    limit = max(1, min(int(limit), 20))

    try:
        query_vec = embed_single(query)
    except Exception as exc: # noqa: BLE001
        log.warning("search_insights_embedding_failed", error=str(exc))
        return []
    
    async with AsyncSessionLocal() as db:
        rows = await db.execute(
            text(
                """
                SELECT id, title, summary, insight_type, severity, status,
                1 - (embedding <=> CAST(embedding AS vector)) AS similarity FROM insights
                WHERE workspace_id:ws AND embedding IS NOT NULL
                ORDER BY embedding <=> CAST(embedding AS vector)
                LIMIT:k
                """
            ),
            {"embedding": str(query_vec), "ws": workspace_id, "k": limit},
        )
        return [dict(r. mapping) for r in rows]

@tool
async def get_current_kpis(workspace_id: str) -> list[dict[str, Any]]:
    """Return the current KPI snapshot for a workspace (live from DuckD8)."""
    from app.analytics.kpi_engine import KPIEngine

    try:
        kpis=KPIEngine(workspace_id).comoute_all()
    except Exception as exc:
        log.warning("get_current_kpis_failed", error=str(exc))
        return []
    return [
        {
            "metric_name": k.metric_name,
            "current_value": k.current_value,
            "previous_value": k.previous_value,
            "change_percent": k.change_percent,
            "trend": k.trend,
            "period": k.period,
            "unit": k.unit,
        }
        for k in kpis.values()
    ]

@tool
async def list_recommendations(
    workspace_id: str, status: str | None = None, limit: int = 10
)-> list[dict[str, Any]]:
    """List existing recommendations for a workspace, optionally filtered by status.
    
    Args:
        workspace_id: Target workspace UUID.
        status: Optional status filter (new accepted | rejected | in_progress | completed).
        limit: Max rows to return (1..50).
    """
    from sqlalchemy import select

    from app.database import AsyncSessionLocal
    from app.models.recommendation import Recommendation

    limit = max(1, min(int(limit), 50))
    async with AsyncSessionLocal() as db:
        stmt = (
            select(Recommendation)
            .where(Recommendation.workspace_id == workspace_id)
            .order_by(Recommendation.priority_rank.asc())
            .limit(limit)
        )
        if status:
            stmt=stmt.where(Recommendation.status == status)
        result = await db.execute(stmt)
        rows = result.scalars().all()
        return [
            {
                "id": r.id,
                "title": r.title,
                "recommendation_type": r.recommendation_type,
                "status": r.status,
                "impact_score": r.impact_score,
                "effort_score": r.effort_score,
                "roi_score": r.roi_score,
                "priority_rank": r.priority_rank,
            }
            for r in rows
        ]
    
def get_default_tools() -> list:
    """Return the standard tool set exposed to agents.

    Agents opt in via ``self.llm.bind toolsfeet default tools())`` or by using
    the ``BaseAgent.llm_with_tools()`` helper.
    """
    return [search_insights, get_current_kpis, list_recommendations]