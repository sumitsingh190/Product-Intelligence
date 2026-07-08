"""
Executive Reporting Agent - generates leadership reports and product summaries.
"""

from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel,Field

from app.agents.base import BaseAgent

class ExecutiveReportOutput(BaseModel):
    title: str
    period: str
    executive_summary: str
    key_wins: list[str]
    key_risks: list[str]
    product_health_score: float=Field(ge=0.0, le=100.0)
    top_customer_issues: list[str] 
    top_opportunities: list[str]
    recommended_priorities: list[str]
    kpi_highlights: list[str]
    engineering_highlights: list[str]
    next_steps: list[str]
    full_markdown: str

SYSTEM_PROMPT="""You are an Executive Reporting Al agent that creates concise, data-driven leadership reports for C-suite and VP-level audiences.

Write reports that are:
-Concise and scannable (executives are busy)
-Data-driven with specific numbers
-Action-oriented (clear next steps)
-Honest about risks and challenges
-Forward-looking with priorities

Use clear headers, bullet points, and highlight the most important information first. 
Always include a health score (0-100) and specific recommended priorities."""

REPORT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", """Generate an executive product report for workspace {workspace_id}.

Period: {period}

Product Analytics:
{analytics_summary}

Customer Intelligence: 
{customer_summary}

Engineering Status: 
{engineering_summary}

Key Recommendations: 
{recommendations_summary}

Competitive Landscape: 
{competitor_summary}

Generate a concise executive report. Lead with the most important insights. 
Calculate an overall product health score (0-100).""") 
])

class ExecutiveReportingAgent (BaseAgent): 
    name ="executive_reporting_agent" 
    description="Generates executive leadership reports and product health sumeries"

    async def run(self, workspace_id: str, context: dict[str, Any]) -> dict[str, Any]: 
        self._log_run_start(workspace_id)

        period=context.get("period", "Last 30 days") 
        analytics=context.get("analytics", {}) 
        customer=context.get("customer_insights",{})
        engineering=context.get("engineering", {})
        recommendations=context.get("strategy", {})
        competitor=context.get("competitor", {})

        try:

            structured_llm= self.llm.with_structured_output(ExecutiveReportOutput)
            chain = REPORT_PROMPT | structured_llm

            result: ExecutiveReportOutput = await chain.ainvoke({

                "workspace_id": workspace_id,
                "period": period,
                "analytics_summary": str(analytics) [:2000],
                "customer_summary": str(customer) [:2000],
                "engineering summary": str(engineering) [:1500],
                "recommendations_summary": str(recommendations) [:2000],
                "competitor_summary": str(competitor) [:1000],
            })

            self._log_run_complete(workspace_id, ["executive_report"])
            return result.model_dump()

        except Exception as e:
            self._log_run_error(workspace_id, e)
            return {"error": str(e)}