from types import SimpleNamespace
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.engine.multi_agent.code_studio_fast_paths import CodeStudioFastPathResult
from app.engine.multi_agent.graph import (
    _build_ambiguous_simulation_clarifier,
    _ground_simulation_query_from_visual_context,
    _infer_pendulum_fast_path_title,
    _looks_like_ambiguous_simulation_request,
    _should_use_pendulum_code_studio_fast_path,
    code_studio_node,
)


class TestPendulumCodeStudioFastPath:
    def test_uses_fast_path_for_clear_pendulum_build_request(self):
        state = {"context": {"code_studio_context": {}}}

        assert _should_use_pendulum_code_studio_fast_path(
            "Build a mini pendulum physics app in chat with drag interaction. Use Code Studio inline.",
            state,
        ) is True

    def test_uses_fast_path_for_pendulum_follow_up_patch_from_active_session(self):
        state = {
            "context": {
                "code_studio_context": {
                    "active_session": {
                        "session_id": "vs-1",
                        "title": "Mini Pendulum Physics App",
                    }
                }
            }
        }

        assert _should_use_pendulum_code_studio_fast_path(
            "Keep the current app and add gravity and damping sliders.",
            state,
        ) is True

    def test_skips_fast_path_when_user_is_explicitly_requesting_code_view(self):
        state = {
            "context": {
                "code_studio_context": {
                    "requested_view": "code",
                    "active_session": {
                        "session_id": "vs-1",
                        "title": "Mini Pendulum Physics App",
                    },
                }
            }
        }

        assert _should_use_pendulum_code_studio_fast_path(
            "Show me the code you are generating.",
            state,
        ) is False

    def test_prefers_active_session_title_for_fast_path_title(self):
        state = {
            "context": {
                "code_studio_context": {
                    "active_session": {
                        "session_id": "vs-1",
                        "title": "Mo phong con lac",
                    }
                }
            }
        }

        assert _infer_pendulum_fast_path_title("Add damping slider", state) == "Mo phong con lac"


class TestSimulationClarifier:
    def test_detects_bare_simulation_followup(self):
        state = {
            "context": {
                "visual_context": {
                    "last_visual_title": "Kimi linear attention",
                }
            }
        }

        assert _looks_like_ambiguous_simulation_request(
            "Wiii tao mo phong cho minh duoc chu ?",
            state,
        ) is True

    def test_clarifier_mentions_last_visual_title(self):
        state = {
            "context": {
                "visual_context": {
                    "last_visual_title": "Kimi linear attention",
                }
            }
        }

        response = _build_ambiguous_simulation_clarifier(state)
        assert "Kimi linear attention" in response
        assert "canvas" in response

    def test_grounded_query_uses_active_visual_title(self):
        state = {
            "context": {
                "visual_context": {
                    "last_visual_title": "Kimi linear attention",
                }
            }
        }

        grounded = _ground_simulation_query_from_visual_context(
            "Wiii tao mo phong cho minh duoc chu ?",
            state,
        )

        assert "Kimi linear attention" in grounded
        assert "canvas" in grounded
        assert "follow-up" in grounded

    @pytest.mark.asyncio
    async def test_code_studio_node_grounds_ambiguous_simulation_followup_from_visual_context(self):
        state = {
            "query": "Wiii tao mo phong cho minh duoc chu ?",
            "context": {
                "visual_context": {
                    "last_visual_title": "Kimi linear attention",
                }
            },
            "domain_id": "maritime",
            "domain_config": {},
        }
        fake_tracer = MagicMock()
        fake_llm = MagicMock()
        captured = {}

        async def fake_execute(*_args, **kwargs):
            captured["query"] = kwargs.get("query")
            return SimpleNamespace(content=""), [], []

        with patch("app.engine.multi_agent.graph._get_or_create_tracer", return_value=fake_tracer), \
             patch("app.engine.multi_agent.graph.settings") as mock_settings, \
             patch("app.engine.multi_agent.graph._build_code_studio_reasoning_summary", new=AsyncMock(return_value="grounded")) as _mock_summary, \
             patch("app.engine.multi_agent.graph._execute_code_studio_tool_rounds", new=AsyncMock(side_effect=fake_execute)), \
             patch("app.engine.multi_agent.graph._bind_direct_tools", return_value=(fake_llm, fake_llm, "any")), \
             patch("app.engine.multi_agent.agent_config.AgentConfigRegistry.get_llm", return_value=fake_llm) as mock_get_llm:
            mock_settings.default_domain = "maritime"
            mock_settings.enable_natural_conversation = False

            result = await code_studio_node(state)

        mock_get_llm.assert_called_once()
        assert "Kimi linear attention" in captured["query"]
        assert result["final_response"] == ""
        assert result["current_agent"] == "code_studio_agent"

    @pytest.mark.asyncio
    async def test_code_studio_node_still_clarifies_when_no_visual_context_exists(self):
        state = {
            "query": "Wiii tao mo phong cho minh duoc chu ?",
            "context": {},
            "domain_id": "maritime",
            "domain_config": {},
        }
        fake_tracer = MagicMock()

        with patch("app.engine.multi_agent.graph._get_or_create_tracer", return_value=fake_tracer), \
             patch("app.engine.multi_agent.graph.settings") as mock_settings, \
             patch("app.engine.multi_agent.graph._build_code_studio_reasoning_summary", new=AsyncMock(return_value="clarify")) as _mock_summary, \
             patch("app.engine.multi_agent.agent_config.AgentConfigRegistry.get_llm") as mock_get_llm:
            mock_settings.default_domain = "maritime"
            mock_settings.enable_natural_conversation = False

            result = await code_studio_node(state)

        mock_get_llm.assert_not_called()
        assert "chưa nói rõ hiện tượng nào" in result["final_response"]
        assert result["current_agent"] == "code_studio_agent"


    @pytest.mark.asyncio
    async def test_code_studio_node_runs_recipe_fast_path_before_provider_selection(self):
        from app.core.exceptions import ProviderUnavailableError

        state = {
            "query": "mo phong COLREG rule 15",
            "context": {},
            "domain_id": "maritime",
            "domain_config": {},
        }
        fake_tracer = MagicMock()
        fast_path_result = CodeStudioFastPathResult(
            response="opened deterministic visual preview",
            thinking_content="deterministic code studio recipe",
            tool_call_events=[],
            tools_used=[{"name": "tool_create_visual_code"}],
            fast_path="fast_colreg15",
        )

        with patch("app.engine.multi_agent.graph._get_or_create_tracer", return_value=fake_tracer), \
             patch("app.engine.multi_agent.graph.settings") as mock_settings, \
             patch("app.engine.multi_agent.graph._looks_like_ambiguous_simulation_request", return_value=False), \
             patch(
                 "app.engine.multi_agent.graph._collect_code_studio_tools",
                 return_value=([SimpleNamespace(name="tool_create_visual_code")], True),
             ), \
             patch(
                 "app.engine.multi_agent.graph._execute_code_studio_fast_path",
                 new=AsyncMock(return_value=fast_path_result),
             ) as mock_fast_path, \
             patch(
                 "app.engine.multi_agent.agent_config.AgentConfigRegistry.get_llm",
                 side_effect=ProviderUnavailableError(
                     provider="test",
                     reason_code="not_configured",
                     message="provider unavailable",
                 ),
             ) as mock_get_llm:
            mock_settings.default_domain = "maritime"
            mock_settings.enable_natural_conversation = False

            result = await code_studio_node(state)

        mock_fast_path.assert_awaited_once()
        mock_get_llm.assert_not_called()
        assert result["final_response"] == "opened deterministic visual preview"
        assert result["tools_used"] == [{"name": "tool_create_visual_code"}]
        assert result["current_agent"] == "code_studio_agent"
