from abc import ABC, abstractmethod
from typing import Any, TypedDict

from __future__ import annotations
import structlog
from langchain_core.messages import BaseMessage

from app.config import settings
from app.observability.llm_metrics import LLMMetricsCallback

log=structlog.get_logger()

_LLM_CALLBACK = LLMMetricsCallback(default_model=settings.groq_model)

def get_llm(temperature: float | None = None,
            *,
            model: str | None = None,
            max_tokens: int | None = None,
            with_callbacks: bool = True):

    """Return the configured Groq chat model.
    
    The default model is `settings.groq_model`. Callers can override
    per-invocation. The observability callback is attached by default so every
    call is tracked in Prometheus + structlog
    """
    from langchain_groq import ChatGroq
    # temp = temperature if temperature is not None else settings.claude_temperature
    # if settings.ai_provider == "anthropic":
    #     from langchain_anthropic import ChatAnthropic
    #     return ChatAnthropic(
    #         model=settings.claude_model,
    #         api_key=settings.anthropic_api_key,
    #         max_tokens=settings.claude_max_tokens,
    #         temperature=temp,
    #     )

    # from langchain_google_genai import ChatGoogleGenerativeAI
    # return ChatGoogleGenerativeAI(
    #     model=settings.gemini_model,
    #     google_api_key=settings.google_api_key,
    #     temperature=temp,
    #     )
    kwargs : dict[str, Any] = {
        "model": model or settings.groq_model,
        "api_key": settings.groq_api_key,
        "temperature": temperature if temperature is not None else settings.groq_temperature,
        "max_tokens": max_tokens or settings.groq_max_tokens,
        "timeout": settings.groq_timeout_seconds,
    }
    if with_callbacks:
        kwargs["callbacks"] = [_LLM_CALLBACK]
    return ChatGroq(**kwargs)

def get_checkpointer():
    """
    Return a LangGraph checkpointer for agent memory

    Prefers a redis-backed checkpointer(db 3, `settings.agent_checkpoint_redis_url`)
    so agent graph state survives worker restarts and is shared across celery workers.
    Falls backs to in-process `MemorySaver` if redis is unreachable
    """
    if not settings.agent_memory_enabled:
        return None
    
    try:
        from langgraph.checkpoint.redis import RedisSaver

        saver = RedisSaver.from_conn_string(settings.agent_checkpoint_redis_url)
        # Newer versions expose an idempotent setup() that creates indices
        setup=getattr(saver, "setup", None)
        if callable(setup):
            setup()
        log.info("agent_checkpointer", backend="redis", url=settings.agent_checkpoint_redis_url)
        return saver
    except Exception as e:
        log.warning("agent_checkpointer_redis_unavailable", error=str(e), fallback="memory")

    from langgraph.checkpoint.memory import MemorySaver

    return MemorySaver()


class AgentState(TypedDict):
    messages: list[BaseMessage]
    workspace_id: str
    context: dict[str, Any]
    output: dict[str, Any]
    error: str | None

class BaseAgent(ABC):

    """Base class for all ProductOS AI agents."""
    name: str = "base_agent"
    description: str = "Base agent"

    def __init__(self) -> None:
        self.llm = get_llm()
        self.log = structlog.get_logger().bind(agent=self.name)

    def llm_with_tools(self, tools: list | None = None):
        """
        Return a copoy of `self.llm` with the given tools bound.

        If `tools` is None, the default tool set from `app.agents.tools` is used.
        
        """
        from app.agents.tools import get_default_tools
        return self.llm.bind_tools(tools if tools is not None else get_default_tools())

    @abstractmethod
    async def run(self,workspace_id: str, context: dict[str,Any]) -> dict[str, Any]:
        """Execute the agent and return structured output"""

    def _log_run_start(self,workspace_id: str) -> None:
        self.log.info("agent_run_start", workspace_id=workspace_id)

    def _log_run_complete(self, workspace_id: str, output_keys: list[str]) -> None:
        self.log.info("agent_run_complete", workspace_id=workspace_id, output_keys=output_keys)

    def _log_run_error(self, workspace_id: str, error: Exception) -> None:
        self.log.error("agent_run_error", workspace_id=workspace_id, exc_info=error)
        