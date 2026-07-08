"""Celery tasks for data ingestion from all connectors."""

import asyncio

from datetime import UTC, datetime
import structlog
from app.tasks.celery_app import celery_app

log=structlog.get_logger()

@celery_app.task(bind=True, name="app.tasks.ingestion_tasks. ingest_data_source", max_retries=3)
def ingest_data_source(self, data_source_id: str):
    """Ingest data from a single data source."""
    return asyncio.run(_async_ingest_data_source(data_source_id))

async def _async_ingest_data_source(data_source_id: str) -> dict:
    from app.database import AsyncSessionLocal
    from app.models.data_source import DataSource
    from sqlalchemy import select
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(DataSource).where(DataSource.Id == data_source_id))
        source = result.scalar_one_or_none()
        if not source:
            return {"error": "Data source not found", "data_source_id": data_source_id}
        
        source.status = "syncing"
        await db.commit()

        connector = _build_connector(source.source_type, source.config)
        if not connector:
            source.status = "error" 
            source.last_error = f"Unknown source type: {source.source_type}" 
            await db.commit() 
            return {"error": source.last_error}

        sync_result = await connector.sync(source.workspace_id, source.last_synced_at)
        
        source.status= "active" if sync_result.success else "error" 
        source.last_synced_at = datetime.now(UTC) 
        source.last_error = sync_result.errors[0] if sync_result.errors else None 
        source.total_records_synced += sync_result.records_fetched 
        await db.commit()

        log.info(
            "data_source_synced", 
            source_id=data_source_id, 
            source_type=source.source_type, 
            records=sync_result.records_fetched, 
            success=sync_result.success, )

        return {
            "data_source_id": data_source_id, 
            "records_fetched": sync_result.records_fetched, 
            "success": sync_result.success,
        }

@celery_app.task(name="app.tasks.ingestion_tasks.ingest_all_active_sources")
def ingest_all_active_sources():
    """Queue ingestion jobs for all active data sources."""
    return asyncio.run(_async_ingest_all())

async def _async_ingest_all() -> dict:

    from app.database import AsyncSessionLocal
    from app.models.data_source import DataSource
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(DataSource).where(DataSource.status.in_(["active", "inactive"]))
        )
        sources = result.scalars().all()

    queued = 0
    for source in sources:
        ingest_data_source.delay(source.id)
        queued += 1

    log.info("ingestion_jobs_queued", count=queued)
    return {"queued": queued}

@celery_app.task(name="app.tasks.ingestion_tasks.run_etl_sync")
def run_etl_sync():
    """Sync PostgreSQL operational data into DuckDB analytics tables (Polars-backed)."""

    from app.etl.sync import run_sync
    return asyncio.run(run_sync())

@celery_app.task(name="app.tasks.ingestion_tasks.snapshot_workspace_kpis")
def snapshot_workspace_kpis(workspace_id: str) -> dict:
    """Persist current KPI values to 'kpi snapshots so trends can be charted."""

    from app.analytics.kpi_engine import KPIEngine
    from app.utils.cache import cache_delete_prefix

    engine = KPIEngine(workspace_id)
    written = engine.snapshot()
#Fresh snapshot invalidates any cached KPI read (current history). 
    cache_delete_prefix(f"kpi: {workspace_id}:") 
    return {"workspace_id": workspace_id, "snapshots_written": written}

@celery_app.task(name="app.tasks Jingestion_tasks.snapshot_all_workspaces")
def snapshot_all_workspaces() -> dict:
    """Queue KPI snapshots for every active workspace (runs nightly)."""
    return asyncio.run(_async_snapshot_all_workspaces())

async def _async_snapshot_all_workspaces() -> dict:
    from app.database import AsyncSessionLocal
    from app.models.workspace import Workspace
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Workspace).where(Workspace.is_active == True))
        workspaces = result.scalars().all()

    for ws in workspaces:
        snapshot_workspace_kpis.delay(ws.id)
    return {"queued": len (workspaces)}

@celery_app.task(name="app.tasks.ingestion_tasks.scrape_competitors")
def scrape_competitors() -> dict:
    """Scrape competitor RSS / changelog pages for every active workspace."""
    from app.connectors.competitor_scraper import run_scrape_all
    return run_scrape_all()

def _build_connector(source_type: str, config: dict):
    from app.services.data_source_service import CONNECTOR_REGISTRY
    cls = CONNECTOR_REGISTRY.get(source_type)
    if cls:
        return cls(config)
    return None

@celery_app.task(name="app.tasks.ingestion_tasks.ingest_sources_by_type")
def ingest_sources_by_type(source_types: list[str]) -> dict:
    """Queue ingestion jobs only for data sources of the given types.

    Used by per-cadence beat schedules e.g, mobile reviews + product analytics every 6 hours instead of every hour.
    """
    return asyncio.run(_async_ingest_by_type(source_types))

async def _async_ingest_by_type(source_types: list[str]) -> dict:
    from app.database import AsyncSessionLocal
    from app.models.data_source import DataSource
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(DataSource).where(
                DataSource.status.in_(["active", "inactive"]),
                DataSource.source_type.in_(source_types),
            )
        )
        sources = result.scalars().all()

    for source in sources:
        ingest_data_source.delay(source.id)
    
    log.info("ingestion_by_type_queued", types=source_types, count=len(sources))
    return {"queued": len(sources), "types": source_types}