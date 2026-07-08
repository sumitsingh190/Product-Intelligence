"""
Customer Intelligence Agent
Analyzes customer reviews, support tickets, and feedback to surface insights.
"""

from typing import Any
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.agents.base import BaseAgent

class CustomerInsight(BaseModel):
    title: str
    summary: str
    insight_type: str= Field(description="complaint | feature_reequest | praise | question")
    severity: str= Field(description="critical | high | medium | low | info")
    evidence: list[str] = Field(description="Supporting quotes or data points")
    affected_users_estimate: int=0
    confidence_score: float=Field(ge=0.0, le=1.0)
    tags: list[str]=[]


class CustomerIntelligenceOutput(BaseModel):
    insights: list[CustomerInsight]
    overall_sentiment: float= Field(description="Sentiment score -1.0 to 1.0")
    top_themes: list[str]
    summary: str
    data_sources_analyzed: list[str]

SYSTEM_PROMPT = """ You are a Customer Intelligence AI agent specialized in analyzing customer feedback, reviews, and 
support tickets for product teams.

Your job is to:
1. Identify recurring complaints and issues
2. Extract feature requests with evidence
3. Detect sentiment trends
4. Cluster related feedback themes
5. Estimate the number of affected users
6. Assess severity based on frequency and user impact

Always base insights on specific evidences from data. Never fabricate data. 
Output structured insights that product managers can act on immediately.
"""

ANALYSIS_PROMPT= ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", """Analyze the following customer feedback data for workspace {workspace_id}.
     
Customer Reviews:
{reviews}
    
Support Tickets:
{support_tickets}
     
Existing Analytics context:
{analytics_context}

Generate actionable customer intelligence insights. Focus on:
- Top complaints (sorted by frequency and severity)
- Feature requests with user demand evidence
- Sentiment trends
- Emerging issues that need immediate attention
     
Return a structured analysis with specific evidence for each insight.""")
])

class CustomerIntelligenceAgent(BaseAgent):
    name = "customer_intelligence_agent"
    description = "Analyzes customer reviews, support tickets, and feedback"

    async def run(self, workspace_id: str, context: dict[str, Any]) -> dict[str, Any]:
        self._log_run_start(workspace_id)

        reviews=context.get("reviews",[])
        support_tickets=context.get("support_tickets",[])
        analytics_context=context.get("analytics",{})

        if not reviews and not support_tickets:
            return{
                "insights" : [],
                "overall_sentiment": 0.0,
                "top_themes": [],
                "summary": "No customer feedback data available for analysis",
                "data_sources_analyzed":[],
            }
        
        try:
            structured_llm=self.llm.with_structured_output(CustomerIntelligenceOutput)
            chain=ANALYSIS_PROMPT | structured_llm

            result: CustomerIntelligenceOutput = await chain.ainvoke({
                "workspace_id": workspace_id,
                "reviews": self._format_reviews(reviews),
                "support_tickets": self._format_tickets(support_tickets),
                "analytics_context": str(analytics_context)[:2000],
            })

            self._log_run_complete(workspace_id, ["insights", "sentiment", "themes"])
            return result.model_dump()
        
        except Exception as e:
            self._log_run_error(workspace_id,e)
            return{
                "insights": [],
                "overall_sentiment":0.0,
                "top_themes": [],
                "summary": f"Analysis failed: {e}",
                "data_sources_analyzed": [],
                "error": str(e),
            }
        
    def _format_review(self,reviews: list) -> str:
        if not reviews:
            return "No reviews available"
        formatted=[]
        for r in reviews[:50]:
            formatted.append(
                f"[{r.get('rating','N/A')}/5] {r.get('text','')}"
                f"(Source: {r.get('source','unknown')}, Date: {r.get('date','unknown')})"
            )
        return "\n".join(formatted)
    
    def _format_tickets(self, tickets: list) -> str:
        if not tickets:
            return "No support tickets available"
        formatted=[]
        for t in tickets[:50]:
            formatted.append(
                f"[{t.get('priority','normal')}] {t.get('description','')[:200]}"
            )
        return "\n".join(formatted)
