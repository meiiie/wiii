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


# ── Sprint 222 Task 4: Feature gate tests ──────────────────────────


def test_config_has_enable_host_context_flag():
    """Feature gate must exist and default to False."""
    from app.core.config import Settings
    default = Settings.model_fields["enable_host_context"].default
    assert default is False


def test_config_has_enable_host_actions_flag():
    """Action gate must exist and default to False."""
    from app.core.config import Settings
    default = Settings.model_fields["enable_host_actions"].default
    assert default is False


def test_config_has_enable_host_skills_flag():
    """Skills gate must exist and default to False."""
    from app.core.config import Settings
    default = Settings.model_fields["enable_host_skills"].default
    assert default is False
