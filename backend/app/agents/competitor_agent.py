"""
Competitor Intelligence Agent
Monitors competitor product releases, feature updates, and market changes.
"""

from typing import Any
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel,Field

from app.agents.base import BaseAgent

class CompetitorUpdate(BaseModel):
    competitor_name: str
    update_type: str = Field(description="feature_launch | pricing_change | partnership | acquisition | other")
    title: str
    description : str
    impact_level: str= Field(description="high | medium | low")
    our_response_needed: bool
    suggested_response: str | None


class CompetitorOutput(BaseModel):
    updates: list[CompetitorUpdate]
    market_threats: list[str]
    market_opportunities: list[str]
    competitive_position: str= Field(description= "leading | competitive | at_risk | lagging")
    summary: str
    urgent_actions: list[str]


SYSTEM_PROMPT= """You are a Competitor Intelligence AI agent that monitors competitive landscape for product teams.

Your job is to:
1. Analyze recent competitor product updates and launches
2. Identify market threats and opportunities.
3. Assess our competitive position.
4. Suggest strategic responses.
5. Identify feature gaps and parity needs

Be objective and evidence-based. Focus on what matters most for product strategy.
"""

ANALYSIS_PROMPT= ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", """Analyze the competitive landscape for workspace {workspacee_id}.

Competitor Updates:
{competitor_updates}

Market News:
{market_news}

Our Product Context:
{product_context}

Identify competitive threats, opportunities, and strategic recommendations.
Assess our competitive position honestly.""")
])

class CompetitorIntelligenceAgent(BaseAgent):
    name = "Competitor_intelligence_agent"
    description= "Monitors competitor products and market intelligence."

    async def run(self, workspace_id: str, context: dict[str, Any])-> dict[str, Any]:
        self._log_run_start(workspace_id)
        competitor_updates=context.get("competitor_updates",[])
        market_news=context.get("market_news",[])
        product_context=context.get("product_context",{})


        if not competitor_updates and not market_news:
            return {
                "updates": [],
                "market_threats": [],
                "market_opportunities":[],
                "competitive_position":"competitive",
                "summary":"No competitor data available for analysis",
                "urgent_actions":[],
            }
        
        try:
            structured_llm= self.llm.with_structured_output(CompetitorOutput)
            chain = ANALYSIS_PROMPT | structured_llm

            result: CompetitorOutput = await chain.ainvoke({
                "workspace_id": workspace_id,
                "competitor_updates": str(competitor_updates)[:3000],
                "market_news": str(market_news)[:2000],
                "product_context": str(product_context)[:1000],
            })

            self._log_run_complete(workspace_id, ["updates", "competitive_position"])
            return result.model_dump()
        
        except Exception as e:
            self._log_run_error(workspace_id,e)
            return{"updates":[], "error":str(e)}
        
