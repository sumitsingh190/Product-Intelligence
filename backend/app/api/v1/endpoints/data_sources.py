from fastapi import APIRouter, Depends, HTTPException, status
from app.core.rbac import require_min_role
from app.deps import CurrentUserDep, SessionDep, ensure_workspace_access
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.data_source import DataSourceCreate, DataSourceResponse, DataSourceUpdate
from app.services.data_source_service import DataSourceService
router = APIRouter()
async def _load(service, source_id, user):
    source = await service.get_by_id(source_id)
    if source is None: raise HTTPException(status_code=404, detail='Data source not found')
    ensure_workspace_access(user, source.workspace_id)
    return source
@router.post('', response_model=DataSourceResponse, status_code=status.HTTP_201_CREATED)
async def create_data_source(payload: DataSourceCreate, workspace_id: str, db: SessionDep, current_user=Depends(require_min_role('admin'))):
    ensure_workspace_access(current_user, workspace_id)
    return await DataSourceService(db).create(payload, workspace_id)
@router.get('', response_model=PaginatedResponse[DataSourceResponse])
async def list_data_sources(workspace_id: str, current_user: CurrentUserDep, db: SessionDep, page: int = 1, page_size: int = 50):
    ensure_workspace_access(current_user, workspace_id)
    return await DataSourceService(db).list_by_workspace(workspace_id, page, page_size)
@router.get('/{data_source_id}', response_model=DataSourceResponse)
async def get_data_source(data_source_id: str, current_user: CurrentUserDep, db: SessionDep):
    service = DataSourceService(db); await _load(service, data_source_id, current_user)
    return await service.get_response(data_source_id)
@router.patch('/{data_source_id}', response_model=DataSourceResponse)
async def update_data_source(data_source_id: str, payload: DataSourceUpdate, db: SessionDep, current_user=Depends(require_min_role('admin'))):
    service = DataSourceService(db); await _load(service, data_source_id, current_user)
    return await service.update(data_source_id, payload)
@router.delete('/{data_source_id}', response_model=MessageResponse)
async def delete_data_source(data_source_id: str, db: SessionDep, current_user=Depends(require_min_role('admin'))):
    service = DataSourceService(db); await _load(service, data_source_id, current_user)
    await service.delete(data_source_id); return MessageResponse(message='Data source deleted')
