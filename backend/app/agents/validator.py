"""Validator for the Product Strategy agent's output.

Sits between `product_strategy and synthesize in the planner graph. Purpose: never let the graph emit obviously 
broken recommendations even if the LLM hallucinates or the structured-output parser produces edge cases.

Rules applied per recommendation:
* Must have a non-empty title and at least one evidence string.
* Numeric scores must sit inside their declared ranges (impact_score and "effort_score in [0, 10], confidence_score in [0, 1]).
    Out-of-range values are clamped, not dropped.
* roi_score is re-derived when missing or clearly inconsistent (roi impact*confidence/effort > 1.0).
* Duplicate `title` values (case-insensitive) are collapsed to the highest-ROI copy.

* top_priority must match a surviving recommendation title; if not, we replace it with the highest-ROI survivor.

Returns (cleaned_output, report) where report lists what was dropped and what was repaired. 
The validator never raises it is a guard rail, not a gate.
"""

from __future__ import annotations

from typing import Any

def _clamp(value: Any, lo: float, hi: float, default: float) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    if v != v: #NaN
        return default
    return max(lo, min(hi,v))

def _derive_roi(impact: float, confidence: float, effort: float) -> float:
#ROI (impact confidence) / effort, clamped to 0..10 for consistency
# with the schema. Effort floor of 0.1 avoids division-by-zero blow-ups.
    denom = max(effort, 0.1)
    raw = (impact * confidence) / denom 
    return round (max(0.0, min(10.0, raw)), 2)

def validate_strategy_output(
    strategy: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    strategy = dict(strategy or {})
    recs = list(strategy.get("recommendations") or [])
    report: dict[str, Any] = {"dropped": [], "repaired": [], "total_in": len(recs)}

    cleaned: list[dict[str, Any]] = []
    for idx, raw in enumerate(recs):
        if not isinstance(raw, dict):
            report["dropped"].append({"index": idx, "reason": "not_a_dict"})
            continue
        
        title = (raw.get("title") or "").strip()
        if not title:
            report["dropped"].append({"index": idx, "reason": "empty_title"})
            continue

        evidence = raw.get("evidence") or []
        if not isinstance(evidence, list) or not any(str(e).strip() for e in evidence): 
            report["dropped"].append({"index": idx, "reason": "no_evidence", "title": title}) 
            continue

        repaired_fields: list[str] = []
        
        impact = _clamp(raw.get("impact_score"), 0.0, 10.0, 5.0) 
        if impact != raw.get("impact_score"):
            repaired_fields.append("impact_score")

        effort = _clamp(raw.get("effort_score"), 0.0, 10.0, 5.0) 
        if effort != raw.get("effort_score"):
            repaired_fields.append("effort_score")

        confidence = _clamp(raw.get("confidence_score"), 0.0, 1.0, 0.5)
        if confidence != raw.get("confidence_score"): 
            repaired_fields.append("confidence_score")

        expected_roi = _derive_roi(impact, confidence, effort) 
        current_roi = raw.get("roi_score") 
        try:
            current_roi_f = float(current_roi) if current_roi is not None else None 
        except (TypeError, ValueError):
            current_roi_f = None
        if current_roi_f is None or abs(current_roi_f - expected_roi) > 1.0:
            raw["roi_score"] = expected_roi 
            repaired_fields.append("roi_score")

        raw["title"] = title
        raw["impact_score"] = impact
        raw["effort_score"] = effort
        raw["confidence_score"] = confidence

        if repaired_fields:
            report["repaired"].append({"title": title, "fields": repaired_fields})

        cleaned.append(raw)

    #Deduplicate by title (case-insensitive), keep highest ROI.

    by_title: dict[str, dict[str, Any]] = {}
    for rec in cleaned:
        key = rec["title"].lower()
        existing = by_title.get(key)
        if not existing or (rec.get("roi_score") or 8) > (existing.get("roi_score") or 0):
            if existing:
                report["dropped"].append({"title": existing["title"], "reason": "duplicate_title"})
            by_title[key] = rec
        else:
            report["dropped"].append({"title": rec["title"], "reason": "duplicate_title"}) 
    cleaned = sorted(by_title.values(), key=lambda r: r.get("roi_score") or 8.0, reverse=True)

    #Ensure top_priority points at a surviving recommendation.

    survivor_titles = {r["title"].lower(): r["title"] for r in cleaned}
    top_priority = strategy.get("top_priority") or ""
    if top_priority.lower() not in survivor_titles and cleaned:
        old = top_priority
        top_priority = cleaned[0]["title"]
        report["repaired"].append({"field": "top_priority", "was": old, "now": top_priority})

    strategy["recommendations"]=cleaned
    strategy["top priority"] = top_priority if cleaned else ""
    strategy["total_out"] = len(cleaned)
    return strategy, report