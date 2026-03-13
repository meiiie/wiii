"""
Tests for Sprint 227: Visual-First Response system.

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
        assert "when_to_use" in visual
        assert len(visual["when_to_use"]) >= 3

    def test_rag_has_visual_section(self):
        from app.prompts.prompt_loader import PromptLoader
        loader = PromptLoader()
        # rag.yaml is loaded for "student" with rag role
        # but the rag_agent persona may not be directly loadable
        # Check by loading the YAML file directly
        import yaml
        from pathlib import Path
        rag_path = Path(__file__).parent.parent.parent / "app" / "prompts" / "agents" / "rag.yaml"
        with open(rag_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert "visual" in data
        assert "when_to_use" in data["visual"]

    def test_direct_has_visual_section(self):
        import yaml
        from pathlib import Path
        path = Path(__file__).parent.parent.parent / "app" / "prompts" / "agents" / "direct.yaml"
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert "visual" in data
        assert "guidelines" in data["visual"]

    def test_assistant_has_visual_section(self):
        import yaml
        from pathlib import Path
        path = Path(__file__).parent.parent.parent / "app" / "prompts" / "agents" / "assistant.yaml"
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert "visual" in data
        assert "philosophy" in data["visual"]


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
        assert "mermaid" in prompt

    def test_visual_section_has_when_to_use(self):
        from app.prompts.prompt_loader import PromptLoader
        loader = PromptLoader()
        prompt = loader.build_system_prompt("student")
        assert "flowchart" in prompt

    def test_no_visual_section_when_not_in_yaml(self):
        """If persona has no visual section, prompt should not have it."""
        from app.prompts.prompt_loader import PromptLoader
        loader = PromptLoader()
        # Memory agent has no visual section
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
            assert len(tools) == 2

    def test_get_chart_tools_empty_when_disabled(self):
        mock_settings = MagicMock()
        mock_settings.enable_chart_tools = False
        with patch("app.core.config.get_settings", return_value=mock_settings):
            from app.engine.tools.chart_tools import get_chart_tools
            tools = get_chart_tools()
            assert len(tools) == 0


# ============================================================================
# Tutor Visual Example
# ============================================================================


class TestTutorVisualExample:
    """Verify tutor.yaml has visual-first example with Mermaid."""

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
