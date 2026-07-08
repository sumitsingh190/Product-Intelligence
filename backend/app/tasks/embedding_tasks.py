"""Celery task for asynchronous embedding generation.

Called from services after an Insight' or 'Document is committed; never blocks the API response. 
Uses Google 'text=embedding=004 (768=dim) via google=generativeai.
"""

import asyncio
import structlog

from sqlalchemy import select
from app.config import settings 
from app.tasks.celery_app import celery_app

log = structlog.get_logger()

@celery_app.task(name="app.tasks.embedding_tasks.embed_insight", max_retries=2)
def embed_insight(insight_id: str) -> dict:
    if not settings.feature_semantic_search:
        return {"skipped": True, "reason": "semantic_search disabled"}
    return asyncio.run(_async_embed_insight(insight_id))

async def _async_embed_insight(insight_id: str) -> dict:
    from app.database import AsyncSessionLocal
    from app.embeddings.embedding_service import embed_single
    from app.models.insight import Insight
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Insight).where(Insight.id == insight_id))
        insight = result.scalar_one_or_none()
        if not insight:
            return {"error": "insight_not_found"}

        text = f"{insight.title}\n\n{insight.summary}\n\n{insight.detail or ''}"
        try:
            insight.embedding=embed_single(text)
            await db.commit()
            return {"insight_id": insight_id, "embedded": True}
        except Exception as e:
            log.warning("embed_insight_failed", insight_id=insight_id, error=str(e))
            return {"insight_id": insight_id, "embedded": False, "error": str(e)}

@celery_app.task(name="app.tasks.embedding tasks.embed_document", max_retries=2)
def embed_document(document_id: str) -> dict:
    if not settings.feature_semantic_search:
        return {"skipped": True, "reason": "semantic_search disabled"}
    return asyncio.run(_async_embed_document(document_id))

async def _async_embed_document(document_id: str) -> dict:
    from app.database import AsyncSessionLocal
    from app.embeddings.embedding_service import embed_single, embed_texts
    from app.models.document import Document
    from app.models.document_chunk import DocumentChunk
    from sqlalchemy import delete

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if not doc:
            return {"error":"document_not_found"}
        
        text=f"{doc.title}\n\n{doc.content_preview or doc.content[:1500]}"
        try:
            doc.embedding = embed_single(text)
        except Exception as e: # noqa: BLE001
            log.warning("embed_document_failed", document_id=document_id, error=str(e)) 
            return {"document_id": document_id, "embedded": False, "error": str(e)}

#Chunk-level embeddings for RAG on long documents.

        chunks = _chunk_text(doc.content or "", size=500, overlap=50)
        chunks_written = 0
        if chunks:
            try:
                vectors = embed_texts(chunks)
                await db.execute(
                    delete(DocumentChunk).where(DocumentChunk.document_id == doc.id) 
                )
                for idx, (piece, vector) in enumerate (zip(chunks, vectors, strict=False)):
                    db.add(
                        DocumentChunk(
                            document_id=doc.id, 
                            workspace_id=doc.workspace_id, 
                            chunk_index=idx, 
                            content=piece, 
                            embedding=vector, 
                        )
                    )
                    chunks_written += 1
            except Exception as e:
                log.warning("embed_document_chunks_failed", document_id=document_id, error=str(e))

        await db.commit()
        return {"document_id": document_id, "embedded": True, "chunks": chunks_written}

def _chunk_text(text: str, size: int=500, overlap: int=50) -> list[str]:
    """Split "text" into overlapping word chunks. Small and dependency-free."""
    words = text.split()
    if not words:
        return []
    chunks: list[str]=[]
    step= max(size - overlap, 1)
    for start in range(0, len(words), step):
        piece = " ".join(words[start: start + size]).strip()
        if piece:
            chunks.append(piece)
        if start + size >= len(words):
            break
    return chunks
