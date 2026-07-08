import uuid
import math

from slugify import slugify
from sqlalchemy import func,select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workspace import Workspace
from app.schemas.common import PaginatedResponse
from app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate

class WorkspaceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, payload: WorkspaceCreate) -> Workspace:
        slug = slugify(payload.name)
        workspace = Workspace(
            id=str(uuid.uuid4()),
            name=payload.name,
            slug=slug,
            description=payload.description,
            workspace_type=payload.workspace_fype,
            config=payload.config,
        )
        self.db.add(workspace)
        await self.db.flush()
        await self.db.refresh(workspace)
        return workspace

    async def get_by_id(self, workspace_id: str) -> Workspace | None:
        result = await self.db.execute(select(Workspace).where(Workspace.id == workspace_id))
        return result.scalar_one_or_none()

    async def list_all(
        self, page: int = 1, page_size: int = 20
    ) -> PaginatedResponse:
        offset = (page - 1) * page_size
        result = await self.db.execute(
            select(Workspace)
            .where(Workspace.is_active == True)
            .order_by(Workspace.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        workspaces=result.scalars().all()
        count_result = await self.db.execute(
                select(func.count())
                .select_from(Workspace)
                .where(Workspace.is_active == True)
        )
        total = count_result.scalar_one()
        return PaginatedResponse(
            items=list(workspaces),
            total=total,
            page=page,
            page_size=page_size, 
            pages=math.ceil(total/page_size) if total else 0,
        )
    
    async def update(self, workspace_id: str, payload: WorkspaceUpdate) -> Workspace | None:
        workspace = await self.get_by_id(workspace_id)
        if not workspace:
            return None
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(workspace, field, value)
        await self.db.flush()
        await self.db.refresh(workspace)
        return workspace

    async def delete(self, workspace_id: str) -> bool:
        workspace = await self.get_by_id(workspace_id)
        if not workspace:
            return False
        workspace.is_active = False
        await self.db.flush()
        return True