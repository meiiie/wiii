"""Discriminated union StreamEvent types for WiiiRunner streaming.

Provides type-safe event construction for the merged streaming queue.

Wire format is unchanged: ``(event_type: str, payload: Any)`` tuple.
These types serve as:
1. Documentation of all possible stream events
2. Type-safe constructors (factory functions)
3. Pattern matching support for consumers (via `from_tuple()`)

Inspired by OpenAI Agents SDK StreamEvent union pattern.

Event categories:
- GraphNodeEvent: A pipeline node completed (guardian, supervisor, agent, synthesizer)
- BusEvent: Intra-node real-time event (thinking_delta, answer_delta, tool_call, etc.)
- GraphDoneEvent: Pipeline completed successfully
- ErrorEvent: Pipeline error
- ProviderUnavailableEvent: LLM provider unavailable
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional, Union


# =========================================================================
# Event types — discriminated by `type` field
# =========================================================================


@dataclass(frozen=True)
class GraphNodeEvent:
    """A pipeline node completed with its output state snapshot.

    Produced by: WiiiRunner.run_streaming() after each node completes.
    Consumed by: graph_streaming.py → SSE events.
    """
    type: Literal["graph"] = "graph"
    node_name: str = ""
    state: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class BusEvent:
    """Intra-node real-time event (thinking delta, answer delta, tool call, etc.).

    Produced by: agent nodes via event bus (get_event_queue).
    Consumed by: graph_streaming.py → SSE events (interleaved with graph events).
    """
    type: Literal["bus"] = "bus"
    event: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class GraphDoneEvent:
    """Pipeline completed successfully — no more events will follow."""
    type: Literal["graph_done"] = "graph_done"


@dataclass(frozen=True)
class ErrorEvent:
    """Pipeline error — consumer should emit error SSE and stop."""
    type: Literal["error"] = "error"
    message: str = ""


@dataclass(frozen=True)
class ProviderUnavailableEvent:
    """LLM provider unavailable — consumer should emit provider error SSE."""
    type: Literal["provider_unavailable"] = "provider_unavailable"
    provider: str = ""
    reason_code: str = ""


# Union of all stream events
StreamEvent = Union[
    GraphNodeEvent,
    BusEvent,
    GraphDoneEvent,
    ErrorEvent,
    ProviderUnavailableEvent,
]


# =========================================================================
# Factory functions — type-safe tuple construction
# =========================================================================


def make_graph_event(node_name: str, state: Dict[str, Any]) -> tuple:
    """Create a graph node completion event tuple."""
    return ("graph", {node_name: state})


def make_bus_event(event: Dict[str, Any]) -> tuple:
    """Create a bus event tuple."""
    return ("bus", event)


def make_graph_done() -> tuple:
    """Create a graph-done sentinel tuple."""
    return ("graph_done", None)


def make_error_event(message: str) -> tuple:
    """Create an error event tuple."""
    return ("error", message)


def make_provider_unavailable_event(provider: str, reason_code: str = "") -> tuple:
    """Create a provider-unavailable event tuple."""
    return ("provider_unavailable", {"provider": provider, "reason_code": reason_code})


# =========================================================================
# Parser — convert tuple back to typed event
# =========================================================================


def from_tuple(t: tuple) -> StreamEvent:
    """Parse a merged-queue tuple into a typed StreamEvent.

    Useful for consumers that want pattern matching:
        event = from_tuple(queue_item)
        match event:
            case GraphNodeEvent(node_name=name):
                ...
            case BusEvent(event=e):
                ...
            case GraphDoneEvent():
                ...
    """
    event_type = t[0] if t else ""

    if event_type == "graph":
        payload = t[1] if len(t) > 1 else {}
        if isinstance(payload, dict):
            node_name = next(iter(payload), "")
            state = payload.get(node_name)
        else:
            node_name = ""
            state = payload
        return GraphNodeEvent(node_name=node_name, state=state)

    if event_type == "bus":
        payload = t[1] if len(t) > 1 else None
        return BusEvent(event=payload)

    if event_type == "graph_done":
        return GraphDoneEvent()

    if event_type == "error":
        message = t[1] if len(t) > 1 else ""
        return ErrorEvent(message=str(message))

    if event_type == "provider_unavailable":
        payload = t[1] if len(t) > 1 else {}
        if isinstance(payload, dict):
            return ProviderUnavailableEvent(
                provider=payload.get("provider", ""),
                reason_code=payload.get("reason_code", ""),
            )
        return ProviderUnavailableEvent(provider=str(payload))

    return ErrorEvent(message=f"Unknown event type: {event_type}")
