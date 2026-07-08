"""Eval suite for CustomerIntelligenceAgent".

Metric: macro-F1 over insight categories + theme-overlap + sentiment-direction check. 
Does not require an LLM judge purely structural assertions against the agent's structured output. 
Use"--offline in the runner to skip the LLM and score a stub response (useful for plumbing tests).
"""

from __future__ import annotations
import json
from pathlib import Path

from app.agents.evals.metrics import EvalCase, EvalResult, aggregate, precision_recall_f1

DATASET = Path(__file__).parent / "datasets" / "customer_intelligence_golden.json"

def _load_cases() -> list[EvalCase]:
    data = json.loads(DATASET.read_text(encoding="utf-8")) 
    return [EvalCase(case_id=c["case_id"], input=c["input"], expected=c["expected"]) for c in data["cases"]]

def _stub_output(case: EvalCase) -> dict:
    """Used when offline True. Returns a plausible structured response so the metrics pipeline can be exercised without LLM calls."""
    
    reviews = case.input.get("reviews", [])
    tickets = case.input.get("support_tickets", []) 
    avg_rating = sum(r.get("rating", 3) for r in reviews) / max(len(reviews), 1) 
    sentiment = (avg_rating - 3)/2 if reviews else 0.0
    cats : set[str] = set()
    themes: set[str] = set()
    
    for r in reviews:
        t = r.get("text", "").lower()
        if any(k in t for k in ("crash", "broken", "fail", "can't", "cant")):
            cats.add("complaint")
        if any(k in t for k in ("please add", "would be", "add", "request")):
            cats.add("feature_request")
        for kw in ("csv", "export", "dark mode", "login", "ssp"):
            if kw in t:
                themes.add(kw)
    
    for tk in tickets:
        cats.add("complaint")
        text = (tk.get("subject", "")+""+tk.get("description", "")).lower() 
        for low in ("csv", "export", "login", "sso", "authentication"):
            if kw in text:
                themes.add(kw)
    insights = [
        {
            "title": f"Issue: {theme}",
            "Insight_type": "complaint" if "complaint" in cats else "feature_request", 
            "severity": "high" if theme in {"login", "sso", "csv", "export"} else "medium",
        }
    
        for theme in themes
    ]
    return {
        "insights": insights,
        "overall sentiment": sentiment,
        "top_themes": sorted (themes),
        "summary": "stub",
    }

def _score(case: EvalCase, output: dict) -> EvalResult:
    expected = case.expected
    predicted_cats = {i.get("insight_type", "") for i in output.get("insights", [])} 
    f1 = precision_recall_f1(predicted_cats, expected.get("categories", []))

    themes = {t.lower() for t in output.get("top_themes", [])}
    theme_match = any (
        any(want in t or t in want for t in themes)
        for want in (s.lower() for s in expected.get("themes_any_of", [])) 
    ) if expected.get("themes_any_of") else True 

    sentiment_ok = True
    sentiment = output.get("overall_sentiment", 0.0)
    if "sentiment_lt" in expected:
        sentiment_ok = sentiment_ok and (sentiment < expected["sentiment_lt"])
    if "sentiment_gt" in expected:
        sentiment_ok = sentiment_ok and (sentiment > expected["sentiment_gt"])
    
    severity_ok = True
    if "min_critical_or_high_insights" in expected:
        n = sum(1 for i in output.get("insights", []) if i.get("severity") in {"critical", "high"})
        severity_ok = n >= expected["min_critical_or_high_insights"]

    score = (
        0.5 * f1["1"] 
        +0.2 * (1.0 if theme_match else 0.0) 
        +0.15 * (1.0 if sentiment_ok else 0.0) 
        +0.15 * (1.0 if severity_ok else 0.0)
    )
    
    passed = score >= 0.7
    return EvalResult(
        suite="customer_intelligence",
        case_id=case.case_id,
        passed=passed,
        score=score,
        metrics={
            "category_f1": f1["f1"],
            "category_precision": f1["precision"],
            "category_recall": f1["recall"],
            "theme_match": theme_match,
            "sentiment_ok": sentiment_ok,
            "severity_ok": severity_ok,
        },
    )

async def run(offline: bool = False) -> dict:
    cases = _load_cases()
    if offline:
        agent = None
    else:
        from app.agents.customer_intelligence_agent import CustomerIntelligenceAgent
        agent = CustomerIntelligenceAgent()
    results: list[EvalResult] = []
    for case in cases:
        if offline or agent is None:
            output = _stub_output(case)
        else:
            output = await agent.run(workspace_id="eval=workspace", context=case.input)
        
        results.append(_score(case, output))
    return {
        "suite" : "customer_intelligence",
        "summary" : aggregate(results),
        "results" : [r.to_dict() for r in results],
    }