from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.deps import ensure_workspace_access, get_current_user
from app.models.user import User

router=APIRouter()

class SearchHit(BaseModel):
    id: str
    title: str
    content_preview: str | None = None
    document_type: str | None = None
    kind: str # "document" | "insight"
    similarity: float | None = None
    keyword_score: float | None = None
    fts_score: float | None = None
    rerank_score: float | None = None

@router.get("", response_model=list[SearchHit])
async def search(
    workspace_id: str=Query(...),
    q: str = Query(..., min_length=2),
    top_k: int = Query(10, ge=1, le=50),
    current_user: User=Depends(get_current_user), 
    db: AsyncSession=Depends(get_db),
):
    """Hybrid search over documents + insights. Returns at most top_k hits."""
    if not settings.feature_semantic_search:
        raise HTTPException(status_code=503, detail="Semantic search disabled")
    ensure_workspace_access(current_user, workspace_id)
    try:
        from app.embeddings.embedding_service import embed_single
        query_vec=embed_single(q)
    except Exception:
        query_vec = None

    candidates: list[dict[str, Any]]=[]

    if query_vec is not None:
        doc_rows=await db.execute(
            text(
                """
                SELECT id, title, content_preview, document_type,
                        1 - (embedding <=> CAST(:embedding AS vector)) AS similarity, 
                        similarity(coalesce(content_preview, '') || ' ' || coalesce(title, ''), :q) AS keyword_score,
                        ts_rank_cd(
                            to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content_preview, "")),
                            websearch_to_tsquery('english', :q)
                        ) AS fts_score
                FROM documents
                WHERE workspace_id = :ws AND embedding IS NOT NULL
                ORDER BY embedding <=> CAST(:embedding AS vector)
                LIMIT :k
                """
            ),
            {"embedding": str(query_vec), "ws": workspace_id, "q": q, "k": top_k * 3},
        )
    else:
        doc_rows = await db.execute(
            text(
                """
                SELECT id, title, content_preview, document_type,
                       NULL::float AS similarity,
                       similarity(coalesce(content_preview, '') || ' ' || coalesce(title, ''), :q) AS keyword_score,
                       ts_rank_cd(
                           to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content_preview, '')),
                           websearch_to_tsquery('english', :q)
                       ) AS fts_score
                FROM documents
                WHERE workspace_id = :ws
                AND (
                    to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content_preview, ''))
                        @@ websearch_to_tsquery('english', :q)
                    OR similarity(coalesce(content_preview, '') || ' ' || coalesce(title, ''), :q) > 0.2
                )
                ORDER BY fts_score DESC NULLS LAST, keyword_score DESC NULLS LAST
                LIMIT :k
                """
            ),
            {"ws": workspace_id, "q": q, "k": top_k * 3},
        )

    for row in doc_rows:
        m=dict(row._mapping)
        candidates.append({
            "id": m["id"],
            "title": m["title"],
            "content_preview": m["content_preview"],
            "document_type": m["document_type"],
            "kind": "document",
            "similarity": float(m["similarity"]) if m["similarity"] is not None else None,
            "keyword_score": float(m["keyword_score"]) if m["keyword_score"] is not None else None,
            "fts_score": float(m["fts_score"]) if m["fts_score"] is not None else None,
        })

    if query_vec is not None:
        chunk_rows = await db.execute(
            text(
                """
                SELECT dc.document_id, dc.chunk_index, dc.content,
                       d.title, d.document_type,
                       1 = (dc.embedding <=> CAST(:embedding AS vector)) AS similarity,
                       ts_rank_cd(
                           to_tsvector('english', coalesce(dc.content, '')),
                           websearch_to_tsquery('english', :q)
                       ) AS fts_score
                FROM document_chunks dc
                JOIN documents d ON d.id = dc.document_id
                WHERE dc.workspace_id = :ws AND dc.embedding IS NOT NULL
                ORDER BY dc.embedding <=> CAST(:embedding AS vector)
                LIMIT :k
                """
            ), 
            {"embedding": str(query_vec), "ws": workspace_id, "q": q, "k" :top_k * 3},
        )
        best_per_doc: dict[str, dict[str, Any]] = {}
        for row in chunk_rows:
            m=dict(row._mapping)
            doc_id= m["document_id"]
            sim=float(m["similarity"]) if m["similarity"] is not None else 0.0
            fts=float(m["fts_score"]) if m["fts_score"] is not None else 0.0
            if doc_id not in best_per_doc or sim > best_per_doc[doc_id]["similarity"]:
                best_per_doc[doc_id]= {
                    "id": doc_id,
                    "title": m["title"],
                    "content_preview": (m["content"] or '') [:500],
                    "document_type": m["document_type"],
                    "kind": "document",
                    "similarity": sim,
                    "keyword_score": None,
                    "fts_score": fts,
                }
        candidates.extend(best_per_doc.values())

    if query_vec is not None:
        ins_rows=await db.execute(
            text(
                """
                SELECT id, title, summary AS content_preview,
                       1 = (embedding <=> CAST(:embedding AS vector)) AS similarity,
                       similarity(coalesce(summary, '') || ' ' || coalesce(title, ''), :q) AS keyword_score,
                       ts_rank_cd(
                           to_tsvector('english', coalesce(title, '') || ' ' || coalesce(summary, '')),
                           websearch_to_tsquery('english', :q)
                       ) AS fts_score
                FROM insights
                WHERE workspace_id = :ws AND embedding IS NOT NULL
                ORDER BY embedding <=> CAST(:embedding AS vector)
                LIMIT :k
                """
            ),
            {"embedding": str(query_vec), "ws": workspace_id, "q": q, "k": top_k * 3},
        )
    else:
        ins_rows=await db.execute(
            text(
                """
                SELECT id, title, summary AS content_preview,
                       NULL::float AS similarity,
                       similarity(coalesce(summary, '') || ' ' || coalesce(title, ''), :q) AS keyword_score,
                       ts_rank_cd(
                           to_tsvector('english', coalesce(title, '') || ' ' || coalesce(summary, '')),
                           websearch_to_tsquery('english', :q)
                       ) AS fts_score
                FROM insights
                WHERE workspace_id = :ws
                AND (
                    to_tsvector('english', coalesce(title, '') || ' ' || coalesce(summary, ''))
                        @@ websearch_to_tsquery('english', :q)
                    OR similarity(coalesce(summary, '') || ' ' || coalesce(title, ''), :q) > 0.2
                )
                ORDER BY fts_score DESC NULLS LAST, keyword_score DESC NULLS LAST
                LIMIT :k
                """
            ),
            {"ws": workspace_id, "q": q, "k": top_k *3},
        )
    

    for row in ins_rows:
        m=dict(row._mapping)
        candidates.append({
            "id": m["id"],
            "title": m["title"],
            "content_preview": m["content_preview"],
            "document_type": "insight",
            "kind": "insight",
            "keyword_score": float(m["keyword_score"]) if m["keyword_score"] is not None else None,
            "similarity": float(m["similarity"]) if m["similarity"] is not None else None,
            "fts_score": float(m["fts_score"]) if m["fts_score"] is not None else None,
        })
    
    if not candidates:
        return []

    best: dict[tuple[str, str], dict[str, Any]] = {}
    for c in candidates:
        key=(c["kind"], c["id"])
        existing=best.get(key)
        if not existing or (c["similarity"] or 0) > (existing ["similarity"] or 0):
            best[key]=c
    candidates = list(best.values())


    _RRF_K = 60

    def _rank_map(signal: str) -> dict[tuple[str, str], int]:
        ranked = sorted(
            (c for c in candidates if c.get(signal) is not None),
            key=lambda c: c.get(signal) or 0.0,
            reverse=True,
        )
        return {(c["kind"], c["id"]): index + 1 for index, c in enumerate(ranked)}

    rank_vec = _rank_map("similarity")
    rank_fts = _rank_map("fts_score")
    rank_kw = _rank_map("keyword_score")

    for c in candidates:
        key = (c["kind"], c["id"])
        score = 0.0
        for rmap in (rank_vec, rank_fts, rank_kw):
            r = rmap.get(key)
            if r is not None:
                score += 1.0 / (_RRF_K + r)
        c["rerank_score"] = round(score, 6)

    candidates.sort(key=lambda c: c.get("rerank_score") or 0.0, reverse=True)
    
    if settings.feature_rag_reranker:
        from app.embeddings.reranker import rerank
        pool = candidates[: max(top_k * 3, top_k)]
        ranked=rerank(q, pool, top_k)
        return [SearchHit(**c) for c in ranked]

    # fts_max = max((c.get("fts_score") or 0.0) for c in candidates) or 1.0 
    # kw_max= max((c.get("keyword_score") or 0.0) for c in candidates) or 1.0
    # for c in candidates:
    #     vec=c.get("similarity") or 0.0
    #     fts=(c.get("fts_score") or 0.0) / fts_max
    #     kw=(c.get("keyword_score") or 0.0) / kw_max
    #     c["rerank_score"] = round(0.6 * vec + 0.3 * fts + 0.1 * kw, 6)
    # candidates.sort(key=lambda c: c.get("rerank_score") or 0.0, reverse=True)
    return [SearchHit(**c) for c in candidates[:top_k]]