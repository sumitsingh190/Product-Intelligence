"""
Planner Agent - coordinates all specialized agents in a LangGraph Workflow.
Routes tasks to the appropriate specialized agent based on the workspace state.
"""

from __future__ import annotations
from typing import Any,Literal, Annotated, TypedDict

import structlog
from langchain_core.messages import BaseMessage
from langgraph.graph import END, StateGraph, START

from app.agents.base import AgentState,BaseAgent,get_llm
from app.agents.customer_intelligence_agent import CustomerIntelligenceAgent
from app.agents.analytics_agent import AnalyticsAgent
from app.agents.engineering_agent import EngineeringIntelligenceAgent
from app.agents.competitor_agent import CompetitorIntelligenceAgent
from app.agents.product_strategy_agent import ProductStrategyAgent
from app.agents.validator import validate_strategy_output
from app.config import settings

log=structlog.get_logger()

INTELLIGENCE_BRANCHES: tuple[str, ...] = (
    "customer_intelligence",
    "analytics",
    "engineering_intelligence",
    "competitor_intelligence"
)

def _merge_context(a: dict[str, Any] | None, b: dict[str, Any] | None) -> dict[str, Any]:
    """
    Reducer for concurrent writes into state['context']

    Each branch writes to tis own top-level key, so a shallow merge is safe.
    """
    merged: dict[str, Any] = dict(a or {})
    merged.update(b or {})
    return merged

class PlannerState(TypedDict):
     messages: list[BaseMessage]
     workspace_id: str
     context: Annotated[dict[str, Any], _merge_context]
     output: dict[str, Any]
     error: str | None


class PlannerAgent(BaseAgent):
    name="planner_agent"
    description="Coordinates all specialized agents and routes analysis tasks"

    def _init_(self) -> None:
        super()._init_()
        self.customer_agent = CustomerIntelligenceAgent()
        self.analytics_agent = AnalyticsAgent()
        self.engineering_agent = EngineeringIntelligenceAgent()
        self.competitor_agent = CompetitorIntelligenceAgent()
        self.strategy_agent = ProductStrategyAgent()
        self._graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(AgentState)

        graph.add_node("router", self._route)
        graph.add_node("customer_intelligence", self._run_customer_intelligence)
        graph.add_node("analytics", self._run_analytics)
        graph.add_node("engineering_intelligence", self._run_engineering)
        graph.add_node("competitor_intelligence", self._run_competitor)
        graph.add_node("product_strategy", self._run_strategy)
        graph.add_node("validate", self._validate)
        graph.add_node("synthesize", self._synthesize)

        # graph.set_entry_point("customer_intelligence")
        # graph.add_edge("customer_intelligence", "analytics")
        # graph.add_edge("analytics", "engineering_intelligence")
        # graph.add_edge("engineering_intelligence", "competitor_intelligence") 
        # graph.add_edge("competitor_intelligence", "product_strategy")
        # graph.add_edge("product_strategy", "synthesize")
        # graph.add_edge("synthesize", END)
        graph.add_edge(START, "router")

        # Fan-out: the dispatcher returns a list of node names, which
        # LangGraph executes concurrently.
        graph.add_conditional_edges(
            "router",
            self._dispatch,
            {name: name for name in INTELLIGENCE_BRANCHES},
        )

        #Fan-in: every parallel branch converges on product_strategy.
        #LangGraph will not fire this node until every dispatched branch
        #has produced a state update.
        for branch in INTELLIGENCE_BRANCHES:
            graph.add_edge(branch, "product_strategy")
        graph.add_edge("product_strategy", "validate")
        graph.add_edge("validate", "synthesize")
        graph.add_edge("synthesize", END)
        
        checkpointer = get_checkpointer()
        return graph.compile(checkpointer=checkpointer) if checkpointer else graph.compile()

# Router
    async def _route(self, state: PlannerState) -> dict[str, Any]:
        selected = self._selected_branches (state)
        log.info(
            "planner_routing",
            workspace_id=state["workspace_id"], 
            branches=list(selected),
        )
        return {"context": {"_routed_branches": list(selected)}}
    
    def _dispatch(self, state: PlannerState) -> list[str]:
        return list(self._selected_branches(state))

    def _selected_branches(self, state: PlannerState) -> tuple[str, ...]: 
        focus=(state.get("context") or {}).get("focus_areas")
        if not focus:
            return INTELLIGENCE_BRANCHES
        
        wanted=(str(f).lower() for f in focus)
        selected=tuple(b for b in INTELLIGENCE_BRANCHES if b in wanted)

        #Never allow an empty fan-out that would starve the join point.
        return selected or INTELLIGENCE_BRANCHES

    async def _run_customer_intelligence(self, state: AgentState) -> AgentState:
        try:
            result = await self.customer_agent.run(  
                state["workspace_id"], state.get("context", {}) 
            )
            state["context"]["customer_insights"] = result

        except Exception as e: 
            log.warning("customer_intelligence_failed", error=str(e)) 
            state["context"]["customer_insights"] ={"insights": [], "error": str(e)}

        return state

    async def _run_analytics(self, state: AgentState) -> AgentState: 
        try:
            result=await self.analytics_agent.run( 
                state["workspace_id"], state.get("context", {})
            )
            state["context"]["analytics"] = result
        except Exception as e: 
            result = log.warning("analytics_failed", error=str(e)) 
            state["context"]["analytics"] = {"kpis": {}, "error": str(e)}
        return state

    async def _run_engineering(self, state: AgentState) -> AgentState: 
        try:
            result=await self.engineering_agent.run( 
                state["workspace_id"], state.get("context", {})
            )
            state["context"]["engineering"] = result
        except Exception as e:
            log.warning("engineering_intelligence_failed", error=str(e)) 
            state["context"]["engineering"] ={"insights": [], "error": str(e)}
        return state

    async def _run_competitor(self, state: AgentState) -> AgentState :
        try:
            result=await self.competitor_agent.run(
                state["workspace_id"], state.get("context", {})
            )
            state["context"]["competitor"] = result
        except Exception as e:
            log.warning("competitor_intelligence_failed", error=str(e)) 
            state["context"]["competitor"] = {"Insights": [], "error": str(e)}
        return state

    async def _run_strategy(self, state: AgentState)-> AgentState:
        try:
            result = await self.strategy_agent.run(
                state["workspace_id"], state.get("context", {})
            )
            state["context"]["strategy"] = result
        except Exception as e:
            log.warning("product_strategy_failed", error=str(e))
            state["context"]["strategy"] = {"recommendations": [], "error": str(e)}
        return state
    
    async def _validate(self, state: PlannerState) -> dict[str, Any]:
        """Guard-rail node: sanitise strategy output before it leaves the graph.

        Drops malformed recommendations, re-derives ROI when inconsistent, and ensures top_priority points 
        at a surviving recommendation. The validation report is stashed on the state so callers can surface it.
        """
        ctx = state.get("context") or ()
        strategy = ctx.get("strategy") or {}
        if not settings.feature_strategy_validator: 
            return {"context": {"validation": {"skipped": True}}}

        cleaned, report = validate_strategy_output(strategy)
        if report["dropped"] or report["repaired"]:
            log.info(
                "planner_validation",
                workspace_id=state ["workspace_id"], 
                dropped=len(report["dropped"]), 
                repaired=len(report["repaired"]),
            )
        return {"context": {"strategy":cleaned, "validation": report}}

    async def _synthesize(self,state:AgentState) -> AgentState:
        ctx=state.get("context",{})
        output={
            "workspace_id": state["workspace_id"],

            "customer_insights": ctx.get("customer_insights", {}),
            "analytics": ctx.get("analytics", {}),
            "engineering": ctx.get("engineering", {}),
            "competitor": ctx.get("competitor", {}),
            "strategy": ctx.get("strategy", {}),
            "validation": ctx.get("validation", {}),
            "routed_branches": ctx.get("_routed_branches", list(INTELLIGENCE_BRANCHES)),
        }

        return {"output": output}

    async def run(self, workspace_id: str, context: dict[str, Any]) -> dict[str, Any]:
        self._log_run_start(workspace_id)   
        initial_state: AgentState = {
            "messages": [],
            "workspace_id": workspace_id,
            "context": context,
            "output": {},
            "error": None,
        }

        thread_id= (context or {}).get("thread_id") or f"workspace:{workspace_id}"
        run_config= {"configurable": {"thread_id":thread_id}}
        try:
            final_state = await self.graph.ainvoke(initial_state, config=run_config)
            self._log_run_complete (workspace_id, list(final_state["output"].keys()))
            return final_state["output"]
        except Exception as e:
            self._log_run_error(workspace_id, e)
            return {"workspace_id": workspace_id, "error": str(e)}