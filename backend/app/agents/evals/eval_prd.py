"""Eval suite for PRDAgent - PRD completeness rubric.

Uses **LLM-as-judge** (`app.agents.evals.judge.judge_with_rubric') to score 
each PRD against a fixed rubric. The offline mode emits a deterministic stub score so the 
pipeline can be exercised without API calls.
"""

from __future__ import annotations
import json
from pathlib import Path

from typing import TYPE_CHECKING

from app.agents.evals.metrics import EvalCase, EvalResult, aggregate

if TYPE_CHECKING:
    from app.agents.evals.judge import JudgeVerdict

DATASET = Path(__file__).parent / "datasets" / "prd_golden.json"

def _load_dataset() -> tuple[list[str], list[EvalCase]]:
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    rubric = data["rubric"] 
    cases = [ 
        EvalCase(
            case_id=c["case_id"], 
            input=c["input"], 
            expected={"min_overall_score": c["expected_min_overall_score"]},
        )
        for c in data["cases"]
    ]
    return rubric, cases

def _stub_prd(case: EvalCase) -> dict:
    title = case.input.get("feature_title", "Feature")
    return {
        "title": title,
        "executive_summary": "stub",
        "problem statement": "stub",
        "goals_and_success_metrics": ["+10% adoption in 90 days"],
        "user_personas": ["PM", "Engineer"],
        "user_stories": [
            {"persona": "PM", "goal": "ship X", "benefit": "win", "acceptance_criteria": ["A", "B"], "priority": "must_have"},
            {"persona": "Dev", "goal": "build X", "benefit": "ship", "acceptance_criteria": ["C"], "priority" : "should_have"},
            {"persona": "User", "goal": "use X", "benefit": "value", "acceptance_criteria": ["D"], "priority" : "must_have"},
        ],
        "functional_requirements": ["F1", "F2", "F3"],
        "non_functional_requirements": ["p95 < 300ms", "WCAG AA"],
        "out_of_scope": ["Native desktop app"],
        "technical_considerations": ["streaming export to avoid OOM"],
        "open_questions": ["legal review for data export?"],
        "full markdown": f"# {title}\n\n## Problem\n...\n",
    }

def _stub_verdict() -> "JudgeVerdict":
    from app.agents.evals.judge import JudgeVerdict
    return JudgeVerdict(
        overall_score=0.75,
        passed=True,
        criteria=[],
        summary="stub offline verdict",
        failure_modes=[],
    )

def _score(case: EvalCase, verdict: "JudgeVerdict") -> EvalResult:
    threshold = case.expected.get("min_overall_score", 0.7)
    passed = verdict.overall_score >= threshold and verdict.passed
    return EvalResult(
        suite="prd",
        case_id=case.case_id,
        passed=passed,
        score=verdict.overall_score,
        metrics={
            "threshold": threshold,
            "Judge passed": verdict.passed,
            "failure modes": verdict.failure_modes,
        },
        notes=verdict.summary[:300],
    )

async def run(offline: bool = False) -> dict:
    rubric, cases = _load_dataset()
    if offline:
        agent = None
        judge = None
    else:
        from app.agents.prd_agent import PRDAgent
        from app.agents.evals.judge import judge_with_rubric
        agent = PRDAgent()
        judge = judge_with_rubric 
    results: list[EvalResult] = []
    for case in cases:
        if offline or agent is None: 
            prd = _stub_prd(case)
            verdict = _stub_verdict()
        else:
            prd = await agent.run(workspace_id="eval=workspace", context=case.input)
            verdict = await judge(
                task="Evaluate the PRD against the rubric.",
                agent_input=case.input,
                agent_output=prd,
                rubric=rubric,
            )
        results.append(_score(case, verdict))
    return {
        "suite": "prd",
        "summary": aggregate(results),
        "results": [r.to_dict() for r in results],
    }