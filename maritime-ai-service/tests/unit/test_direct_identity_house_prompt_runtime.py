from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.engine.multi_agent.graph import direct_response_node


@pytest.mark.asyncio
async def test_direct_response_node_uses_house_voice_prompt_for_identity_turn():
    fake_tracer = MagicMock()
    fake_llm = MagicMock()
    state = {
        "query": "Wiii là ai?",
        "context": {},
        "domain_config": {},
        "provider": "zhipu",
        "routing_metadata": {"method": "structured", "intent": "social"},
    }

    with patch(
        "app.engine.multi_agent.graph._get_or_create_tracer",
        return_value=fake_tracer,
    ), patch(
        "app.engine.multi_agent.agent_config.AgentConfigRegistry.get_llm",
        return_value=fake_llm,
    ) as mock_get_llm, patch(
        "app.engine.multi_agent.graph._collect_direct_tools",
        return_value=([], False),
    ) as mock_collect_tools, patch(
        "app.engine.multi_agent.graph._bind_direct_tools",
        return_value=(fake_llm, fake_llm, None),
    ), patch(
        "app.engine.multi_agent.graph._build_direct_system_messages",
        return_value=[],
    ) as mock_build_messages, patch(
        "app.engine.multi_agent.graph._execute_direct_tool_rounds",
        new=AsyncMock(return_value=(SimpleNamespace(content="Minh la Wiii.", tool_calls=[]), [], [])),
    ), patch(
        "app.engine.multi_agent.graph._extract_direct_response",
        return_value=("Minh la Wiii.", "", []),
    ), patch(
        "app.engine.multi_agent.graph._build_direct_reasoning_summary",
        new=AsyncMock(return_value="Cau nay cham vao chinh Wiii nen minh muon dap that gan."),
    ):
        result = await direct_response_node(state)

    assert result["final_response"] == "Minh la Wiii."
    assert mock_get_llm.call_args.kwargs["provider_override"] == "zhipu"
    mock_collect_tools.assert_not_called()
    assert mock_build_messages.call_args.kwargs["role_name"] == "direct_chatter_agent"
    assert mock_build_messages.call_args.kwargs["history_limit"] == 10
    assert mock_build_messages.call_args.kwargs["tools_context_override"] is None
    fake_tracer.end_step.assert_called_once()


@pytest.mark.asyncio
async def test_direct_response_node_preserves_runtime_tier_after_llm_bind():
    fake_tracer = MagicMock()

    class _FakeBoundLLM:
        pass

    class _FakeLLM:
        _wiii_provider_name = "google"
        _wiii_model_name = "gemini-3.1-pro-preview"
        _wiii_tier_key = "deep"

        def bind(self, **_kwargs):
            return _FakeBoundLLM()

    state = {
        "query": "Wiii duoc sinh ra nhu the nao?",
        "context": {},
        "domain_config": {},
        "provider": "google",
        "routing_metadata": {"method": "structured", "intent": "social"},
    }
    captured_llm = {}

    def _capture_bind_direct_tools(llm, *_args, **_kwargs):
        captured_llm["llm"] = llm
        return llm, llm, None

    with patch(
        "app.engine.multi_agent.graph._get_or_create_tracer",
        return_value=fake_tracer,
    ), patch(
        "app.engine.multi_agent.graph.settings.enable_natural_conversation",
        True,
    ), patch(
        "app.engine.multi_agent.graph.settings.llm_presence_penalty",
        0.2,
    ), patch(
        "app.engine.multi_agent.graph.settings.llm_frequency_penalty",
        0.1,
    ), patch(
        "app.engine.multi_agent.agent_config.AgentConfigRegistry.get_llm",
        return_value=_FakeLLM(),
    ), patch(
        "app.engine.multi_agent.graph._collect_direct_tools",
        return_value=([], False),
    ), patch(
        "app.engine.multi_agent.graph._bind_direct_tools",
        side_effect=_capture_bind_direct_tools,
    ), patch(
        "app.engine.multi_agent.graph._build_direct_system_messages",
        return_value=[],
    ), patch(
        "app.engine.multi_agent.graph._execute_direct_tool_rounds",
        new=AsyncMock(return_value=(SimpleNamespace(content="Minh la Wiii.", tool_calls=[]), [], [])),
    ), patch(
        "app.engine.multi_agent.graph._extract_direct_response",
        return_value=("Minh la Wiii.", "", []),
    ), patch(
        "app.engine.multi_agent.graph._build_direct_reasoning_summary",
        new=AsyncMock(return_value=""),
    ):
        await direct_response_node(state)

    bound_llm = captured_llm["llm"]
    assert getattr(bound_llm, "_wiii_provider_name", None) == "google"
    assert getattr(bound_llm, "_wiii_model_name", None) == "gemini-3.1-pro-preview"
    assert getattr(bound_llm, "_wiii_tier_key", None) == "deep"
