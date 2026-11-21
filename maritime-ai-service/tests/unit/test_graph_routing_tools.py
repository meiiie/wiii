from types import SimpleNamespace
from unittest.mock import patch

from app.engine.multi_agent.graph import (
    _direct_required_tool_names,
    _bind_direct_tools,
    _collect_direct_tools,
    _collect_code_studio_tools,
)


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


class TestDirectKnowledgeSearchGating:
    @patch("app.engine.multi_agent.graph.settings")
    @patch("app.engine.multi_agent.graph.filter_tools_for_visual_intent")
    @patch("app.engine.multi_agent.graph.filter_tools_for_role")
    @patch("app.engine.tools.visual_tools.get_visual_tools")
    @patch("app.engine.tools.chart_tools.get_chart_tools")
    @patch("app.engine.tools.rag_tools.tool_knowledge_search")
    def test_social_turn_does_not_bind_knowledge_search(
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
        mock_settings.enable_lms_integration = False

        mock_knowledge_search.name = "tool_knowledge_search"
        mock_chart_tools.return_value = [SimpleNamespace(name="tool_generate_interactive_chart")]
        mock_visual_tools.return_value = [SimpleNamespace(name="tool_generate_visual")]
        mock_filter_role.side_effect = lambda tools, user_role: tools
        mock_filter_visual.side_effect = lambda tools, *_args, **_kwargs: tools

        tools, force_tools = _collect_direct_tools(
            "có thể uống rượu thưởng trăng không ?",
            "student",
        )

        tool_names = [tool.name for tool in tools]
        assert force_tools is False
        assert "tool_knowledge_search" not in tool_names
        assert "tool_knowledge_search" not in _direct_required_tool_names(
            "có thể uống rượu thưởng trăng không ?",
            "student",
        )

    @patch("app.engine.multi_agent.graph.settings")
    @patch("app.engine.multi_agent.graph.filter_tools_for_visual_intent")
    @patch("app.engine.multi_agent.graph.filter_tools_for_role")
    @patch("app.engine.tools.visual_tools.get_visual_tools")
    @patch("app.engine.tools.chart_tools.get_chart_tools")
    @patch("app.engine.tools.rag_tools.tool_knowledge_search")
    def test_visual_turn_does_not_bind_knowledge_search(
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
        mock_settings.enable_lms_integration = False

        mock_knowledge_search.name = "tool_knowledge_search"
        mock_chart_tools.return_value = [SimpleNamespace(name="tool_generate_interactive_chart")]
        mock_visual_tools.return_value = [SimpleNamespace(name="tool_generate_visual")]
        mock_filter_role.side_effect = lambda tools, user_role: tools
        mock_filter_visual.side_effect = lambda tools, *_args, **_kwargs: tools

        tools, force_tools = _collect_direct_tools(
            "Visual cho mình xem thống kê dữ liệu hiện tại giá dầu mấy ngày gần đây",
            "student",
        )

        tool_names = [tool.name for tool in tools]
        assert force_tools is True
        assert "tool_knowledge_search" not in tool_names
        assert "tool_knowledge_search" not in _direct_required_tool_names(
            "Visual cho mình xem thống kê dữ liệu hiện tại giá dầu mấy ngày gần đây",
            "student",
        )

    @patch("app.engine.multi_agent.graph.settings")
    @patch("app.engine.multi_agent.graph.filter_tools_for_visual_intent")
    @patch("app.engine.multi_agent.graph.filter_tools_for_role")
    @patch("app.engine.tools.visual_tools.get_visual_tools")
    @patch("app.engine.tools.chart_tools.get_chart_tools")
    @patch("app.engine.tools.rag_tools.tool_knowledge_search")
    def test_explicit_retrieval_turn_keeps_knowledge_search(
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
        mock_settings.enable_lms_integration = False

        mock_knowledge_search.name = "tool_knowledge_search"
        mock_chart_tools.return_value = [SimpleNamespace(name="tool_generate_interactive_chart")]
        mock_visual_tools.return_value = [SimpleNamespace(name="tool_generate_visual")]
        mock_filter_role.side_effect = lambda tools, user_role: tools
        mock_filter_visual.side_effect = lambda tools, *_args, **_kwargs: tools

        tools, force_tools = _collect_direct_tools(
            "Tra cứu tài liệu nội bộ về quy định an toàn hàng hải",
            "student",
        )

        tool_names = [tool.name for tool in tools]
        assert "tool_knowledge_search" in tool_names
        assert "tool_knowledge_search" in _direct_required_tool_names(
            "Tra cứu tài liệu nội bộ về quy định an toàn hàng hải",
            "student",
        )


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

        llm_with_tools, llm_auto, forced_choice = _bind_direct_tools(llm, [tool], True)

        assert llm.calls[0]["tool_choice"] is None
        assert llm.calls[1]["tool_choice"] == "tool_create_visual_code"
        assert llm_auto["tool_choice"] is None
        assert llm_with_tools["tool_choice"] == "tool_create_visual_code"
        assert forced_choice == "tool_create_visual_code"

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

        llm_with_tools, _llm_auto, forced_choice = _bind_direct_tools(llm, tools, True)

        assert llm.calls == [None, "any"]
        assert llm_with_tools["tool_choice"] == "any"
        assert forced_choice == "any"

    def test_preserves_runtime_metadata_across_bound_wrappers(self):
        class FakeBound(dict):
            pass

        class FakeLLM:
            def __init__(self):
                self._wiii_provider_name = "google"
                self._wiii_model_name = "gemini-3.1-pro-preview"
                self._wiii_tier_key = "deep"

            def bind_tools(self, tools, tool_choice=None):
                return FakeBound(tool_choice=tool_choice, count=len(tools))

        llm = FakeLLM()
        tool = SimpleNamespace(name="tool_generate_visual")

        llm_with_tools, llm_auto, forced_choice = _bind_direct_tools(llm, [tool], True)

        assert getattr(llm_auto, "_wiii_provider_name", None) == "google"
        assert getattr(llm_auto, "_wiii_model_name", None) == "gemini-3.1-pro-preview"
        assert getattr(llm_auto, "_wiii_tier_key", None) == "deep"
        assert getattr(llm_with_tools, "_wiii_tier_key", None) == "deep"
        assert forced_choice == "tool_generate_visual"
