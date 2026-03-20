"""
Unit tests for Multi-Agent Graph routing logic.

Tests:
- route_decision() for all 4 routes
- _build_domain_config() fallback behavior
- _get_domain_greetings() fallback behavior

Sprint 233: should_skip_grader removed — grader node eliminated from pipeline.
"""

import asyncio
import pytest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch, MagicMock

from app.engine.multi_agent.graph import (
    route_decision,
    _build_domain_config,
    _build_visual_tool_runtime_metadata,
    _build_ambiguous_simulation_clarifier,
    _build_code_studio_progress_messages,
    _build_code_studio_retry_status,
    _format_code_studio_progress_message,
    _get_domain_greetings,
    _bind_direct_tools,
    _collect_direct_tools,
    _collect_code_studio_tools,
    _execute_code_studio_tool_rounds,
    _ground_simulation_query_from_visual_context,
    _infer_pendulum_fast_path_title,
    _looks_like_ambiguous_simulation_request,
    _should_use_pendulum_code_studio_fast_path,
    code_studio_node,
    supervisor_node,
)


# =============================================================================
# Tests: route_decision
# =============================================================================

class TestRouteDecision:
    def test_routes_to_rag_agent(self):
        state = {"next_agent": "rag_agent"}
        assert route_decision(state) == "rag_agent"

    def test_routes_to_tutor_agent(self):
        state = {"next_agent": "tutor_agent"}
        assert route_decision(state) == "tutor_agent"

    def test_routes_to_memory_agent(self):
        state = {"next_agent": "memory_agent"}
        assert route_decision(state) == "memory_agent"

    def test_routes_to_direct(self):
        state = {"next_agent": "direct"}
        assert route_decision(state) == "direct"

    def test_routes_to_code_studio_agent(self):
        state = {"next_agent": "code_studio_agent"}
        assert route_decision(state) == "code_studio_agent"

    def test_unknown_agent_defaults_to_direct(self):
        state = {"next_agent": "unknown_agent"}
        assert route_decision(state) == "direct"

    def test_missing_next_agent_defaults_to_rag(self):
        state = {}
        assert route_decision(state) == "rag_agent"

    def test_empty_next_agent_defaults_to_direct(self):
        state = {"next_agent": ""}
        assert route_decision(state) == "direct"


# =============================================================================
# Sprint 233: TestShouldSkipGrader removed — grader node eliminated from pipeline.
# CRAG confidence is the sole confidence source. See test_sprint44_*.py for
# CRAG grading tests that remain valid.
# =============================================================================


# =============================================================================
# Tests: visual runtime metadata
# =============================================================================

class TestVisualRuntimeMetadata:
    def test_chart_runtime_metadata_prefers_inline_html_svg(self):
        metadata = _build_visual_tool_runtime_metadata({}, "Ve bieu do so sanh toc do cac loai tau container")

        assert metadata is not None
        assert metadata["presentation_intent"] == "chart_runtime"
        assert metadata["visual_intent_mode"] == "inline_html"
        assert metadata["preferred_render_surface"] == "svg"
        assert metadata["planning_profile"] == "chart_svg"
        assert metadata["preferred_visual_tool"] == "tool_generate_visual"


# =============================================================================
# Tests: _build_domain_config
# =============================================================================

class TestBuildDomainConfig:
    def test_fallback_returns_dict(self):
        """When domain registry returns None, returns generic fallback."""
        with patch("app.domains.registry.get_domain_registry") as mock_reg:
            mock_reg.return_value.get.return_value = None
            config = _build_domain_config("nonexistent")
        assert isinstance(config, dict)
        assert "domain_name" in config
        assert "domain_id" in config
        assert "routing_keywords" in config

    def test_fallback_has_rag_description(self):
        with patch("app.domains.registry.get_domain_registry") as mock_reg:
            mock_reg.return_value.get.return_value = None
            config = _build_domain_config("nonexistent")
        assert "rag_description" in config
        assert len(config["rag_description"]) > 0

    def test_fallback_has_tutor_description(self):
        with patch("app.domains.registry.get_domain_registry") as mock_reg:
            mock_reg.return_value.get.return_value = None
            config = _build_domain_config("nonexistent")
        assert "tutor_description" in config
        assert len(config["tutor_description"]) > 0


# =============================================================================
# Tests: _get_domain_greetings
# =============================================================================

class TestGetDomainGreetings:
    def test_fallback_returns_dict(self):
        with patch("app.domains.registry.get_domain_registry") as mock_reg:
            mock_reg.return_value.get.return_value = None
            greetings = _get_domain_greetings("nonexistent")
        assert isinstance(greetings, dict)

    def test_fallback_has_vietnamese_greetings(self):
        with patch("app.domains.registry.get_domain_registry") as mock_reg:
            mock_reg.return_value.get.return_value = None
            greetings = _get_domain_greetings("nonexistent")
        assert "xin chào" in greetings
        assert "hi" in greetings

    def test_fallback_has_english_greetings(self):
        with patch("app.domains.registry.get_domain_registry") as mock_reg:
            mock_reg.return_value.get.return_value = None
            greetings = _get_domain_greetings("nonexistent")
        assert "hello" in greetings
        assert "thanks" in greetings


# =============================================================================
# Tests: supervisor_node adaptive thinking for visual/code quality
# =============================================================================

class TestSupervisorNodeThinkingEffort:
    @pytest.mark.asyncio
    async def test_escalates_recipe_backed_premium_simulation_to_high_when_not_explicit(self):
        state = {
            "query": "Hãy mô phỏng vật lý con lắc có thể kéo thả chuột",
            "context": {},
        }
        result_state = {
            "query": state["query"],
            "context": {},
            "routing_metadata": {"intent": "code_execution"},
            "next_agent": "code_studio_agent",
        }
        fake_supervisor = SimpleNamespace(process=AsyncMock(return_value=result_state))
        fake_registry = SimpleNamespace(tracer=SimpleNamespace(span=lambda *args, **kwargs: nullcontext()))
        fake_tracer = MagicMock()

        with patch("app.engine.multi_agent.graph.get_supervisor_agent", return_value=fake_supervisor), \
             patch("app.engine.multi_agent.graph.get_agent_registry", return_value=fake_registry), \
             patch("app.engine.multi_agent.graph.get_reasoning_tracer", return_value=fake_tracer):
            result = await supervisor_node(state)

        assert result["thinking_effort"] == "max"

    @pytest.mark.asyncio
    async def test_preserves_explicit_thinking_effort(self):
        state = {
            "query": "Hãy mô phỏng vật lý con lắc có thể kéo thả chuột",
            "context": {},
            "thinking_effort": "low",
        }
        result_state = {
            "query": state["query"],
            "context": {},
            "routing_metadata": {"intent": "code_execution"},
            "next_agent": "code_studio_agent",
        }
        fake_supervisor = SimpleNamespace(process=AsyncMock(return_value=result_state))
        fake_registry = SimpleNamespace(tracer=SimpleNamespace(span=lambda *args, **kwargs: nullcontext()))
        fake_tracer = MagicMock()

        with patch("app.engine.multi_agent.graph.get_supervisor_agent", return_value=fake_supervisor), \
             patch("app.engine.multi_agent.graph.get_agent_registry", return_value=fake_registry), \
             patch("app.engine.multi_agent.graph.get_reasoning_tracer", return_value=fake_tracer):
            result = await supervisor_node(state)

        assert result["thinking_effort"] == "low"


# =============================================================================
# Tests: _collect_code_studio_tools
# =============================================================================

class TestCollectCodeStudioTools:
    @patch("app.engine.multi_agent.graph.settings")
    @patch("app.engine.multi_agent.graph.filter_tools_for_visual_intent")
    @patch("app.engine.multi_agent.graph.filter_tools_for_role")
    @patch("app.engine.tools.output_generation_tools.get_output_generation_tools")
    @patch("app.engine.tools.visual_tools.get_visual_tools")
    @patch("app.engine.tools.chart_tools.get_chart_tools")
    def test_restricts_clear_app_requests_to_preferred_tool(
        self,
        mock_chart_tools,
        mock_visual_tools,
        mock_output_tools,
        mock_filter_role,
        mock_filter_visual,
        mock_settings,
    ):
        mock_settings.enable_code_execution = False
        mock_settings.enable_browser_agent = False
        mock_settings.enable_privileged_sandbox = False
        mock_settings.sandbox_provider = ""
        mock_settings.sandbox_allow_browser_workloads = False
        mock_settings.enable_structured_visuals = True

        tool_create_visual_code = SimpleNamespace(name="tool_create_visual_code")
        tool_generate_visual = SimpleNamespace(name="tool_generate_visual")
        tool_generate_html_file = SimpleNamespace(name="tool_generate_html_file")

        mock_chart_tools.return_value = [tool_generate_visual]
        mock_visual_tools.return_value = [tool_create_visual_code]
        mock_output_tools.return_value = [tool_generate_html_file]
        mock_filter_role.side_effect = lambda tools, user_role: tools
        mock_filter_visual.side_effect = lambda tools, *_args, **_kwargs: tools

        tools, force_tools = _collect_code_studio_tools(
            "Build a mini pendulum physics app in chat with drag interaction",
            "student",
        )

        assert force_tools is True
        assert [tool.name for tool in tools] == ["tool_create_visual_code"]


class TestCollectDirectTools:
    @patch("app.engine.multi_agent.graph.settings")
    @patch("app.engine.multi_agent.graph.filter_tools_for_visual_intent")
    @patch("app.engine.multi_agent.graph.filter_tools_for_role")
    @patch("app.engine.tools.visual_tools.get_visual_tools")
    @patch("app.engine.tools.chart_tools.get_chart_tools")
    @patch("app.engine.tools.rag_tools.tool_knowledge_search")
    def test_restricts_clear_chart_visual_requests_to_preferred_tool(
        self,
        mock_knowledge_search,
        mock_chart_tools,
        mock_visual_tools,
        mock_filter_role,
        mock_filter_visual,
        mock_settings,
    ):
        mock_settings.enable_character_tools = False
        mock_settings.enable_code_execution = False
        mock_settings.enable_structured_visuals = True

        tool_generate_visual = SimpleNamespace(name="tool_generate_visual")
        tool_generate_chart = SimpleNamespace(name="tool_generate_interactive_chart")

        mock_knowledge_search.name = "tool_knowledge_search"
        mock_chart_tools.return_value = [tool_generate_chart]
        mock_visual_tools.return_value = [tool_generate_visual]
        mock_filter_role.side_effect = lambda tools, user_role: tools
        mock_filter_visual.side_effect = lambda tools, *_args, **_kwargs: tools

        tools, force_tools = _collect_direct_tools(
            "Ve bieu do so sanh toc do cac loai tau container.",
            "student",
        )

        assert force_tools is True
        assert [tool.name for tool in tools] == ["tool_generate_visual"]

    @patch("app.engine.multi_agent.graph.settings")
    @patch("app.engine.multi_agent.graph.filter_tools_for_visual_intent")
    @patch("app.engine.multi_agent.graph.filter_tools_for_role")
    @patch("app.engine.tools.visual_tools.get_visual_tools")
    @patch("app.engine.tools.chart_tools.get_chart_tools")
    @patch("app.engine.tools.lms_tools.get_all_lms_tools")
    @patch("app.engine.tools.rag_tools.tool_knowledge_search")
    def test_plain_quiz_study_turn_without_creation_verbs_does_not_force_code_visual_tools(
        self,
        mock_knowledge_search,
        mock_get_lms_tools,
        mock_chart_tools,
        mock_visual_tools,
        mock_filter_role,
        mock_filter_visual,
        mock_settings,
    ):
        mock_settings.enable_character_tools = False
        mock_settings.enable_code_execution = False
        mock_settings.enable_structured_visuals = True
        mock_settings.enable_lms_integration = True

        mock_knowledge_search.name = "tool_knowledge_search"
        mock_chart_tools.return_value = [SimpleNamespace(name="tool_generate_interactive_chart")]
        mock_visual_tools.return_value = [
            SimpleNamespace(name="tool_generate_visual"),
            SimpleNamespace(name="tool_create_visual_code"),
        ]
        mock_get_lms_tools.return_value = [SimpleNamespace(name="tool_lms_get_progress")]
        mock_filter_role.side_effect = lambda tools, user_role: tools
        mock_filter_visual.side_effect = lambda tools, *_args, **_kwargs: tools

        tools, force_tools = _collect_direct_tools(
            "Cho minh bo quiz tieng Trung de on tap duoc khong?",
            "student",
        )

        tool_names = [tool.name for tool in tools]
        assert force_tools is False
        assert "tool_create_visual_code" not in tool_names
        assert "tool_generate_visual" not in tool_names


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
             patch("app.engine.multi_agent.graph._bind_direct_tools", return_value=(fake_llm, fake_llm)), \
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
        assert "chua noi ro hien tuong nao" in result["final_response"]
        assert result["current_agent"] == "code_studio_agent"


class TestCodeStudioProgressHeartbeat:
    def test_simulation_progress_messages_are_living_and_specific(self):
        state = {
            "context": {
                "visual_context": {
                    "last_visual_title": "Kimi linear attention",
                }
            }
        }

        messages = _build_code_studio_progress_messages(
            "Wiii tao mo phong cho minh duoc chu ?",
            state,
        )

        assert any("state model" in message for message in messages)
        assert any("canvas loop" in message for message in messages)
        assert any("Kimi linear attention" in message for message in messages)

    def test_progress_message_includes_elapsed_seconds(self):
        formatted = _format_code_studio_progress_message("Minh dang dung canvas loop...", 42.1)
        assert "(da 42s)" in formatted

    def test_retry_status_is_honest_about_long_running_simulation(self):
        retry = _build_code_studio_retry_status(
            "Wiii tao mo phong cho minh duoc chu ?",
            {"context": {"visual_context": {"last_visual_title": "Kimi linear attention"}}},
            elapsed_seconds=240,
        )
        assert "preview that" in retry
        assert "(da 240s)" in retry

    @pytest.mark.asyncio
    async def test_preserves_timeout_fallback_response_without_overwrite(self):
        from langchain_core.messages import AIMessage

        class SlowLLM:
            async def ainvoke(self, _messages):
                await asyncio.sleep(0.01)
                return AIMessage(content="stale primary response")

        class FallbackLLM:
            def bind_tools(self, _tools):
                return self

            async def ainvoke(self, _messages):
                return AIMessage(content="fallback recovery response")

        async def push_event(_event):
            return None

        async def fake_render_reasoning(**_kwargs):
            return SimpleNamespace(
                label="Dang tong hop",
                summary="Dang tong hop",
                phase="synthesize",
                action_text="",
                delta_chunks=[],
            )

        time_values = iter([0.0, 241.0, 241.0, 241.0, 241.0])

        with patch("app.engine.multi_agent.graph.time.time", side_effect=lambda: next(time_values, 241.0)), \
             patch("app.engine.multi_agent.graph._render_reasoning", new=fake_render_reasoning), \
             patch("app.engine.llm_pool.get_llm_moderate", return_value=FallbackLLM()):
            llm_response, _messages, _events = await _execute_code_studio_tool_rounds(
                SlowLLM(),
                SlowLLM(),
                [],
                [SimpleNamespace(name="tool_create_visual_code")],
                push_event,
                query="",
                state={},
            )

        assert "fallback recovery response" in llm_response.content


class TestBindDirectTools:
    def test_forces_exact_tool_name_when_single_tool_is_bound(self):
        class FakeLLM:
            def __init__(self):
                self.calls = []

            def bind_tools(self, tools, tool_choice=None):
                self.calls.append({
                    "tools": tools,
                    "tool_choice": tool_choice,
                })
                return {"tool_choice": tool_choice, "count": len(tools)}

        llm = FakeLLM()
        tool = SimpleNamespace(name="tool_create_visual_code")

        llm_with_tools, llm_auto = _bind_direct_tools(llm, [tool], True)

        assert llm.calls[0]["tool_choice"] is None
        assert llm.calls[1]["tool_choice"] == "tool_create_visual_code"
        assert llm_auto["tool_choice"] is None
        assert llm_with_tools["tool_choice"] == "tool_create_visual_code"

    def test_keeps_any_when_multiple_tools_are_bound(self):
        class FakeLLM:
            def __init__(self):
                self.calls = []

            def bind_tools(self, tools, tool_choice=None):
                self.calls.append(tool_choice)
                return {"tool_choice": tool_choice, "count": len(tools)}

        llm = FakeLLM()
        tools = [
            SimpleNamespace(name="tool_generate_visual"),
            SimpleNamespace(name="tool_create_visual_code"),
        ]

        llm_with_tools, _llm_auto = _bind_direct_tools(llm, tools, True)

        assert llm.calls == [None, "any"]
        assert llm_with_tools["tool_choice"] == "any"
