from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import TimestampSchema

RecommendationType = Literal["feature", "bug fix", "performance", "ux", "security", "tech_debt", "research"]
RecommendationStatus = Literal ["new", "accepted", "rejected", "in_progress", "completed", "deferred"]

class RecommendationResponse(TimestampSchema):
    id: str
    title: str
    description: str
    rationale: str | None
    recommendation_type: RecommendationType
    status: RecommendationStatus
    impact_score: float
    effort_score: float
    confidence_score: float
    roi_score: float
    priority_rank: int
    estimated_effort_days: int | None
    estimated_users_impacted: int | None
    estimated_revenue_impact: float | None
    evidence: list
    insight_ids: list[str]
    tags: list[str]
    acceptance_criteria: list
    workspace_id: str
    ai_metadata: dict

class RecommendationStatusUpdate (BaseModel):
    status: RecommendationStatus

class RecommendationFilter(BaseModel):
    recommendation_type: RecommendationType | None = None
    status: RecommendationStatus | None=None
    min_roi_score: float | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)