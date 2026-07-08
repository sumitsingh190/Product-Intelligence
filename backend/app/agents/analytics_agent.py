"""
Analytics Agent
Queries DuckDB to generate KPIs, detect trends, and surface product health metrics.
"""

from typing import Any
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel,Field

from app.agents.base import BaseAgent

class KPIInsight(BaseModel):
    metric_name: str
    current_value: float
    previous_value: float | None
    change_percent: float | None
    trend: str = Field(description="up | down | stable | new")
    significance: str = Field(description="critical | significant | normal | negligible")
    interpretation: str


class AnalyticsOutput(BaseModel):
    kpi_insights: list[KPIInsight]
    anomalies: list[str]
    trends: list[str]
    health_score: float = Field(ge=0.0, le=100.0, description="Overall product health 0-100")
    summary: str
    recommended_actions: list[str]

SYSTEM_PROMPT="""You are an Analytics AI agent specialized in interpreting product metrics and KPIS for product teams.

Your job is to:
1. Interpret KPI data and identify significant changes
2. Detect anomalies that need immediate attention
3. Identify positive and negative trends
4. Calculate overall product health score
5. Generate actionable recommendations based on data

Always distinguish between statistically significant changes and noise.
Focus on metrics that directly impact user experience and business outcomes."""

ANALYSIS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", """Analyze the following product analytics data for workspace {workspace_id}.

KPI Data:
{kpi_data}

User Behavior Data: 
{behavior_data}
     
Retention Data:
{retention_data}
    
Funnel Data:
{funnel_data}
     
Analyze all metrics and provide structural insights. Calculate an overall product health score (0-100)
based on the data quality and trends you observe."""),
])

class AnalyticsAgent(BaseAgent):
    name = "analytics_agent"
    description = "Queries DuckDB and interprets product KPIs and metrics"

    async def run(self, workspace_id: str, context: dict[str, Any]) -> dict[str, Any]: 
        self._log_run_start(workspace_id)
        kpi_data=context.get("kpi_data", {})
        behavior_data=context.get("behavior_data", {})
        retention_data=context.get("retention_data", ())
        funnel_data=context.get("funnel_data", ())

        if not any([kpi_data, behavior_data, retention_data, funnel_data]):
            return {
                "kpi_insights": [],
                "anomalies": [],
                "trends": [],
                "health_score": 0.0,
                "summary": "Ho analytics data available for analysis.",
                "recommended_actions": [],
            }

        try:
            structured_llm = self.llm.with_structured_output(AnalyticsOutput) 
            chain = ANALYSIS_PROMPT |  structured_llm

            result: AnalyticsOutput = await chain.ainvoke({
                "workspace_id": workspace_id,
                "kpi_data": str(kpi_data)[:3000],
                "behavior_data": str(behavior_data)[:2000],
                "retention_data": str(retention_data)[:2000],
                "funnel_data": str(funnel_data)[:2000],
            })

            self._log_run_complete(workspace_id, ["kpi_insights","health_score"])
            return result.model_dump()
        except Exception as e:
            self._log_run_error(workspace_id,e)
            return{
                "kpi_insights": [],
                "anomalies": [],
                "trends": [],
                "health_score": 0.0,
                "summary": f"Analysis failed : {e}",
                "recommended_actions": [],
                "error": str(e),
            }