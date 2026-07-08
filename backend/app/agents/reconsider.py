"""Explicit "reconsider rejected recommendations" logic.

The Strategy Agent's prompt already tells the LLM "don't re-propose rejected ideas unless the evidence has materially changed." 
That's a soft hint. This module is the hard signal that makes it real: for every past rejected recommendation, 
count how many current insights match its topic; if that count has grown significantly since the decision was made, 
flag the entry with reconsider: True and ship it back into the strategy prompt.

The strategy agent's prompt is aware of this flag (see product_strategy_agent.py") and treats flagged entries as 
explicit candidates for revival rather than "do not repeat".

Kept pure Pythonno LLM calls, no external deps so it's cheap enough to run at the top of every daily analysis pass.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Protocol

_TOKEN_RE = re.compile(r"[a-z0-9]{4,}")
_STOPWORDS = { "the", "and", "for", "with", "that", "this", "from", "have", "into", "your", "you", "our", 
              "are", "was", "were", "will", "not", "but", "any", "all", "how", "why", "what", "when", "does", 
              "did", "has", "had", "them", "they", "their", "these", "those", "some", "than", "then", "user", 
              "users", "feature", "features", #too generic in this domain
}

_MIN_ABSOLUTE = 3
_MIN_GROWTH_RATIO= 2.0

class _InsightLike(Protocol):
    title: str
    summary: str | None

def _tokenize(text: str | None) -> set[str]:
    if not text:
        return set()
    return {t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS}

def _keywords_for(title: str, description: str | None = None) -> set[str]:
    return _tokenize(f"{title} {description or ''}")

def _count_matches(keywords: set[str], insights: Iterable[_InsightLike]) -> int:
    if not keywords:
        return 0
    hits = 0
    for i in insights:
        tokens = _tokenize(f"{getattr(i, 'title','')} {getattr(i, 'summary', '') or ''}")

    if keywords & tokens:
        hits += 1
    return hits

def annotate_reconsider(
    decisions: list[dict[str, Any]],
    current_insights: Iterable[_InsightLike],
    *,
    raw_decisions: list [Any] | None = None,
) -> list[dict[str, Any]]:
    """Return decisions with a reconsider flag and evidence_delta".
    
    Parameters
    -----------
    decisions
        Plain dicts (decision, reason, title from snapshot) as 
        already produced by the daily-analysis task.
    current_insights
        Iterable of ORM Insight rows for the workspace (any object with
        title and raw decisions summary works hence the InsightLike protocol).
    raw_decisions
        Optional parallel list of the underlying ORM rows, needed to read each decision's "snapshot 
        When omitted we fall back to (which holds the baseline evidence count). snapshot_evidence_count 1 per row.
    """
    insights_list = list (current_insights)
    raw_list = list(raw_decisions) if raw_decisions is not None else []
    annotated: list[dict[str, Any]]=[] 
    
    for i, d in enumerate(decisions):
        entry = dict(d)
        if entry.get("decision") != "rejected":
            annotated.append(entry)
            continue
        
        title = entry.get("title") or ""
        keywords = _keywords_for(title)

        # Baseline: how many evidence bullets were attached to the rec at #decision time. 
        # Falls back to 1 so a rec rejected with zero evidence #can still be flagged if enough new insights show up.

        baseline = 1
        
        if i < len(raw_list) and raw_list[i] is not None:
            snap = getattr(raw_list[i], "snapshot", None) or {}
            baseline = max(1, len(snap.get("evidence") or []))

        current = _count_matches(keywords, insights_list)
        if current >= _MIN_ABSOLUTE and current >= _MIN_GROWTH_RATIO * baseline:
            entry["reconsider"] = True
            entry["evidence_delta"]=(
                f"was {baseline} evidence bullets; {current} related insights are open now"
            )
        annotated.append(entry)
    return annotated