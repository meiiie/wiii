"""
Tests for Sprint 227 + 228: Visual-First Response system.

Sprint 227: Mermaid diagrams inline in chat.
Sprint 228: Interactive HTML widgets (```widget code blocks) — Claude-like visuals.

Verifies that agent YAML files include visual directives and that
the PromptLoader correctly renders them into the system prompt.
"""

from unittest.mock import patch, MagicMock


# ============================================================================
# Visual YAML Section in Agent Personas
# ============================================================================


class TestVisualYAMLSection:
    """Verify visual section exists in agent YAML files."""

    def test_tutor_has_visual_section(self):
        from app.prompts.prompt_loader import PromptLoader
        loader = PromptLoader()
        persona = loader.get_persona("student")
        assert "visual" in persona, "tutor.yaml should have 'visual' section"
        visual = persona["visual"]
        assert "mermaid" in visual
        assert "widget" in visual

    def test_tutor_mermaid_subsection(self):
        from app.prompts.prompt_loader import PromptLoader
        loader = PromptLoader()
        persona = loader.get_persona("student")
        mermaid = persona["visual"]["mermaid"]
        assert "when_to_use" in mermaid
        assert len(mermaid["when_to_use"]) >= 3

    def test_tutor_widget_subsection(self):
        from app.prompts.prompt_loader import PromptLoader
        loader = PromptLoader()
        persona = loader.get_persona("student")
        widget = persona["visual"]["widget"]
        assert "when_to_use" in widget
        assert "rules" in widget
        assert len(widget["when_to_use"]) >= 3

    def test_rag_has_visual_section(self):
        import yaml
        from pathlib import Path
        rag_path = Path(__file__).parent.parent.parent / "app" / "prompts" / "agents" / "rag.yaml"
        with open(rag_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert "visual" in data
        assert "mermaid" in data["visual"]
        assert "widget" in data["visual"]

    def test_direct_has_visual_section(self):
        import yaml
        from pathlib import Path
        path = Path(__file__).parent.parent.parent / "app" / "prompts" / "agents" / "direct.yaml"
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert "visual" in data
        assert "guidelines" in data["visual"]
        assert "widget" in data["visual"]

    def test_assistant_has_visual_section(self):
        import yaml
        from pathlib import Path
        path = Path(__file__).parent.parent.parent / "app" / "prompts" / "agents" / "assistant.yaml"
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert "visual" in data
        assert "philosophy" in data["visual"]
        assert "widget" in data["visual"]


# ============================================================================
# PromptLoader Visual Rendering
# ============================================================================


class TestPromptLoaderVisualRendering:
    """Verify PromptLoader renders visual section into system prompt."""

    def test_system_prompt_contains_visual_section(self):
        from app.prompts.prompt_loader import PromptLoader
        loader = PromptLoader()
        prompt = loader.build_system_prompt("student")
        assert "TRỰC QUAN HÓA" in prompt

    def test_visual_section_has_mermaid_instruction(self):
        from app.prompts.prompt_loader import PromptLoader
        loader = PromptLoader()
        prompt = loader.build_system_prompt("student")
        assert "mermaid" in prompt.lower() or "MERMAID" in prompt

    def test_visual_section_has_widget_instruction(self):
        """Sprint 228: Widget instructions should appear in system prompt."""
        from app.prompts.prompt_loader import PromptLoader
        loader = PromptLoader()
        prompt = loader.build_system_prompt("student")
        assert "widget" in prompt.lower() or "WIDGET" in prompt

    def test_visual_section_has_flowchart(self):
        from app.prompts.prompt_loader import PromptLoader
        loader = PromptLoader()
        prompt = loader.build_system_prompt("student")
        assert "flowchart" in prompt

    def test_visual_section_has_chart_js_reference(self):
        """Sprint 228: Widget instructions should reference Chart.js CDN."""
        from app.prompts.prompt_loader import PromptLoader
        loader = PromptLoader()
        prompt = loader.build_system_prompt("student")
        assert "chart.js" in prompt.lower() or "Chart.js" in prompt

    def test_no_visual_section_when_not_in_yaml(self):
        """If persona has no visual section, prompt should not have it."""
        import yaml
        from pathlib import Path
        memory_path = Path(__file__).parent.parent.parent / "app" / "prompts" / "agents" / "memory.yaml"
        with open(memory_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert "visual" not in data


# ============================================================================
# Chart Tools Default
# ============================================================================


class TestChartToolsDefault:
    """Verify chart_tools is enabled by default."""

    def test_chart_tools_enabled_by_default(self):
        from app.core.config import Settings
        s = Settings(_env_file=None)
        assert s.enable_chart_tools is True

    def test_get_chart_tools_returns_tools(self):
        mock_settings = MagicMock()
        mock_settings.enable_chart_tools = True
        with patch("app.core.config.get_settings", return_value=mock_settings):
            from app.engine.tools.chart_tools import get_chart_tools
            tools = get_chart_tools()
            assert len(tools) == 3  # mermaid + chart + interactive_chart

    def test_get_chart_tools_empty_when_disabled(self):
        mock_settings = MagicMock()
        mock_settings.enable_chart_tools = False
        with patch("app.core.config.get_settings", return_value=mock_settings):
            from app.engine.tools.chart_tools import get_chart_tools
            tools = get_chart_tools()
            assert len(tools) == 0

    def test_interactive_chart_tool_exists(self):
        """Sprint 228: tool_generate_interactive_chart should be in chart_tools."""
        mock_settings = MagicMock()
        mock_settings.enable_chart_tools = True
        with patch("app.core.config.get_settings", return_value=mock_settings):
            from app.engine.tools.chart_tools import get_chart_tools
            tools = get_chart_tools()
            tool_names = [t.name for t in tools]
            assert "tool_generate_interactive_chart" in tool_names


# ============================================================================
# Tutor Visual Examples (Mermaid + Widget)
# ============================================================================


class TestTutorVisualExample:
    """Verify tutor.yaml has visual-first examples with Mermaid and Widget."""

    def test_tutor_has_mermaid_example(self):
        import yaml
        from pathlib import Path
        path = Path(__file__).parent.parent.parent / "app" / "prompts" / "agents" / "tutor.yaml"
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        examples = data.get("examples", [])
        mermaid_examples = [
            ex for ex in examples
            if "mermaid" in ex.get("output", "")
        ]
        assert len(mermaid_examples) >= 1, "tutor.yaml should have at least 1 Mermaid example"

    def test_tutor_mermaid_example_has_flowchart(self):
        import yaml
        from pathlib import Path
        path = Path(__file__).parent.parent.parent / "app" / "prompts" / "agents" / "tutor.yaml"
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        examples = data.get("examples", [])
        mermaid_examples = [
            ex for ex in examples
            if "flowchart" in ex.get("output", "")
        ]
        assert len(mermaid_examples) >= 1

    def test_tutor_has_widget_example(self):
        """Sprint 228: tutor.yaml should have at least 1 interactive widget example."""
        import yaml
        from pathlib import Path
        path = Path(__file__).parent.parent.parent / "app" / "prompts" / "agents" / "tutor.yaml"
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        examples = data.get("examples", [])
        widget_examples = [
            ex for ex in examples
            if "widget" in ex.get("output", "")
        ]
        assert len(widget_examples) >= 1, "tutor.yaml should have at least 1 widget example"

    def test_tutor_widget_example_has_chart_js(self):
        """Sprint 228: Widget example should use Chart.js."""
        import yaml
        from pathlib import Path
        path = Path(__file__).parent.parent.parent / "app" / "prompts" / "agents" / "tutor.yaml"
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        examples = data.get("examples", [])
        chartjs_examples = [
            ex for ex in examples
            if "chart.js" in ex.get("output", "").lower() or "Chart(" in ex.get("output", "")
        ]
        assert len(chartjs_examples) >= 1, "tutor.yaml should have widget example with Chart.js"


# ============================================================================
# Widget YAML Configuration
# ============================================================================


class TestWidgetYAMLConfig:
    """Verify widget configuration is correct across all agents."""

    def _load_yaml(self, agent_name: str):
        import yaml
        from pathlib import Path
        path = Path(__file__).parent.parent.parent / "app" / "prompts" / "agents" / f"{agent_name}.yaml"
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def test_all_agents_have_widget_rules(self):
        """All visual agents should have widget rules."""
        for agent in ["tutor", "rag", "direct", "assistant"]:
            data = self._load_yaml(agent)
            widget = data.get("visual", {}).get("widget", {})
            assert "when_to_use" in widget, f"{agent}.yaml should have widget.when_to_use"

    def test_widget_format_mentions_code_block(self):
        """Widget format should mention code block syntax."""
        for agent in ["tutor", "rag", "direct", "assistant"]:
            data = self._load_yaml(agent)
            widget = data.get("visual", {}).get("widget", {})
            fmt = widget.get("format", "")
            assert "widget" in fmt.lower(), f"{agent}.yaml widget.format should mention 'widget'"

    def test_visual_guidelines_mention_priority(self):
        """Guidelines should establish text → mermaid → widget priority."""
        for agent in ["tutor", "rag", "direct", "assistant"]:
            data = self._load_yaml(agent)
            guidelines = data.get("visual", {}).get("guidelines", [])
            priority_mentioned = any(
                "text" in g.lower() and "mermaid" in g.lower() and "widget" in g.lower()
                for g in guidelines
            )
            assert priority_mentioned, f"{agent}.yaml should have priority guideline"


# ============================================================================
# Interactive Chart Tool (Sprint 228)
# ============================================================================


class TestInteractiveChartTool:
    """Verify tool_generate_interactive_chart works correctly."""

    def test_generates_widget_code_block(self):
        """Tool output should contain ```widget code block."""
        from app.engine.tools.chart_tools import tool_generate_interactive_chart
        result = tool_generate_interactive_chart.invoke({
            "chart_type": "bar",
            "labels_json": '["A", "B", "C"]',
            "datasets_json": '[{"label": "Test", "data": [10, 20, 30]}]',
            "title": "Test Chart",
        })
        assert "```widget" in result
        assert "chart.js" in result.lower()
        assert "Chart(" in result or "Chart(" in result

    def test_generates_pie_chart(self):
        from app.engine.tools.chart_tools import tool_generate_interactive_chart
        result = tool_generate_interactive_chart.invoke({
            "chart_type": "pie",
            "labels_json": '["Red", "Blue"]',
            "datasets_json": '[{"label": "Colors", "data": [60, 40]}]',
            "title": "Pie Chart",
        })
        assert "```widget" in result
        assert "'pie'" in result

    def test_generates_doughnut_chart(self):
        from app.engine.tools.chart_tools import tool_generate_interactive_chart
        result = tool_generate_interactive_chart.invoke({
            "chart_type": "doughnut",
            "labels_json": '["X", "Y"]',
            "datasets_json": '[{"label": "D", "data": [70, 30]}]',
        })
        assert "```widget" in result
        assert "'doughnut'" in result

    def test_invalid_chart_type_defaults_to_bar(self):
        from app.engine.tools.chart_tools import tool_generate_interactive_chart
        result = tool_generate_interactive_chart.invoke({
            "chart_type": "invalid",
            "labels_json": '["A"]',
            "datasets_json": '[{"label": "T", "data": [1]}]',
        })
        assert "'bar'" in result

    def test_invalid_json_returns_error(self):
        from app.engine.tools.chart_tools import tool_generate_interactive_chart
        result = tool_generate_interactive_chart.invoke({
            "chart_type": "bar",
            "labels_json": "not json",
            "datasets_json": '[{"label": "T", "data": [1]}]',
        })
        assert "Error" in result

    def test_horizontal_bar_uses_index_axis(self):
        from app.engine.tools.chart_tools import tool_generate_interactive_chart
        result = tool_generate_interactive_chart.invoke({
            "chart_type": "horizontalBar",
            "labels_json": '["A", "B"]',
            "datasets_json": '[{"label": "H", "data": [5, 10]}]',
        })
        assert "```widget" in result
        assert "'bar'" in result  # converted to bar
        assert "indexAxis" in result  # with y axis

    def test_vietnamese_labels_preserved(self):
        from app.engine.tools.chart_tools import tool_generate_interactive_chart
        result = tool_generate_interactive_chart.invoke({
            "chart_type": "pie",
            "labels_json": '["Lỗi con người", "Hỏng thiết bị", "Thời tiết"]',
            "datasets_json": '[{"label": "Tai nạn", "data": [80, 10, 10]}]',
            "title": "Phân bố tai nạn",
        })
        assert "Lỗi con người" in result
        assert "Phân bố tai nạn" in result
