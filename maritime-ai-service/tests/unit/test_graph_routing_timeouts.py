from types import SimpleNamespace
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.engine.multi_agent.graph import (
    _capture_public_thinking_event,
    _public_reasoning_delta_chunks,
    _resolve_direct_answer_timeout_profile,
    _resolve_public_thinking_content,
    direct_response_node,
)


class TestDirectAnswerTimeoutProfile:
    def test_zhipu_identity_turn_uses_structured_timeout_profile(self):
        assert _resolve_direct_answer_timeout_profile(
            provider_name="zhipu",
            is_identity_turn=True,
            is_short_house_chatter=False,
            use_house_voice_direct=False,
            tools_bound=False,
        ) == "structured"

    def test_google_identity_turn_keeps_default_timeout_profile(self):
        assert _resolve_direct_answer_timeout_profile(
            provider_name="google",
            is_identity_turn=True,
            is_short_house_chatter=False,
            use_house_voice_direct=False,
            tools_bound=False,
        ) is None

    def test_tool_bound_turn_keeps_existing_timeout_path(self):
        assert _resolve_direct_answer_timeout_profile(
            provider_name="zhipu",
            is_identity_turn=True,
            is_short_house_chatter=True,
            use_house_voice_direct=True,
            tools_bound=True,
        ) is None

    @pytest.mark.asyncio
    async def test_direct_response_node_uses_house_voice_for_obvious_social_turn(self):
        fake_tracer = MagicMock()
        fake_llm = MagicMock()
        state = {
            "query": "Xin chào hảo hán",
            "context": {},
            "domain_config": {},
            "provider": "zhipu",
            "routing_metadata": {"method": "always_on_social_fast_path", "intent": "social"},
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
            new=AsyncMock(return_value=(SimpleNamespace(content="Chào hảo hán~", tool_calls=[]), [], [])),
        ), patch(
            "app.engine.multi_agent.graph._extract_direct_response",
            return_value=("Chào hảo hán~", "", []),
        ), patch(
            "app.engine.multi_agent.graph._build_direct_reasoning_summary",
            new=AsyncMock(return_value="Mình bắt nhịp câu chào này để mở nhịp trò chuyện tự nhiên."),
        ):
            result = await direct_response_node(state)

        assert "hảo hán" in result["final_response"]
        assert mock_get_llm.call_args.kwargs["provider_override"] == "zhipu"
        mock_collect_tools.assert_not_called()
        assert mock_build_messages.call_args.kwargs["role_name"] == "direct_chatter_agent"
        assert mock_build_messages.call_args.kwargs["history_limit"] == 0
        assert mock_build_messages.call_args.kwargs["tools_context_override"] == ""
        fake_tracer.end_step.assert_called_once()

    @pytest.mark.asyncio
    async def test_direct_response_node_uses_house_voice_for_laughter_social_turn(self):
        fake_tracer = MagicMock()
        fake_llm = MagicMock()
        state = {
            "query": "hẹ hẹ",
            "context": {},
            "domain_config": {},
            "provider": "zhipu",
            "routing_metadata": {"method": "always_on_social_fast_path", "intent": "social"},
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
            new=AsyncMock(return_value=(SimpleNamespace(content="Hẹ hẹ~ mình ở đây nè.", tool_calls=[]), [], [])),
        ), patch(
            "app.engine.multi_agent.graph._extract_direct_response",
            return_value=("Hẹ hẹ~ mình ở đây nè.", "", []),
        ), patch(
            "app.engine.multi_agent.graph._build_direct_reasoning_summary",
            new=AsyncMock(return_value="Mình bắt nhịp tiếng cười nhẹ này để đáp lại có hồn hơn."),
        ):
            result = await direct_response_node(state)

        assert "Hẹ hẹ" in result["final_response"]
        assert mock_get_llm.call_args.kwargs["provider_override"] == "zhipu"
        mock_collect_tools.assert_not_called()
        assert mock_build_messages.call_args.kwargs["role_name"] == "direct_chatter_agent"
        assert mock_build_messages.call_args.kwargs["history_limit"] == 0
        assert mock_build_messages.call_args.kwargs["tools_context_override"] == ""
        fake_tracer.end_step.assert_called_once()


    @pytest.mark.asyncio
    async def test_direct_response_node_uses_house_voice_for_reaction_turn(self):
        fake_tracer = MagicMock()
        fake_llm = MagicMock()
        state = {
            "query": "wow",
            "context": {},
            "domain_config": {},
            "provider": "zhipu",
            "routing_metadata": {"method": "always_on_chatter_fast_path", "intent": "social"},
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
            new=AsyncMock(return_value=(SimpleNamespace(content="Woa~", tool_calls=[]), [], [])),
        ), patch(
            "app.engine.multi_agent.graph._extract_direct_response",
            return_value=("Woa~", "", []),
        ), patch(
            "app.engine.multi_agent.graph._build_direct_reasoning_summary",
            new=AsyncMock(return_value="Mình giữ nhịp tự nhiên cho câu trò chuyện ngắn này."),
        ):
            result = await direct_response_node(state)

        assert result["final_response"] == "Woa~"
        assert mock_get_llm.call_args.kwargs["provider_override"] == "zhipu"
        mock_collect_tools.assert_not_called()
        assert mock_build_messages.call_args.kwargs["role_name"] == "direct_chatter_agent"
        assert mock_build_messages.call_args.kwargs["history_limit"] == 0
        assert mock_build_messages.call_args.kwargs["tools_context_override"] == ""
        fake_tracer.end_step.assert_called_once()

    @pytest.mark.asyncio
    async def test_direct_response_node_uses_house_voice_for_vague_banter_turn(self):
        fake_tracer = MagicMock()
        fake_llm = MagicMock()
        state = {
            "query": "gì đó",
            "context": {},
            "domain_config": {},
            "provider": "zhipu",
            "routing_metadata": {"method": "always_on_chatter_fast_path", "intent": "off_topic"},
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
            new=AsyncMock(return_value=(SimpleNamespace(content="Bạn thả lửng một ý nhỏ nè~", tool_calls=[]), [], [])),
        ), patch(
            "app.engine.multi_agent.graph._extract_direct_response",
            return_value=("Bạn thả lửng một ý nhỏ nè~", "", []),
        ), patch(
            "app.engine.multi_agent.graph._build_direct_reasoning_summary",
            new=AsyncMock(return_value="Mình giữ nhịp mở để bạn nối tiếp dễ hơn."),
        ):
            result = await direct_response_node(state)

        assert "ý nhỏ" in result["final_response"]
        assert mock_get_llm.call_args.kwargs["provider_override"] == "zhipu"
        mock_collect_tools.assert_not_called()
        assert mock_build_messages.call_args.kwargs["role_name"] == "direct_chatter_agent"
        assert mock_build_messages.call_args.kwargs["history_limit"] == 0
        assert mock_build_messages.call_args.kwargs["tools_context_override"] == ""
        fake_tracer.end_step.assert_called_once()

    @pytest.mark.asyncio
    async def test_direct_response_node_keeps_identity_turn_on_full_prompt_without_tools(self):
        fake_tracer = MagicMock()
        fake_llm = MagicMock()
        state = {
            "query": "ban la ai",
            "context": {},
            "domain_config": {},
            "provider": "zhipu",
            "routing_metadata": {"method": "structured", "intent": "selfhood"},
            "_routing_hint": {"kind": "identity_probe", "intent": "selfhood", "shape": "identity"},
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
            new=AsyncMock(return_value=(SimpleNamespace(content="MÃ¬nh lÃ  Wiii.", tool_calls=[]), [], [])),
        ), patch(
            "app.engine.multi_agent.graph._extract_direct_response",
            return_value=("MÃ¬nh lÃ  Wiii.", "", []),
        ), patch(
            "app.engine.multi_agent.graph._build_direct_reasoning_summary",
            new=AsyncMock(return_value="MÃ¬nh Ä‘ang cháº¡m láº¡i pháº§n tá»± thÃ¢n cá»§a Wiii trÆ°á»›c khi tráº£ lá»i."),
        ):
            result = await direct_response_node(state)

        assert "Wiii" in result["final_response"]
        assert mock_get_llm.call_args.kwargs["provider_override"] == "zhipu"
        assert mock_get_llm.call_args.args[0] == "direct_identity"
        mock_collect_tools.assert_not_called()
        assert mock_build_messages.call_args.kwargs["role_name"] == "direct_chatter_agent"
        assert mock_build_messages.call_args.kwargs["history_limit"] >= 6
        assert mock_build_messages.call_args.kwargs["tools_context_override"] is None
        fake_tracer.end_step.assert_called_once()

    @pytest.mark.asyncio
    async def test_direct_response_node_keeps_house_provider_for_llm_but_preserves_auto_failover(self):
        fake_tracer = MagicMock()
        fake_llm = MagicMock()
        state = {
            "query": "ban la ai",
            "context": {},
            "domain_config": {},
            "provider": "auto",
            "_house_routing_provider": "google",
            "routing_metadata": {"method": "structured", "intent": "selfhood"},
            "_routing_hint": {"kind": "identity_probe", "intent": "selfhood", "shape": "identity"},
        }

        execute_direct_tool_rounds = AsyncMock(
            return_value=(SimpleNamespace(content="Mình là Wiii.", tool_calls=[]), [], [])
        )

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
        ), patch(
            "app.engine.multi_agent.graph._execute_direct_tool_rounds",
            new=execute_direct_tool_rounds,
        ), patch(
            "app.engine.multi_agent.graph._extract_direct_response",
            return_value=("Mình là Wiii.", "", []),
        ), patch(
            "app.engine.multi_agent.graph._build_direct_reasoning_summary",
            new=AsyncMock(return_value="Mình chỉ cần đáp thật và đứng đúng là Wiii thôi."),
        ):
            result = await direct_response_node(state)

        assert result["final_response"] == "Mình là Wiii."
        assert mock_get_llm.call_args.kwargs["provider_override"] == "google"
        assert execute_direct_tool_rounds.await_args.kwargs["provider"] is None
        mock_collect_tools.assert_not_called()
        fake_tracer.end_step.assert_called_once()

    def test_public_reasoning_delta_chunks_keep_interval_body(self):
        beat = SimpleNamespace(
            summary=(
                "Câu này cần một nhịp đáp chậm và thật hơn là một lời giải thích vội.\n\n"
                "Mình muốn mở lời vừa đủ dịu để nếu bạn muốn kể tiếp thì vẫn còn chỗ cho nhịp đó đi ra."
            ),
            delta_chunks=[
                "Câu này cần một nhịp đáp chậm và thật hơn là một lời giải thích vội.",
                "Mình muốn mở lời vừa đủ dịu để nếu bạn muốn kể tiếp thì vẫn còn chỗ cho nhịp đó đi ra.",
            ],
        )

        assert _public_reasoning_delta_chunks(beat) == [
            "Câu này cần một nhịp đáp chậm và thật hơn là một lời giải thích vội.",
            "Mình muốn mở lời vừa đủ dịu để nếu bạn muốn kể tiếp thì vẫn còn chỗ cho nhịp đó đi ra.",
        ]

    def test_capture_public_thinking_event_only_uses_thinking_deltas(self):
        state = {"_public_thinking_fragments": []}

        _capture_public_thinking_event(
            state,
            {"type": "thinking_start", "summary": "Mình muốn mở lời vừa đủ dịu."},
        )
        _capture_public_thinking_event(
            state,
            {"type": "thinking_delta", "content": "Mình muốn mở lời vừa đủ dịu."},
        )
        _capture_public_thinking_event(
            state,
            {"type": "thinking_delta", "content": "Mình muốn mở lời vừa đủ dịu."},
        )
        _capture_public_thinking_event(
            state,
            {"type": "status", "content": "iteration=0"},
        )

        assert state["_public_thinking_fragments"] == ["Mình muốn mở lời vừa đủ dịu."]

    def test_capture_public_thinking_event_redacts_secret_text(self):
        state = {"_public_thinking_fragments": []}

        _capture_public_thinking_event(
            state,
            {
                "type": "thinking_start",
                "content": "Bearer raw-start-token-12345678",
                "node": "direct",
                "details": {"access_token": "raw-access-token"},
            },
        )
        _capture_public_thinking_event(
            state,
            {
                "type": "thinking_delta",
                "content": "Mình kiểm tra Bearer raw-delta-token-12345678",
                "node": "direct",
            },
        )

        serialized = str(state)
        assert "<redacted-secret>" in serialized
        assert "raw-start-token-12345678" not in serialized
        assert "raw-access-token" not in serialized
        assert "raw-delta-token-12345678" not in serialized

    def test_resolve_public_thinking_content_prefers_interval_fragments_over_summary(self):
        state = {
            "_public_thinking_fragments": [
                "Câu này cần một nhịp đáp chậm và thật hơn là một lời giải thích vội.",
                "Mình muốn mở lời vừa đủ dịu để nếu bạn muốn kể tiếp thì vẫn còn chỗ cho nhịp đó đi ra.",
            ],
            "thinking_content": "Nhịp này không cần kéo dài quá tay.",
        }

        assert _resolve_public_thinking_content(state, fallback="fallback") == (
            "Câu này cần một nhịp đáp chậm và thật hơn là một lời giải thích vội.\n\n"
            "Mình muốn mở lời vừa đủ dịu để nếu bạn muốn kể tiếp thì vẫn còn chỗ cho nhịp đó đi ra."
        )

    @pytest.mark.asyncio
    async def test_direct_response_node_prefers_interval_fragments_for_final_thinking_content(self):
        fake_tracer = MagicMock()
        fake_llm = MagicMock()
        state = {
            "query": "buon qua",
            "context": {},
            "domain_config": {},
            "provider": "auto",
            "routing_metadata": {"method": "structured", "intent": "emotional"},
            "_routing_hint": {"kind": "emotional_support", "intent": "emotional"},
            "_public_thinking_fragments": [],
        }

        async def _fake_execute(*args, **kwargs):
            working_state = kwargs["state"]
            working_state["_public_thinking_fragments"] = [
                "Câu này cần một nhịp đáp chậm và thật hơn là một lời giải thích vội.",
                "Mình muốn mở lời vừa đủ dịu để nếu bạn muốn kể tiếp thì vẫn còn chỗ cho nhịp đó đi ra.",
            ]
            return SimpleNamespace(content="Mình ở đây với bạn.", tool_calls=[]), [], []

        with patch(
            "app.engine.multi_agent.graph._get_or_create_tracer",
            return_value=fake_tracer,
        ), patch(
            "app.engine.multi_agent.agent_config.AgentConfigRegistry.get_llm",
            return_value=fake_llm,
        ), patch(
            "app.engine.multi_agent.graph._collect_direct_tools",
            return_value=([], False),
        ), patch(
            "app.engine.multi_agent.graph._bind_direct_tools",
            return_value=(fake_llm, fake_llm, None),
        ), patch(
            "app.engine.multi_agent.graph._build_direct_system_messages",
            return_value=[],
        ), patch(
            "app.engine.multi_agent.graph._execute_direct_tool_rounds",
            new=AsyncMock(side_effect=_fake_execute),
        ), patch(
            "app.engine.multi_agent.graph._extract_direct_response",
            return_value=("Mình ở đây với bạn.", "", []),
        ), patch(
            "app.engine.multi_agent.graph._build_direct_reasoning_summary",
            new=AsyncMock(return_value="Nhịp này không cần kéo dài quá tay."),
        ):
            result = await direct_response_node(state)

        assert result["thinking_content"] == (
            "Câu này cần một nhịp đáp chậm và thật hơn là một lời giải thích vội.\n\n"
            "Mình muốn mở lời vừa đủ dịu để nếu bạn muốn kể tiếp thì vẫn còn chỗ cho nhịp đó đi ra."
        )
        assert result["final_response"] == "Mình ở đây với bạn."
        fake_tracer.end_step.assert_called_once()

    @pytest.mark.asyncio
    async def test_direct_response_node_backfills_emotional_thinking_without_native_or_fragments(self):
        fake_tracer = MagicMock()
        fake_llm = MagicMock()
        state = {
            "query": "minh buon qua",
            "context": {},
            "domain_config": {},
            "provider": "auto",
            "routing_metadata": {"method": "structured", "intent": "emotional"},
            "_routing_hint": {"kind": "emotional_support", "intent": "emotional"},
            "_public_thinking_fragments": [],
        }

        with patch(
            "app.engine.multi_agent.graph._get_or_create_tracer",
            return_value=fake_tracer,
        ), patch(
            "app.engine.multi_agent.agent_config.AgentConfigRegistry.get_llm",
            return_value=fake_llm,
        ), patch(
            "app.engine.multi_agent.graph._collect_direct_tools",
            return_value=([], False),
        ), patch(
            "app.engine.multi_agent.graph._bind_direct_tools",
            return_value=(fake_llm, fake_llm, None),
        ), patch(
            "app.engine.multi_agent.graph._build_direct_system_messages",
            return_value=[],
        ), patch(
            "app.engine.multi_agent.graph._execute_direct_tool_rounds",
            new=AsyncMock(return_value=(SimpleNamespace(content="Mình ở đây.", tool_calls=[]), [], [])),
        ), patch(
            "app.engine.multi_agent.graph._extract_direct_response",
            return_value=("Mình ở đây.", "", []),
        ), patch(
            "app.engine.multi_agent.graph._build_direct_reasoning_summary",
            new=AsyncMock(return_value="Câu này cần một nhịp đáp chậm và thật hơn là một lời giải thích vội."),
        ):
            result = await direct_response_node(state)

        assert result.get("thinking_content", "") == "Câu này cần một nhịp đáp chậm và thật hơn là một lời giải thích vội."
        assert "khoảng chùng xuống" not in result.get("thinking_content", "").lower()

    @pytest.mark.asyncio
    async def test_direct_response_node_surfaces_model_visible_thought_for_emotional_turns(self):
        fake_tracer = MagicMock()
        fake_llm = MagicMock()
        state = {
            "query": "minh thay te qua",
            "context": {},
            "domain_config": {},
            "provider": "auto",
            "routing_metadata": {"method": "structured", "intent": "social"},
            "_routing_hint": {"kind": "emotional_support", "intent": "social"},
            "_public_thinking_fragments": [],
        }

        with patch(
            "app.engine.multi_agent.graph._get_or_create_tracer",
            return_value=fake_tracer,
        ), patch(
            "app.engine.multi_agent.agent_config.AgentConfigRegistry.get_llm",
            return_value=fake_llm,
        ), patch(
            "app.engine.multi_agent.graph._collect_direct_tools",
            return_value=([], False),
        ), patch(
            "app.engine.multi_agent.graph._bind_direct_tools",
            return_value=(fake_llm, fake_llm, None),
        ), patch(
            "app.engine.multi_agent.graph._build_direct_system_messages",
            return_value=[],
        ), patch(
            "app.engine.multi_agent.graph._execute_direct_tool_rounds",
            new=AsyncMock(return_value=(SimpleNamespace(content="ignored", tool_calls=[]), [], [])),
        ), patch(
            "app.engine.multi_agent.graph._extract_direct_response",
            return_value=(
                "Oi, nghe ban noi ma minh thay lo qua.",
                "Nguoi ban cua minh dang thay khong on, minh muon hoi tham nhe thoi.",
                [],
            ),
        ), patch(
            "app.engine.multi_agent.graph._build_direct_reasoning_summary",
            new=AsyncMock(return_value="template narrator should not win"),
        ):
            result = await direct_response_node(state)

        assert result["final_response"] == "Oi, nghe ban noi ma minh thay lo qua."
        assert result["thinking_content"] == "Nguoi ban cua minh dang thay khong on, minh muon hoi tham nhe thoi."
        assert result["thinking"] == "Nguoi ban cua minh dang thay khong on, minh muon hoi tham nhe thoi."
