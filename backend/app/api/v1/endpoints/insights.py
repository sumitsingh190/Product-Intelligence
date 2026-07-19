from fastapi import APIRouter, HTTPException, Query, status
from app.deps import CurrentUserDep, SessionDep, ensure_workspace_access
from app.schemas.common import PaginatedResponse
from app.schemas.insight import InsightFilter, InsightResponse, InsightStatusUpdate
from app.services.insight_service import InsightService

router=APIRouter()

@router.get("", response_model=PaginatedResponse[InsightResponse])
async def list_insights(
    workspace_id: str,
    current_user: CurrentUserDep,
    db: SessionDep,
    insight_type: str | None = Query(None),
    severity: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    page: int=Query(1, ge=1),
    page_size: int = Query (20, ge=1, le=100),
):
    ensure_workspace_access(current_user, workspace_id)
    service = InsightService(db)
    filters = InsightFilter(
        insight_type=insight_type,
        severity=severity,
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    return await service.list_by_workspace(workspace_id, filters)

@router.get("/{insight_id}", response_model=InsightResponse)
async def get_insight(insight_id: str, current_user: CurrentUserDep, db: SessionDep):
    service=InsightService(db)
    insight=await service.get_by_id(insight_id)
    if not insight:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insight not found")
    ensure_workspace_access(current_user, insight.workspace_id)
    return insight

@router.patch("/{insight_id}/status", response_model=InsightResponse)
async def update_insight_status(
    insight_id: str,
    payload: InsightStatusUpdate,
    current_user: CurrentUserDep,
    db: SessionDep,
):
    service=InsightService(db)
    insight = await service.get_by_id(insight_id)
    if not insight:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insight not found")
    ensure_workspace_access(current_user, insight.workspace_id)
    return await service.update_status(insight_id, payload.status)


@router.post("/analyze", status_code=status.HTTP_202_ACCEPTED)
async def trigger_analysis(
    workspace_id: str,
    current_user: CurrentUserDep,
    db: SessionDep,
):
    """Trigger Al analysis for the workspace. Returns a task 10 for polling. """
    ensure_workspace_access(current_user, workspace_id) 
    from app.tasks.analysis_tasks import run_workspace_analysis
    task = run_workspace_analysis.delay(workspace_id) 
    return {"task_id": task.id, "status": "queued"}