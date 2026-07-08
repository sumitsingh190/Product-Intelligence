"""Deterministic metrics for agent evaluation.

Pure=Python (stdlib only). Used by `eval modules and runner.py".
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field 
from typing import Iterable, Sequence

#Data classes

@dataclass
class EvalCase:
    """A single golden example."""
    case_id: str
    input: dict
    expected: dict
    metadata: dict = field(default_factory=dict)

@dataclass
class EvalResult:
    suite: str
    case_id: str
    passed: bool
    score: float # 0.0.. 1.0
    metrics: dict = field(default_factory=dict)
    notes: str = ""

def to_dict(self) -> dict:
    return{
        "suite": self.suite,
        "case_id": self.case_id,
        "passed": self.passed,
        "score": round(self.score, 3),
        "metrics": {k: (round(v, 3) if isinstance(v, float) else v) for k, v in self.metrics.items()},
        "notes": self.notes,
    }

 #Classification metrics

def precision_recall_f1(
    predicted: Iterable[str],
    expected: Iterable[str],    
)-> dict[str, float]:
    """Set=based precision/recall/F1 on labels (case=insensitive)."""

    p = (s.strip().lower() for s in predicted if s and s.strip())
    e=(s.strip().lower() for s in expected if s and s.strip())
    if not p and not e:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "tp": 0, "fp": 0, "fn": 0}
    tp = len(p & e)
    fp = len(p - e)
    fn = len(e - p)
    precision = tp / (tp+fp) if (tp + fp) else 0.0
    recall = tp / (tp+fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }

#Ranking metrics (used for ROI / priority ordering quality)

def kendall_tau(predicted_order: Sequence [str], expected_order: Sequence[str]) -> float:
    """Kendall tau-b coefficient on common items. Range -1..1; 1 == identical order.
    
    Items present in only one of the sequences are ignored. If fewer than 2
    items overlap, returns 0.0.
    """

    common = [x for x in predicted_order if x in expected_order]
    if len(common) < 2:
        return 0.0

    expected_rank = {item: i for i, item in enumerate(expected_order)}
    pred_rank = {item: i for i, item in enumerate (predicted_order)}
    concordant = 0
    discordant = 0
    for i in range(len(common)):
        for j in range(1+1, len(common)):
            a, b = common[i], common[j]
            sign_pred = pred_rank[a] - pred_rank[b]
            sign_exp = expected_rank[a] - expected_rank[b]
            if sign_pred * sign_exp > 0:
                concordant += 1
            elif sign_pred * sign_exp < 0:
                discordant += 1
    total = concordant + discordant
    return (concordant - discordant) / total if total else 0.0

def ndcg_at_k(
    predicted_order: Sequence [str],
    relevance: dict[str, float],
    k: int = 10,
) -> float:
    """Normalized Discounted Cumulative Gain @ k.
    "relevance maps item-id -> graded relevance (e.g. expected ROI 0..10).
    """
    if not predicted_order or not relevance:
        return 0.0
    
    def dcg(items: Sequence [str]) -> float:
        return sum(
            (2** relevance.get(item, 0.0) - 1) / math.log2(i + 2)
            for i, item in enumerate(items[:k])
        )
    
    actual = dcg(predicted_order)
    ideal_order = sorted(relevance, key=lambda x: relevance [x], reverse=True)
    ideal = dcg(ideal_order)
    return actual / ideal if ideal > 0 else 0.0

# Rubric aggregation

def rubric_score(
    judged: dict[str, int | float],
    *,
    scale_max: int = 5,
)-> float:
    """Mean rubric score normalised to 0..1.

    judged is a mapping criterion -> raw score (typically 1..scale_max).
    """
    if not judged:
        return 0.0
    
    values = [float(v) for v in judged.values() if isinstance(v, (int, float))]
    if not values:
        return 0.0
    
    return sum(values) / (len(values) * scale_max)

# Aggregation across cases

def aggregate(results: list[EvalResult]) ->dict:
    if not results:
        return {"count": 0, "pass_rate": 0.0, "mean_score": 0.0}

    passed = sum(1 for r in results if r.passed)
    return {
        "count": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "pass_rate": round(passed / len(results), 3),
        "mean_score": round(sum(r.score for r in results) / len(results), 3),
        "min_score": round(min(r.score for r in results), 3),
        "max_score": round(max(r.score for r in results), 3),
    }