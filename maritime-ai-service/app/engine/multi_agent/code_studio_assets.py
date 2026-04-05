"""Code Studio skill/example asset loading helpers."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_CODE_STUDIO_SKILLS_CACHE: list[str] | None = None
_CODE_STUDIO_EXAMPLES_CACHE: dict[str, str] = {}

_CODE_STUDIO_SKILL_FILES = [
    "VISUAL_CODE_GEN.md",
]

_CODE_STUDIO_EXAMPLE_MAP: dict[str, str] = {
    "simulation": "canvas_wave_interference.html",
    "physics": "canvas_wave_interference.html",
    "animation": "canvas_wave_interference.html",
    "diagram": "svg_ship_encounter.html",
    "architecture": "svg_ship_encounter.html",
    "comparison": "html_comparison_clean.html",
    "chart": "svg_horizontal_bar_clean.html",
    "benchmark": "svg_horizontal_bar_clean.html",
    "statistics": "svg_horizontal_bar_clean.html",
    "horizontal_bar": "svg_horizontal_bar_clean.html",
    "process": "html_process_flow_clean.html",
    "workflow": "html_process_flow_clean.html",
    "timeline": "html_process_flow_clean.html",
    "dashboard": "dashboard_metrics.html",
    "metrics": "dashboard_metrics.html",
    "overview": "dashboard_metrics.html",
    "tool": "widget_maritime_calculator.html",
    "quiz": "widget_maritime_calculator.html",
    "calculator": "widget_maritime_calculator.html",
    "radar": "svg_radar_clean.html",
    "spider": "svg_radar_clean.html",
    "bar_chart": "svg_vertical_bar_clean.html",
    "column": "svg_vertical_bar_clean.html",
    "vertical_bar": "svg_vertical_bar_clean.html",
    "pie": "svg_donut_clean.html",
    "donut": "svg_donut_clean.html",
    "doughnut": "svg_donut_clean.html",
    "line_chart": "svg_line_clean.html",
    "line": "svg_line_clean.html",
    "svg_motion": "svg_motion_animation.html",
    "motion": "svg_motion_animation.html",
    "morph": "svg_motion_animation.html",
    "particle": "canvas_particle_system.html",
    "particles": "canvas_particle_system.html",
    "effect": "canvas_particle_system.html",
}


def _load_code_studio_visual_skills() -> list[str]:
    """Load and cache all visual skills for code_studio_agent."""
    global _CODE_STUDIO_SKILLS_CACHE
    if _CODE_STUDIO_SKILLS_CACHE is not None:
        return _CODE_STUDIO_SKILLS_CACHE

    skills_dir = (
        Path(__file__).resolve().parent.parent
        / "reasoning" / "skills" / "subagents" / "code_studio_agent"
    )
    results: list[str] = []
    for filename in _CODE_STUDIO_SKILL_FILES:
        skill_path = skills_dir / filename
        try:
            raw = skill_path.read_text(encoding="utf-8")
            if raw.startswith("---"):
                parts = raw.split("---", 2)
                if len(parts) >= 3:
                    results.append(parts[2].strip())
                    continue
            results.append(raw.strip())
        except Exception as exc:  # pragma: no cover - defensive logging only
            logger.debug("[CODE_STUDIO] Skill %s unavailable: %s", filename, exc)

    _CODE_STUDIO_SKILLS_CACHE = results
    return _CODE_STUDIO_SKILLS_CACHE


def _load_code_studio_example(visual_type: str) -> str | None:
    """Load a reference example on-demand based on visual_type."""
    filename = _CODE_STUDIO_EXAMPLE_MAP.get(visual_type)
    if not filename:
        return None

    if filename in _CODE_STUDIO_EXAMPLES_CACHE:
        return _CODE_STUDIO_EXAMPLES_CACHE[filename]

    examples_dir = (
        Path(__file__).resolve().parent.parent
        / "reasoning" / "skills" / "subagents" / "code_studio_agent" / "examples"
    )
    example_path = examples_dir / filename
    try:
        raw = example_path.read_text(encoding="utf-8")
        lines = raw.split("\n")
        if len(lines) > 250:
            truncated = (
                "\n".join(lines[:250])
                + "\n<!-- ... truncated — see full example in examples/ folder -->"
            )
        else:
            truncated = raw
        _CODE_STUDIO_EXAMPLES_CACHE[filename] = truncated
        return truncated
    except Exception as exc:  # pragma: no cover - defensive logging only
        logger.debug("[CODE_STUDIO] Example %s unavailable: %s", filename, exc)
        return None
