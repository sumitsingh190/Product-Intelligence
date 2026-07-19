"""LLM observability: token usage, latency, and cost per Groq model.

Attaches a LangChain callback (LLMMetricsCallback) to every LLM instance returned by app.agents.base.get_llm, 
so every `ainvoke / astream call is automatically instrumented. Metrics are exposed via the existing 
prometheus-fastapi-instrumentator/metrics endpoint.

Costs are computed from a static per-model USD-per-1M-token pricing table. 
Update GROQ PRICING_PER_MTOK when Groq changes prices.
"""


from __future__ import annotations
import time
from typing import Any
from uuid import UUID

import structlog
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult
from prometheus_client import Counter, Histogram

log=structlog.get_logger()

GROQ_PRICING_PER_MTOK: dict[str, tuple[float, float]] = {
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "1lama-3.1-70b-versatile": (0.59, 0.79),
    "llama-3.1-8b-instant": (0.05, 0.08),
    "llama-3.1-8b-instant": (0.05, 0.08),
    "llama-3.2-1b-preview": (0.04, 0.04),
    "llama-3.2-3b-preview": (0.06, 0.06),
    "llama-3.2-11b-vision-preview": (0.18, 0.18),
    "llama-3.2-90b-vision-preview": (0.90, 0.90),
    "mixtral-8x7b-32768": (0.24, 0.24),
    "gemma2-9b-it": (0.20, 0.20),
}

_DEFAULT_PRICE = (0.59, 0.79) #fallback matches llama-3.3-70b

def compute_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float: 
    in_price, out_price = GROQ_PRICING_PER_MTOK.get(model, _DEFAULT_PRICE)
    return (prompt_tokens * in_price + completion_tokens * out_price) / 1_000_000


llm_calls_total = Counter(
    "llm_calls_total",
    "Total number of LLM Invocations",
    labelnames=("model", "status"),
)

llm_tokens_total = Counter(
    "llm_tokens_total",
    "Total tokens consumed by LLM calls",
    labelnames=("model", "kind"), #kind prompt completion
)

llm_cost_usd_total = Counter(
    "llm_cost_usd_total",
    "Cumulative cost of LLM calls in USD",
    labelnames=("model",),
)

llm_latency_seconds = Histogram(
    "llm_latency_seconds",
    "End-to-end LLM call latency in seconds",
    labelnames=("model",), 
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0), )

class LLMMetricsCallback(AsyncCallbackHandler):
    """Records prompt/completion tokens, latency, and USD cost for each call.
    Works with LangChain'sainvoke, astream',,abatch", and structured output chains. 
    Latency is measured wall-clock from 'on_llm_start to `on_llm_end` / `on_llm_error`.
    """
    def __init__(self, default_model: str="unknown") -> None:
        self.default_model=default_model
        self._starts: dict[UUID, tuple[float, str]] = {}

    def _resolve_model(self, serialized: dict | None, kwargs: dict) -> str:
        if serialized:
            kw = serialized.get("kwargs") or {}
            for key in ("model", "model _name"):
                if kw.get(key):
                    return str(kw[key])

        params = kwargs.get("invocation_params") or {}
        for key in ("model", "model_name"):
            if params.get(key):
                return str(params[key])
        return self.default_model

    async def on_llm_start(
        self,
        serialized: dict | None,
        prompts: list[str],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:

        model = self._resolve_model(serialized, kwargs)
        self._starts[run_id] = (time.perf_counter(), model)

    async def on_chat_model_start(
        self,
        serialized: dict | None, 
        messages: list[list[Any]],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        model=self._resolve_model(serialized, kwargs)
        self._starts[run_id] = (time.perf_counter(), model)

    async def on_llm_end(
        self, response: LLMResult, *, run_id: UUID, **kwargs: Any
    ) -> None:
        start, model = self._starts.pop(run_id, (time.perf_counter(), self.default_model)) 
        latency=time.perf_counter() - start
        prompt_tokens, completion_tokens=self._extract_token_usage(response) 
        cost = compute_cost_usd (model, prompt_tokens, completion_tokens)

        llm_calls_total.labels(model=model, status="ok").inc()
        llm_latency_seconds.labels(model=model).observe(latency)
        if prompt_tokens:
            llm_tokens_total.labels(model=model, kind="prompt").inc(prompt_tokens)
        if completion_tokens:
            llm_tokens_total.labels (model=model, kind="completion").inc(completion_tokens)
        if cost:
            llm_cost_usd_total.labels(model=model).inc(cost)

        log.info(
            "llm_call",
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=round(latency*1000, 2),
            cost_usd=round(cost, 6),
        )

    async def on_llm_error(
        self, error: BaseException, *, run_id: UUID, **kwargs: Any
    ) -> None:
        start, model=self._starts.pop(run_id, (time.perf_counter(), self.default_model))
        latency=time.perf_counter() - start
        llm_calls_total.labels (model=model, status="error").inc()
        llm_latency_seconds.labels (model=model).observe(latency)
        log.warning(
            "llm_call_error",
            model=model, 
            latency_ms=round(latency*1000, 2),
            error=str(error),
        )

    @staticmethod
    def _extract_token_usage(response: LLMResult) -> tuple[int, int]: 
        """Extract (prompt_tokens, completion_tokens) from an LLMResult.

        Groq exposes usage under 11m_output["token_usage"]"; some LangChain integrations 
        put it under usage_metadata on the generation itself.
        """
        out=response.llm_output or {}
        usage=out.get("token_usage") or out.get("usage") or {}
        pt=int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
        ct=int(usage.get("completion_tokens") or usage.get("output tokens") or 0)
        if pt or ct:
            return pt, ct
        
        # Fallback: scan generations for usage_metadata (LangChain 0.3+)

        for gen_list in response.generations:
            for gen in gen_list:
                msg = getattr(gen, "message", None)
                meta = getattr(msg, "usage_metadata", None) if msg else None
                if meta:
                    pt += int(meta.get("input_tokens", 0))
                    ct += int(meta.get("output_tokens", 0))
        return pt, ct