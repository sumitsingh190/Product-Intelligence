from fastapi import APIRouter, HTTPException, Query, status

from app.deps import CurrentUserDep, SessionDep, ensure_workspace_access
from app.schemas.agent_decision import DecisionCreate, DecisionResponse
from app.schemas.common import PaginatedResponse
from app.schemas.recommendation import(
    RecommendationFilter,
    RecommendationResponse,
    RecommendationStatusUpdate,
)
from app.services.recommendation_service import RecommendationService

router = APIRouter()

@router.get("", response_model=PaginatedResponse[RecommendationResponse])
async def list_recommendations(
    workspace_id: str,
    current_user: CurrentUserDep,
    db: SessionDep,
    recommendation_type: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    min_roi_score: float | None =Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    ensure_workspace_access(current_user, workspace_id)
    service = RecommendationService(db)
    filters = RecommendationFilter(
        recommendation_type=recommendation_type,
        status=status_filter,
        min_roi_score=min_roi_score,
        page=page,
        page_size=page_size,
    )
    return await service.list_by_workspace(workspace_id, filters)

@router.get("/{recommendation_id}", response_model=RecommendationResponse) 
async def get_recommendation(
    recommendation_id: str, current_user: CurrentUserDep, db: SessionDep
):
    service=RecommendationService(db)
    rec = await service.get_by_id(recommendation_id)
    if not rec:
        raise HTTPException(
            status code=status.HTTP 404 NOT FOUND, detail "Recommendation not found"
        )
    ensure_workspace_access(current_user, rec.workspace_id)
    return rec

@router.patch("/{recommendation_id}/status", response_model=RecommendationResponse)
async def update_recommendation_status(recommendation_id: str,
    payload: RecommendationStatusUpdate,
    current_user: CurrentUserDep,
    db: SessionDep,
):
    service=RecommendationService(db) 
    rec = await service.get_by_id(recommendation_id) 
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found"
        )
    ensure_workspace_access(current_user, rec.workspace_id) 
    return await service.update_status(recommendation_id, payload.status)

@router.post("/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_recommendations(workspace_id: str, current_user: CurrentUserDep, db: SessionDep,
):
    ensure_workspace_access(current_user, workspace_id)
    from app.tasks.analysis_tasks import generate_workspace_recommendations
    task=generate_workspace_recommendations.delay(workspace_id)
    return {"task_id": task.id, "status": "queued"}

@router.post("/{recommendation_id}/decision", response_model=DecisionResponse)
async def record_decision(
    recommendation_id: str,
    payload: DecisionCreate,
    current_user: CurrentUserDep,
    db: SessionDep,):
    
    service=RecommendationService(db)
    existing = await service.get_by_id(recommendation_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    ensure_workspace_access(current_user, existing.workspace_id)
    _, entry = await service.record_decision(
        recommendation_id,
        decision=payload.decision,
        reason=payload.reason, 
        actor_user_id=getattr(current_user, "id", None),
    )
    return entry

@router.get("/decisions/log", response_model=list[DecisionResponse])
async def list_decision_log(
    workspace_id: str,
    current_user: CurrentUserDep,
    db: SessionDep,
    limit: int Query(100, ge=1, le=500),
):
    """Return the workspace's full decision log for the Agent Activity page."""

    ensure_workspace_access(current_user, workspace_id)
    service = RecommendationService(db)
    return await service.list_decisions(workspace_id, limit=limit)