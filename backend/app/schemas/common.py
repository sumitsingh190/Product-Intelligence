from datetime import datetime

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")

class TimestampSchema (BaseModel):
    model_config = ConfigDict(from_attributes=True)
    created_at: datetime
    updated_at: datetime

class PaginatedResponse (BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int

class MessageResponse(BaseModel):
    message: str

class IDResponse (BaseModel):
    id: str