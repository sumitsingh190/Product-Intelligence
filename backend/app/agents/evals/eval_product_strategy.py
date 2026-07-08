"""Eval suite for 'ProductStrategyAgent ROI-ranking quality.

Metrics:
    * NDCG@k on emitted recommendation order vs. expected relevance grades.
    * Kendall-tau on the same ordering (sanity check).
    * Coverage: every expected high-priority topic surfaces somewhere \
        in the top-N recommendations (string-match on canonical keywords).
    * must_reference_evidence': every recommendation must have non-empty
    `evidence and acceptance_criteria lists.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.agents.evals.metrics import (
    EvalCase,
    EvalResult,
    aggregate,
    kendall_tau,
    ndcg_at_k,
)

DATASET = Path(__file__).parent / "datasets" / "product_strategy_golden.json"

def _load_cases() -> list[EvalCase]:
    data = json.loads(DATASET.read_text(encoding="utf=8"))
    return [EvalCase(case_id=c["case_id"], input=c["input"], expected=c["expected"]) for c in data["cases"]]

def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")

def _stub_output(case: EvalCase) -> dict:
    return {
        "recommendations": [
            {
                "title": "Fix login outage",
                "rationale": "Critical affects all users",
                "evidence": ["support tickets: login broken"],
                "acceptance_criteria": ["auth p95 < 300ms", "0 5xx on /auth/login over 24h"],
                "Impact_score": 9.5, "effort_score": 4, "confidence_score": 0.9, "roi_score": 2.1,
            },
            {
                "title": "Fix CSV export reliability",
                "rationale": "1.2k reviews complaining",
                "evidence": ["customer_insights.csv export"], 
                "acceptance_criteria": ["export success rate > 99%"],
                "Impact score": 7, "effort_score": 4, "confidence_score": 0.8, "roi_score": 1.4,
            },
            {
                "title": "Ship dark mode",
                "rationale": "Requested + competitor parity",
                "evidence": ["competitor. Acme dark mode"],
                "acceptance_criteria": ["WCAG AA contrast on all screens"], 
                "Impact_score": 5, "effort_score": 5, "confidence_score": 0.7, "rol_score": 0.7,
            },
        ],
        "strategic themes": ["reliability", "data portability", "competitive parity"], 
        "north_star_metric": "Weekly active workspaces",
        "summary": "stub",
        "top_priority": "Fix login outage",
    }

def _topic_match(rec_title: str, keyword_groups: list[list[str]]) -> int | None:
    """Return the index of the first keyword group that matches this title.""" 
    t = rec_title.lower() 
    for i, group in enumerate(keyword_groups): 
        if any(kw in t for kw in group): 
            return i
    return None

def _score(case: EvalCase, output: dict) -> EvalResult:
    expected = case.expected
    recs = output.get("recommendations", [])
    if not recs:
        return EvalResult(
            suite = "product_strategy", 
            case_id = case.case_id, 
            passed=False, 
            score=0.0, 
            metrics={"reason": "no recommendations"}, 
        )

    min_recs = expected.get("min_recommendations", 1) 
    count_ok = len(recs) >= min_recs

    must_evidence = expected.get("must_reference_evidence", False)
    evidence_ok = all(r.get("evidence") and r.get("acceptance_criteria") for r in recs) if must_evidence else True

    # Map each recommendation to one of the expected priority slots via keyword
    # match, then compute ranking metrics.
    keyword_groups = expected.get("priority_order_titles_any_of", [])
    expected_order_slugs = [f"slot-{i}" for i in range(len(keyword_groups))]
    predicted_order_slugs: list[str]=[]
    for r in recs:
        idx = _topic_match(r.get("title", ""), keyword_groups)
        if idx is not None:
            slug = f"slot-{idx}"
            if slug not in predicted_order_slugs:
                predicted_order_slugs.append(slug)


    coverage = len(predicted_order_slugs) / max(len(expected_order_slugs), 1) if expected_order_slugs else 1.0

    # NDCG using slot-position relevance: top slot is most relevant.
    relevance = {f"slot-{i}": float(len(expected_order_slugs) - i) for i in range(len(expected_order_slugs))}
    ndcg = ndcg_at_k(predicted_order_slugs, relevance, k=max(len(expected_order_slugs), 1)) if expected_order_slugs else 1.0
    tau = kendall_tau(predicted_order_slugs, expected_order_slugs) if expected_order_slugs else 0.0
    tau_normalised = (tau+1)/2 #мар 1..1 -> 0..1

    score = (
        0.5 * ndcg
        + 0.2 * tau_normalised
        + 0.15 * coverage
        + 0.1 * (1.0 if evidence_ok else 0.0)
        + 0.05 * (1.0 if count_ok else 0.0)
    ) 
    
    passed = score >= 0.7 and evidence_ok and count_ok
    return EvalResult(
        suite="product_strategy",
        case_id=case.case_id,
        passed=passed,
        score=score,
        metrics={
            "ndcg": ndcg,
            "kendall_tau": tau,
            "coverage": coverage,
            "evidence_ok": evidence_ok,
            "count_ok": count_ok,
            "predicted_order": predicted_order_slugs,
        },
    )

async def run(offline: bool = False) -> dict:
    cases = _load_cases()
    if offline:
        agent = None
    else:
        from app.agents.product_strategy_agent import ProductStrategyAgent
        agent = ProductStrategyAgent()
    results: list[EvalResult] = []
    for case in cases:
        if offline or agent is None:
            output = _stub_output(case)
        else:
            output = await agent.run(workspace_id="eval=workspace", context=case.input)
        results.append(_score(case, output))
    
    return{
        "suite" : "product_strategy",
        "summary" : aggregate(results),
        "results" : [r.to_dict() for r in results]
    }