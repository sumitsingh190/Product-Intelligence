from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import TimestampSchema

WorkspaceType = Literal["product", "mobile_app", "web_app", "api", "platform"]

class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    workspace_type: WorkspaceType = "product"
    config: dict = {}

class WorkspaceUpdate (BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    workspace_type: WorkspaceType | None = None
    config: dict | None = None

class WorkspaceResponse(TimestampSchema):
    id: str
    name: str
    slug: str
    description: str | None
    workspace_type: str
    is_active: bool
    config: dict