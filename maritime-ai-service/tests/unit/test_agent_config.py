"""
Tests for AgentConfigRegistry — Sprint 69: Per-Agent Provider Config.

Tests cover:
- AgentNodeConfig defaults and custom values
- AgentConfigRegistry initialization, get_config, get_llm, reset
- JSON overrides parsing
- All default node configs present
"""

import json
import sys
import types
import pytest
from unittest.mock import patch, MagicMock

# Break circular import: multi_agent.__init__ → graph → agents → tutor_node
# → services.__init__ → chat_service → multi_agent.graph
_cs_key = "app.services.chat_service"
_svc_key = "app.services"
_had_cs = _cs_key in sys.modules
_had_svc = _svc_key in sys.modules
_orig_cs = sys.modules.get(_cs_key)
if not _had_cs:
    _mock_cs = types.ModuleType(_cs_key)
    _mock_cs.ChatService = type("ChatService", (), {})
    _mock_cs.get_chat_service = lambda: None
    sys.modules[_cs_key] = _mock_cs

from app.engine.multi_agent.agent_config import (
    AgentNodeConfig,
    AgentConfigRegistry,
    _DEFAULT_CONFIGS,
)

if not _had_cs:
    sys.modules.pop(_cs_key, None)
    if not _had_svc:
        sys.modules.pop(_svc_key, None)
elif _orig_cs is not None:
    sys.modules[_cs_key] = _orig_cs


# =============================================================================
# TestAgentNodeConfig
# =============================================================================


class TestAgentNodeConfig:
    """Tests for AgentNodeConfig dataclass."""

    def test_defaults(self):
        config = AgentNodeConfig("test_node")
        assert config.node_id == "test_node"
        assert config.provider == "google"
        assert config.model is None
        assert config.tier == "moderate"
        assert config.temperature == 0.5
        assert config.max_agentic_steps == 5
        assert config.enable_thinking is True
        assert config.enable_agentic_loop is False

    def test_custom_provider(self):
        config = AgentNodeConfig("test", provider="openai")
        assert config.provider == "openai"

    def test_custom_tier(self):
        config = AgentNodeConfig("test", tier="deep")
        assert config.tier == "deep"

    def test_enable_agentic_loop(self):
        config = AgentNodeConfig("test", enable_agentic_loop=True)
        assert config.enable_agentic_loop is True

    def test_custom_temperature(self):
        config = AgentNodeConfig("test", temperature=0.0)
        assert config.temperature == 0.0

    def test_custom_model(self):
        config = AgentNodeConfig("test", model="gemini-3.1-flash-lite-preview")
        assert config.model == "gemini-3.1-flash-lite-preview"

    def test_custom_max_steps(self):
        config = AgentNodeConfig("test", max_agentic_steps=10)
        assert config.max_agentic_steps == 10


# =============================================================================
# TestAgentConfigRegistry
# =============================================================================


class TestAgentConfigRegistry:
    """Tests for AgentConfigRegistry singleton."""

    def setup_method(self):
        AgentConfigRegistry.reset()

    def teardown_method(self):
        AgentConfigRegistry.reset()

    def test_initialize_loads_defaults(self):
        AgentConfigRegistry.initialize()
        assert AgentConfigRegistry._initialized is True
        assert len(AgentConfigRegistry._configs) == len(_DEFAULT_CONFIGS)

    def test_get_config_returns_matching(self):
        AgentConfigRegistry.initialize()
        config = AgentConfigRegistry.get_config("tutor_agent")
        assert config.node_id == "tutor_agent"
        assert config.tier == "moderate"

    def test_get_unknown_fallback(self):
        AgentConfigRegistry.initialize()
        config = AgentConfigRegistry.get_config("unknown_node")
        assert config.node_id == "unknown_node"
        assert config.tier == "moderate"  # default

    def test_get_llm_delegates_to_pool(self):
        AgentConfigRegistry.initialize()
        mock_llm = MagicMock()

        with patch(
            "app.engine.llm_pool.get_llm_moderate",
            return_value=mock_llm,
        ) as mock_get:
            result = AgentConfigRegistry.get_llm("tutor_agent")
            mock_get.assert_called_once()
            assert result == mock_llm

    def test_get_llm_light_for_supervisor(self):
        AgentConfigRegistry.initialize()
        mock_llm = MagicMock()

        with patch(
            "app.engine.llm_pool.get_llm_light",
            return_value=mock_llm,
        ) as mock_get:
            result = AgentConfigRegistry.get_llm("supervisor")
            mock_get.assert_called_once()
            assert result == mock_llm

    def test_get_llm_moderate_for_rag(self):
        AgentConfigRegistry.initialize()
        mock_llm = MagicMock()

        with patch(
            "app.engine.llm_pool.get_llm_moderate",
            return_value=mock_llm,
        ) as mock_get:
            result = AgentConfigRegistry.get_llm("rag_agent")
            mock_get.assert_called_once()
            assert result == mock_llm

    def test_reset_clears_state(self):
        AgentConfigRegistry.initialize()
        assert AgentConfigRegistry._initialized is True
        AgentConfigRegistry.reset()
        assert AgentConfigRegistry._initialized is False
        assert len(AgentConfigRegistry._configs) == 0

    def test_override_json_changes_tier(self):
        overrides = json.dumps({"tutor_agent": {"tier": "deep"}})
        AgentConfigRegistry.initialize(overrides)
        config = AgentConfigRegistry.get_config("tutor_agent")
        assert config.tier == "deep"

    def test_override_json_changes_provider(self):
        overrides = json.dumps({"supervisor": {"provider": "openai"}})
        AgentConfigRegistry.initialize(overrides)
        config = AgentConfigRegistry.get_config("supervisor")
        assert config.provider == "openai"

    def test_invalid_json_fallback(self):
        AgentConfigRegistry.initialize("not valid json {{{")
        # Should still initialize with defaults
        assert AgentConfigRegistry._initialized is True
        config = AgentConfigRegistry.get_config("tutor_agent")
        assert config.tier == "moderate"

    def test_all_defaults_present(self):
        AgentConfigRegistry.initialize()
        expected = {
            "tutor_agent", "rag_agent", "supervisor",
            "guardian", "grader", "memory", "direct", "synthesizer",
            "code_studio_agent",
        }
        assert set(AgentConfigRegistry._configs.keys()) == expected

    def test_tutor_moderate_tier(self):
        AgentConfigRegistry.initialize()
        config = AgentConfigRegistry.get_config("tutor_agent")
        assert config.tier == "moderate"
        assert config.enable_agentic_loop is True

    def test_supervisor_light_tier(self):
        AgentConfigRegistry.initialize()
        config = AgentConfigRegistry.get_config("supervisor")
        assert config.tier == "light"
        assert config.temperature == 0.3

    def test_guardian_temp_zero(self):
        AgentConfigRegistry.initialize()
        config = AgentConfigRegistry.get_config("guardian")
        assert config.temperature == 0.0
        assert config.tier == "light"

    def test_tutor_agentic_enabled(self):
        AgentConfigRegistry.initialize()
        config = AgentConfigRegistry.get_config("tutor_agent")
        assert config.enable_agentic_loop is True

    def test_effort_override(self):
        AgentConfigRegistry.initialize()
        mock_llm = MagicMock()

        with patch(
            "app.engine.llm_pool.get_llm_for_effort",
            return_value=mock_llm,
        ) as mock_effort:
            result = AgentConfigRegistry.get_llm("tutor_agent", effort_override="high")
            mock_effort.assert_called_once()
            assert result == mock_llm

    def test_effort_override_with_correct_default_tier(self):
        AgentConfigRegistry.initialize()
        mock_llm = MagicMock()

        with patch(
            "app.engine.llm_pool.get_llm_for_effort",
            return_value=mock_llm,
        ) as mock_effort:
            AgentConfigRegistry.get_llm("direct", effort_override="medium")
            # Direct node has tier="light"
            call_args = mock_effort.call_args
            assert call_args[0][0] == "medium"
            # default_tier should be ThinkingTier.LIGHT
            from app.engine.llm_factory import ThinkingTier
            assert call_args[1]["default_tier"] == ThinkingTier.LIGHT

    def test_multiple_resets(self):
        AgentConfigRegistry.initialize()
        AgentConfigRegistry.reset()
        AgentConfigRegistry.reset()  # Should not error
        assert AgentConfigRegistry._initialized is False

    def test_auto_initialize_on_get_config(self):
        # Without explicit initialize, get_config should auto-initialize
        config = AgentConfigRegistry.get_config("tutor_agent")
        assert config.node_id == "tutor_agent"
        assert AgentConfigRegistry._initialized is True

    def test_override_adds_new_node(self):
        overrides = json.dumps({"custom_node": {"tier": "deep", "provider": "ollama"}})
        AgentConfigRegistry.initialize(overrides)
        config = AgentConfigRegistry.get_config("custom_node")
        assert config.tier == "deep"
        assert config.provider == "ollama"

    def test_override_ignores_node_id_change(self):
        overrides = json.dumps({"tutor_agent": {"node_id": "hacked"}})
        AgentConfigRegistry.initialize(overrides)
        config = AgentConfigRegistry.get_config("tutor_agent")
        assert config.node_id == "tutor_agent"  # Not changed

    def test_override_non_dict_values_ignored(self):
        overrides = json.dumps({"tutor_agent": "not_a_dict"})
        AgentConfigRegistry.initialize(overrides)
        config = AgentConfigRegistry.get_config("tutor_agent")
        assert config.tier == "moderate"  # Default preserved

    def test_empty_override_string(self):
        AgentConfigRegistry.initialize("")
        assert AgentConfigRegistry._initialized is True

    def test_none_override_string(self):
        AgentConfigRegistry.initialize(None)
        assert AgentConfigRegistry._initialized is True
