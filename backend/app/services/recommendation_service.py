import math

from sqlalchemy import func,select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_decision import AgentDecision
from app.models.recommendation import Recommendation
from app.schemas.common import PaginatedResponse

class RecommendationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
    
    async def get_by_id(self, rec_id: str) -> Recommendation | None:
        result = await self.db.execute(
            select(Recommendation).where(Recommendation.id == rec_id)
        )
        return result.scalar_one_or_none()

    async def list_by_workspace(self, workspace_id: str, filters) -> PaginatedResponse: 
        query = select(Recommendation).where(Recommendation.workspace_id ==workspace_id) 
        count_query = (
            select(func.count())
            .select_from(Recommendation)
            .where(Recommendation.workspace_id == workspace_id)
        )

        if filters.recommendation_type:
            query = query.where(Recommendation.recommendation_type == filters.recommendation_type) 
            count_query = count_query.where(Recommendation.recommendation_type == filters.recommendation_type)
    
        if filters.status:
            query = query.where(Recommendation.status == filters.status)
            count_query = count_query.where(Recommendation.status == filters.status)

        if filters.min_roi_score is not None: 
            query = query.where(Recommendation.roi_score >= filters.min_roi_score) 
            count_query = count_query.where(Recommendation.roi_score >= filters.min_roi_score)

        offset = (filters.page - 1) * filters.page_size
        query = (
            query.order_by(Recommendation.priority_rank.asc(), Recommendation.roi_score.desc()) 
            .offset(offset)
            .limit(filters.page_size)
        )     
        result = await self.db.execute(query)
        recs = result.scalars().all()

        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()
        
        return PaginatedResponse(
            items=list(recs),
            total=total,
            page=filters.page,
            page_size=filters.page_size,
            pages=math.ceil(total / filters.page_size) if total else 8,
        )
    
    async def update_status(self, rec_id: str, new_status: str) -> Recommendation | None:
        rec = await self.get_by_id(rec_id)
        if not rec:
            return None
        rec.status = new_status
        await self.db.flush()
        await self.db.refresh(rec)
        return rec

    async def record_decision(
        self,
        rec_id: str,
        decision: str,
        reason: str | None,
        actor_user_id: str | None,
    ):
        """Update the recommendation status and append an AgentDecision row in the same transaction so audit + status can never diverge."""
        rec = await self.get_by_id(rec_id)
        if not rec:
            return None, None
        rec.status = decision
        entry = AgentDecision(
            workspace_id=rec.workspace_id,
            recommendation_id=rec.id,
            decided_by_user_id=actor_user_id,
            decision=decision,
            reason=reason,
            snapshot={
                "title": rec.title,
                "description": rec.description,
                "recommendation_type": rec.recommendation_type,
                "impact_score": rec.impact_score,
                "effort_score": rec.effort_score,
                "roi_score": rec.roi_score,
                "evidence": rec.evidence,
            },
        )
        self.db.add(entry)
        await self.db.flush()
        await self.db.refresh(rec)
        await self.db.refresh(entry)
        return rec, entry

    async def list_decisions(self, workspace_id: str, limit: int = 100):
        """Return the workspace's decision log, newest first."""
        result=await self.db.execute(
            select(AgentDecision)
            .where(AgentDecision.workspace_id == workspace_id)
            .order_by(AgentDecision.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())