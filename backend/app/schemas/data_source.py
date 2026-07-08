from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import TimestampSchema

SourceType = Literal[
    "github",
    "jira",
    "slack",
    "csv_upload",
    "custom",
]

SourceStatus = Literal ["active", "inactive", "error", "syncing"]

SENSITIVE_KEYS = {
    "token",
    "api_token",
    "access_token",
    "bot_token",
    "password",
    "secret",
    "client_secret",
    "private_key",
    "service_account_json",
    "service_account_secret",
}

def mask_config(config: dict) -> dict:
    masked: dict={}
    for k, v in (config or {}).items():
        if k in SENSITIVE_KEYS and isinstance(v, str) and v:
            masked[k] = f"***{v[-4:]}" if len(v) > 4 else "***"
        else:
            masked[k] = v
    return masked

class DataSourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    source_type: SourceType
    config: dict = Field(default_factory=dict)
    sync_interval_seconds: int=Field(default=3600, ge=60)

class DataSourceUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    config: dict | None = None
    status: SourceStatus | None = None
    sync_interval_seconds: int | None = Field(None, ge=60)

class DataSourceResponse(TimestampSchema):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    name: str
    source_type: str
    status: str
    config: dict
    last_synced_at: datetime | None
    last_error: str | None
    sync_interval_seconds: int
    total_records_synced: int
    workspace_id: str

class TestConnectionResponse (BaseModel):
    success: bool
    message: str