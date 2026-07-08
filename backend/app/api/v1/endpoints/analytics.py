"""
Analytics endpoints - KPIs and trend history backed by DuckDB.
"""

from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.kpi_engine import KPIEngine
from app.database import get_db
from app.deps import get_current_user
from app.models.project import Project
from app.models.user import User
from app.models.workspace import Workspace

router=APIRouter()

class KPIPoint(BaseModel):
    metric_name: str
    current_value: float
    previous_value: float | None
    change_percent: float | None
    period: str
    unit: str
    trend: str

class KPIHistoryPoint(BaseModel):
    snapshot_date: date
    metric_value: float

async def _verify_workspace_access(
workspace_id: str, user: User, db: AsyncSession
) -> Workspace:
    """Ensure the requesting user belongs to the workspace's org."""

    result = await db.execute(
        select(Workspace).join(Project).where(
            Workspace.id == workspace_id, 
            Project.organization_id == user.organization_id,
        )
    )

    ws = result.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws

@router.get("/kpis", response_model=list[KPIPoint])
async def get_kpis(
    workspace_id: str = Query(...),
    current_user: User = Depends (get_current_user),
    db: AsyncSession = Depends(get_db),
):

    """Compute the current KPI snapshot for a workspace (live, not cached)."""
    await _verify_workspace_access (workspace_id, current_user, db)

    engine=KPIEngine(workspace_id)
    kpis=engine.compute_all()
    return [
        KPIPoint(
            metric_name=k.metric_name,
            current_value=k.current_value,
            previous_value=k.previous_value,
            change_percent=k.change_percent,
            period=k.period,
            unit=k.unit,
            trend=k.trend,
        )
        for k in kpis.values()
    ]

@router.get("/kpis/{metric_name}/history", response_model=list[KPIHistoryPoint])
async def get_kpi_history(
    metric_name: str,
    workspace_id: str = Query(...),
    days: int = Query(90, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return historical daily snapshots for one metric, oldest first."""

    await _verify_workspace_access(workspace_id, current_user, db) 
    rows = KPIEngine(workspace_id).history(metric_name, days=days)
    return [KPIHistoryPoint(**r) for r in rows]

@router.post("/kpis/snapshot")
async def trigger_kpi_snapshot(
    workspace_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger a KPI snapshot (also runs nightly via Celery beat)."""
    await _verify_workspace_access(workspace_id, current_user, db) 
    from app.tasks.ingestion_tasks import snapshot_workspace_kpis 
    snapshot_workspace_kpis.delay(workspace_id)
    return {"status": "queued", "workspace_id": workspace_id}