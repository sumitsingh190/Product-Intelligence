"""LLM=as-judge utility.

Reuses app.agents.base.get_llm' so the judge runs on the same Groq
model configured for the rest of the platform.

Outputs are validated with Pydantic via "llm.with_structured_output(...)" -
no string parsing.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class RubricCriterion (BaseModel):
    name: str
    score: int = Field(ge=1, le=5, description="1 (poor) .. 5 (excellent)")
    reasoning: str

class JudgeVerdict(BaseModel):
    overall_score: float = Field(ge=0.0, le=1.0)
    passed: bool
    criteria: list[RubricCriterion]
    summary: str
    failure_modes: list[str] = []


JUDGE_SYSTEM = """You are a strict, evidence-based evaluator of AI-generated outputs. 
Score each rubric criterion on a 1-5 scale, where:
    5- excellent meets or exceeds expectation with concrete evidence
    4- good meets expectation with minor gaps
    3- adequate partially meets expectation
    2- weak significant gaps
    1- unacceptable fails the criterion

Be specific and cite the output text in your reasoning. Do NOT inflate scores. 
The overall_score is the average of criterion scores normalised to 0..1. 
A submission passes only if overall_score >= 0.7.
"""

_JUDGE_HUMAN = """Evaluate the following AI output against the rubric.

## Task
{task}

## Input given to the agent 
{agent_input}

## Agent output 
{agent_output}

## Rubric criteria 
{rubric}

Return a strict JSON verdict."""

async def judge_with_rubric(
    task: str,
    agent_input: Any,
    agent_output: Any,
    rubric: list[str],
)-> JudgeVerdict:
    """Run an LLM-as-judge pass for one (input, output) pair.""" 
    from langchain_core.prompts import ChatPromptTemplate 
    from app.agents.base import get_llm

    prompt = ChatPromptTemplate.from_messages([("system", JUDGE_SYSTEM), ("human", _JUDGE_HUMAN)])
    llm = get_llm(temperature=0.0)
    structured  = llm.with_structured_output(JudgeVerdict) 
    chain = prompt | structured 
    rubric_str = "\n".join(f"- {c}" for c in rubric)
    verdict: JudgeVerdict = await chain.ainvoke({
        "task": task,
        "agent_input": str(agent_input)[:6000],
        "agent_output": str(agent_output) [:6000],
        "rubric": rubric_str,
    })
    return verdict

#Pairwise comparator (for A/B model comparisons or regression tests)

class PairwisePreference (BaseModel):
    winner: str = Field(description="'A' | 'B' | 'tie'")
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)

_PAIRWISE_SYSTEM = (
    "You compare two Al outputs against the same prompt and pick the better one." 
    "Be impartial; prefer evidence and specificity over verbosity."
)
_PAIRWISE_HUMAN = """Task: {task}

Output A: {a}

Output: B: {b}

Pick the better output. If they are equivalent, return 'tie'."""

async def pairwise_judge(task: str, a: Any, b: Any) -> PairwisePreference: 
    from langchain_core.prompts import ChatPromptTemplate 
    from app.agents.base import get_llm

    prompt = ChatPromptTemplate.from_messages([("system", _PAIRWISE_SYSTEM), ("human", _PAIRWISE_HUMAN)]) 
    llm = get_llm(temperature=0.0)
    structured = llm.with_structured_output(PairwisePreference) 
    chain = prompt | structured 
    return await chain.ainvoke({"task": task, "a": str(a)[:6000], "b": str(b)[:6000]})        
