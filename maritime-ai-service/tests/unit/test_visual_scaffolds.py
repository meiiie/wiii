"""Tests for visual scaffold library (Phase 1)."""

import pytest

from app.engine.tools.visual_scaffolds import (
    _looks_like_dashboard,
    _looks_like_quiz,
    _looks_like_simulation,
    build_scaffold,
    detect_scaffold,
)


class TestDetectScaffold:
    def test_pendulum_detection(self):
        assert detect_scaffold("con lac dao dong", "") == "pendulum"
        assert detect_scaffold("pendulum simulation", "") == "pendulum"

    def test_simulation_detection(self):
        assert detect_scaffold("mo phong va cham", "simulation") == "simulation"
        assert detect_scaffold("wave interference", "") == "simulation"
        assert detect_scaffold("vat ly luong luc", "") == "simulation"

    def test_simulation_not_pendulum(self):
        """Pendulum tokens should match before generic simulation."""
        result = detect_scaffold("pendulum physics", "")
        assert result == "pendulum"  # More specific match wins

    def test_quiz_detection(self):
        assert detect_scaffold("trac nghiem colreg", "") == "quiz"
        assert detect_scaffold("quiz about SOLAS", "") == "quiz"
        assert detect_scaffold("", "quiz") == "quiz"

    def test_dashboard_detection(self):
        assert detect_scaffold("bang dieu khien hang hai", "") == "dashboard"
        assert detect_scaffold("analytics dashboard", "") == "dashboard"
        assert detect_scaffold("", "dashboard") == "dashboard"

    def test_no_match(self):
        assert detect_scaffold("hello world", "") is None
        assert detect_scaffold("", "chart") is None

    def test_visual_type_override(self):
        assert detect_scaffold("something", "simulation") == "simulation"
        assert detect_scaffold("something", "quiz") == "quiz"
        assert detect_scaffold("something", "dashboard") == "dashboard"


class TestBuildScaffold:
    def test_simulation_scaffold_produces_html(self):
        html = build_scaffold("simulation", "Test Sim", "Test subtitle", "mo phong")
        assert "<!DOCTYPE html>" in html
        assert "Canvas runtime" in html
        assert "speed-slider" in html
        assert "intensity-slider" in html
        assert "WiiiVisualBridge" in html

    def test_simulation_scaffold_has_quality_features(self):
        html = build_scaffold("simulation", "Test")
        assert "requestAnimationFrame" in html  # Animation loop
        assert "--bg" in html  # CSS variables
        assert "prefers-color-scheme" in html  # Dark/light mode
        assert "@media" in html  # Responsive

    def test_quiz_scaffold_produces_html(self):
        html = build_scaffold("quiz", "Test Quiz", "Test your knowledge")
        assert "<!DOCTYPE html>" in html
        assert "react@18.3.1" in html  # React CDN
        assert "babel" in html  # Babel transpilation
        assert "WiiiVisualBridge" in html
        assert "Quiz" in html

    def test_quiz_scaffold_uses_react(self):
        html = build_scaffold("quiz", "Quiz")
        assert 'type="text/babel"' in html
        assert "ReactDOM.createRoot" in html

    def test_dashboard_scaffold_produces_html(self):
        html = build_scaffold("dashboard", "Test Dashboard", "Metrics")
        assert "<!DOCTYPE html>" in html
        assert "dash-kpi" in html
        assert "dash-card" in html
        assert "WiiiVisualBridge" in html

    def test_dashboard_scaffold_has_responsive_grid(self):
        html = build_scaffold("dashboard", "Dash")
        assert "grid-template-columns" in html
        assert "@media" in html
        assert "auto-fit" in html

    def test_pendulum_scaffold_delegates(self):
        """Pendulum scaffold should delegate to existing implementation."""
        html = build_scaffold("pendulum", "Pendulum Test", "Physics")
        assert "pendulum" in html.lower()
        assert "canvas" in html.lower()

    def test_unknown_scaffold_raises(self):
        with pytest.raises(ValueError, match="Unknown scaffold"):
            build_scaffold("nonexistent", "Test")


class TestDetectionHelpers:
    def test_looks_like_simulation_true(self):
        assert _looks_like_simulation("<canvas>test</canvas>", "Sim", "mo phong vat ly")

    def test_looks_like_simulation_false(self):
        assert not _looks_like_simulation("<div>text</div>", "Chart", "bieu do")

    def test_looks_like_simulation_excludes_pendulum(self):
        assert not _looks_like_simulation("canvas pendulum", "Pendulum", "con lac")

    def test_looks_like_quiz_true(self):
        assert _looks_like_quiz("", "Quiz", "trac nghiem")

    def test_looks_like_quiz_false(self):
        assert not _looks_like_quiz("", "Chart", "bieu do gia")

    def test_looks_like_dashboard_true(self):
        assert _looks_like_dashboard("", "Dash", "analytics dashboard")

    def test_looks_like_dashboard_false(self):
        assert not _looks_like_dashboard("", "Sim", "mo phong vat ly")


class TestScaffoldQualityScore:
    """Verify scaffolds pass their own quality scoring pipeline."""

    def test_simulation_scaffold_scores_well(self):
        from app.engine.tools.visual_code_quality import quality_score_visual_output_impl

        html = build_scaffold("simulation", "Physics Sim", "Test")
        score, deficiencies = quality_score_visual_output_impl(html, "simulation")
        assert score >= 6, f"Simulation scaffold scored {score}/10: {deficiencies}"

    def test_dashboard_scaffold_scores_well(self):
        from app.engine.tools.visual_code_quality import quality_score_visual_output_impl

        html = build_scaffold("dashboard", "Metrics Dashboard", "Test")
        score, deficiencies = quality_score_visual_output_impl(html, "")
        assert score >= 5, f"Dashboard scaffold scored {score}/10: {deficiencies}"

    def test_quiz_scaffold_scores_well(self):
        from app.engine.tools.visual_code_quality import quality_score_visual_output_impl

        html = build_scaffold("quiz", "Knowledge Quiz", "Test")
        score, deficiencies = quality_score_visual_output_impl(html, "quiz")
        assert score >= 5, f"Quiz scaffold scored {score}/10: {deficiencies}"
