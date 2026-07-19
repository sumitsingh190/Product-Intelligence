from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func,select

from app.deps import CurrentUserDep, SessionDep, ensure_workspace_access
from app.models.workspace import Workspace
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.workspace import WorkspaceCreate, WorkspaceResponse, WorkspaceUpdate
from app.services.workspace_service import WorkspaceService

router=APIRouter()

@router.get("/current", response_model=WorkspaceResponse)
async def get_current_workspace(current_user: CurrentUserDep, db: SessionDep):
    """Return the workspace this user belongs to."""
    if not current_user.workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User has no workspace",
        )
    result=await db.execute(
        select(Workspace).where(
            Workspace.id == current_user.workspace_id, 
            Workspace.is_active == True
        ) 
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found",
        )
    return workspace

@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(payload: WorkspaceCreate, current_user: CurrentUserDep, db: SessionDep,):
    service = WorkspaceService(db) 
    return await service.create(payload)

@router.get("", response_model=PaginatedResponse [WorkspaceResponse])

async def list_workspaces(current_user: CurrentUserDep, db: SessionDep, page: int=1, page_size: int=20, ):
    if getattr(current_user, "is_superuser", False): 
        service=WorkspaceService(db) 
        return await service.list_all(page=page, page_size=page_size)

    if not current_user.workspace_id:
        return PaginatedResponse(items=[], total=0, page=page, page_size=page_size, pages=0)

    result = await db.execute(
        select (Workspace).where(
            Workspace.id == current_user.workspace_id, 
            Workspace.is_active == True))

    workspaces=list(result.scalars().all()) 
    return PaginatedResponse( 
        items=workspaces, 
        total=len(workspaces), 
        page=1, 
        page_size=page_size, 
        pages=1 if workspaces else 0,
    )

@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(workspace_id: str, current_user: CurrentUserDep, db: SessionDep):
    ensure_workspace_access(current_user, workspace_id)
    service=WorkspaceService(db)
    workspace=await service.get_by_id(workspace_id)
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return workspace

@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: str,
    payload: WorkspaceUpdate,
    current_user: CurrentUserDep,
    db: SessionDep,
):
    ensure_workspace_access(current_user, workspace_id)
    service=WorkspaceService(db)
    workspace = await service.update(workspace_id, payload)
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return workspace

@router.delete("/{workspace_id}", response_model=MessageResponse)
async def delete_workspace (workspace_id: str, current_user: CurrentUserDep, db: SessionDep):
    ensure_workspace_access(current_user, workspace_id)
    service=WorkspaceService(db)
    deleted=await service.delete(workspace_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return MessageResponse(message="Workspace deleted")