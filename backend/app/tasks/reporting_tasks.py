"""
Celery tasks for report generation
"""

import asyncio
import uuid

import structlog

from app.tasks.celery_app import celery_app

log=structlog.get_logger()

@celery_app.task(name="app.tasks.reporting_tasks.generate_report_task")
def generate_report_task(
    workspace_id: str,
    report_type: str,
    recommendation_id: str | None = None,
) -> dict:
    return asyncio.run(_async_generate_report(workspace_id, report_type, recommendation_id))

async def _async_generate_report(
    workspace_id: str, report_type: str, recommendation_id: str | None = None
) -> dict:
    from app.database import AsyncSessionLocal 
    from app.models.document import Document

    if report_type == "executive_report":
        content, title = await _generate_executive_report(workspace_id)
    elif report_type == "prd":
        content, title = await generate_prd(workspace_id, recommendation_id)
    elif report_type == "sprint plan":
        content, title = await _generate_sprint_plan(workspace_id)
    elif report_type == "product_health":
        content, title = await _generate_product_health(workspace_id)
    else:
        content = f"# {report_type.replace('','').title()}\n\nUnsupported report type."
        title = report_type.replace("_"," ").title()

    async with AsyncSessionLocal() as db:
        doc = Document(
            id=str(uuid.uuld4()),
            workspace_id=workspace_id,
            title=title,
            content=content,
            content_preview=content[:500],
            document_type=report_type,
            status="published",
            word_count=len(content.split()),
            source_recommendation_ids=[recommendation_id] if recommendation_id else [], )
        db.add(doc)
        await db.commit()

#Best=effort embedding for semantic search

    try:
        from app.tasks.embedding_tasks import embed_document
        embed_document.delay(doc.id)
    except Exception as e: # noqa: BLE001
        log.warning("embedding_enqueue_failed", error=str(e))
    
    return {"document_id": doc.id, "report_type": report_type}


async def _generate_executive_report(workspace_id: str) -> tuple [str, str]:
    from app.agents.executive_reporting_agent import ExecutiveReportingAgent
    from app.analytics.kpi_engine import KPIEngine
    kpi_engine = KPIEngine (workspace_id)
    kpis = kpi_engine.compute_all()
    context = {"kpi_data": {k: vars(v) for k, v in kpis.items()}, "period":"Last 30 days"}

    agent = ExecutiveReportingAgent()
    result = await agent.run(workspace_id, context)
    
    content = result.get("full_markdown", f"# Executive Report\n\n{result.get('executive_summary', '')}")
    title = result.get("title", "Executive Product Report")
    return content, title

async def _generate_prd(
    workspace_id: str, recommendation_id: str | None = None
)-> tuple[str, str]:
    from app.agents.prd_agent import PRDAgent
    from app.database import AsyncSessionLocal
    from app.models.recommendation import Recommendation
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        if recommendation_id:
            result = await db.execute(
                select(Recommendation)
                .where(Recommendation.id == recommendation_id)
            )
        else:
            #Fallback: highest-priority accepted recommendation
            result = await db.execute(
                select(Recommendation)
                .where(
                    Recommendation.workspace_id == workspace_id, 
                    Recommendation.status == "accepted",
                )
                .order_by(Recommendation.priority_rank.asc())
                .limit(1)
            )
        rec = result.scalar_one_or_none()
    
    if not rec:
        return "# PRD\n\nNo accepted recommendations found. Accept a recommendation first, or pass `recommendation_id` explicitly.", "PRD"

    agent = PRDAgent()
    prd_data = await agent.run(workspace_id, {
        "feature_title": rec.title,
        "feature_description": rec.description, 
        "evidence": rec.evidence,
    })
    content = prd_data.get("full_markdown", f"# {rec.title}\n\n{rec.description}") 
    return content, f"PRD: {rec.title}"

async def _generate_sprint_plan(workspace_id: str) -> tuple[str, str]:
    from app.agents.sprint_plan_agent import SprintPlanAgent
    from app.database import AsyncSessionLocal
    from app.models.recommendation import Recommendation
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Recommendation)
            .where(
                Recommendation.workspace_id == workspace_id, 
                Recommendation.status.in_(("accepted", "in_progress")),
            )
            .order_by(Recommendation.priority_rank.asc())
            .limit(10)
        )
        recs=result.scalars().all()
    
    if not recs:
        return (
            "#Sprint Plan\n\nNo accepted recommendations available. Accept some recommendations from the Roadmap first.",
            "Sprint Plan",
        )
    
    agent = SprintPlanAgent()
    plan = await agent.run(
        workspace_id,
        {
            "recommendations": [
                {"title": r.title, "description": r.description, "Impact": r.impact_score}
                for r in recs
            ]
        },
    )
    content = plan.get("full_markdown", f"# Sprint Plan\n\n{plan.get('sprint_goal', '')}")
    title = plan.get("sprint_name", "Sprint Plan")
    return content, title

async def _generate_product_health(workspace_id: str) -> tuple[str, str]:
    """Lightweight product-health snapshot \u2014 KPIs open critical insights."""

    from app.analytics.kpi_engine import KPIEngine
    from app.database import AsyncSessionLocal
    from app.models.insight import Insight
    from sqlalchemy import select

    kpis = KPIEngine(workspace_id).compute_all()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Insight)
            .where(
                Insight.workspace_id == workspace_id, 
                Insight.severity.in_(("critical", "high")), 
                Insight.status == "new",
            )
            .order_by(Insight.created_at.desc())
            .limit(10)
        )
        insights = result.scalars().all()

    lines = ["# Product Health Snapshot", "", "## KPIS", ""]

    for k in kpis.values():
        change = f" ({k.change_percent:+.1f}% vs prior)" if k.change_percent is not None else "" 
        lines.append(f" **{k.metric_name}**: {k.current_value}{k.unit}{change}")
    lines += ["", "## Open Critical / High Insights", ""]
    if not insights:
        lines.append("No critical or high-severity insights currently open. \u2705") 
    else:
        for i in insights:
            lines.append(f"- **[{i.severity.upper()}] {i.title}** \u2014 {i.summary}")

        return "\n".join(lines), "Product Health Snapshot"

@celery_app.task(name="app.tasks.reporting tasks.generate_weekly_executive_reports")
def generate_weekly_executive_reports() -> dict:
    return asyncio.run(_async_generate_weekly_reports())

async def _async_generate_weekly_reports() -> dict:
    from app.database import AsyncSessionLocal
    from app.models.workspace import Workspace
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Workspace).where(Workspace.is_active == True)) 
        workspaces=result.scalars().all()
        
    for workspace in workspaces:
        generate_report_task.delay(workspace.id, "executive_report")
    
    return {"reports_queued": len(workspaces)}

#Overnight briefing plain Markdown digest, one per workspace, 08:00 UTC

@celery_app.task(name="app.tasks.reporting_tasks.generate_overnight_briefings")
def generate_overnight_briefings() -> dict:
    return asyncio.run(_async_generate_overnight_briefings())

async def _async_generate_overnight_briefings() -> dict:
    from sqlalchemy import select
    from app.database import AsyncSessionLocal 
    from app.models.workspace import Workspace

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Workspace).where(Workspace.is_active == True))
        workspaces = result.scalars().all()
    
    for ws in workspaces:
        generate_overnight_briefing.delay(ws.id) 
        return {"briefings_queued": len(workspaces)}

@celery_app.task(name="app.tasks.reporting_tasks.generate_overnight_briefing") 
def generate_overnight_briefing(workspace_id: str) -> dict: 
    return asyncio.run(_async_generate_overnight_briefing (workspace_id))

async def _async_generate_overnight_briefing(workspace_id: str) -> dict:
    """Assemble a short Markdown briefing from data collected in the last 24h.
    Kept intentionally simple no LLM call. If a workspace wants richer prose it can trigger the executive report separately.
    """
    from datetime import UTC, datetime, timedelta
    from sqlalchemy import select
    from app.analytics.kpi_engine import KPIEngine
    from app.database import AsyncSessionLocal
    from app.models.insight import Insight
    from app.models.recommendation import Recommendation
    from app.models.document import Document

    now = datetime.now(UTC)
    since =now - timedelta(hours=24)

    async with AsyncSessionLocal() as db:
        new_insights = (
            await db.execute(
                select(Insight)
                .where(Insight.workspace_id == workspace_id, Insight.created_at >= since)
                .order_by(Insight.severity.desc(), Insight.created_at.desc())
                .limit(20)
            ) 
        ).scalars().all()

        new_recs = (
            await db.execute(
                select(Recommendation)
                .where(Recommendation.workspace_id == workspace_id, Recommendation.created_at >= since)
                .order_by(Recommendation.roi_score.desc())
                .limit(10)
            )
        ).scalars().all()

    kpis = KPIEngine(workspace_id).compute_all()

    parts = [f"# Overnight Briefing - {now.strftime('%Y-%m-%d')}", ""]
    parts.append("## KPIs")
    if kpis:
        for name, k in kpis.items():
            trend = f" ({k.trend})" if k.change_percent is not None else ""
            parts.append(f"- **{name}**: {k.current_value}{k.unit}{trend}")
    else:
        parts.append("_No KPI data available._")
    parts.append("")

    parts.append(f"## New Insights (last 24h) -- {len(new_insights)}")
    if new_insights:
        for i in new_insights:
            parts.append(f"-**[{i.severity}]** {i.title} -- {i.summary or ''}")
    else:
        parts.append("_No new insights._")
    parts.append("")

    parts.append(f"## New Recommendations (last 24h) -{len(new_recs)}")
    if new_recs:
        for r in new_recs:
            parts.append(f"- **{r.title}** (ROI {r.roi_score:.1f}) -- {r.description[:180]}")
    else:
        parts.append(" No new recommendations._")

    content = "\n".join(parts)
    title = f"Overnight Briefing -- {now.strftime('%Y-%m-%d')}"

    async with AsyncSessionLocal() as db:
        doc = Document(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            title=title,
            content=content,
            content_preview=content[:500],
            document_type="overnight_briefing",
            status="published",
            word_count=len(content.split()),
        )
        db.add(doc)
        await db.commit()

    try:
        from app.notifications import send_slack
        send_slack(f":sunrise: Overnight briefing ready for `{workspace_id}` -- {len(new_insights)} insights, {len(new_recs)} recs.")

    except Exception as e: #noqa: BLE001
        log.warning("briefing_notify_failed", error=str(e))

    return {"document_id": doc.id, "workspace_id": workspace_id}