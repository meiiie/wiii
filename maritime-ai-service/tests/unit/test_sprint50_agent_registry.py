"""
Tests for Sprint 50: AgentRegistry and AgentTracer coverage.

Tests agent registry including:
- TraceSpan (dataclass, duration_ms)
- AgentTracer (start/end trace, span context manager, get_trace_summary)
- AgentRegistry (init, register, unregister, get, get_config, get_by_category, get_by_access_level, get_all, get_all_configs, get_tools_for_agent, get_agents_for_tool, tracing, count, is_registered, summary, list_all)
- Singleton (get_agent_registry, register_agent)
"""

import pytest
from unittest.mock import MagicMock, patch
import time

from app.engine.agents.config import AgentConfig, AgentCategory, AccessLevel


# ============================================================================
# TraceSpan
# ============================================================================


class TestTraceSpan:
    """Test TraceSpan dataclass."""

    def test_defaults(self):
        from app.engine.agents.registry import TraceSpan
        span = TraceSpan(
            span_id="s1", trace_id="t1", agent_id="rag",
            operation="retrieve", start_time=100.0
        )
        assert span.status == "running"
        assert span.end_time is None
        assert span.error is None

    def test_duration_ms_with_end(self):
        from app.engine.agents.registry import TraceSpan
        span = TraceSpan(
            span_id="s1", trace_id="t1", agent_id="rag",
            operation="retrieve", start_time=100.0, end_time=100.5
        )
        assert abs(span.duration_ms - 500.0) < 0.1

    def test_duration_ms_no_end(self):
        from app.engine.agents.registry import TraceSpan
        span = TraceSpan(
            span_id="s1", trace_id="t1", agent_id="rag",
            operation="retrieve", start_time=100.0
        )
        assert span.duration_ms == 0.0


# ============================================================================
# AgentTracer
# ============================================================================


class TestAgentTracer:
    """Test AgentTracer tracing."""

    def test_start_trace(self):
        from app.engine.agents.registry import AgentTracer
        tracer = AgentTracer()
        trace_id = tracer.start_trace()
        assert trace_id is not None
        assert len(trace_id) == 8
        assert trace_id in tracer._traces

    def test_end_trace(self):
        from app.engine.agents.registry import AgentTracer
        tracer = AgentTracer()
        tid = tracer.start_trace()
        spans = tracer.end_trace(tid)
        assert spans == []
        assert tracer._current_trace_id is None

    def test_end_nonexistent_trace(self):
        from app.engine.agents.registry import AgentTracer
        tracer = AgentTracer()
        spans = tracer.end_trace("nonexistent")
        assert spans == []

    def test_span_success(self):
        from app.engine.agents.registry import AgentTracer
        tracer = AgentTracer()
        tid = tracer.start_trace()
        with tracer.span("rag_agent", "retrieve", {"query": "test"}) as span:
            pass  # Simulate work
        assert span.status == "success"
        assert span.end_time is not None
        assert span.duration_ms >= 0
        assert span.metadata == {"query": "test"}
        assert len(tracer._traces[tid]) == 1

    def test_span_error(self):
        from app.engine.agents.registry import AgentTracer
        tracer = AgentTracer()
        tid = tracer.start_trace()
        with pytest.raises(ValueError):
            with tracer.span("rag_agent", "retrieve") as span:
                raise ValueError("something went wrong")
        assert span.status == "error"
        assert span.error == "something went wrong"
        assert span.end_time is not None

    def test_span_no_active_trace(self):
        from app.engine.agents.registry import AgentTracer
        tracer = AgentTracer()
        # No trace started — span still works (untraced)
        with tracer.span("agent", "op") as span:
            pass
        assert span.trace_id == "untraced"

    def test_get_trace_summary_empty(self):
        from app.engine.agents.registry import AgentTracer
        tracer = AgentTracer()
        assert tracer.get_trace_summary("nonexistent") == {}

    def test_get_trace_summary(self):
        from app.engine.agents.registry import AgentTracer
        tracer = AgentTracer()
        tid = tracer.start_trace()
        with tracer.span("rag", "retrieve"):
            pass
        with tracer.span("grader", "grade"):
            pass
        summary = tracer.get_trace_summary(tid)
        assert summary["trace_id"] == tid
        assert summary["span_count"] == 2
        assert "rag" in summary["agents_involved"]
        assert "grader" in summary["agents_involved"]
        assert summary["total_duration_ms"] >= 0


# ============================================================================
# AgentRegistry — init
# ============================================================================


class TestRegistryInit:
    """Test registry initialization."""

    def test_init(self):
        from app.engine.agents.registry import AgentRegistry
        reg = AgentRegistry()
        assert reg._agents == {}
        assert reg._initialized is False
        assert len(reg._configs) > 0  # Default configs loaded


# ============================================================================
# AgentRegistry — register / unregister
# ============================================================================


class TestRegisterUnregister:
    """Test agent registration."""

    def test_register_with_explicit_id(self):
        from app.engine.agents.registry import AgentRegistry
        reg = AgentRegistry()
        agent = MagicMock()
        config = AgentConfig(id="test", name="Test", role="R", goal="G")
        reg.register(agent, config, agent_id="test")
        assert reg.get("test") is agent
        assert reg.get_config("test") is config

    def test_register_with_agent_id_attr(self):
        from app.engine.agents.registry import AgentRegistry
        reg = AgentRegistry()
        agent = MagicMock()
        agent.agent_id = "from_attr"
        reg.register(agent)
        assert reg.is_registered("from_attr")

    def test_register_with_config_id(self):
        from app.engine.agents.registry import AgentRegistry
        reg = AgentRegistry()
        agent = MagicMock(spec=[])
        agent.config = MagicMock()
        agent.config.id = "from_config"
        reg.register(agent)
        assert reg.is_registered("from_config")

    def test_register_with_class_name(self):
        from app.engine.agents.registry import AgentRegistry
        reg = AgentRegistry()

        class MyCustomAgent:
            pass

        agent = MyCustomAgent()
        reg.register(agent)
        assert reg.is_registered("mycustomagent")

    def test_register_creates_default_config(self):
        from app.engine.agents.registry import AgentRegistry
        reg = AgentRegistry()

        class NewAgent:
            pass

        reg.register(NewAgent(), agent_id="new_agent")
        config = reg.get_config("new_agent")
        assert config is not None
        assert config.name == "NewAgent"

    def test_unregister_existing(self):
        from app.engine.agents.registry import AgentRegistry
        reg = AgentRegistry()
        reg.register(MagicMock(), agent_id="to_remove")
        assert reg.unregister("to_remove") is True
        assert not reg.is_registered("to_remove")

    def test_unregister_nonexistent(self):
        from app.engine.agents.registry import AgentRegistry
        reg = AgentRegistry()
        assert reg.unregister("nonexistent") is False


# ============================================================================
# AgentRegistry — retrieval
# ============================================================================


class TestRegistryRetrieval:
    """Test agent retrieval methods."""

    def _make_registry(self):
        from app.engine.agents.registry import AgentRegistry
        reg = AgentRegistry()
        cfg_rag = AgentConfig(id="rag", name="RAG", role="R", goal="G",
                              category=AgentCategory.RETRIEVAL, access_level=AccessLevel.READ,
                              tools=["search", "retrieve"])
        cfg_tutor = AgentConfig(id="tutor", name="Tutor", role="T", goal="G",
                                category=AgentCategory.TEACHING, access_level=AccessLevel.READ,
                                tools=["explain"])
        cfg_admin = AgentConfig(id="admin_agent", name="Admin", role="A", goal="G",
                                category=AgentCategory.ROUTING, access_level=AccessLevel.ADMIN,
                                tools=["search"])
        reg.register(MagicMock(), cfg_rag, "rag")
        reg.register(MagicMock(), cfg_tutor, "tutor")
        reg.register(MagicMock(), cfg_admin, "admin_agent")
        return reg

    def test_get_existing(self):
        reg = self._make_registry()
        assert reg.get("rag") is not None

    def test_get_nonexistent(self):
        reg = self._make_registry()
        assert reg.get("nonexistent") is None

    def test_get_config(self):
        reg = self._make_registry()
        cfg = reg.get_config("rag")
        assert cfg.name == "RAG"

    def test_get_by_category(self):
        reg = self._make_registry()
        rag_agents = reg.get_by_category(AgentCategory.RETRIEVAL)
        assert len(rag_agents) == 1

    def test_get_by_category_empty(self):
        reg = self._make_registry()
        direct_agents = reg.get_by_category(AgentCategory.DIRECT)
        assert direct_agents == []

    def test_get_by_access_level(self):
        reg = self._make_registry()
        admins = reg.get_by_access_level(AccessLevel.ADMIN)
        assert len(admins) == 1

    def test_get_all(self):
        reg = self._make_registry()
        all_agents = reg.get_all()
        assert len(all_agents) == 3

    def test_get_all_configs(self):
        reg = self._make_registry()
        configs = reg.get_all_configs()
        assert "rag" in configs
        assert "tutor" in configs


# ============================================================================
# AgentRegistry — tool mapping
# ============================================================================


class TestToolMapping:
    """Test tool-agent mapping."""

    def test_get_tools_for_agent(self):
        from app.engine.agents.registry import AgentRegistry
        reg = AgentRegistry()
        cfg = AgentConfig(id="rag", name="RAG", role="R", goal="G", tools=["search", "retrieve"])
        reg.register(MagicMock(), cfg, "rag")
        tools = reg.get_tools_for_agent("rag")
        assert tools == ["search", "retrieve"]

    def test_get_tools_nonexistent(self):
        from app.engine.agents.registry import AgentRegistry
        reg = AgentRegistry()
        assert reg.get_tools_for_agent("nonexistent") == []

    def test_get_agents_for_tool(self):
        from app.engine.agents.registry import AgentRegistry
        reg = AgentRegistry()
        cfg1 = AgentConfig(id="a1", name="A1", role="R", goal="G", tools=["search"])
        cfg2 = AgentConfig(id="a2", name="A2", role="R", goal="G", tools=["search", "grade"])
        reg.register(MagicMock(), cfg1, "a1")
        reg.register(MagicMock(), cfg2, "a2")
        agents = reg.get_agents_for_tool("search")
        assert "a1" in agents
        assert "a2" in agents

    def test_get_agents_for_tool_none(self):
        from app.engine.agents.registry import AgentRegistry
        reg = AgentRegistry()
        assert reg.get_agents_for_tool("nonexistent") == []


# ============================================================================
# AgentRegistry — tracing
# ============================================================================


class TestRegistryTracing:
    """Test registry tracing integration."""

    def test_tracer_property(self):
        from app.engine.agents.registry import AgentRegistry, AgentTracer
        reg = AgentRegistry()
        assert isinstance(reg.tracer, AgentTracer)

    def test_start_request_trace(self):
        from app.engine.agents.registry import AgentRegistry
        reg = AgentRegistry()
        tid = reg.start_request_trace()
        assert tid is not None

    def test_end_request_trace(self):
        from app.engine.agents.registry import AgentRegistry
        reg = AgentRegistry()
        tid = reg.start_request_trace()
        summary = reg.end_request_trace(tid)
        assert summary == {}  # No spans yet


# ============================================================================
# AgentRegistry — utilities
# ============================================================================


class TestRegistryUtilities:
    """Test utility methods."""

    def test_count(self):
        from app.engine.agents.registry import AgentRegistry
        reg = AgentRegistry()
        assert reg.count() == 0
        reg.register(MagicMock(), agent_id="a1")
        assert reg.count() == 1

    def test_is_registered(self):
        from app.engine.agents.registry import AgentRegistry
        reg = AgentRegistry()
        reg.register(MagicMock(), agent_id="a1")
        assert reg.is_registered("a1") is True
        assert reg.is_registered("a2") is False

    def test_summary(self):
        from app.engine.agents.registry import AgentRegistry
        reg = AgentRegistry()
        cfg = AgentConfig(id="rag", name="RAG", role="R", goal="G",
                          category=AgentCategory.RETRIEVAL, tools=["search"])
        reg.register(MagicMock(), cfg, "rag")
        summary = reg.summary()
        assert summary["total_registered"] == 1
        assert "retrieval" in summary["categories"]
        assert len(summary["agents"]) == 1
        assert summary["agents"][0]["id"] == "rag"

    def test_list_all(self):
        from app.engine.agents.registry import AgentRegistry
        reg = AgentRegistry()
        reg.register(MagicMock(), agent_id="a1")
        reg.register(MagicMock(), agent_id="a2")
        ids = reg.list_all()
        assert "a1" in ids
        assert "a2" in ids


# ============================================================================
# Singleton
# ============================================================================


class TestSingleton:
    """Test singleton pattern."""

    def test_get_agent_registry(self):
        import app.engine.agents.registry as mod
        mod._registry = None
        r1 = mod.get_agent_registry()
        r2 = mod.get_agent_registry()
        assert r1 is r2
        mod._registry = None  # Cleanup

    def test_register_agent_convenience(self):
        import app.engine.agents.registry as mod
        mod._registry = None
        agent = MagicMock()
        mod.register_agent(agent, agent_id="test_conv")
        reg = mod.get_agent_registry()
        assert reg.is_registered("test_conv")
        mod._registry = None  # Cleanup
