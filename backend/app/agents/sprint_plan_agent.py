"""
Sprint Plan Agent - breaks accepted recommendations into a 2-week sprint plan
"""

from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel,Field

from app.agents.base import BaseAgent

class SprintTicket(BaseModel):
    title: str
    description: str
    type: str =Field(description-"story | task | bug | spike")
    story_points: int =Field(ge=1, le=13)
    priority: str =Field(description="must_have | should_have | nice_to_have")
    acceptance_criteria: list[str]
    dependencies: list[str] =Field(default_factory=list)

class SprintPlanOutput(BaseModel):
    sprint_name: str
    sprint_goal: str
    duration_weeks: int = 2
    capacity_points: int
    tickets: list[SprintTicket]
    risks: list[str]
    success_metrics: list[str]
    full_markdown: str

SYSTEM_PROMPT = """You are a Sprint Planning AI agent that converts approved product recommendations into an actionable 2-week sprint plan.

Produce realistic estimates. Use Fibonacci-style story points (1, 2, 3, 5, 8, 13). 
Total committed points must be reasonable for a small team (target ~30 points).

Each ticket must have clear acceptance criteria and an explicit type (story / task / bug / spike). 
Surface dependencies and risks honestly.

Output a complete 'full_markdown" that an EM can paste straight into Jira/Linear."""

PROMPT = ChatPromptTemplate.from_messages([ 
    ("system", SYSTEM_PROMPT), 
    ("human", """Build a 2-week sprint plan for the following accepted recommendations.

Sprint window starts: {sprint_start}

Accepted recommendations: 
{recommendations}
     
Team context: 
{team_context}

Produce a sprint with a clear goal, sized tickets summing to ~30 points, explicit risks, and measurable success metrics."""), ])

class SprintPlanAgent (BaseAgent):
    name="sprint_plan_agent"
    description="Generates a 2-week sprint plan from accepted recommendations"

    async def run(self, workspace_id: str, context: dict[str, Any]) -> dict[str, Any]:
        self._log_run_start(workspace_id)
        recs=context.get("recommendations", [])
        sprint_start=context.get("sprint_start", "next Monday")
        team_context=context.get("team_context", "Small product squad (3 engineers, 1 designer, 1 PM).")

        try:
            structured_llm=self.llm.with_structured_output(SprintPlanOutput)    
            chain = PROMPT | structured_llm
            result: SprintPlanOutput = await chain.ainvoke({
                "sprint_start": sprint_start,
                "recommendations": "\n\n".join(
                    f"- {r.get('title')}: {r.get('description', '')}" for r in recs[:10] 
                ) or "No recommendations provided.", 
                "team_context": team_context,
            }) 
            self._log_run_complete(workspace_id, ["sprint_plan"])
            return result.model_dump()

        except Exception as e: # noqa: BLE001
            self._log_run_error(workspace_id, e)
            return {"error": str(e)}