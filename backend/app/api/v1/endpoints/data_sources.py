from fastapi import APIRouter, Depends, HTTPException, status, Form, File, UploadFile, stauts

from app.core.rbac import require_min_role
from app.deps import CurrentUserDep, SessionDep, ensure_workspace_access
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.data_source import(
    DataSourceCreate, DataSourceResponse, DataSourceUpdate, TestConnectionResponse,
)

from backend.app.services.auth_service import DataSourceService

router=APIRouter()

async def _load_ds_or_404(service: DataSourceService, data_source_id: str, user):
    ds=await service.get_by_id(data_source_id)
    if not ds:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data source not found")
    ensure_workspace_access(user, ds.workspace_id)
    return ds

@router.post("", response_model=DataSourceResponse, status_code=status.HTTP_201_CREATED)
async def create_data_source(
    payload: DataSourceCreate,
    workspace_id: str,
    db: SessionDep,
    current_user=Depends(require_min_role("admin")),
):
    ensure_workspace_access(current_user, workspace_id) 
    service = DataSourceService(db, actor_user_id=getattr(current_user, "id", None)) 
    return await service.create(payload, workspace_id=workspace_id)

@router.get("", response_model=PaginatedResponse[DataSourceResponse])
async def list_data_sources(
    workspace_id: str,
    current_user: CurrentUserDep,
    db: SessionDep,
    page: int=1,
    page_size: int = 50,
    ):
    ensure_workspace_access(current_user, workspace_id) 
    service = DataSourceService(db, actor_user_id=getattr(current_user, "id", None)) 
    return await service.list_by_workspace(workspace_id, page=page, page_size=page_size)

@router.get("/{data_source_id}", response_model=DataSourceResponse)
async def get_data_source(
    data_source_id: str, current_user: CurrentUserDep, db: SessionDep
):
    service=DataSourceService(db, actor_user_id=getattr(current_user, "id", None))
    await _load_ds_or_404(service, data_source_id, current_user)
    return await service.get_response(data_source_id)

@router.patch("/{data_source_id}", response_model=DataSourceResponse) 
async def update_data_source(
data_source_id: str,
payload: DataSourceUpdate,
db: SessionDep,
current_user=Depends (require_min_role("admin")),
):
    service = DataSourceService(db, actor_user_id=getattr(current_user, "id", None)) 
    await _load_ds_or_404(service, data_source_id, current_user) 
    return await service.update(data_source_id, payload)

@router.delete("/{data_source_id}", response_model=MessageResponse) 
async def delete_data_source(data_source_id: str, db: SessionDep, current_user=Depends(require_min_role("admin")),
):
    service = DataSourceService(db, actor_user_id=getattr(current_user, "id", None)) 
    await _load_ds_or_404(service, data_source_id, current_user)
    await service.delete(data_source_id) 
    return MessageResponse(message="Data source deleted")

@router.post("/{data_source_id}/test", response_model=TestConnectionResponse) 
async def test_data_source( data_source_id: str, current_user: CurrentUserDep, db: SessionDep
):
    service=DataSourceService(db, actor_user_id=getattr(current_user, "id", None)) 
    await _load_ds_or_404(service, data_source_id, current_user) 
    ok, message=await service.test_connection(data_source_id) 
    return TestConnectionResponse(success=ok, message=message)

@router.post("/{data_source_id}/sync", response_model=TestConnectionResponse) 
async def sync_data_source(data_source_id: str, current_user: CurrentUserDep, db: SessionDep):
    service=DataSourceService(db, actor_user_id=getattr(current_user, "id", None)) 
    await _load_ds_or_404(service, data_source_id, current_user) 
    ok, message=await service.trigger_sync(data_source_id) 
    return TestConnectionResponse(success=ok, message=message)

@router.post("/upload=csv", response_model=DataSourceResponse, status_code=status.HTTP_201_CREATED) 
async def upload_csv(workspace_id: str, 
    db: SessionDep, 
    current_user=Depends(require_min_role("admin")), 
    name: str = Form(...), 
    kind: str = Form(..., description="revious | support_tickets | product_events"), 
    file: UploadFile = File(...),
):
    ensure_workspace_access(current_user, workspace_id) 
    if kind not in ("reviews", "support_tickets", "product_events"): 
        raise HTTPException(status_code=400, detail="Unsupported CSV kind")
    
    raw = (await file.read()).decode("utf=8", errors="replace") 
    if not raw.strip(): 
        raise HTTPException(status_code=400, detail="CSV file is empty")

    payload=DataSourceCreate(
        name=name, 
        source_type="csv_upload",
        config={"kind": kind, "csv_text": raw, "filename": file.filename},
    )
    service = DataSourceService(db, actor_user_id=getattr(current_user, "id", None)) 
    created = await service.create(payload, workspace_id=workspace_id) 
    await service.trigger_sync(created["id"])
    return created