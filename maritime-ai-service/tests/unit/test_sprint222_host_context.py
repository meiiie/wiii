"""Sprint 222: Universal Context Engine — host_context_prompt in AgentState."""
import pytest


def test_agent_state_has_host_context_prompt_field():
    """AgentState TypedDict must include host_context_prompt."""
    from app.engine.multi_agent.state import AgentState
    annotations = AgentState.__annotations__
    assert "host_context_prompt" in annotations, (
        "AgentState missing host_context_prompt field"
    )


def test_agent_state_has_host_context_field():
    """AgentState must include host_context (raw dict from request)."""
    from app.engine.multi_agent.state import AgentState
    annotations = AgentState.__annotations__
    assert "host_context" in annotations, (
        "AgentState missing host_context field"
    )
