"""
Product Strategy Agent
Synthesizes all intelligence to generate prioritized roadmap recommendation.
"""

from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.agents.base import BaseAgent

class StrategicRecommendation (BaseModel):
    title: str
    description: str
    recommendation_type: str =Field(
        description-"feature | bug fix | performance | ux | security | tech_debt | research"
    )
    impact_score: float=Field(ge=0.0, le=10.0, description="Business impact 0-10")
    effort_score: float=Field(ge-0.0, le=10.0, description="Engineering effort 0-10")
    confidence_score: float=Field(ge=0.0, le=1.0)
    roi_score: float=Field(ge=0.0, le=10.0, description="ROI impact / effort")
    rationale: str
    evidence: list[str]
    estimated_effort_days: int | None
    estimated_users_impacted: int | None
    acceptance_criteria: list[str]
    tags: list[str] = [] 
    insight_references: list[str] = []

class ProductStrategyOutput(BaseModel):
    recommendations: list[StrategicRecommendation]
    strategic_themes: list[str]
    north_star_metric: str
    summary: str
    top_priority: str

SYSTEM_PROMPT = """You are a Product Stratogy Al agent that synthesizes intelligence from multiple sources to generate prioritized product roadmap recommendations.

Your job is to:

1. Synthesize inslahts from customer feedback, analvtics, engineering, and competitive data
2. Generate specific, actionable product recommendations
3. Score each recommendation by impact (0-10), effort (8-10), and calculate ROI
4. Prioritize based on evidence and business value
5. Generate clear acceptance criteria for each recommendation

Use the RICE framework (Reach, Impact, Confidence, Effort) for scoring.
ROI score (Impact Confidence) / Effort

Be specific. Every recommendation must have clear evidence and measurable acceptance criteria."""

ANALYSIS_PROMPT = ChatPromptTemplate.from_messages([

    ("system", SYSTEM_PROMPT), 
    ("human", """Generate strategic product recommendations for workspace {workspace_id}.

Customer Intelligence: 
{customer_insights}

Analytics Insights: 
{analytics_insights}

Engineering Intelligence:
{engineering insights}

Competitor Intelligence:
{competitor_insights}

I

Generate 5-18 prioritized recommendations ranked by ROI score. 
Each recommendation must include evidence, acceptance criteria, and scoring."""),
])

class ProductStrategyAgent(BaseAgent): 
    name="product_strategy_agent"
    description="Synthesizes all signals to generate prioritized roadmap recommendations"

    async def run(self, workspace_id: str, context: dict[str, Any]) -> dict[str, Any]:
        self._log_run_start(workspace_id)

        customer_insights=context.get("customer_insights", {})
        analytics_insights=context.get("analytics", {})
        engineering_insights=context.get("engineering", {})
        competitor_insights=context.get("competitor", {})

        has_data = any([
            customer_insights.get("insights"),
            analytics_insights.get("kpi_insights"),
            engineering_insights.get("insights"),
            competitor_insights.get("updates"),
        ])
        
        
        if not has_data:
            return {
                "recommendations": [],
                "strategic themes": [],
                "north_star_metric": "Unknown",
                "summary": "Insufficient data to generate recommendations.",
                "top priority":"",
            }
        
        try:
            structured_llm=self.llm.with_structured_output(ProductStrategyOutput)
            chain = ANALYSIS_PROMPT | structured_llm
            
            result: ProductStrategyOutput = await chain.ainvoke({

                "workspace_id": workspace_id,
                "customer insights": str(customer_insights) [:3000],
                "analytics_insights": str(analytics_insights) [:2000],
                "engineering insights": str(engineering_insights) [:2000], 
                "competitor_insights": str(competitor_insights)[:1500],
                })

            self._log_run_complete(workspace_id, ["recommendations"])
            return result.model_dump()

        except Exception as e:
            self._log_run_error(workspace_id, e) 
            return {"recommendations": [], "error": str(e)}