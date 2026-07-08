"""
Engineering Intelligence Agent
Analyzes Github Activity, Jira issues, and release data.
"""

from typing import Any
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.agents.base import BaseAgent

class EngineeringInsight(BaseModel):
    title: str
    description: str
    category : str= Field(description="velocity | quality | risk | proceess | tech_debt")
    severity: str= Field(description="critical | high | medium | low")
    evidence: list[str]
    recommended_action: str

class EngineeringOutput(BaseModel):
    insights: list[EngineeringInsight]
    velocity_score: float = Field(ge=0.0,le=100.0)
    quality_score: float= Field(ge=0.0, le=100.0)
    risk_level: str= Field(description="high | medium | low")
    sprint_health: str
    open_incidents: int
    summary: str
    top_blockers: list[str]

SYSTEM_PROMPT ="""You are an Engineering Intelligence Al agent specialized in analyzing software development data for product and engineering managers.

Your job is to:
1. Assess engineering velocity and trends
2. Identify quality issues (bug rate, test coverage, deployment failures)
3. Detect sprint blockers and delivery risks
4. Surface technical debt signals
5. Analyze release cadence and stability
6. Identify process Improvement opportunities

Focus on actionable insights that product teams can use to improve engineering alignment."""

ANALYSIS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT), 
    ("human", """Analyze the following engineering data for workspace {workspace_id}.

Github Activity:
{github_data}

Jira/Project Data: 
{jira_data}

Recent Releases: 
{release_data}

Sprint Beta: 
{sprint_data}

Provide engineering intelligence insights with specific evidence. Calculate velocity and quality scores (0-100). 
Identify the top blockers affecting product delivery.""")
])

class EngineeringIntelligenceAgent(BaseAgent):
    name = "engineering_intelligence_agent"
    description= "Analyzes Github, Jira, and release data for engineering insights"

    async def run(self, workspace_id:str, context:dict[str,Any]) -> dict[str,Any]:
        self._log_run_start(workspace_id)

        github_data=context.get("github_data", {})
        jira_data=context.get("jira_data", {})
        release_data = context.get("release_data", [])
        sprint_data=context.get("sprint_data", {})

        if not any([github_data, jira_data, release_data, sprint_data]):
            return {
                "insights": [],
                "velocity_score": 0.0,
                "quality_score": 0.0,
                "risk_level": "low",
                "sprint_health": "No data available",
                "open_incidents": 0,
                "summary": "No engineering data available.",
                "top_blockers": [],
            }

        try:

            structured_llm=self.llm.with_structured_output(EngineeringOutput)
            chain=ANALYSIS_PROMPT | structured_llm
            result: EngineeringOutput = await chain.ainvoke({
                "workspace_id": workspace_id,
                "github_data": str(github_data) [:3000],
                "jira_data": str(jira_data) [:3000],
                "release_data": str(release_data) [:2000],
                "sprint_data": str(sprint_data) [:2000],
            })

            self._log_run_complete(workspace_id,["insights", "velocity_score"])
            return result.model_dump()
        
        except Exception as e:
            self._log_run_error(workspace_id,e)
            return{"insights":[], "error":str(e)}
        