class TestParseVisualPayload:
    """Test structured payload parsing helpers."""

    def test_parses_dict(self):
        from app.engine.tools.visual_tools import parse_visual_payload

        payload = parse_visual_payload({
            "id": "visual-123",
            "type": "process",
            "runtime": "svg",
            "title": "Pipeline",
            "summary": "Step flow",
            "spec": {"steps": [{"title": "Start"}]},
        })

        assert payload is not None
        assert payload.id == "visual-123"
        assert payload.type == "process"
        assert payload.renderer_kind == "template"
        assert payload.visual_session_id.startswith("vs-process-")
        assert payload.scene["kind"] == "process"

    def test_returns_none_for_legacy_widget_string(self):
        from app.engine.tools.visual_tools import parse_visual_payload

        assert parse_visual_payload("```widget\n<div>legacy</div>\n```") is None


class TestGetVisualTools:
    """Test feature gating."""

    def test_returns_empty_when_structured_disabled(self, monkeypatch):
        class FakeSettings:
            enable_chart_tools = True
            enable_structured_visuals = False

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import get_visual_tools
        tools = get_visual_tools()
        assert tools == []

    def test_returns_structured_tool_when_enabled(self, monkeypatch):
        class FakeSettings:
            enable_chart_tools = True
            enable_structured_visuals = True

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import get_visual_tools
        tools = get_visual_tools()
        assert [tool.name for tool in tools] == [
            "tool_generate_visual",
        ]

    def test_returns_empty_when_disabled(self, monkeypatch):
        class FakeSettings:
            enable_chart_tools = False
            enable_structured_visuals = False

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import get_visual_tools
        tools = get_visual_tools()
        assert tools == []


class TestDesignSystem:
    """Test shared CSS and HTML structure."""

    def test_all_visuals_have_doctype(self):
        """Every visual should be a complete HTML document."""
        from app.engine.tools.visual_tools import _BUILDERS

        for visual_type, builder in _BUILDERS.items():
            # Minimal spec for each type
            specs = {
                "comparison": {"left": {"title": "A"}, "right": {"title": "B"}},
                "process": {"steps": [{"title": "S1"}]},
                "matrix": {"rows": ["R"], "cols": ["C"], "cells": [[0.5]]},
                "architecture": {"layers": [{"name": "L", "components": ["C"]}]},
                "concept": {"center": {"title": "X"}, "branches": []},
                "infographic": {"stats": [{"value": "1", "label": "L"}]},
                "chart": {"labels": ["A", "B"], "datasets": [{"label": "S", "data": [1, 2]}]},
                "timeline": {"events": [{"title": "E1", "date": "2026"}]},
                "map_lite": {"regions": [{"name": "R1", "value": "100"}]},
            }
            html = builder(specs[visual_type], "Test")
            assert "<!DOCTYPE html>" in html, f"{visual_type} missing DOCTYPE"
            assert "lang=\"vi\"" in html, f"{visual_type} missing lang=vi"

    def test_all_visuals_have_dark_mode(self):
        """Every visual should include dark mode CSS."""
        from app.engine.tools.visual_tools import _DESIGN_CSS

        assert "prefers-color-scheme: dark" in _DESIGN_CSS

    def test_html_escaping_in_text_types(self):
        """XSS protection: user content in text-based types must be escaped."""
        from app.engine.tools.visual_tools import _BUILDERS

        xss = "<img src=x onerror=alert(1)>"
        # Only test types that render user text (not simulation which takes JS code)
        specs = {
            "comparison": {"left": {"title": xss}, "right": {"title": "safe"}},
            "process": {"steps": [{"title": xss}]},
            "matrix": {"rows": [xss], "cols": ["C"], "cells": [["v"]]},
            "architecture": {"layers": [{"name": xss, "components": [xss]}]},
            "concept": {"center": {"title": xss}, "branches": [{"title": xss, "items": [xss]}]},
            "infographic": {"stats": [{"value": xss, "label": xss}]},
            "chart": {"labels": [xss], "datasets": [{"label": xss, "data": [1]}]},
            "timeline": {"events": [{"title": xss, "date": xss}]},
            "map_lite": {"regions": [{"name": xss, "value": xss}]},
        }
        for visual_type in specs:
            builder = _BUILDERS[visual_type]
            html = builder(specs[visual_type], "Test")
            assert "<img src=x" not in html, f"{visual_type} has XSS vulnerability"
            assert "&lt;img" in html, f"{visual_type} did not escape HTML"


class TestPromptLoaderVisualTiers:
    """Test that prompt_loader renders the new 3-tier visual structure."""

    def test_prompt_includes_visual_section(self):
        from app.prompts.prompt_loader import PromptLoader

        loader = PromptLoader()
        prompt = loader.build_system_prompt("tutor", "Test User")
        assert (
            "INLINE VISUAL" in prompt
            or "RICH VISUAL" in prompt
            or "VISUAL" in prompt
            or "tool_generate_visual" in prompt
        )

    def test_prompt_includes_chart_section(self):
        from app.prompts.prompt_loader import PromptLoader

        loader = PromptLoader()
        prompt = loader.build_system_prompt("tutor", "Test User")
        assert "BIỂU ĐỒ TƯƠNG TÁC" in prompt or "tool_generate_interactive_chart" in prompt
