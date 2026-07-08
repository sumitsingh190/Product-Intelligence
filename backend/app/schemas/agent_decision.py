"""Schemas for Agent Decision"."""

from __future__ import annotations
from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


DecisionKind = Literal ["accepted", "rejected", "deferred", "in_progress", "completed"]

class DecisionCreate(BaseModel):
    decision: DecisionKind
    reason: str | None = Field(default=None, max_length=2000)

class DecisionResponse (BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    workspace_id: str
    recommendation_id: str
    decided_by_user_id: str | None
    decision: str
    reason: str | None
    snapshot: dict
    created_at: datetime