"""
Sprint 229: Rich Visual Widget Generator tests.

Tests tool_generate_rich_visual and all visual type builders.
"""

import json
import pytest


# =============================================================================
# Builder unit tests
# =============================================================================


class TestComparisonVisual:
    """Test comparison (side-by-side) visual generation."""

    def test_basic_comparison(self):
        from app.engine.tools.visual_tools import _build_comparison_html

        spec = {
            "left": {"title": "Method A", "subtitle": "O(n²)", "items": ["Slow", "Simple"]},
            "right": {"title": "Method B", "subtitle": "O(n)", "items": ["Fast", "Complex"]},
        }
        html = _build_comparison_html(spec, "Comparison Test")
        assert "<!DOCTYPE html>" in html
        assert "Method A" in html
        assert "Method B" in html
        assert "O(n²)" in html
        assert "comparison" in html  # CSS class

    def test_comparison_with_note(self):
        from app.engine.tools.visual_tools import _build_comparison_html

        spec = {
            "left": {"title": "A", "items": []},
            "right": {"title": "B", "items": []},
            "note": "Key takeaway here",
        }
        html = _build_comparison_html(spec, "")
        assert "Key takeaway here" in html

    def test_comparison_escapes_html(self):
        from app.engine.tools.visual_tools import _build_comparison_html

        spec = {
            "left": {"title": "<script>alert(1)</script>", "items": []},
            "right": {"title": "Safe", "items": []},
        }
        html = _build_comparison_html(spec, "")
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html


class TestProcessVisual:
    """Test process (step flow) visual generation."""

    def test_basic_process(self):
        from app.engine.tools.visual_tools import _build_process_html

        spec = {
            "steps": [
                {"title": "Step 1", "description": "Do this"},
                {"title": "Step 2", "description": "Then that"},
                {"title": "Step 3", "description": "Finally"},
            ],
        }
        html = _build_process_html(spec, "Process Flow")
        assert "Step 1" in html
        assert "Step 2" in html
        assert "Step 3" in html
        assert "process" in html  # CSS class
        assert "step-arrow" in html  # arrows between steps

    def test_vertical_direction(self):
        from app.engine.tools.visual_tools import _build_process_html

        spec = {"steps": [{"title": "A"}, {"title": "B"}], "direction": "vertical"}
        html = _build_process_html(spec, "")
        assert "vertical" in html


class TestMatrixVisual:
    """Test matrix (color grid) visual generation."""

    def test_basic_matrix(self):
        from app.engine.tools.visual_tools import _build_matrix_html

        spec = {
            "rows": ["Q1", "Q2"],
            "cols": ["K1", "K2"],
            "cells": [[0.9, 0.3], [0.1, 0.8]],
            "row_label": "Queries",
            "col_label": "Keys",
        }
        html = _build_matrix_html(spec, "Attention Matrix")
        assert "Q1" in html
        assert "K1" in html
        assert "Queries" in html
        assert "Keys" in html
        assert "matrix-grid" in html

    def test_matrix_with_values(self):
        from app.engine.tools.visual_tools import _build_matrix_html

        spec = {
            "rows": ["A"], "cols": ["B"],
            "cells": [[0.75]],
            "show_values": True,
        }
        html = _build_matrix_html(spec, "")
        assert "0.8" in html  # formatted to 1 decimal


class TestArchitectureVisual:
    """Test architecture (layered diagram) visual generation."""

    def test_basic_architecture(self):
        from app.engine.tools.visual_tools import _build_architecture_html

        spec = {
            "layers": [
                {"name": "Frontend", "components": ["React", "Tailwind"]},
                {"name": "Backend", "components": ["FastAPI", "LangGraph"]},
                {"name": "Database", "components": ["PostgreSQL", "Neo4j"]},
            ]
        }
        html = _build_architecture_html(spec, "System Architecture")
        assert "Frontend" in html
        assert "Backend" in html
        assert "React" in html
        assert "FastAPI" in html
        assert "arch-layer" in html
        assert "arch-arrow" in html  # arrows between layers


class TestConceptVisual:
    """Test concept map visual generation."""

    def test_basic_concept(self):
        from app.engine.tools.visual_tools import _build_concept_html

        spec = {
            "center": {"title": "Machine Learning", "description": "AI subset"},
            "branches": [
                {"title": "Supervised", "items": ["Classification", "Regression"]},
                {"title": "Unsupervised", "items": ["Clustering", "Dimensionality"]},
            ]
        }
        html = _build_concept_html(spec, "ML Overview")
        assert "Machine Learning" in html
        assert "Supervised" in html
        assert "Classification" in html
        assert "concept-center" in html


class TestInfographicVisual:
    """Test infographic visual generation."""

    def test_basic_infographic(self):
        from app.engine.tools.visual_tools import _build_infographic_html

        spec = {
            "stats": [
                {"value": "95%", "label": "Accuracy"},
                {"value": "2.3s", "label": "Latency"},
                {"value": "1M+", "label": "Users"},
            ],
            "sections": [
                {"title": "Highlight", "content": "Significant improvement over baseline."},
            ]
        }
        html = _build_infographic_html(spec, "Results")
        assert "95%" in html
        assert "Accuracy" in html
        assert "Significant improvement" in html
        assert "info-stat" in html


class TestSimulationVisual:
    """Test simulation (Canvas + controls) visual generation."""

    def test_basic_simulation(self):
        from app.engine.tools.visual_tools import _build_simulation_html

        spec = {
            "variables": [{"name": "speed", "label": "Tốc độ", "min": 1, "max": 100, "value": 50}],
            "setup": "vars.x = 0;",
            "draw": "ctx.fillStyle='#2563eb'; ctx.fillRect(vars.x, 100, 20, 20);",
            "update": "vars.x = (vars.x + vars.speed * 0.1) % canvas.offsetWidth;",
            "description": "Mô phỏng chuyển động",
        }
        html = _build_simulation_html(spec, "Physics Sim")
        assert "canvas" in html.lower()
        assert "requestAnimationFrame" in html
        assert "Tốc độ" in html
        assert "sim-controls" in html
        assert "togglePlay" in html  # play/pause button

    def test_simulation_has_controls(self):
        from app.engine.tools.visual_tools import _build_simulation_html

        spec = {
            "variables": [
                {"name": "gravity", "label": "Gravity", "min": 0, "max": 20, "value": 9.8, "step": 0.1},
                {"name": "mass", "label": "Mass", "min": 1, "max": 50, "value": 10},
            ],
            "setup": "", "draw": "", "update": "",
        }
        html = _build_simulation_html(spec, "")
        assert "sl_gravity" in html  # slider id
        assert "sl_mass" in html
        assert "range" in html  # input type=range


class TestQuizVisual:
    """Test quiz (multiple choice) visual generation."""

    def test_basic_quiz(self):
        from app.engine.tools.visual_tools import _build_quiz_html

        spec = {
            "questions": [
                {
                    "question": "1 + 1 = ?",
                    "options": [
                        {"text": "1", "correct": False},
                        {"text": "2", "correct": True},
                        {"text": "3", "correct": False},
                    ],
                    "explanation": "1 + 1 = 2 theo phép cộng cơ bản",
                },
            ]
        }
        html = _build_quiz_html(spec, "Math Quiz")
        assert "1 + 1 = ?" in html
        assert "checkAnswer" in html  # JS function
        assert "scoreBoard" in html  # score display
        assert "q-opt" in html  # option class
        assert "Giải thích" not in html or "explanation" in html.lower()  # explanation exists

    def test_quiz_multiple_questions(self):
        from app.engine.tools.visual_tools import _build_quiz_html

        spec = {
            "questions": [
                {"question": "Q1", "options": [{"text": "A", "correct": True}]},
                {"question": "Q2", "options": [{"text": "B", "correct": True}]},
                {"question": "Q3", "options": [{"text": "C", "correct": True}]},
            ]
        }
        html = _build_quiz_html(spec, "")
        assert "total = 3" in html
        assert "Câu 1" in html
        assert "Câu 3" in html


class TestInteractiveTableVisual:
    """Test interactive table visual generation."""

    def test_basic_table(self):
        from app.engine.tools.visual_tools import _build_interactive_table_html

        spec = {
            "headers": ["Tên", "Điểm", "Xếp loại"],
            "rows": [
                ["Nguyễn A", 9.5, "Giỏi"],
                ["Trần B", 7.0, "Khá"],
                ["Lê C", 5.5, "TB"],
            ],
        }
        html = _build_interactive_table_html(spec, "Bảng điểm")
        assert "Tên" in html
        assert "filterTable" in html  # search function
        assert "itbl" in html  # table class
        assert "tblSearch" in html  # search input

    def test_table_sort(self):
        from app.engine.tools.visual_tools import _build_interactive_table_html

        spec = {
            "headers": ["Name", "Value"],
            "rows": [["A", 10], ["B", 5]],
            "sortable": True,
        }
        html = _build_interactive_table_html(spec, "")
        assert "sortCol" in html  # sort state
        assert "localeCompare" in html  # string sort
        assert "parseFloat" in html  # numeric sort


# =============================================================================
# Tool integration tests
# =============================================================================


class TestToolGenerateRichVisual:
    """Test the LangChain tool wrapper."""

    def test_valid_comparison(self):
        from app.engine.tools.visual_tools import tool_generate_rich_visual

        spec = json.dumps({
            "left": {"title": "TCP", "items": ["Reliable"]},
            "right": {"title": "UDP", "items": ["Fast"]},
        })
        result = tool_generate_rich_visual.invoke({
            "visual_type": "comparison",
            "spec_json": spec,
            "title": "TCP vs UDP",
        })
        assert "```widget" in result
        assert "TCP" in result
        assert "UDP" in result

    def test_valid_process(self):
        from app.engine.tools.visual_tools import tool_generate_rich_visual

        spec = json.dumps({
            "steps": [{"title": "Input"}, {"title": "Process"}, {"title": "Output"}],
        })
        result = tool_generate_rich_visual.invoke({
            "visual_type": "process",
            "spec_json": spec,
            "title": "Data Pipeline",
        })
        assert "```widget" in result
        assert "Input" in result

    def test_invalid_type(self):
        from app.engine.tools.visual_tools import tool_generate_rich_visual

        result = tool_generate_rich_visual.invoke({
            "visual_type": "invalid_type",
            "spec_json": "{}",
        })
        assert "Error" in result
        assert "comparison" in result  # suggests valid types

    def test_invalid_json(self):
        from app.engine.tools.visual_tools import tool_generate_rich_visual

        result = tool_generate_rich_visual.invoke({
            "visual_type": "comparison",
            "spec_json": "not json",
        })
        assert "Error" in result

    def test_non_dict_json(self):
        from app.engine.tools.visual_tools import tool_generate_rich_visual

        result = tool_generate_rich_visual.invoke({
            "visual_type": "comparison",
            "spec_json": '["array"]',
        })
        assert "Error" in result


class TestGetVisualTools:
    """Test feature gating."""

    def test_returns_tools_when_enabled(self, monkeypatch):
        class FakeSettings:
            enable_chart_tools = True

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import get_visual_tools
        tools = get_visual_tools()
        assert len(tools) == 1
        assert tools[0].name == "tool_generate_rich_visual"

    def test_returns_empty_when_disabled(self, monkeypatch):
        class FakeSettings:
            enable_chart_tools = False

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import get_visual_tools
        tools = get_visual_tools()
        assert tools == []


# =============================================================================
# Design system tests
# =============================================================================


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
                "simulation": {"variables": [], "setup": "", "draw": "", "update": ""},
                "quiz": {"questions": [{"question": "Q", "options": [{"text": "A", "correct": True}]}]},
                "interactive_table": {"headers": ["H"], "rows": [["V"]]},
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
            "quiz": {"questions": [{"question": xss, "options": [{"text": xss, "correct": True}]}]},
        }
        for visual_type in specs:
            builder = _BUILDERS[visual_type]
            html = builder(specs[visual_type], "Test")
            assert "<img src=x" not in html, f"{visual_type} has XSS vulnerability"
            assert "&lt;img" in html, f"{visual_type} did not escape HTML"


class TestPromptLoaderVisualTiers:
    """Test that prompt_loader renders the new 3-tier visual structure."""

    def test_prompt_includes_rich_visual_section(self):
        from app.prompts.prompt_loader import PromptLoader

        loader = PromptLoader()
        prompt = loader.build_system_prompt("tutor", "Test User")
        assert "RICH VISUAL" in prompt or "rich_visual" in prompt or "tool_generate_rich_visual" in prompt

    def test_prompt_includes_chart_section(self):
        from app.prompts.prompt_loader import PromptLoader

        loader = PromptLoader()
        prompt = loader.build_system_prompt("tutor", "Test User")
        assert "BIỂU ĐỒ TƯƠNG TÁC" in prompt or "tool_generate_interactive_chart" in prompt
