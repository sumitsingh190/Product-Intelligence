import math
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import BaseConnector
from app.connectors.csv_connector import CSVUploadConnector
from app.connectors.github_connector import GitHubConnector
from app.connectors.jira_connector import JiraConnector
from app.connectors.slack_connector import SlackConnector

from app.models.data_source import DataSource
from app.schemas.common import PaginatedResponse
from app.schemas.data_source import (
    DataSourceCreate, DataSourceUpdate, mask_config
)

CONNECTOR_REGISTRY: dict[str, type [BaseConnector]] = {
    "github": GitHubConnector,
    "jira": JiraConnector,
    "slack": SlackConnector,
    "csv_upload": CSVUploadConnector,
}


def _build_connector(source_type: str, config: dict[str, Any]) -> BaseConnector | None:
    cls = CONNECTOR_REGISTRY.get(source_type)
    if cls is None:
        return None
    return cls(config or {})


def _to_response_dict(ds: DataSource) -> dict:
    return {
        "id": ds.id,
        "name": ds.name,
        "source_type": ds.source_type,
        "status": ds.status,
        "config": mask_config(ds.config or ()),
        "last_synced_at": ds.last_synced_at,
        "last_error": ds.last_error,
        "sync_interval_seconds": ds.sync_interval_seconds,
        "total_records_synced": ds.total_records_synced,
        "workspace_id": ds.workspace_id, 
        "created_at" : ds.created_at,
        "updated_at": ds.updated_at,
    }

class DataSourceService:
    def __init__(self, db: AsyncSession, actor_user_id: str | None = None) -> None:
        self.db = db
        self.actor_user_id = actor_user_id

    async def create(self, payload: DataSourceCreate, workspace_id: str) -> dict:
        ds = DataSource(
            id=str(uuid.uuid4()),
            name=payload.name,
            source_type=payload.source_type,
            status="inactive",
            config=payload.config or {},
            sync_interval_seconds=payload.sync_interval_seconds,
            workspace_id=workspace_id,
            ) 
        self.db.add(ds)
        await self.db.flush()
        await self.db.refresh(ds)
        return _to_response_dict(ds)

    async def get_by_id(self, data_source_id: str) -> DataSource | None: 
        result = await self.db.execute(
            select(DataSource).where(DataSource.id == data_source_id)
        )
        return result.scalar_one_or_none()

    async def get_response(self, data_source_id: str) -> dict | None: 
        ds = await self.get_by_id(data_source_id)
        return _to_response_dict(ds) if ds else None

    async def list_by_workspace(
        self, workspace_id: str, page: int = 1, page_size: int= 50
    ) -> PaginatedResponse:
        offset = (page-1)*page_size
        result = await self.db.execute(select(DataSource).where(DataSource.workspace_id == workspace_id).order_by(DataSource.created_at.desc())
        .offset(offset)
        .limit(page_size)
        )
        rows = result.scalars().all()
        count_result = await self.db.execute(
            select(func.count())
            .select_from(DataSource)
            .where(DataSource.workspace_id == workspace_id)
        )
        total = count_result.scalar_one()
        return PaginatedResponse(
            items=[_to_response_dict(r) for r in rows],
            total=total,
            page=page,
            page_size=page_size, 
            pages=math.ceil(total/page_size) if total else 0,
        )
    
    async def update(self, data_source_id: str, payload: DataSourceUpdate) -> dict | None:
        ds = await self.get_by_id(data_source_id)
        if not ds:
            return None
        data=payload.model_dump(exclude_unset=True)
        if "config" in data and data["config"] is not None:
            ds.config={**(ds.config or {}), **data["config"]}
            del data["config"]
        for field, value in data.items():
            setattr(ds, field, value)

        await self.db.flush()
        await self.db.refresh(ds)
        return _to_response_dict(ds)

    async def delete(self, data_source_id: str) -> bool:
        ds = await self.get_by_id(data_source_id)
        if not ds:
            return False
        await self.db.delete(ds)
        await self.db.flush()
        return True

    async def test_connection(self, data_source_id: str) -> tuple [bool, str]:
        ds = await self.get_by_id(data_source_id)
        if not ds:
            return False, "Data source not found"

        connector = _build_connector(ds.source_type, ds.config or ())
        if connector is None:
            return False, f"No connector implementation for '{ds.source_type}'"

        try:
            ok = await connector.test_connection()
        except Exception as e:
            ds.status = "error"
            ds.last_error = str(e)
            await self.db.flush()
            return False, f"Connection failed: {e}"

        if ok:
            ds.status = "active"
            ds.last_error = None
        else:
            ds.status = "error"
            ds.last_error = "Authentication or endpoint check failed"
        await self.db.flush()
        return ok, "Connection successful" if ok else (ds.last_error or "Connection failed")

    async def trigger_sync(self, data_source_id: str) -> tuple[bool, str]:
        ds = await self.get_by_id(data_source_id)
        if not ds:
            return False, "Data source not found"
        connector = _build_connector(ds.source_type, ds.config or {})
        if connector is None:
            return False, f"No connector implementation for '{ds.source_type}'"
        ds.status = "syncing"
        await self.db.flush()
        try:
            result = await connector.sync(workspace_id=ds.workspace_id)
        except Exception as e:
            ds.status = "error"
            ds.last_error = str(e)
            await self.db.flush()
            return False, f"Sync failed: {e}"
        ds.status = "active" if result.success else "error"
        ds.last_synced_at=datetime.now(UTC)
        ds.total_records_synced = (ds.total_records_synced or e) + result.records_fetched
        ds.last_error = "; ".join(result.errors) if result.errors else None
        await self.db.flush()
        return result.success,(
            f"Synced {result.records_fetched} records"
            if result.success
            else (ds.last_error or "Sync failed")
        )