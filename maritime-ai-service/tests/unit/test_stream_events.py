"""Unit tests for P4: Discriminated union StreamEvent types."""

import pytest

from app.engine.multi_agent.stream_events import (
    BusEvent,
    ErrorEvent,
    GraphDoneEvent,
    GraphNodeEvent,
    ProviderUnavailableEvent,
    StreamEvent,
    from_tuple,
    make_bus_event,
    make_error_event,
    make_graph_done,
    make_graph_event,
    make_provider_unavailable_event,
)


# =========================================================================
# Event dataclass types
# =========================================================================


class TestEventTypes:
    def test_graph_node_event(self):
        e = GraphNodeEvent(node_name="rag_agent", state={"query": "test"})
        assert e.type == "graph"
        assert e.node_name == "rag_agent"
        assert e.state["query"] == "test"

    def test_bus_event(self):
        e = BusEvent(event={"type": "thinking_delta", "content": "x"})
        assert e.type == "bus"
        assert e.event["type"] == "thinking_delta"

    def test_graph_done_event(self):
        e = GraphDoneEvent()
        assert e.type == "graph_done"

    def test_error_event(self):
        e = ErrorEvent(message="DB down")
        assert e.type == "error"
        assert e.message == "DB down"

    def test_provider_unavailable_event(self):
        e = ProviderUnavailableEvent(provider="google", reason_code="rate_limit")
        assert e.type == "provider_unavailable"
        assert e.provider == "google"

    def test_events_are_frozen(self):
        e = GraphNodeEvent(node_name="rag_agent")
        with pytest.raises(AttributeError):
            e.type = "bus"  # type: ignore[misc]


# =========================================================================
# Factory functions — produce correct tuple format
# =========================================================================


class TestFactoryFunctions:
    def test_make_graph_event(self):
        t = make_graph_event("rag_agent", {"query": "COLREG"})
        assert t == ("graph", {"rag_agent": {"query": "COLREG"}})

    def test_make_bus_event(self):
        t = make_bus_event({"type": "answer_delta", "content": "hello"})
        assert t == ("bus", {"type": "answer_delta", "content": "hello"})

    def test_make_graph_done(self):
        t = make_graph_done()
        assert t == ("graph_done", None)

    def test_make_error_event(self):
        t = make_error_event("Processing timeout")
        assert t == ("error", "Processing timeout")

    def test_make_provider_unavailable_event(self):
        t = make_provider_unavailable_event("google", "rate_limit")
        assert t[0] == "provider_unavailable"
        assert t[1]["provider"] == "google"
        assert t[1]["reason_code"] == "rate_limit"


# =========================================================================
# from_tuple parser — round-trip
# =========================================================================


class TestFromTuple:
    def test_parse_graph_event(self):
        e = from_tuple(("graph", {"rag_agent": {"query": "test"}}))
        assert isinstance(e, GraphNodeEvent)
        assert e.node_name == "rag_agent"
        assert e.state == {"query": "test"}

    def test_parse_bus_event(self):
        e = from_tuple(("bus", {"type": "thinking_delta", "content": "x"}))
        assert isinstance(e, BusEvent)
        assert e.event["type"] == "thinking_delta"

    def test_parse_graph_done(self):
        e = from_tuple(("graph_done", None))
        assert isinstance(e, GraphDoneEvent)

    def test_parse_error_event(self):
        e = from_tuple(("error", "DB connection failed"))
        assert isinstance(e, ErrorEvent)
        assert e.message == "DB connection failed"

    def test_parse_provider_unavailable_dict(self):
        e = from_tuple(("provider_unavailable", {"provider": "google", "reason_code": "timeout"}))
        assert isinstance(e, ProviderUnavailableEvent)
        assert e.provider == "google"
        assert e.reason_code == "timeout"

    def test_parse_provider_unavailable_exception(self):
        """Provider unavailable with exception payload."""
        e = from_tuple(("provider_unavailable", RuntimeError("rate limited")))
        assert isinstance(e, ProviderUnavailableEvent)

    def test_parse_unknown_type_returns_error(self):
        e = from_tuple(("unknown_type", "data"))
        assert isinstance(e, ErrorEvent)
        assert "unknown_type" in e.message

    def test_parse_empty_tuple(self):
        e = from_tuple(())
        assert isinstance(e, ErrorEvent)

    def test_parse_graph_empty_payload(self):
        e = from_tuple(("graph", {}))
        assert isinstance(e, GraphNodeEvent)
        assert e.node_name == ""
        assert e.state is None

    def test_roundtrip_graph_event(self):
        """Factory → tuple → parse → same values."""
        t = make_graph_event("tutor_agent", {"query": "test"})
        e = from_tuple(t)
        assert isinstance(e, GraphNodeEvent)
        assert e.node_name == "tutor_agent"

    def test_roundtrip_bus_event(self):
        t = make_bus_event({"type": "tool_call", "name": "search"})
        e = from_tuple(t)
        assert isinstance(e, BusEvent)
        assert e.event["name"] == "search"


# =========================================================================
# StreamEvent union type
# =========================================================================


class TestStreamEventUnion:
    def test_all_event_types_are_in_union(self):
        """All event types should be assignable to StreamEvent."""
        events: list[StreamEvent] = [
            GraphNodeEvent(node_name="rag_agent"),
            BusEvent(event={"type": "thinking_delta"}),
            GraphDoneEvent(),
            ErrorEvent(message="fail"),
            ProviderUnavailableEvent(provider="google"),
        ]
        assert len(events) == 5
        types = {type(e) for e in events}
        assert types == {GraphNodeEvent, BusEvent, GraphDoneEvent, ErrorEvent, ProviderUnavailableEvent}
