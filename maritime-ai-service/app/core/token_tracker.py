"""
Token & Cost Tracker — Per-Request LLM Usage Accounting.

SOTA 2026: Track token usage and estimated cost per request.
Uses ContextVar for request-scoped isolation (like Request-ID middleware).
"""

import logging
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_current_tracker: ContextVar[Optional["TokenTracker"]] = ContextVar(
    "token_tracker", default=None
)


@dataclass
class LLMCall:
    """Single LLM invocation record."""

    model: str
    tier: str  # deep / moderate / light
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: float = 0.0
    component: str = ""  # e.g. "supervisor", "rag_agent"


@dataclass
class TokenTracker:
    """Accumulates token usage for a single request."""

    request_id: str = ""
    calls: List[LLMCall] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)

    def record(self, call: LLMCall) -> None:
        """Record a single LLM call."""
        self.calls.append(call)

    @property
    def total_input_tokens(self) -> int:
        return sum(c.input_tokens for c in self.calls)

    @property
    def total_output_tokens(self) -> int:
        return sum(c.output_tokens for c in self.calls)

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    @property
    def total_calls(self) -> int:
        return len(self.calls)

    @property
    def estimated_cost_usd(self) -> float:
        """Estimate cost based on Gemini Flash pricing (2026)."""
        # Gemini 3 Flash: $0.075/1M input, $0.30/1M output
        input_cost = self.total_input_tokens * 0.075 / 1_000_000
        output_cost = self.total_output_tokens * 0.30 / 1_000_000
        return input_cost + output_cost

    def summary(self) -> Dict:
        """Return summary dict suitable for API response metadata."""
        return {
            "total_calls": self.total_calls,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
            "duration_ms": round((time.time() - self.start_time) * 1000, 1),
        }


def start_tracking(request_id: str = "") -> TokenTracker:
    """Start token tracking for the current request context."""
    tracker = TokenTracker(request_id=request_id)
    _current_tracker.set(tracker)
    return tracker


def get_tracker() -> Optional[TokenTracker]:
    """Get the current request's token tracker, if any."""
    return _current_tracker.get()


def record_llm_call(
    model: str,
    tier: str,
    input_tokens: int,
    output_tokens: int,
    duration_ms: float = 0.0,
    component: str = "",
) -> None:
    """Record an LLM call on the current request tracker."""
    tracker = _current_tracker.get()
    if tracker is not None:
        tracker.record(
            LLMCall(
                model=model,
                tier=tier,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                duration_ms=duration_ms,
                component=component,
            )
        )


# =============================================================================
# LangChain Callback Handler for automatic token tracking
# Sprint 27: Wires token_tracker to LLM pool via LangChain callbacks
# =============================================================================

class TokenTrackingCallback:
    """
    LangChain callback handler that auto-records token usage.

    Attached to LLM instances at creation time in LLMPool.
    Uses ContextVar to find the per-request TokenTracker.

    Provides BaseCallbackHandler-compatible attributes so that
    LangChain's callback manager can introspect the handler
    without requiring a full class inheritance chain.

    Usage:
        callback = TokenTrackingCallback(tier="moderate")
        llm = ChatGoogleGenerativeAI(callbacks=[callback], ...)
    """

    # BaseCallbackHandler compatibility (LangChain >=0.3)
    run_inline = False
    raise_error = False
    ignore_llm = False
    ignore_retry = True
    ignore_chain = True
    ignore_agent = True
    ignore_retriever = True
    ignore_chat_model = False
    ignore_custom_event = True

    def __init__(self, tier: str = "unknown"):
        self.tier = tier

    def on_chat_model_start(self, serialized, messages, **kwargs) -> None:
        """Called when chat model starts. No-op; we only track on_llm_end."""

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        """Called for each streamed token. No-op for tracking."""

    def on_llm_error(self, error, **kwargs) -> None:
        """Called when LLM errors. No-op; errors handled elsewhere."""

    def on_llm_end(self, response, **kwargs) -> None:
        """Called when LLM finishes. Extract token usage and record it."""
        tracker = _current_tracker.get()
        if tracker is None:
            return

        try:
            # Extract token usage from LangChain response
            input_tokens = 0
            output_tokens = 0
            model_name = ""

            # LLMResult has generations list; each generation has message
            if hasattr(response, "generations") and response.generations:
                for gen_list in response.generations:
                    for gen in gen_list:
                        msg = getattr(gen, "message", None)
                        if msg and hasattr(msg, "usage_metadata"):
                            meta = msg.usage_metadata
                            if isinstance(meta, dict):
                                input_tokens += meta.get("input_tokens", 0) or meta.get("prompt_tokens", 0)
                                output_tokens += meta.get("output_tokens", 0) or meta.get("completion_tokens", 0)
                            elif hasattr(meta, "input_tokens"):
                                input_tokens += getattr(meta, "input_tokens", 0)
                                output_tokens += getattr(meta, "output_tokens", 0)
                        if msg and hasattr(msg, "response_metadata"):
                            rm = msg.response_metadata
                            if isinstance(rm, dict):
                                model_name = rm.get("model_name", "")

            # Fallback: check llm_output dict
            if input_tokens == 0 and hasattr(response, "llm_output") and response.llm_output:
                usage = response.llm_output.get("usage", {}) or response.llm_output.get("token_usage", {})
                if usage:
                    input_tokens = usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0)
                    output_tokens = usage.get("completion_tokens", 0) or usage.get("output_tokens", 0)
                model_name = model_name or response.llm_output.get("model_name", "")

            if input_tokens > 0 or output_tokens > 0:
                record_llm_call(
                    model=model_name or "unknown",
                    tier=self.tier,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    component=kwargs.get("tags", [""])[0] if kwargs.get("tags") else "",
                )
        except Exception as e:
            logger.debug("Token tracking callback error (non-fatal): %s", e)
