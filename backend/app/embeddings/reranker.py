"""
Pragmatic second-stage RAG reranker combines vector similarity, BM25-lite, and query-term coverage into a single relevance score over the RRF top-N.

No external ML dependencies. Runs in <1 ms for a few hundred candidates, 
which is what we ever see from the hybrid search endpoint. Trades absolute quality for 
portability swap in a cross-encoder later by re-implementing 'rerank()".

Score composition (per candidate)::

final = 0.55 * vector_similarity     #cosine, already in [0, 1]

        +0.30 * bm25_normalized       #normalized to peer max

        +0.15 * query_coverage      #fraction of query terms matched


Candidates missing a vector score (keyword-only fallback path) get weighted on the remaining two signals 
this keeps the search endpoint usable even when the embedding provider is offline.
"""

from __future__ import annotations

import math
import re
from typing import Any

STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "have", "into",
    "your", "you", "our", "are", "was", "were", "will", "can", "not", "but",
    "any", "all", "how", "why", "what", "when", "which", "who", "does", "did",
    "has", "had", "its", "it's", "them", "they", "their", "there", "these",
    "those", "over", "such", "some", "than", "then", "very", "just", "also",
}

_TOKEN_RE = re.compile(r" [a-z0-9]{2,}")

#BM25 constants Okapi defaults, no need to tune for our tiny candidate sets.

_BM25_K1 = 1.5
_BM25_B = 0.75

#Score weights.
_W_VECTOR = 0.55
_W_BM25 = 0.30
_W_COVERAGE = 0.15

def _tokenize(text: str | None) -> list[str]:
    if not text:
        return []
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in STOPWORDS]

def _candidate_text(hit: dict[str, Any]) -> str:
    parts = [hit.get("title") or "", hit.get("content_preview") or ""]
    return " ".join(p for p in parts if p)

def _bm25_scores(query_terms: list [str], docs: list[list[str]]) -> list[float]: 
    """Return one BM25 score per document (same order as docs")."""
    if not query_terms or not docs: 
        return [0.0] * len(docs)

    n_docs = len(docs)
    doc_lens = [len(d) for d in docs]
    avg_len = sum(doc_lens) / n_docs if n_docs else 0.0

#Doc frequency: number of docs containing each unique query term.

    df: dict[str, int] = {}
    for term in set(query_terms):
        df[term] = sum(1 for d in docs if term in d)

#Okapi IDF with the +1 smoothing that keeps rare-term IDF positive.

    idf: dict[str, float] = {
        t: math.log(((n_docs - c + 0.5)/ (c + 0.5)) + 1.0)
        for t, c in df.items()
    }

    scores: list[float] = []
    for tokens, dl in zip(docs, doc_lens):
    #tf lookup: build once per doc.
        tf: dict[str, int] = {}
        for tok in tokens:
            if tok in idf: # only care about query terms
                tf[tok] = tf.get(tok, 0)+1
    
        if not tf:
            scores.append(0.0)
            continue

        length_norm = 1.0 - BM25_B + BM25_B(dl/avg_len if avg_len else 1.0)
        score = 0.0
        for term, freq in tf.items():
            numerator=freq*(_BM25_K1 + 1.0)
            denominator=freq + _BM25_K1 + length_norm

            score += idf[term] * (numerator / denominator)
        scores.append(score)
        return scores

def _query_coverage(query_terms: list[str], doc_tokens: list[str]) -> float:
    if not query_terms:
        return 0.0
    q_set=set(query_terms)
    d_set=set(doc_tokens)
    return len(q_set & d_set) / len(q_set)

def rerank(
    query: str,
    hits: list[dict[str, Any]],
    top_k: int,
    )-> list[dict[str, Any]]:

    """Reorder hits by composite relevance and return the top top k

Each hit gets a rerank_score field added in place. Original signal fields (similarity, "keyword_score", fts score) are preserved.
"""

    if not hits:
        return []
    
    q_terms= _tokenize(query)
    docs_tokens = [_tokenize(_candidate_text(h)) for h in hits]

    bm25_raw = _bm25_scores(q_terms, docs_tokens)
    bm25_max = max(bm25_raw) or 1.6
    bm25_norm = [s/bm25_max for s in bm25_raw]

    for hit, dt, bm in zip(hits, docs_tokens, bm25_norm):
        vec = hit.get("similarity") or 0.0
        COV = _query_coverage(q_terms, dt)
        final= _W_VECTOR * vec + _W_BM25 * bm+ _W_COVERAGE * COV
        hit["rerank_score"]= round(float(final), 6)

    hits.sort(key=lambda h: h.get("rerank_score", 0.0), reverse=True)
    return hits[:top_k]