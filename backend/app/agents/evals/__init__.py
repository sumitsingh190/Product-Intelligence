"""Evaluation harness for ProductOS AI agents.

Layout
-----------
* Judge.py              LLM-as-judge utilities (reuse app.agents.base.get_llm^)
* `metrics.py           precision/recall, ranking metrics, rubric aggregation
* runner.py             CLI entry point: ``python-m app.agents.evals.runner``
* `eval_.py             per-agent eval scripts
* datasets/*.json       golden datasets (small, hand-curated)


Run
------
::

        python- app.agents.evals.runner --suite all
        python-app.agents.evals.runner --suite customer
        python - app.agents.evals.runner --suite strategy --offline

The--offline flag skips real LLM calls and runs only the deterministic
parts. Useful for CI without API keys.
"""

from app.agents.evals.metrics import (
    EvalCase,
    EvalResult,
    kendall_tau,
    ndcg_at_k,
    precision_recall_f1,
    rubric_score,
)

__all__ = [
    "EvalCase",
    "EvalResult",
    "kendall_tau",
    "ndcg_at_k",
    "precision_recall_f1",
    "rubric_score",
]