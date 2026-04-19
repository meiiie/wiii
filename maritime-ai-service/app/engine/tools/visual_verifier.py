"""Visual Verifier — inspired by Claude Design's fork_verifier_agent.

Runs independent checks on visual HTML output, like a sub-agent in its
own iframe. Silent on pass — only reports when something is wrong.

Check categories:
1. Quality score (reuses existing quality_score_visual_output_impl)
2. AI slop patterns (gradient spam, emoji, banned fonts, etc.)
3. Render surface validation
4. Responsiveness
5. Accessibility basics

Usage:
    verifier = VisualVerifier(min_score=6)
    result = verifier.verify(html, visual_type="simulation")
    if not result.passed:
        logger.warning("Visual issues: %s", result.deficiencies)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.engine.tools.visual_ai_slop import check_ai_slop_patterns
from app.engine.tools.visual_code_quality import quality_score_visual_output_impl

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class VisualVerificationResult:
    """Result from visual verification checks."""

    score: int
    passed: bool
    deficiencies: list[str] = field(default_factory=list)
    slop_violations: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


class VisualVerifier:
    """Verify visual output quality — inspired by Claude Design's fork_verifier_agent.

    Runs checks independently. Silent on pass — only reports when something
    is wrong. Can be used standalone or integrated into the pipeline.

    Args:
        min_score: Minimum quality score (0-10) to pass. Default 6.
        check_slop: Whether to run AI slop checks. Default True.
        check_accessibility: Whether to run accessibility checks. Default True.
    """

    def __init__(
        self,
        *,
        min_score: int = 6,
        check_slop: bool = True,
        check_accessibility: bool = True,
    ):
        self._min_score = min_score
        self._check_slop = check_slop
        self._run_accessibility = check_accessibility

    def verify(self, html: str, visual_type: str = "") -> VisualVerificationResult:
        """Run all verification checks on HTML output.

        Returns VisualVerificationResult with score, pass/fail, and details.
        """
        if not html or not html.strip():
            return VisualVerificationResult(
                score=0,
                passed=False,
                deficiencies=["Empty HTML output."],
            )

        all_deficiencies: list[str] = []
        slop_violations: list[str] = []
        suggestions: list[str] = []
        high_severity: list = []

        # 1. Quality score (reuses existing pipeline)
        quality_score, quality_deficiencies = quality_score_visual_output_impl(html, visual_type)
        all_deficiencies.extend(quality_deficiencies)

        # 2. AI slop check
        if self._check_slop:
            slop_results = check_ai_slop_patterns(html)
            for violation in slop_results:
                slop_violations.append(f"[{violation.severity}] {violation.rule}: {violation.message}")
            # High-severity slop also counts as deficiency
            high_severity = [v for v in slop_results if v.severity == "high"]
            for v in high_severity:
                all_deficiencies.append(v.message)

        # 3. Render surface check
        surface_issues = self._check_render_surface(html, visual_type)
        all_deficiencies.extend(surface_issues)

        # 4. Responsiveness check
        responsive_issues = self._check_responsiveness(html)
        all_deficiencies.extend(responsive_issues)

        # 5. Accessibility check
        if self._run_accessibility:
            a11y_issues = self._check_accessibility(html)
            all_deficiencies.extend(a11y_issues)

        # Generate suggestions based on deficiencies
        suggestions = self._generate_suggestions(all_deficiencies)

        # Final score = quality_score minus slop penalties (capped at 0)
        final_score = max(0, quality_score - len(high_severity))
        passed = final_score >= self._min_score

        return VisualVerificationResult(
            score=final_score,
            passed=passed,
            deficiencies=all_deficiencies,
            slop_violations=slop_violations,
            suggestions=suggestions,
        )

    def _check_render_surface(self, html: str, visual_type: str) -> list[str]:
        """Verify proper render surface for the visual type."""
        issues: list[str] = []
        lowered = html.lower()
        is_simulation = visual_type in ("simulation", "physics", "animation")

        if is_simulation:
            has_canvas = "<canvas" in lowered
            has_svg = "<svg" in lowered
            has_raf = "requestanimationframe" in lowered
            if not has_canvas and not has_svg:
                issues.append(
                    "Simulation missing render surface — needs Canvas or SVG element."
                )
            if not has_raf:
                issues.append(
                    "Simulation missing animation loop — needs requestAnimationFrame."
                )

        if visual_type == "chart":
            has_chart_lib = any(
                token in lowered
                for token in ("<svg", "<canvas", "chart.js", "recharts", "d3.", "plotly", "echarts")
            )
            if not has_chart_lib:
                issues.append(
                    "Chart missing proper chart library or SVG surface."
                )

        return issues

    def _check_responsiveness(self, html: str) -> list[str]:
        """Check responsive layout basics."""
        issues: list[str] = []
        lowered = html.lower()

        has_grid = "grid" in lowered
        has_flex = "flex" in lowered
        has_media_query = "@media" in html
        has_max_width = "max-width" in lowered

        if not has_grid and not has_flex:
            issues.append(
                "No CSS Grid or Flexbox detected — output may not be responsive."
            )
        if not has_media_query and not has_max_width:
            issues.append(
                "No @media queries or max-width detected — may not adapt to smaller screens."
            )

        return issues

    def _check_accessibility(self, html: str) -> list[str]:
        """Check accessibility basics."""
        issues: list[str] = []
        lowered = html.lower()

        has_aria = "aria-" in lowered
        has_role = 'role="' in lowered
        has_label = "aria-label" in lowered or "<label" in lowered
        has_alt = "alt=" in lowered

        interactive_elements = (
            lowered.count("<button")
            + lowered.count('<input')
            + lowered.count("<select")
        )

        if interactive_elements > 0 and not has_label:
            issues.append(
                f"Found {interactive_elements} interactive elements but no aria-label or <label> — "
                "screen readers cannot identify controls."
            )

        if "prefers-reduced-motion" not in lowered and "requestanimationframe" in lowered:
            issues.append(
                "Animation present but no prefers-reduced-motion check — "
                "add @media (prefers-reduced-motion: reduce) to disable animations."
            )

        return issues

    def _generate_suggestions(self, deficiencies: list[str]) -> list[str]:
        """Generate actionable suggestions from deficiencies."""
        suggestions: list[str] = []

        if any("CSS variables" in d for d in deficiencies):
            suggestions.append("Add :root { --bg, --fg, --accent } CSS variables for theming.")

        if any("dark/light" in d.lower() for d in deficiencies):
            suggestions.append("Add @media (prefers-color-scheme: light) { :root { ... } } for dark/light support.")

        if any("controls" in d.lower() and "tuong tac" in d.lower() for d in deficiencies):
            suggestions.append("Add at least 2 <input type='range'> sliders for user parameter control.")

        if any("WiiiVisualBridge" in d for d in deficiencies):
            suggestions.append("Add window.WiiiVisualBridge.reportResult(kind, payload, summary, status) for interaction reporting.")

        if any("responsive" in d.lower() for d in deficiencies):
            suggestions.append("Use CSS Grid with @media (max-width: 720px) for responsive layout.")

        return suggestions
