"""Shared tracer store for multi-agent graph execution."""

from __future__ import annotations

import uuid
from typing import Dict, Optional

from app.engine.multi_agent.state import AgentState
from app.engine.reasoning_tracer import ReasoningTracer, get_reasoning_tracer


_TRACERS: Dict[str, ReasoningTracer] = {}


def _get_or_create_tracer(state: AgentState) -> ReasoningTracer:
    """Get existing tracer from store or create a new one."""
    trace_id = state.get("_trace_id")
    if trace_id and trace_id in _TRACERS:
        return _TRACERS[trace_id]

    tracer = get_reasoning_tracer()
    trace_id = str(uuid.uuid4())
    _TRACERS[trace_id] = tracer
    state["_trace_id"] = trace_id
    return tracer


def _cleanup_tracer(trace_id: Optional[str]) -> None:
    """Remove tracer from module-level storage after graph completion."""
    if trace_id and trace_id in _TRACERS:
        del _TRACERS[trace_id]
