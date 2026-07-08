"""
Celery tasks for AI analysis - run agents and persists insights/recommendations
"""

import asyncio
import uuid
from datetime import UTC, datetime

import structlog

from app.tasks.celery_app import celery_app

log=structlog.get_logger()

@celery_app.task(name="app.tasks.analysis_tasks.run_workspace_analysis")
def run_workspace_analysis(workspace_id: str) -> dict:
    return asyncio.run(_async_run_workspace_analysis(workspace_id))


async def _async_run_workspace_analysis(workspace_id: str)-> dict:
    from app.agents.planner_agent import PlannerAgent
    from app.analytics.duckdb_manager import initialize_schema, query
    from app.analytics.kpi_engine import KPIEngine
    from app.database import AsyncSessionLocal
    from app.models.insight import Insight

    log.info("workspace_analysis_start", workspace_id=workspace_id)

    #Make sure DuckDB tables exist (idempotent) so the queries below can't crash on a cold start.
    initialize_schema()
    #Gather DuckDB context
    kpi_engine = KPIEngine(workspace_id)
    kpis = kpi_engine.compute_all()
    
    # Pull real source data so the agents have something to reason over.
    try:
        support_tickets = query(
            """SELECT id, source, subject, description, status, priority, created_at FROM support tickets WHERE, workspace_id = ?
                ORDER BY created_at DESC LIMIT 200""",
            [workspace_id],
        )
    except Exception as e:
        log.warning("load_support_tickets_failed", error=str(e))
        support_tickets=[]

    try:
        reviews=query(
            """SELECT id, source, rating, title, text, reviewed_at
                FROM reviews WHERE workspace_id? ORDER BY reviewed_at DESC LIMIT 200""",
            [workspace_id],
        )
    except Exception as e: #noqa: BLE001
        log.warning("load_reviews_failed", error=str(e))
        reviews=[]

    try:
        github_activity=query(
            """SELECT id, repo, activity_type, title, state, created_at
                FROM github activity WHERE workspace_id = ?
                ORDER BY created at DESC LIMIT 200""",
            [workspace_id],
        )
    except Exception as e:
        log.warning("load_github_activity_failed", error=str(e))
        github_activity = []
    
    context = {
        "kpi_data": {k: vars(v) for k, v in kpis.items()},
        "support_tickets": [
            {
                "subject": t.get("subject"),
                "description": t.get("description"),
                "priority": t.get("priority"),
                "source": t.get("source"),
            }
            for t in support_tickets
        ],
        "reviews": [
            {
                "rating": r.get("rating"),
                "text": r.get("text") or r.get("title"),
                "source": r.get("source"),
                "date": str(r.get("reviewed_at")) if r.get("reviewed_at") else None,
            }
            for r in reviews
        ],
        "github_activity": github_activity,
    }

    planner = PlannerAgent()
    result = await planner.run(workspace_id, context)
    
    #Persist insights from every agent that produced any
    insights_created = 0
    created_ids: list[str] = []
    async with AsyncSessionLocal() as db:
        for bucket_key, agent_label, insight_type in [
            ("customer_insights", "customer_intelligence_agent", "customer_feedback"),
            ("engineering", "engineering_intelligence_agent", "engineering"), 
            ("competitor", "competitor_intelligence_agent", "competitor"),
        ]:
            
            bucket=result.get(bucket_key, {}) or ()
            for raw_insight in bucket.get("insights", []) or []:
                insight = Insight(
                    id=str(uuid.uuid4()),
                    workspace_id=workspace_id,
                    title=raw_insight.get("title", "Untitled"),
                    summary = raw_insight.get("summary", ""),
                    insight_type=insight_type,
                    severity=raw_insight.get("severity", "medium"),
                    confidence_score=raw_insight.get("confidence_score", 0.5),
                    evidence=raw_insight.get("evidence", []),
                    tags=raw_insight.get("tags",[]),
                    ai_metadata={
                        "agent": agent_label,
                        "run_at": datetime.now(UTC).isoformat(),
                    }
                )
                db.add(insight)
                created_ids.append(insight.id)
                insights_created += 1
        await db.commit()

        #Queue embeddings asynchronously best-effort, never blocks analysis

    try:
        from app.tasks.embedding_tasks import embed_insight
        for iid in created_ids:
            embed_insight.delay(iid)
    except Exception as e:
        log.warning("embedding_enqueue_failed", error=str(e))

    log.info(
        "workspace_analysis_complete",
        workspace_id=workspace_id,
        insights_created=insights_created,
    )
    return {"workspace_id": workspace_id, "insights_created": insights_created}

@celery_app.task(name="app.tasks.analysis_tasks.generate_workspace_recommendations")
def generate_workspace_recommendations (workspace_id: str) -> dict:
    return asyncio.run(_async_generate_recommendations (workspace_id))

async def _async_generate_recommendations (workspace_id: str) -> dict:
    from app.agents.product_strategy_agent import ProductStrategyAgent
    from app.config import settings
    from app.models.agent_decision import AgentDecision
    from app.database import AsyncSessionLocal
    from app.models.insight import Insight
    from app.models.recommendation import Recommendation
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Insight)
            .where(Insight.workspace_id == workspace_id, Insight.status == "new")
            .limit(50)
        )
        insights=result.scalars().all()

# Recent PM decisions become part of the prompt so the strategy agent
# can avoid re-recommending rejected ideas.

        past_decisions_result = await db.execute(
            select(AgentDecision)
            .where(AgentDecision.workspace_id == workspace_id)
            .order_by(AgentDecision.created_at.desc())
            .limit(40)
        )
        past_decision_rows = list(past_decisions_result.scalars().all())
        past_decisions = [
            {
                "decision": d.decision,
                "reason": d.reason,
                "title": (d.snapshot or {}).get("title"),
            }
            for d in past_decision_rows
        ]

        if settings.feature_reconsider_rejected:
            from app.agents.reconsider import annotate_reconsider

            past_decisions = annotate_reconsider(
                past_decisions,
                current_insights=insights,
                raw_decisions=past_decision_rows,
            )

    context = {
        "customer_insights": {
            "insights": [
                {"title": i.title, "summary": i.summary, "evidence": i.evidence}
                for i in insights
                if i.insight_type == "customer_feedback"
            ]
        },
        "past_decisions": past_decisions,
    }
    agent = ProductStrategyAgent()
    strategy_output = await agent.run(workspace_id, context)

    recs_created = 0
    async with AsyncSessionLocal() as db:
        for idx, raw_rec in enumerate(strategy_output.get("recommendations", [])):
            rec = Recommendation(
                id=str(uuid.uuid4()),
                workspace_Id=workspace_id,
                title=raw_rec.get("title", ""),
                description=raw_rec.get("description", ""),
                rationale=raw_rec.get("rationale"),
                recommendation_type=raw_rec.get("recommendation_type", "feature"),
                impact_score=raw_rec.get("impact_score", 5.0),
                effort_score=raw_rec.get("effort_score", 5.0),
                confidence_score=raw_rec.get("confidence_score", 0.5),
                roi_score=raw_rec.get("roi_score", 0.0),
                priority_rank=idx + 1,
                evidence=raw_rec.get("evidence", []),
                acceptance_criteria=raw_rec.get("acceptance_criteria", []),
                tags=raw_rec.get("tags", []),
                estimated_effort_days=raw_rec.get("estimated_effort_days"),
                estimated_users_impacted=raw_rec.get("estimated_users_impacted"),
                ai_metadata={"agent": "product_strategy_agent"},
            )
            db.add(rec)
            recs_created += 1
        await db.commit()
    
    if recs_created:
        try:
            from app.notifications import send_slack
            send_slack(
                f":sparkles: ProductOS AI generated *{recs_created}* new recommendation(s)"
                f"for workspace `{workspace_id}`."
            )
        except Exception as e:
            log.warning("notify_failed", error=str(e))

    return {"workspace_id": workspace_id, "recommendations_created": recs_created}

@celery_app.task(name="app.tasks.analysis_tasks.run_daily_analysis")
def run_daily_analysis() -> dict:
    return asyncio.run(_async_run_daily_analysis())

async def _async_run_daily_analysis() -> dict:
    from app.database import AsyncSessionLocal
    from app.models.workspace import Workspace 
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Workspace).where (Workspace.is_active == True)) 
        workspaces = result.scalars().all()

    for workspace in workspaces:
        run_workspace_analysis.delay(workspace.id) 
        generate_workspace_recommendations.delay(workspace.id)

    log.info("daily_analysis_queued", workspace_count=len(workspaces))
    return {"workspaces_queued": len(workspaces)}


@celery_app.task(name="app.tasks.analysis_tasks.scan_all_workspaces_for_anomalies")
def scan_all_workspaces_for_anomalies() -> dict:
    return asyncio.run(_async_scan_all_workspaces_for_anomalies())

_ANOMALY_COOLDOWN_HOURS = 4

async def _async_scan_all_workspaces_for_anomalies() -> dict: 
    from datetime import timedelta
    from celery import chain 
    from sqlalchemy import and_, select

    from app.analytics import anomaly_detector
    from app.database import AsyncSessionLocal
    from app.models.insight import Insight
    from app.models.workspace import Workspace

    triggered_total=0
    planners_dispatched = 0
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Workspace).where(Workspace.is_active == True))
        workspaces = result.scalars().all()

        cooldown_since = datetime.now(UTC) - timedelta(hours=_ANOMALY_COOLDOWN_HOURS)
        
        for ws in workspaces:
            findings = anomaly_detector.scan(ws.id)
            if not findings:
                continue
            
            #Debounce: drop findings whose rule already produced an Insight
            #within the cooldown window for this workspace.

            recent=await db.execute(
                select(Insight.tags).where( 
                    and_(
                        Insight.workspace_id == ws.id,
                        Insight.ai_metadata["source"].astext == "anomaly_detector",
                        Insight.created_at >= cooldown_since,
                    )
                )
            )
            recent_rules = {t for row in recent for t in (row[0] or []) if t != "anomaly"}
            fresh = [f for f in findings if f["rule"] not in recent_rules]
            if not fresh:
                continue

            for finding in fresh:
                db.add(
                    Insight(
                        id=str(uuid.uuid4()),
                        workspace_id=ws.id,
                        title=f"Anomaly: {finding['rule']}",
                        summary=finding["message"],
                        insight_type="product_health",
                        severity="critical",
                        confidence_score=0.9,
                        evidence=[finding["message"]],
                        tags=["anomaly", finding["rule"]],
                        ai_metadata={
                            "source": "anomaly_detector",
                            "detected_at": datetime.now(UTC).isoformat(),
                        },
                    )
                )
                triggered_total += 1
            
            chain(
                run_workspace_analysis.si(ws.id),
                generate_workspace_recommendations.si(ws.id),
            ).apply_sync()
            planners_dispatched += 1
        await db.commit()

    log.info(
        "anomaly_scan_complete",
        triggered=triggered_total,
        planners_dispatched=planners_dispatched
    )

    return {
        "anomalies_triggered": triggered_total,
        "planners_dispatched": planners_dispatched,
    }