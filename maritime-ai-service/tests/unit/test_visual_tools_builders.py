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
