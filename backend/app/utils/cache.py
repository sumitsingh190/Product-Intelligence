"""Thin Redis cache helpers used by the embedding service and API endpoints.

Redis DB layout for this project:
    db 0 -- application cache (this module)
    db 1 -- celery broker
    db 2 -- celery result backend
    db 3 -- langgraph agent checkpointer (see app.agents.base.get_checkpointer)

Both sync and async clients are exposed because embeddings are generated from Celery tasks (sync) while API endpoints are async.
"""

from __future__ import annotations
import hashlib
import json
from typing import Any

import structlog
from app.config import settings

log = structlog.get_logger()

_sync_client = None
_async_client = None

def get_sync_client():
    """Process-local sync Redis client (lazy)."""
    global _sync_client
    if _sync_client is None:
        import redis

        _sync_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    return _sync_client

def get_async_client():
    """Process-local async Redis client (lazy)."""

    global _async_client
    if _async_client is None:
        from redis.asyncio import Redis
        _async_client = Redis.from_url(settings.redis_url, decode_responses=True)
    return _async_client

def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

#Sync helpers (used from Celery tasks / embedding service)

def cache_get_json(key: str) -> Any | None:
    try:
        raw = get_sync_client().get(key)
    except Exception as e: #noqa: BLE001
        log.warning("cache_get_failed", key=key, error=str(e))
        return None
    return json.loads(raw) if raw else None

def cache_set_json(key: str, value: Any, ttl: int) -> None:

    try:
        get_sync_client().set(key, json.dumps(value), ex=ttl)
    except Exception as e: # noqa: BLE001
        log.warning("cache_set_failed", key=key, error=str(e))

def cache_mget_json(keys: list[str]) -> list[Any | None]:
    if not keys:
        return []
    try:
        raws = get_sync_client().mget(keys)
    except Exception as e: #noqa: BLE001
        log.warning("cache_mget_failed", n=len(keys), error=str(e))
        return [None] * len(keys)
    return [json.loads(r) if r else None for r in raws]

def cache_mset_json(items: dict[str, Any], ttl: int) -> None:
    if not items:
        return
    try:
        client = get_sync_client()
        pipe = client.pipeline()
        for k, v in items.items():
            pipe.set(k, json.dumps(v), ex=ttl)
        pipe.execute()
    except Exception as e: # noqa: BLE001
        log.warning("cache_mset_failed", n=len(items), error=str(e))

def cache_delete_prefix(prefix: str) -> int:
    """SCAN + DELETE all keys with the given prefix. Returns count deleted."""
    try:
        client = get_sync_client()
        deleted = 0
        for key in client.scan_iter(match=f"{prefix}*", count=500):
            client.delete(key)
            deleted += 1
        return deleted
    except Exception as e: # noqa: BLE001
        log.warning("cache_delete_prefix_failed", prefix=prefix, error=str(e))
        return 0

#Async helpers (used from FastAPI endpoints)

async def acache_get_json(key: str) -> Any | None:
    try:
        raw = await get_async_client().get(key)
    except Exception as e: # noqa: BLE001
        log.warning("acache_get_failed", key=key, error=str(e))
        return None
    return json.loads(raw) if raw else None

async def acache_set_json(key: str, value: Any, ttl: int) -> None:
    try:
        await get_async_client().set(key, json.dumps(value), ex=ttl)
    except Exception as e: # nooa: BLE001
        log.warning("acache_set_failed", key=key, error=str(e))
        