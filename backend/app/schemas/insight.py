from typing import Literal
from pydantic import BaseModel, Field

from app.schemas.common import TimestampSchema

InsightType = Literal["customer_feedback", "engineering", "analytics", "competitor", "product_health"]
InsightSeverity = Literal["critical", "high", "medium", "low", "info"]
InsightStatus = Literal["new", "acknowledged", "in_progress", "resolved", "dismissed"]

class InsightResponse(TimestampSchema):
    id: str
    title: str
    summary: str
    detail: str | None
    insight_type: InsightType
    severity: InsightSeverity
    status: InsightStatus
    confidence_score: float
    affected_users_estimate: int | None
    evidence: list
    tags: list[str]
    workspace_id: str
    ai_metadata: dict

class InsightStatusUpdate (BaseModel):
    status: InsightStatus

class InsightFilter(BaseModel):
    insight_type: InsightType | None = None
    severity: InsightSeverity | None = None
    status: InsightStatus | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)