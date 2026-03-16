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


class TestReactAppVisual:
    """Test React app (Claude-level architecture) visual generation."""

    def test_basic_react_app(self):
        from app.engine.tools.visual_tools import _build_react_app_html

        spec = {
            "code": "function App() { const [count, setCount] = React.useState(0); return React.createElement('div', null, React.createElement('h1', null, 'Count: ' + count), React.createElement('button', {onClick: () => setCount(c => c+1)}, '+1')); }"
        }
        html = _build_react_app_html(spec, "Counter App")
        assert "react@18" in html  # React CDN
        assert "react-dom@18" in html  # ReactDOM CDN
        assert "babel" in html.lower()  # Babel for JSX
        assert "tailwindcss" in html  # Tailwind CDN
        assert "Recharts" in html  # Recharts CDN
        assert "Counter App" in html  # title
        assert "function App()" in html  # component code
        assert 'type="text/babel"' in html  # JSX script type

    def test_react_app_no_code_returns_error(self):
        from app.engine.tools.visual_tools import _build_react_app_html

        html = _build_react_app_html({}, "Test")
        assert "Error" in html

    def test_react_app_with_recharts(self):
        from app.engine.tools.visual_tools import _build_react_app_html

        spec = {
            "code": """function App() {
  const data = [{name: 'A', value: 400}, {name: 'B', value: 300}];
  return React.createElement('div', {className: 'p-4'},
    React.createElement(BarChart, {width: 400, height: 200, data: data},
      React.createElement(Bar, {dataKey: 'value', fill: '#2563eb'})
    )
  );
}"""
        }
        html = _build_react_app_html(spec, "Recharts Demo")
        assert "BarChart" in html
        assert "Recharts.min.js" in html


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


class TestToolGenerateVisual:
    """Test the structured visual payload tool."""

    def test_returns_visual_payload_json(self):
        from app.engine.tools.visual_tools import parse_visual_payload, tool_generate_visual

        result = tool_generate_visual.invoke({
            "visual_type": "comparison",
            "spec_json": json.dumps({
                "left": {"title": "Softmax"},
                "right": {"title": "Linear"},
            }),
            "title": "Softmax vs Linear",
            "summary": "Quick comparison",
        })
        payload = parse_visual_payload(result)

        assert payload is not None
        assert payload.type == "comparison"
        assert payload.renderer_kind == "template"
        assert payload.shell_variant == "editorial"
        assert payload.patch_strategy == "spec_merge"
        assert payload.runtime == "svg"
        assert payload.title == "Softmax vs Linear"
        assert payload.summary == "Quick comparison"
        assert payload.visual_session_id.startswith("vs-comparison-")
        assert payload.figure_group_id.startswith("fg-comparison-")
        assert payload.figure_index == 1
        assert payload.figure_total == 1
        assert payload.pedagogical_role == "comparison"
        assert payload.chrome_mode == "editorial"
        assert payload.claim == "Quick comparison"
        assert payload.scene["kind"] == "comparison"
        assert payload.controls[0]["id"] == "focus_side"
        assert payload.annotations
        assert payload.lifecycle_event == "visual_open"
        assert payload.fallback_html is not None
        assert payload.metadata["source_tool"] == "tool_generate_visual"

    def test_returns_grouped_figure_payloads_for_article_flow(self):
        from app.engine.tools.visual_tools import parse_visual_payloads, tool_generate_visual

        result = tool_generate_visual.invoke({
            "visual_type": "comparison",
            "spec_json": json.dumps({
                "figures": [
                    {
                        "type": "comparison",
                        "title": "Chi phi tinh toan",
                        "summary": "Softmax tang nhanh hon khi context dai ra.",
                        "claim": "Figure 1 chot van de chi phi tinh toan.",
                        "pedagogical_role": "problem",
                        "spec": {
                            "left": {"title": "Softmax attention"},
                            "right": {"title": "Linear attention"},
                        },
                    },
                    {
                        "type": "process",
                        "title": "Co che cap nhat bo nho",
                        "pedagogical_role": "mechanism",
                        "spec": {
                            "steps": [
                                {"title": "Doc token moi"},
                                {"title": "Cap nhat state S"},
                                {"title": "Sinh dau ra"},
                            ],
                        },
                    },
                ],
            }),
            "title": "Giai thich Kimi Linear",
        })
        payloads = parse_visual_payloads(result)

        assert len(payloads) == 2
        assert {payload.figure_index for payload in payloads} == {1, 2}
        assert {payload.figure_total for payload in payloads} == {2}
        assert len({payload.figure_group_id for payload in payloads}) == 1
        assert payloads[0].pedagogical_role == "problem"
        assert payloads[1].pedagogical_role == "mechanism"
        assert payloads[0].claim == "Figure 1 chot van de chi phi tinh toan."
        assert payloads[1].claim
        assert payloads[0].renderer_kind == "template"
        assert payloads[1].renderer_kind == "template"
        assert payloads[0].metadata["source_tool"] == "tool_generate_visual"
        assert payloads[1].metadata["source_tool"] == "tool_generate_visual"

    def test_supports_patch_operation_with_existing_session(self):
        from app.engine.tools.visual_tools import parse_visual_payload, tool_generate_visual

        result = tool_generate_visual.invoke({
            "visual_type": "process",
            "spec_json": json.dumps({
                "steps": [{"title": "Step 1"}, {"title": "Step 2"}],
            }),
            "visual_session_id": "vs-process-123",
            "operation": "patch",
        })
        payload = parse_visual_payload(result)

        assert payload is not None
        assert payload.visual_session_id == "vs-process-123"
        assert payload.lifecycle_event == "visual_patch"
        assert payload.patch_strategy == "spec_merge"
        assert payload.scene["kind"] == "process"

    def test_runtime_context_can_promote_followup_to_patch(self):
        from app.engine.tools.runtime_context import build_tool_runtime_context, tool_runtime_scope
        from app.engine.tools.visual_tools import parse_visual_payload, tool_generate_visual

        runtime = build_tool_runtime_context(
            session_id="session-1",
            user_id="user-1",
            user_role="admin",
            metadata={
                "preferred_visual_operation": "patch",
                "preferred_visual_session_id": "vs-comparison-keep",
            },
        )
        with tool_runtime_scope(runtime):
            result = tool_generate_visual.invoke({
                "visual_type": "comparison",
                "spec_json": json.dumps({
                    "left": {"title": "Before"},
                    "right": {"title": "After"},
                }),
                "operation": "open",
            })

        payload = parse_visual_payload(result)

        assert payload is not None
        assert payload.visual_session_id == "vs-comparison-keep"
        assert payload.lifecycle_event == "visual_patch"

    def test_runtime_context_overrides_hallucinated_patch_session_id(self):
        from app.engine.tools.runtime_context import build_tool_runtime_context, tool_runtime_scope
        from app.engine.tools.visual_tools import parse_visual_payload, tool_generate_visual

        runtime = build_tool_runtime_context(
            session_id="session-1",
            user_id="user-1",
            user_role="admin",
            metadata={
                "preferred_visual_operation": "patch",
                "preferred_visual_session_id": "vs-comparison-keep",
            },
        )
        with tool_runtime_scope(runtime):
            result = tool_generate_visual.invoke({
                "visual_type": "process",
                "spec_json": json.dumps({
                    "steps": [{"title": "One"}, {"title": "Two"}, {"title": "Three"}],
                }),
                "operation": "patch",
                "visual_session_id": "hallucinated-new-session",
            })

        payload = parse_visual_payload(result)

        assert payload is not None
        assert payload.visual_session_id == "vs-comparison-keep"
        assert payload.lifecycle_event == "visual_patch"

    def test_supports_app_runtime_types(self):
        from app.engine.tools.visual_tools import parse_visual_payload, tool_generate_visual

        result = tool_generate_visual.invoke({
            "visual_type": "simulation",
            "spec_json": json.dumps({
                "html": "<div>Sim</div>",
                "ui_runtime": "html",
            }),
        })
        payload = parse_visual_payload(result)

        assert payload is not None
        assert payload.renderer_kind == "app"
        assert payload.patch_strategy == "app_state"
        assert payload.chrome_mode == "app"
        assert payload.runtime_manifest["ui_runtime"] == "html"

    def test_supports_inline_html_renderer(self):
        from app.engine.tools.visual_tools import parse_visual_payload, tool_generate_visual

        result = tool_generate_visual.invoke({
            "visual_type": "concept",
            "spec_json": json.dumps({
                "html": "<section><h1>Custom inline visual</h1></section>",
            }),
            "renderer_kind": "inline_html",
        })
        payload = parse_visual_payload(result)

        assert payload is not None
        assert payload.renderer_kind == "inline_html"
        assert payload.patch_strategy == "replace_html"
        assert payload.fallback_html is not None

    def test_runtime_context_auto_groups_explanatory_template_visuals(self):
        from app.engine.tools.runtime_context import build_tool_runtime_context, tool_runtime_scope
        from app.engine.tools.visual_tools import parse_visual_payloads, tool_generate_visual

        runtime = build_tool_runtime_context(
            session_id="session-article-1",
            user_id="user-1",
            user_role="admin",
            metadata={
                "visual_force_tool": True,
                "visual_intent_mode": "template",
                "visual_intent_reason": "chart-template",
                "visual_user_query": "Explain Kimi linear attention in charts",
                "visual_requested_type": "chart",
            },
        )

        with tool_runtime_scope(runtime):
            result = tool_generate_visual.invoke({
                "visual_type": "chart",
                "spec_json": json.dumps({
                    "chart_type": "line",
                    "labels": ["1k", "4k", "16k", "64k"],
                    "datasets": [
                        {"label": "Softmax", "data": [1, 16, 256, 4096]},
                        {"label": "Linear", "data": [1, 4, 16, 64]},
                    ],
                }),
                "title": "Compute cost vs context length",
                "summary": "Softmax tang nhanh hon Linear khi context dai len.",
            })

        payloads = parse_visual_payloads(result)

        assert len(payloads) == 2
        assert {payload.figure_total for payload in payloads} == {2}
        assert len({payload.figure_group_id for payload in payloads}) == 1
        assert payloads[0].type == "chart"
        assert payloads[0].pedagogical_role == "benchmark"
        assert payloads[1].type == "infographic"
        assert payloads[1].pedagogical_role == "conclusion"
        assert payloads[1].claim.startswith("Điểm chốt của Compute cost vs context length")

    def test_runtime_context_can_plan_three_figures_for_dense_stepwise_explanation(self):
        from app.engine.tools.runtime_context import build_tool_runtime_context, tool_runtime_scope
        from app.engine.tools.visual_tools import parse_visual_payloads, tool_generate_visual

        runtime = build_tool_runtime_context(
            session_id="session-article-3",
            user_id="user-1",
            user_role="admin",
            metadata={
                "visual_force_tool": True,
                "visual_intent_mode": "template",
                "visual_intent_reason": "chart-template",
                "visual_user_query": "Explain Kimi linear attention in charts step by step with mechanism and benchmark",
                "visual_requested_type": "chart",
            },
        )

        with tool_runtime_scope(runtime):
            result = tool_generate_visual.invoke({
                "visual_type": "chart",
                "spec_json": json.dumps({
                    "chart_type": "line",
                    "labels": ["1k", "4k", "16k", "64k", "256k", "1M"],
                    "datasets": [
                        {"label": "Softmax", "data": [1, 16, 256, 4096, 65536, 1048576]},
                        {"label": "Linear", "data": [1, 4, 16, 64, 256, 1024]},
                    ],
                }),
                "title": "Compute cost vs context length",
                "summary": "Softmax tang nhanh hon Linear khi context dai len.",
            })

        payloads = parse_visual_payloads(result)

        assert len(payloads) == 3
        assert {payload.figure_total for payload in payloads} == {3}
        assert [payload.pedagogical_role for payload in payloads] == ["benchmark", "mechanism", "conclusion"]
        assert payloads[1].type == "infographic"
        assert payloads[2].type == "infographic"

    def test_runtime_context_keeps_simple_template_visual_single_when_scope_is_narrow(self):
        from app.engine.tools.runtime_context import build_tool_runtime_context, tool_runtime_scope
        from app.engine.tools.visual_tools import parse_visual_payloads, tool_generate_visual

        runtime = build_tool_runtime_context(
            session_id="session-article-simple-1",
            user_id="user-1",
            user_role="admin",
            metadata={
                "visual_force_tool": True,
                "visual_intent_mode": "template",
                "visual_intent_reason": "comparison",
                "visual_user_query": "So sanh nhanh TCP va UDP",
                "visual_requested_type": "comparison",
            },
        )

        with tool_runtime_scope(runtime):
            result = tool_generate_visual.invoke({
                "visual_type": "comparison",
                "spec_json": json.dumps({
                    "left": {"title": "TCP"},
                    "right": {"title": "UDP"},
                }),
                "title": "TCP vs UDP",
                "summary": "Dat TCP canh UDP de thay su khac nhau co ban.",
            })

        payloads = parse_visual_payloads(result)

        assert len(payloads) == 1
        assert payloads[0].figure_total == 1
        assert payloads[0].type == "comparison"

    def test_runtime_context_does_not_auto_group_app_runtime(self):
        from app.engine.tools.runtime_context import build_tool_runtime_context, tool_runtime_scope
        from app.engine.tools.visual_tools import parse_visual_payloads, tool_generate_visual

        runtime = build_tool_runtime_context(
            session_id="session-app-1",
            user_id="user-1",
            user_role="admin",
            metadata={
                "visual_force_tool": True,
                "visual_intent_mode": "app",
                "visual_intent_reason": "app-request",
                "visual_user_query": "Hay mo phong vat ly con lac",
                "visual_requested_type": "simulation",
            },
        )

        with tool_runtime_scope(runtime):
            result = tool_generate_visual.invoke({
                "visual_type": "simulation",
                "spec_json": json.dumps({
                    "html": "<div>Sim</div>",
                    "ui_runtime": "html",
                }),
            })

        payloads = parse_visual_payloads(result)

        assert len(payloads) == 1
        assert payloads[0].type == "simulation"
        assert payloads[0].renderer_kind == "app"
        assert payloads[0].figure_total == 1

    def test_runtime_context_auto_groups_infographic_explanations(self):
        from app.engine.tools.runtime_context import build_tool_runtime_context, tool_runtime_scope
        from app.engine.tools.visual_tools import parse_visual_payloads, tool_generate_visual

        runtime = build_tool_runtime_context(
            session_id="session-article-infographic-1",
            user_id="user-1",
            user_role="admin",
            metadata={
                "visual_force_tool": True,
                "visual_intent_mode": "template",
                "visual_intent_reason": "article-figure",
                "visual_user_query": "Explain Kimi linear attention in charts",
                "visual_requested_type": "infographic",
            },
        )

        with tool_runtime_scope(runtime):
            result = tool_generate_visual.invoke({
                "visual_type": "infographic",
                "spec_json": json.dumps({
                    "sections": [
                        {"title": "Van de", "content": "Softmax can ma tran day du O(n^2)."},
                        {"title": "Co che", "content": "Linear attention chuyen sang running state."},
                        {"title": "Ket qua", "content": "Context dai hon voi chi phi gon hon."},
                    ],
                }),
                "title": "Co che Linear Attention cua Kimi",
                "summary": "Ba diem nhan: van de, co che, va ket qua.",
            })

        payloads = parse_visual_payloads(result)

        assert len(payloads) == 2
        assert {payload.figure_total for payload in payloads} == {2}
        assert len({payload.figure_group_id for payload in payloads}) == 1
        assert payloads[0].type == "infographic"
        assert payloads[1].type == "infographic"
        assert payloads[1].pedagogical_role == "conclusion"

    def test_runtime_context_does_not_auto_group_patch_turn(self):
        from app.engine.tools.runtime_context import build_tool_runtime_context, tool_runtime_scope
        from app.engine.tools.visual_tools import parse_visual_payloads, tool_generate_visual

        runtime = build_tool_runtime_context(
            session_id="session-patch-1",
            user_id="user-1",
            user_role="admin",
            metadata={
                "visual_force_tool": True,
                "visual_intent_mode": "template",
                "visual_intent_reason": "comparison",
                "visual_user_query": "Giu visual hien tai va highlight bottleneck",
                "preferred_visual_operation": "patch",
                "preferred_visual_session_id": "vs-comparison-keep",
            },
        )

        with tool_runtime_scope(runtime):
            result = tool_generate_visual.invoke({
                "visual_type": "comparison",
                "spec_json": json.dumps({
                    "left": {"title": "Before"},
                    "right": {"title": "After"},
                }),
                "operation": "open",
            })

        payloads = parse_visual_payloads(result)

        assert len(payloads) == 1
        assert payloads[0].lifecycle_event == "visual_patch"
        assert payloads[0].visual_session_id == "vs-comparison-keep"

    def test_generates_natural_default_summary_and_takeaway_annotation(self):
        from app.engine.tools.visual_tools import parse_visual_payload, tool_generate_visual

        result = tool_generate_visual.invoke({
            "visual_type": "comparison",
            "spec_json": json.dumps({
                "left": {"title": "Softmax attention"},
                "right": {"title": "Linear attention"},
            }),
            "title": "Softmax vs Linear",
        })
        payload = parse_visual_payload(result)

        assert payload is not None
        assert payload.summary == "Đặt Softmax attention cạnh Linear attention để thấy điểm khác biệt chính."
        assert payload.annotations[0]["title"] == "Điểm chốt"


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

    def test_returns_legacy_tool_when_structured_disabled(self, monkeypatch):
        class FakeSettings:
            enable_chart_tools = True
            enable_structured_visuals = False

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import get_visual_tools
        tools = get_visual_tools()
        assert len(tools) == 1
        assert tools[0].name == "tool_generate_rich_visual"

    def test_returns_structured_and_legacy_tools_when_enabled(self, monkeypatch):
        class FakeSettings:
            enable_chart_tools = True
            enable_structured_visuals = True

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import get_visual_tools
        tools = get_visual_tools()
        assert [tool.name for tool in tools] == [
            "tool_generate_visual",
            "tool_generate_rich_visual",
        ]

    def test_returns_empty_when_disabled(self, monkeypatch):
        class FakeSettings:
            enable_chart_tools = False
            enable_structured_visuals = False

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
                "chart": {"labels": ["A", "B"], "datasets": [{"label": "S", "data": [1, 2]}]},
                "timeline": {"events": [{"title": "E1", "date": "2026"}]},
                "map_lite": {"regions": [{"name": "R1", "value": "100"}]},
                "simulation": {"variables": [], "setup": "", "draw": "", "update": ""},
                "quiz": {"questions": [{"question": "Q", "options": [{"text": "A", "correct": True}]}]},
                "interactive_table": {"headers": ["H"], "rows": [["V"]]},
                "react_app": {"code": "function App() { return React.createElement('div', null, 'Hello'); }"},
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
        assert (
            "INLINE VISUAL" in prompt
            or "RICH VISUAL" in prompt
            or "tool_generate_visual" in prompt
            or "tool_generate_rich_visual" in prompt
        )

    def test_prompt_includes_chart_section(self):
        from app.prompts.prompt_loader import PromptLoader

        loader = PromptLoader()
        prompt = loader.build_system_prompt("tutor", "Test User")
        assert "BIỂU ĐỒ TƯƠNG TÁC" in prompt or "tool_generate_interactive_chart" in prompt


# =============================================================================
# New builder tests (chart, timeline, map_lite)
# =============================================================================


class TestChartVisual:
    """Test chart (SVG bar/line) visual generation."""

    def test_basic_bar_chart(self):
        from app.engine.tools.visual_tools import _build_chart_html

        spec = {
            "labels": ["Q1", "Q2", "Q3"],
            "datasets": [{"label": "Revenue", "data": [100, 200, 150]}],
        }
        html = _build_chart_html(spec, "Revenue Chart")
        assert "<!DOCTYPE html>" in html
        assert "Revenue" in html
        assert "Q1" in html
        assert "<svg" in html
        assert "chart-legend" in html

    def test_line_chart(self):
        from app.engine.tools.visual_tools import _build_chart_html

        spec = {
            "chart_type": "line",
            "labels": ["Jan", "Feb"],
            "datasets": [{"label": "Growth", "data": [10, 20]}],
        }
        html = _build_chart_html(spec, "Growth")
        assert "<path" in html  # line path
        assert "<circle" in html  # data points

    def test_multi_dataset_chart(self):
        from app.engine.tools.visual_tools import _build_chart_html

        spec = {
            "labels": ["A", "B"],
            "datasets": [
                {"label": "Series 1", "data": [10, 20]},
                {"label": "Series 2", "data": [15, 25]},
            ],
        }
        html = _build_chart_html(spec, "Multi")
        assert "Series 1" in html
        assert "Series 2" in html

    def test_empty_chart(self):
        from app.engine.tools.visual_tools import _build_chart_html

        html = _build_chart_html({}, "Empty")
        assert "No chart data" in html


class TestTimelineVisual:
    """Test timeline visual generation."""

    def test_basic_timeline(self):
        from app.engine.tools.visual_tools import _build_timeline_html

        spec = {
            "events": [
                {"title": "Founded", "date": "2020", "description": "Company started"},
                {"title": "Series A", "date": "2022", "description": "Raised funding"},
            ],
        }
        html = _build_timeline_html(spec, "Company History")
        assert "<!DOCTYPE html>" in html
        assert "Founded" in html
        assert "2020" in html
        assert "Company started" in html
        assert "timeline" in html
        assert "tl-event" in html

    def test_timeline_uses_steps_fallback(self):
        from app.engine.tools.visual_tools import _build_timeline_html

        spec = {"steps": [{"title": "Step 1"}, {"title": "Step 2"}]}
        html = _build_timeline_html(spec, "")
        assert "Step 1" in html
        assert "Step 2" in html


class TestMapLiteVisual:
    """Test map_lite (region cards) visual generation."""

    def test_basic_map_lite(self):
        from app.engine.tools.visual_tools import _build_map_lite_html

        spec = {
            "regions": [
                {"name": "North", "value": "1.2M", "description": "Northern region"},
                {"name": "South", "value": "800K", "description": "Southern region"},
            ],
        }
        html = _build_map_lite_html(spec, "Population")
        assert "<!DOCTYPE html>" in html
        assert "North" in html
        assert "1.2M" in html
        assert "Northern region" in html
        assert "map-grid" in html

    def test_map_lite_with_tags(self):
        from app.engine.tools.visual_tools import _build_map_lite_html

        spec = {
            "regions": [
                {"name": "Zone A", "value": "High", "tags": ["priority", "active"]},
            ],
        }
        html = _build_map_lite_html(spec, "Zones")
        assert "priority" in html
        assert "active" in html
        assert "map-card-tag" in html


# =============================================================================
# Code-gen routing tests
# =============================================================================


class TestCodeGenRouting:
    """Test enable_code_gen_visuals feature flag routing."""

    def test_flag_off_keeps_template_default(self, monkeypatch):
        class FakeSettings:
            enable_code_gen_visuals = False

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import _infer_renderer_kind

        assert _infer_renderer_kind("comparison", {}) == "template"
        assert _infer_renderer_kind("architecture", {}) == "template"

    def test_flag_on_routes_explanatory_to_inline_html(self, monkeypatch):
        class FakeSettings:
            enable_code_gen_visuals = True

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import _infer_renderer_kind

        assert _infer_renderer_kind("comparison", {}) == "inline_html"
        assert _infer_renderer_kind("process", {}) == "inline_html"
        assert _infer_renderer_kind("architecture", {}) == "inline_html"
        assert _infer_renderer_kind("concept", {}) == "inline_html"
        assert _infer_renderer_kind("infographic", {}) == "inline_html"
        assert _infer_renderer_kind("matrix", {}) == "inline_html"
        assert _infer_renderer_kind("chart", {}) == "inline_html"
        assert _infer_renderer_kind("timeline", {}) == "inline_html"
        assert _infer_renderer_kind("map_lite", {}) == "inline_html"

    def test_flag_on_does_not_affect_legacy_sandbox(self, monkeypatch):
        class FakeSettings:
            enable_code_gen_visuals = True

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import _infer_renderer_kind

        assert _infer_renderer_kind("simulation", {}) == "app"
        assert _infer_renderer_kind("quiz", {}) == "app"
        assert _infer_renderer_kind("react_app", {}) == "app"

    def test_explicit_renderer_kind_overrides_flag(self, monkeypatch):
        class FakeSettings:
            enable_code_gen_visuals = True

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import _infer_renderer_kind

        assert _infer_renderer_kind("comparison", {}, "template") == "template"

    def test_intent_resolver_upgrades_template_when_flag_on(self, monkeypatch):
        class FakeSettings:
            enable_code_gen_visuals = True

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.multi_agent.visual_intent_resolver import resolve_visual_intent

        decision = resolve_visual_intent("so sanh TCP va UDP")
        assert decision.mode == "inline_html"
        assert "code-gen" in decision.reason

    def test_intent_resolver_keeps_template_when_flag_off(self, monkeypatch):
        class FakeSettings:
            enable_code_gen_visuals = False

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.multi_agent.visual_intent_resolver import resolve_visual_intent

        decision = resolve_visual_intent("so sanh TCP va UDP")
        assert decision.mode == "template"

    def test_intent_resolver_does_not_upgrade_app_mode(self, monkeypatch):
        class FakeSettings:
            enable_code_gen_visuals = True

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.multi_agent.visual_intent_resolver import resolve_visual_intent

        decision = resolve_visual_intent("mo phong vat ly con lac")
        assert decision.mode == "app"

    def test_intent_resolver_does_not_upgrade_text_mode(self, monkeypatch):
        class FakeSettings:
            enable_code_gen_visuals = True

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.multi_agent.visual_intent_resolver import resolve_visual_intent

        decision = resolve_visual_intent("hello world")
        assert decision.mode == "text"


# =============================================================================
# Enhanced builder field tests
# =============================================================================


class TestEnhancedBuilderFields:
    """Test that upgraded builders render new spec fields."""

    def test_architecture_renders_description(self):
        from app.engine.tools.visual_tools import _build_architecture_html

        spec = {
            "layers": [
                {"name": "API", "description": "REST endpoints and routing", "components": ["FastAPI"]},
            ],
        }
        html = _build_architecture_html(spec, "")
        assert "REST endpoints and routing" in html
        assert "arch-layer-desc" in html

    def test_comparison_renders_highlight(self):
        from app.engine.tools.visual_tools import _build_comparison_html

        spec = {
            "left": {"title": "A", "items": []},
            "right": {"title": "B", "items": []},
            "highlight": "A is clearly better for performance",
        }
        html = _build_comparison_html(spec, "")
        assert "A is clearly better for performance" in html
        assert "comp-highlight" in html

    def test_concept_renders_branch_description(self):
        from app.engine.tools.visual_tools import _build_concept_html

        spec = {
            "center": {"title": "ML"},
            "branches": [
                {"title": "Supervised", "description": "Learns from labeled data", "items": ["SVM"]},
            ],
        }
        html = _build_concept_html(spec, "")
        assert "Learns from labeled data" in html
        assert "concept-branch-desc" in html

    def test_infographic_renders_highlights_and_takeaway(self):
        from app.engine.tools.visual_tools import _build_infographic_html

        spec = {
            "stats": [{"value": "99%", "label": "Accuracy"}],
            "highlights": ["Best in class", "Production ready"],
            "takeaway": "This model outperforms all baselines.",
        }
        html = _build_infographic_html(spec, "")
        assert "Best in class" in html
        assert "Production ready" in html
        assert "info-highlights" in html
        assert "This model outperforms all baselines" in html
        assert "info-takeaway" in html

    def test_process_renders_content_and_signals(self):
        from app.engine.tools.visual_tools import _build_process_html

        spec = {
            "steps": [
                {
                    "title": "Parse",
                    "description": "Parse input",
                    "content": "Uses recursive descent parser",
                    "signals": ["AST", "tokens"],
                },
            ],
        }
        html = _build_process_html(spec, "")
        assert "Uses recursive descent parser" in html
        assert "step-content" in html
        assert "AST" in html
        assert "step-signal" in html


# =============================================================================
# Phase 4: LLM code_html tests
# =============================================================================


class TestCodeHtmlResolve:
    """Test _resolve_code_html helper."""

    def test_empty_code_html_returns_none(self, monkeypatch):
        class FakeSettings:
            enable_llm_code_gen_visuals = True

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import _resolve_code_html

        assert _resolve_code_html("", "comparison", "T", {}) is None
        assert _resolve_code_html("   ", "comparison", "T", {}) is None

    def test_flag_off_ignores_code_html(self, monkeypatch):
        class FakeSettings:
            enable_llm_code_gen_visuals = False

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import _resolve_code_html

        result = _resolve_code_html("<div>Custom</div>", "comparison", "T", {})
        assert result is None

    def test_wraps_body_in_design_system(self, monkeypatch):
        class FakeSettings:
            enable_llm_code_gen_visuals = True

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import _resolve_code_html

        result = _resolve_code_html(
            '<div class="custom">Hello World</div>',
            "concept",
            "Test Title",
            {},
        )
        assert result is not None
        assert "<!DOCTYPE html>" in result
        assert "Hello World" in result
        assert "Test Title" in result  # title rendered
        assert "--accent" in result  # design system CSS vars

    def test_extracts_style_blocks(self, monkeypatch):
        class FakeSettings:
            enable_llm_code_gen_visuals = True

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import _resolve_code_html

        code = '<style>.box{color:red}</style><div class="box">Hi</div>'
        result = _resolve_code_html(code, "concept", "", {})
        assert result is not None
        assert ".box{color:red}" in result
        assert '<div class="box">Hi</div>' in result

    def test_full_html_document_passthrough(self, monkeypatch):
        class FakeSettings:
            enable_llm_code_gen_visuals = True

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import _resolve_code_html

        full_doc = "<!DOCTYPE html><html><body><p>Full doc</p></body></html>"
        result = _resolve_code_html(full_doc, "concept", "T", {})
        assert result == full_doc  # returned as-is


class TestCodeHtmlToolIntegration:
    """Test code_html param in tool_generate_visual."""

    def test_code_html_produces_inline_html_payload(self, monkeypatch):
        class FakeSettings:
            enable_llm_code_gen_visuals = True
            enable_code_gen_visuals = False

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import parse_visual_payload, tool_generate_visual

        result = tool_generate_visual.invoke({
            "visual_type": "architecture",
            "spec_json": json.dumps({"layers": [{"name": "L1", "components": ["C1"]}]}),
            "title": "Custom Arch",
            "summary": "LLM-generated HTML",
            "code_html": '<style>.custom{color:var(--accent)}</style><div class="custom">Custom SVG diagram here</div>',
        })
        payload = parse_visual_payload(result)

        assert payload is not None
        assert payload.renderer_kind == "inline_html"
        assert payload.fallback_html is not None
        assert "Custom SVG diagram here" in payload.fallback_html
        assert ".custom{color:var(--accent)}" in payload.fallback_html
        assert "<!DOCTYPE html>" in payload.fallback_html

    def test_code_html_ignored_when_flag_off(self, monkeypatch):
        class FakeSettings:
            enable_llm_code_gen_visuals = False
            enable_code_gen_visuals = False

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import parse_visual_payload, tool_generate_visual

        result = tool_generate_visual.invoke({
            "visual_type": "comparison",
            "spec_json": json.dumps({
                "left": {"title": "A"},
                "right": {"title": "B"},
            }),
            "title": "Test",
            "code_html": "<div>Should be ignored</div>",
        })
        payload = parse_visual_payload(result)

        assert payload is not None
        assert payload.renderer_kind == "template"
        # fallback_html should be builder output, not code_html
        if payload.fallback_html:
            assert "Should be ignored" not in payload.fallback_html

    def test_code_html_skips_auto_grouping(self, monkeypatch):
        class FakeSettings:
            enable_llm_code_gen_visuals = True
            enable_code_gen_visuals = False

        monkeypatch.setattr("app.core.config.get_settings", lambda: FakeSettings())
        from app.engine.tools.visual_tools import parse_visual_payloads, tool_generate_visual
        from app.engine.tools.runtime_context import build_tool_runtime_context, tool_runtime_scope

        runtime = build_tool_runtime_context(
            session_id="session-codegen-1",
            user_id="user-1",
            user_role="admin",
            metadata={
                "visual_force_tool": True,
                "visual_intent_mode": "template",
                "visual_intent_reason": "chart-template",
                "visual_user_query": "Explain with charts",
                "visual_requested_type": "chart",
            },
        )

        with tool_runtime_scope(runtime):
            result = tool_generate_visual.invoke({
                "visual_type": "chart",
                "spec_json": json.dumps({"labels": ["A"], "datasets": [{"label": "S", "data": [1]}]}),
                "title": "Custom Chart",
                "code_html": '<svg><rect width="100" height="50" fill="var(--accent)"/></svg>',
            })

        payloads = parse_visual_payloads(result)
        # Should be single payload, not auto-grouped
        assert len(payloads) == 1
        assert payloads[0].renderer_kind == "inline_html"
