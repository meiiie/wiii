from types import SimpleNamespace
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.engine.multi_agent.graph import (
    _ainvoke_with_fallback,
    direct_response_node,
    code_studio_node,
)


class TestGraphFailoverDelegation:
    @pytest.mark.asyncio
    async def test_fallback_rebind_preserves_provider_specific_tool_choice(self):
        tools = [
            SimpleNamespace(name="tool_web_search"),
            SimpleNamespace(name="tool_get_current_datetime"),
        ]

        class FakeFallbackLLM:
            def __init__(self):
                self._wiii_provider_name = "openai"
                self.bind_calls: list[str | None] = []

            def bind_tools(self, _tools, tool_choice=None):
                self.bind_calls.append(tool_choice)
                return {"tool_choice": tool_choice}

        fallback_llm = FakeFallbackLLM()

        async def _fake_failover(_llm, _messages, **kwargs):
            prepared = kwargs["on_fallback"](fallback_llm)
            return prepared

        with patch(
            "app.engine.llm_pool.ainvoke_with_failover",
            side_effect=_fake_failover,
        ):
            result = await _ainvoke_with_fallback(
                MagicMock(),
                ["hello"],
                tools=tools,
                tool_choice="any",
                provider="google",
            )

        assert fallback_llm.bind_calls == ["required"]
        assert result == {"tool_choice": "required"}

    @pytest.mark.asyncio
    async def test_timeout_profile_is_forwarded_to_failover_helper(self):
        captured: dict[str, object] = {}

        async def _fake_failover(_llm, _messages, **kwargs):
            captured.update(kwargs)
            return {"ok": True}

        with patch(
            "app.engine.llm_pool.ainvoke_with_failover",
            side_effect=_fake_failover,
        ):
            result = await _ainvoke_with_fallback(
                MagicMock(),
                ["hello"],
                timeout_profile="background",
            )

        assert captured["timeout_profile"] == "background"
        assert result == {"ok": True}


class TestProviderFlowIntegrity:
    @pytest.mark.asyncio
    async def test_direct_visual_auto_applies_visual_thinking_floor(self):
        fake_tracer = MagicMock()
        fake_llm = MagicMock()
        fake_llm._wiii_provider_name = "zhipu"
        fake_llm._wiii_model_name = "glm-4.5-air"
        state = {
            "query": "Visual cho mình xem thống kê dữ liệu hiện tại giá dầu mấy ngày gần đây",
            "context": {},
            "domain_config": {},
            "provider": "auto",
            "routing_metadata": {"method": "structured", "intent": "web_search"},
        }

        mock_execute = AsyncMock(
            return_value=(SimpleNamespace(content="Đã dựng chart", tool_calls=[]), [], [])
        )

        with patch(
            "app.engine.multi_agent.graph._get_or_create_tracer",
            return_value=fake_tracer,
        ), patch(
            "app.engine.multi_agent.agent_config.AgentConfigRegistry.get_native_llm",
            return_value=fake_llm,
        ) as mock_get_native_llm, patch(
            "app.engine.multi_agent.agent_config.AgentConfigRegistry.get_llm",
            return_value=fake_llm,
        ) as mock_get_llm, patch(
            "app.engine.multi_agent.graph._collect_direct_tools",
            return_value=([SimpleNamespace(name="tool_generate_visual")], False),
        ), patch(
            "app.engine.multi_agent.graph._bind_direct_tools",
            return_value=(fake_llm, fake_llm, None),
        ), patch(
            "app.engine.multi_agent.graph._build_direct_system_messages",
            return_value=[],
        ), patch(
            "app.engine.multi_agent.graph._execute_direct_tool_rounds",
            new=mock_execute,
        ), patch(
            "app.engine.multi_agent.graph._extract_direct_response",
            return_value=("Đã dựng chart", "", []),
        ), patch(
            "app.engine.multi_agent.graph._build_direct_reasoning_summary",
            new=AsyncMock(return_value="Mình đang giữ phần nhìn và phần nghĩa đi cùng nhau."),
        ):
            result = await direct_response_node(state)

        assert result["final_response"] == "Đã dựng chart"
        assert mock_get_native_llm.call_args.kwargs["effort_override"] == "high"
        mock_get_llm.assert_not_called()
        assert mock_execute.call_args.kwargs["provider"] is None
        assert result["provider"] == "auto"
        assert result["model"] == "glm-4.5-air"

    @pytest.mark.asyncio
    async def test_code_studio_respects_explicit_provider_override(self):
        fake_tracer = MagicMock()
        fake_llm = MagicMock()
        fake_llm._wiii_provider_name = "zhipu"
        fake_llm._wiii_model_name = "glm-5"
        state = {
            "query": "Tạo mô phỏng hảo hán uống rượu ngắm trăng",
            "context": {},
            "domain_config": {},
            "provider": "zhipu",
            "routing_metadata": {"method": "structured", "intent": "code_execution"},
        }

        mock_execute = AsyncMock(
            return_value=(SimpleNamespace(content="Đã mở Code Studio", tool_calls=[]), [], [])
        )

        with patch(
            "app.engine.multi_agent.graph._get_or_create_tracer",
            return_value=fake_tracer,
        ), patch(
            "app.engine.multi_agent.agent_config.AgentConfigRegistry.get_llm",
            return_value=fake_llm,
        ) as mock_get_llm, patch(
            "app.engine.multi_agent.graph._looks_like_ambiguous_simulation_request",
            return_value=False,
        ), patch(
            "app.engine.multi_agent.graph._collect_code_studio_tools",
            return_value=([SimpleNamespace(name="tool_create_visual_code")], True),
        ), patch(
            "app.engine.multi_agent.graph._bind_direct_tools",
            return_value=(fake_llm, fake_llm, "tool_create_visual_code"),
        ), patch(
            "app.engine.multi_agent.graph._build_direct_system_messages",
            return_value=[],
        ), patch(
            "app.engine.multi_agent.graph._execute_code_studio_fast_path",
            new=AsyncMock(return_value=None),
        ), patch(
            "app.engine.multi_agent.graph._execute_code_studio_tool_rounds",
            new=mock_execute,
        ), patch(
            "app.engine.multi_agent.graph._extract_direct_response",
            return_value=("Đã mở Code Studio", "", []),
        ):
            result = await code_studio_node(state)

        assert result["final_response"] == "Đã mở Code Studio"
        assert mock_get_llm.call_args.kwargs["provider_override"] == "zhipu"
        assert mock_execute.call_args.kwargs["provider"] == "zhipu"
