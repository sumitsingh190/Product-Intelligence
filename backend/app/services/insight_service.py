import math

from sqlalchemy import func,select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.insight import Insight
from app.schemas.common import PaginatedResponse
from app.schemas.insight import InsightFilter



class InsightService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        
    async def get_by_id(self, insight_id: str) -> Insight | None:
        result = await self.db.execute(select(Insight).where(Insight.id == insight_id))
        return result.scalar_one_or_none()

    async def list_by_workspace(
        self, workspace_id: str, filters: InsightFilter
    )-> PaginatedResponse:
        query=select(Insight).where(Insight.workspace_id == workspace_id)
        count_query = (
            select(func.count()).select_from(Insight).where(Insight.workspace_id == workspace_id)
        )

        if filters.insight_type:
            query = query.where(Insight.insight_type == filters.insight_type)
            count_query = count_query.where(Insight.insight_type == filters.insight_type)
        if filters.severity:
            query = query.where(Insight.severity == filters.severity)
            count_query = count_query.where(Insight.severity == filters.severity)
        if filters.status:
            query = query.where(Insight.status == filters.status)
            count_query = count_query.where(Insight.status == filters.status)

        offset = (filters.page - 1) * filters.page_size
        query = query.order_by(Insight.created_at.desc()).offset(offset).limit(filters.page_size)

        result = await self.db.execute(query)
        insights = result.scalars().all()

        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        return PaginatedResponse(
            items=list(insights),
            total=total,
            page=filters.page,
            page_size=filters.page_size,
            pages=math.ceil(total / filters.page_size) if total else 0,
        )
    

    async def update_status(self, insight_id: str, new_status: str) -> Insight | None:
        insight = await self.get_by_id(insight_id)
        if not insight:
            return None
        insight.status = new_status
        await self.db.flush()
        await self.db.refresh(insight)
        return insight