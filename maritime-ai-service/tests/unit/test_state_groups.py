"""Unit tests for AgentState typed overlays (P2)."""

import typing

import pytest

from app.engine.multi_agent.state import (
    AgentOutput,
    AgentState,
    DomainConfig,
    HostContext,
    InputContext,
    RoutingState,
    RuntimeMeta,
    SubagentState,
    ThinkingState,
    get_agent_output,
    get_domain_config,
    get_host_context,
    get_input_context,
    get_routing_state,
    get_runtime_meta,
    get_subagent_state,
    get_thinking_state,
    merge_into_state,
)


def _full_state() -> dict:
    """Build a state dict with at least one field from every group."""
    return {
        # InputContext
        "query": "COLREG là gì?",
        "user_id": "user-1",
        "session_id": "sess-1",
        "context": {"conversation_summary": "Discussion về COLREG"},
        "user_context": {},
        "learning_context": {},
        "messages": [],
        "images": [],
        "conversation_phase": "engaged",
        # RoutingState
        "current_agent": "rag_agent",
        "next_agent": "rag_agent",
        "routing_metadata": {"intent": "lookup", "confidence": 0.9},
        "guardian_passed": True,
        "domain_notice": None,
        # AgentOutput
        "agent_outputs": {},
        "rag_output": "COLREG là Công ước...",
        "tutor_output": "",
        "memory_output": "",
        "final_response": "COLREG là Công ước quốc tế...",
        "sources": [{"title": "COLREG Guide", "url": "https://example.com"}],
        "tools_used": [{"name": "hybrid_search", "duration_ms": 120}],
        "tool_call_events": [],
        "grader_score": 0.85,
        "grader_feedback": "Good",
        "evidence_images": [],
        "_answer_streamed_via_bus": False,
        # ThinkingState
        "reasoning_trace": None,
        "thinking_content": "User hỏi về COLREG...",
        "thinking_lifecycle": None,
        "thinking": "Hmm, COLREG...",
        "_public_thinking_fragments": [],
        "_thinking_trajectory": None,
        "thinking_effort": "high",
        # DomainConfig
        "domain_id": "maritime",
        "domain_config": {"domain_name": "Hàng hải"},
        "skill_context": None,
        "capability_context": None,
        "provider": "google",
        "model": "gemini-3.1-flash-lite-preview",
        "organization_id": None,
        # RuntimeMeta
        "iteration": 0,
        "max_iterations": 3,
        "error": None,
        "_trace_id": "trace-123",
        "_event_bus_id": "bus-456",
        "_execution_provider": "google",
        "_execution_model": "gemini-3.1-flash-lite-preview",
        "_llm_failover_events": [],
        "_runner_error": None,
        "_runner_error_node": None,
        "_reroute_count": 0,
        "_aggregator_action": None,
        "_aggregator_reasoning": None,
        "_parallel_targets": [],
        # HostContext
        "host_context": {"page_type": "quiz"},
        "host_capabilities": {"tools": []},
        "host_action_feedback": None,
        "host_context_prompt": "Bạn đang ở trang quiz",
        "host_capabilities_prompt": None,
        "host_session": None,
        "host_session_prompt": None,
        "operator_session": None,
        "operator_context_prompt": None,
        "widget_feedback_prompt": None,
        "living_context_prompt": None,
        "memory_block_context": None,
        "reasoning_policy": None,
        # SubagentState
        "subagent_reports": [],
    }


# =========================================================================
# Group TypedDicts — type hints exist
# =========================================================================


class TestGroupTypeHints:
    """Each group TypedDict has the expected fields."""

    def test_input_context_fields(self):
        hints = typing.get_type_hints(InputContext)
        assert "query" in hints
        assert "user_id" in hints
        assert "session_id" in hints
        assert "context" in hints
        assert "conversation_phase" in hints

    def test_routing_state_fields(self):
        hints = typing.get_type_hints(RoutingState)
        assert "current_agent" in hints
        assert "next_agent" in hints
        assert "routing_metadata" in hints
        assert "guardian_passed" in hints

    def test_agent_output_fields(self):
        hints = typing.get_type_hints(AgentOutput)
        assert "rag_output" in hints
        assert "tutor_output" in hints
        assert "final_response" in hints
        assert "sources" in hints
        assert "tools_used" in hints

    def test_runtime_meta_fields(self):
        hints = typing.get_type_hints(RuntimeMeta)
        assert "_trace_id" in hints
        assert "_event_bus_id" in hints
        assert "_execution_provider" in hints
        assert "_runner_error" in hints

    def test_thinking_state_fields(self):
        hints = typing.get_type_hints(ThinkingState)
        assert "thinking" in hints
        assert "thinking_content" in hints
        assert "thinking_effort" in hints
        assert "reasoning_trace" in hints

    def test_domain_config_fields(self):
        hints = typing.get_type_hints(DomainConfig)
        assert "domain_id" in hints
        assert "provider" in hints
        assert "model" in hints
        assert "organization_id" in hints

    def test_host_context_fields(self):
        hints = typing.get_type_hints(HostContext)
        assert "host_context" in hints
        assert "host_context_prompt" in hints
        assert "operator_context_prompt" in hints

    def test_subagent_state_fields(self):
        hints = typing.get_type_hints(SubagentState)
        assert "subagent_reports" in hints


# =========================================================================
# Accessor functions — extract groups correctly
# =========================================================================


class TestAccessors:
    def test_get_input_context(self):
        state = _full_state()
        ic = get_input_context(state)
        assert ic["query"] == "COLREG là gì?"
        assert ic["user_id"] == "user-1"
        assert ic["conversation_phase"] == "engaged"
        # Should NOT contain routing fields
        assert "current_agent" not in ic
        assert "final_response" not in ic

    def test_get_routing_state(self):
        state = _full_state()
        rs = get_routing_state(state)
        assert rs["current_agent"] == "rag_agent"
        assert rs["guardian_passed"] is True
        assert "query" not in rs

    def test_get_agent_output(self):
        state = _full_state()
        ao = get_agent_output(state)
        assert ao["final_response"].startswith("COLREG")
        assert len(ao["sources"]) == 1
        assert ao["grader_score"] == pytest.approx(0.85)
        assert "query" not in ao
        assert "_trace_id" not in ao

    def test_get_runtime_meta(self):
        state = _full_state()
        rm = get_runtime_meta(state)
        assert rm["_trace_id"] == "trace-123"
        assert rm["_event_bus_id"] == "bus-456"
        assert "query" not in rm
        assert "final_response" not in rm

    def test_get_thinking_state(self):
        state = _full_state()
        ts = get_thinking_state(state)
        assert ts["thinking_effort"] == "high"
        assert ts["thinking_content"] is not None
        assert "query" not in ts

    def test_get_domain_config(self):
        state = _full_state()
        dc = get_domain_config(state)
        assert dc["domain_id"] == "maritime"
        assert dc["provider"] == "google"
        assert "final_response" not in dc

    def test_get_host_context(self):
        state = _full_state()
        hc = get_host_context(state)
        assert hc["host_context"]["page_type"] == "quiz"
        assert hc["host_context_prompt"] == "Bạn đang ở trang quiz"
        assert "query" not in hc

    def test_get_subagent_state(self):
        state = _full_state()
        ss = get_subagent_state(state)
        assert "subagent_reports" in ss
        assert "query" not in ss

    def test_empty_state_returns_empty_groups(self):
        state: AgentState = {}
        assert get_input_context(state) == {}
        assert get_routing_state(state) == {}
        assert get_agent_output(state) == {}

    def test_groups_cover_all_state_fields(self):
        """Every field in _full_state() should be captured by at least one group."""
        state = _full_state()
        all_group_keys = (
            get_input_context(state).keys()
            | get_routing_state(state).keys()
            | get_agent_output(state).keys()
            | get_runtime_meta(state).keys()
            | get_thinking_state(state).keys()
            | get_domain_config(state).keys()
            | get_host_context(state).keys()
            | get_subagent_state(state).keys()
        )
        for key in state:
            assert key in all_group_keys, f"Field {key!r} not covered by any group"


# =========================================================================
# Merge helper
# =========================================================================


class TestMergeIntoState:
    def test_merge_adds_fields(self):
        state: AgentState = {"query": "test"}
        merge_into_state(state, routing=RoutingState(current_agent="rag_agent"))
        assert state["current_agent"] == "rag_agent"
        assert state["query"] == "test"

    def test_merge_overwrites(self):
        state: AgentState = {"current_agent": "direct"}
        merge_into_state(state, routing=RoutingState(current_agent="rag_agent"))
        assert state["current_agent"] == "rag_agent"


# =========================================================================
# AgentState remains flat dict (backward compat)
# =========================================================================


class TestBackwardCompat:
    def test_state_is_plain_dict(self):
        state: AgentState = {"query": "test", "current_agent": "rag"}
        assert isinstance(state, dict)
        assert state.get("query") == "test"
        assert state["current_agent"] == "rag"
        assert state.get("nonexistent") is None

    def test_state_get_with_default(self):
        state: AgentState = {}
        assert state.get("grader_score", 0.0) == 0.0
        assert state.get("query", "") == ""

    def test_state_set_and_read(self):
        state: AgentState = {}
        state["final_response"] = "Done"
        state["sources"] = [{"title": "A"}]
        assert state["final_response"] == "Done"
        assert len(state["sources"]) == 1
