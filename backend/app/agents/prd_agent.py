"""
PRD Agent - generates Product Requirement Documents from recommendations and insights.
"""

from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.agents.base import BaseAgent

class UserStory(BaseModel):
    persona: str
    goal: str
    benefit: str
    acceptance_criteria: list[str]
    priority: str=Field(description="must_have | should_have | nice_to_have")

class PRDOutput(BaseModel):
    title: str
    executive_summary: str
    problem_statement: str
    goals_and_success_metrics: list[str]
    user_personas: list[str]
    user_stories: list[UserStory]
    functional_requirements: list[str]
    non_functional_requirements: list[str]
    out_of_scope: list[str]
    technical_considerations: list[str]
    open_questions: list[str]
    full_markdown: str

SYSTEM_PROMPT = """You are a PRD (Product Requirement Document) AI agent that generates professional product requirements documents.

Write PRDs that are:
-Clear and unambiguous
-Evidence-based (reference customer data, analytics)
-Developer-friendly (specific acceptance criteria)
-Structured with proper sections

Follow standard PRD best practices. Each user story should follow the format: 
"As a [persona], I want to [goal] so that [benefit]."

Generate complete, production-ready PRDs."""

PRD_PROMPT =ChatPromptTemplate.from_messages([ 
    ("system", SYSTEM_PROMPT), 
    ("human", """Generate a complete PRD for the following feature/initiative.

Feature Title: {feature_title} 
Description: {feature_description}

Supporting Evidence: 
{evidence}

Customer Feedback Context: 
{customer_context}

Analytics Context: 
{analytics_context}

Generate a comprehensive PRD with all sections. Include specific acceptance criteria, 
user stories, and measurable success metrics."""), ])

class PRDAgent(BaseAgent): 
    name="prd_agent" 
    description="Generates Product Requirement Documents from recommendations"

    async def run(self, workspace_id: str, context: dict[str, Any]) -> dict[str, Any]: 
        self._log_run_start(workspace_id)

        feature_title =context.get("feature_title", "Untitled Feature")
        feature_description = context.get("feature_description", "")
        evidence = context.get("evidence", [])
        customer_context=context.get("customer_insights", {})
        analytics_context=context.get("analytics", {})

        try:
            structured_llm =self.llm.with_structured_output(PRDOutput)
            chain=PRD_PROMPT | structured_llm
        
            result: PRDOutput=await chain.ainvoke({
                "feature_title": feature_title,
                "evidence": "\n".join(str(e) for e in evidence[:20]),
                "feature_description": feature_description, 
                "customer_context": str(customer_context)[:2000], 
                "analytics_context": str(analytics_context)[:1500],
            }) 
            self._log_run_complete(workspace_id, ["prd"])
            return result.model_dump()

        except Exception as e:
            self._log_run_error(workspace_id, e)
            return {"error": str(e)}

    async def generate_from_recommendation(
        self, workspace_id: str, recommendation_id: str, db ) -> dict[str, Any]:

        from app.models.recommendation import Recommendation
        from sqlalchemy import select

        result=await db.execute(
            select(Recommendation).where(Recommendation.id==recommendation_id)
        )
        rec=result.scalar_one_or_none()
        if not rec:
            return {"error":"Recommendation not found"}
        
        context={
            "feature_title": rec.title,
            "feature_description" : rec.description,
            "evidence" : rec.evidence,
        }

        return await self.run(workspace_id, context)