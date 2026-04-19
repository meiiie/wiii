"""Tests for visual verifier (Phase 2)."""

import pytest

from app.engine.tools.visual_verifier import VisualVerifier, VisualVerificationResult


# ---------------------------------------------------------------------------
# Sample HTML fixtures
# ---------------------------------------------------------------------------

GOOD_SIMULATION_HTML = """<!DOCTYPE html>
<html><head>
<style>
:root { --bg: #0f172a; --fg: #e2e8f0; --accent: #38bdf8; }
@media (prefers-color-scheme: light) { :root { --bg: #f8fafc; } }
</style></head>
<body>
<canvas id="sim"></canvas>
<input type="range" min="0" max="1" step="0.1" value="0.5" aria-label="Speed">
<input type="range" min="0" max="10" step="0.5" value="5" aria-label="Gravity">
<span id="angle" aria-live="polite">0.0</span>
<span id="vel" aria-live="polite">0.0</span>
<script>
function loop() {
  requestAnimationFrame(loop);
  const dt = Math.min(0.032, (performance.now() - lastTime) / 1000);
}
window.WiiiVisualBridge.reportResult('test', {}, 'ok', 'done');
</script>
</body></html>"""

BAD_HTML = "<div>Hello</div>"

MINIMAL_SIMULATION_HTML = """<!DOCTYPE html>
<html><head><style>body { background: #000; }</style></head>
<body><canvas id="sim"></canvas></body></html>"""

AI_SLOP_HTML = """<!DOCTYPE html>
<html><head><style>
:root { --bg: #fff; --fg: #000; --accent: blue; }
@media (prefers-color-scheme: light) { :root { --bg: #f8fafc; } }
body { font-family: Inter; }
.hero {
  background: linear-gradient(135deg, #7c3aed, #3b82f6);
  border-left: 4px solid #8b5cf6;
  border-radius: 12px;
}
</style></head>
<body>
<div class="hero">🚀✨💡🔥🎯📈💪🎉🏆👏🌟</div>
<div class="stat-card">1</div><div class="stat-card">2</div>
<div class="stat-card">3</div><div class="stat-card">4</div>
<div class="stat-card">5</div><div class="stat-card">6</div>
<div class="stat-card">7</div>
<div style="background: linear-gradient(#a,#b)"></div>
<div style="background: linear-gradient(#c,#d)"></div>
<div style="background: linear-gradient(#e,#f)"></div>
</body></html>"""


class TestVisualVerifier:
    def test_good_simulation_passes(self):
        verifier = VisualVerifier(min_score=6)
        result = verifier.verify(GOOD_SIMULATION_HTML, "simulation")
        assert isinstance(result, VisualVerificationResult)
        assert result.score >= 6
        assert result.passed is True

    def test_bad_html_fails(self):
        verifier = VisualVerifier(min_score=6)
        result = verifier.verify(BAD_HTML, "simulation")
        assert result.passed is False

    def test_empty_html_fails(self):
        verifier = VisualVerifier()
        result = verifier.verify("", "")
        assert result.passed is False
        assert result.score == 0

    def test_ai_slop_detected(self):
        verifier = VisualVerifier(min_score=6, check_slop=True)
        result = verifier.verify(AI_SLOP_HTML, "")
        assert len(result.slop_violations) > 0

    def test_slop_check_disabled(self):
        verifier = VisualVerifier(min_score=1, check_slop=False)
        result = verifier.verify(AI_SLOP_HTML, "")
        assert len(result.slop_violations) == 0

    def test_accessibility_check(self):
        verifier = VisualVerifier(min_score=1, check_accessibility=True)
        # HTML with buttons but no aria-label
        html = """
        <html><body>
        <style>:root { --bg: #fff; --fg: #000; --accent: blue; }
        @media (prefers-color-scheme: light) { :root { --bg: #f8fafc; } }</style>
        <button>Click</button>
        <script>
        function loop() { requestAnimationFrame(loop); }
        loop();
        window.WiiiVisualBridge.reportResult('x',{},'','');
        </script>
        </body></html>
        """
        result = verifier.verify(html, "")
        a11y_issues = [d for d in result.deficiencies if "aria-label" in d]
        assert len(a11y_issues) > 0

    def test_accessibility_check_disabled(self):
        verifier = VisualVerifier(min_score=1, check_accessibility=False)
        html = "<html><body><button>Click</button></body></html>"
        result = verifier.verify(html, "")
        a11y_issues = [d for d in result.deficiencies if "aria-label" in d]
        assert len(a11y_issues) == 0

    def test_render_surface_check_simulation(self):
        verifier = VisualVerifier(min_score=1)
        html = "<html><body><div>No canvas</div></body></html>"
        result = verifier.verify(html, "simulation")
        surface_issues = [d for d in result.deficiencies if "render surface" in d.lower()]
        assert len(surface_issues) > 0

    def test_render_surface_check_chart(self):
        verifier = VisualVerifier(min_score=1)
        html = "<html><body><div class='bar'>No chart lib</div></body></html>"
        result = verifier.verify(html, "chart")
        surface_issues = [d for d in result.deficiencies if "chart library" in d.lower()]
        assert len(surface_issues) > 0

    def test_responsiveness_check(self):
        verifier = VisualVerifier(min_score=1)
        html = "<html><body><div>Fixed width only</div></body></html>"
        result = verifier.verify(html, "")
        responsive_issues = [d for d in result.deficiencies if "responsive" in d.lower() or "Flexbox" in d]
        assert len(responsive_issues) > 0

    def test_suggestions_generated(self):
        verifier = VisualVerifier(min_score=10)
        result = verifier.verify(BAD_HTML, "")
        assert len(result.suggestions) > 0

    def test_slop_violations_penalty_reduces_score(self):
        """High-severity slop should reduce the final score."""
        verifier_no_slop = VisualVerifier(min_score=1, check_slop=False)
        verifier_with_slop = VisualVerifier(min_score=1, check_slop=True)

        result_clean = verifier_no_slop.verify(AI_SLOP_HTML, "")
        result_slop = verifier_with_slop.verify(AI_SLOP_HTML, "")

        # Slop checker should reduce score via high-severity violations
        assert result_slop.score <= result_clean.score


class TestVisualVerificationResult:
    def test_result_dataclass(self):
        result = VisualVerificationResult(
            score=8,
            passed=True,
            deficiencies=[],
            slop_violations=[],
            suggestions=[],
        )
        assert result.score == 8
        assert result.passed is True

    def test_result_with_deficiencies(self):
        result = VisualVerificationResult(
            score=3,
            passed=False,
            deficiencies=["Missing CSS variables"],
            slop_violations=["[high] gradient_overuse"],
            suggestions=["Add :root CSS variables"],
        )
        assert len(result.deficiencies) == 1
        assert len(result.slop_violations) == 1
        assert len(result.suggestions) == 1
