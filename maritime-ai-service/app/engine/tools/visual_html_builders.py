"""Compatibility shell for structured visual HTML builders."""

from __future__ import annotations

import logging
from typing import Any

from app.engine.tools.visual_chart_builders import (
    _build_chart_html_impl,
    _normalize_chart_spec,
)
from app.engine.tools.visual_html_core import _DESIGN_CSS, _esc, _wrap_html
from app.engine.tools.visual_html_layout_builders import (
    _build_architecture_html,
    _build_comparison_html_impl,
    _build_concept_html,
    _build_infographic_html,
    _build_map_lite_html,
    _build_matrix_html,
    _build_process_html,
    _build_timeline_html,
)

logger = logging.getLogger(__name__)


def _build_comparison_html(spec: dict[str, Any], title: str) -> str:
    """Two-column comparison surface with chart fallback for row-data shapes."""
    logger.info(
        "[COMPARISON_BUILDER] Input spec keys: %s",
        list(spec.keys()) if spec else "None",
    )

    if "data" in spec and isinstance(spec.get("data"), list) and "left" not in spec:
        return _build_chart_html_impl(spec, title)

    return _build_comparison_html_impl(spec, title)


def _build_chart_html(spec: dict[str, Any], title: str) -> str:
    """Chart builder with comparison-shape fallback for legacy payloads."""
    logger.info("[CHART_BUILDER] Input spec keys: %s", list(spec.keys()) if spec else "None")

    if "left" in spec or "right" in spec:
        return _build_comparison_html(spec, title)

    return _build_chart_html_impl(spec, title)


_BUILDERS = {
    "comparison": _build_comparison_html,
    "process": _build_process_html,
    "matrix": _build_matrix_html,
    "architecture": _build_architecture_html,
    "concept": _build_concept_html,
    "infographic": _build_infographic_html,
    "chart": _build_chart_html,
    "timeline": _build_timeline_html,
    "map_lite": _build_map_lite_html,
}
