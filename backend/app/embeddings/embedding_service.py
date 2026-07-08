"""
Embedding service - Google AI Studio (Gemini) embeddings for pgvector.

Uses the `models/text-embedding-004` model by default (768 dims, matches the pgvector column).
Configure via `settings.embedding_model` + `settings.google_api_key`

The google SDK call is synchronous; async call sites wrap it with `asyncio.to_thread` so we never block the event loop.

"""

from __future__ import annotations

import structlog
from app.config import settings

log=structlog.get_logger()

_configured=False

def _ensure_configured() -> None:
    """Configure google.generativeai once with the API key from settings."""
    global _configured
    if _configured:
        return

    if not settings.google_api_key:
        raise RuntimeError(
            "GOOGLE_API_KEY is not set configure it in env to enable embeddings."
        )
    
    import google.generativeai as genai
    genai.configure(api_key=settings.google_api_key)
    _configured=True
    log.info("google_embeddings_configured", model=settings.embedding_model)

def _cache_key(text: str) -> str:
    from app.utils.cache import stable_hash
    return f"emb: {settings.embedding_model}:{settings.embedding_task_type}: {stable_hash(text)}"

def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a list of texts. Returns list of float vectors.
    Batches by settings.embedding_batch_size (Gemini accepts a single list per call for text-embedding-004). 
    Results are cached in Redis keyed by (model, task_type, sha256(text)) with a long TTL, so re-embedding an 
    unchanged insight/document/query is free.
    """
    if not texts:
        return []
    
    from app.utils.cache import cache_mget_json, cache_mset_json

    keys = [_cache_key(t) for t in texts]
    cached = cache_mget_json(keys)
    out: list[list[float] | None] = [c if c is not None else None for c in cached]
    misses = [(i, texts[i]) for i, v in enumerate(out) if v is None]
    if not misses:
        return [v for v in out if v is not None]# type: ignore [misc]

    _ensure_configured()

    import google.generativeai as genai
    batch_size=max(1, int(settings.embedding_batch_size))
    fresh: dict[str, list[float]] = {}

    for start in range(0, len(misses), batch_size):
        batch = misses[start: start + batch_size]
        result = genai.embed_content(
            model=settings.embedding_model, 
            content=[t for _, t in batch],
            task_type=settings.embedding_task_type,
        )
        emb=result["embedding"]

        if emb and isinstance (emb[0], (int, float)):
            vectors = [list(emb)]
        else:
            vectors = [list(v) for v in emb]
        
        for (idx, text), vec in zip(batch, vectors, strict=True):
            out[idx] = vec
            fresh[keys[idx]] = vec

    cache_mset_json(fresh,ttl=settings.cache_ttl_long)
    return [v for v in out]

def embed_single(text: str)-> list[float]:
    return embed_texts([text])[0]