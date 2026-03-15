"""Resolve when a query needs text, mermaid, template visuals, inline HTML, or app runtime."""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Any, Literal


VisualMode = Literal["text", "mermaid", "template", "inline_html", "app"]

_LEGACY_VISUAL_TOOL_NAMES = frozenset({
    "tool_generate_interactive_chart",
    "tool_generate_chart",
    "tool_generate_rich_visual",
    "tool_generate_mermaid",
})

_VISUAL_PATCH_KEYWORDS = (
    "highlight",
    "focus on",
    "focus only",
    "bottleneck",
    "giu cung visual",
    "giu nguyen visual",
    "same visual",
    "same visual session",
    "keep the same visual",
    "reuse visual",
    "update visual",
    "patch visual",
    "modify visual",
    "change this visual",
    "annotate",
    "them annotation",
    "lam ro",
    "nhan manh",
    "chi show",
    "chi hien thi",
    "doi thanh 3 buoc",
    "doi thanh",
    "bien thanh",
    "thanh 3 buoc",
    "so do nay",
    "turn this into",
    "convert this visual",
    "filter",
    "loc theo",
    "zoom in",
)


@dataclass(frozen=True)
class VisualIntentDecision:
    mode: VisualMode
    force_tool: bool = False
    visual_type: str | None = None
    reason: str = ""


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text.lower())
    normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    normalized = normalized.replace("đ", "d")
    normalized = re.sub(r"[^a-z0-9\s/+.-]", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def detect_visual_patch_request(query: str) -> bool:
    """Return True when the query looks like a follow-up edit to an existing visual."""
    normalized = _normalize(query)
    if not normalized:
        return False
    return _contains_any(normalized, _VISUAL_PATCH_KEYWORDS)


def preferred_visual_tool_name(structured_visuals_enabled: bool) -> str:
    """Return the preferred rich visual tool for the current runtime mode."""
    return "tool_generate_visual" if structured_visuals_enabled else "tool_generate_rich_visual"


def required_visual_tool_names(
    visual_decision: VisualIntentDecision,
    *,
    structured_visuals_enabled: bool,
) -> tuple[str, ...]:
    """Return the visual tool names that should remain available for an explicit intent."""
    if not visual_decision.force_tool:
        return ()

    if visual_decision.mode in {"template", "inline_html", "app"}:
        return (preferred_visual_tool_name(structured_visuals_enabled),)
    if visual_decision.mode == "mermaid":
        return ("tool_generate_mermaid",)
    return ()


def filter_tools_for_visual_intent(
    tools: list[Any],
    visual_decision: VisualIntentDecision,
    *,
    structured_visuals_enabled: bool,
) -> list[Any]:
    """Reduce drift toward legacy visual tools when structured intent is explicit."""
    if not structured_visuals_enabled:
        return tools

    allowed_names = set(
        required_visual_tool_names(
            visual_decision,
            structured_visuals_enabled=structured_visuals_enabled,
        )
    )
    if not allowed_names:
        return tools

    filtered: list[Any] = []
    for tool in tools:
        tool_name = str(getattr(tool, "name", "") or getattr(tool, "__name__", "") or "")
        if tool_name in allowed_names:
            filtered.append(tool)
            continue
        if tool_name in _LEGACY_VISUAL_TOOL_NAMES:
            continue
        filtered.append(tool)

    return filtered


def resolve_visual_intent(query: str) -> VisualIntentDecision:
    """Classify a user request into the most suitable visual delivery mode."""
    normalized = _normalize(query)
    if not normalized:
        return VisualIntentDecision(mode="text", reason="empty-query")

    if _contains_any(
        normalized,
        (
            "visual studio",
            "visual basic",
            "artifact repository",
        ),
    ):
        return VisualIntentDecision(mode="text", reason="false-positive-visual")

    if _contains_any(
        normalized,
        (
            "landing page",
            "website",
            "microsite",
            "web app",
            "mini app",
            "mini tool",
            "interactive tool",
            "html file",
            "excel file",
            "spreadsheet",
            "word file",
            "docx",
            "xlsx",
            "download file",
            "artifact",
            "dashboard",
            "dashboard app",
            "react app",
            "simulation",
            "simulate",
            "simulator",
            "mo phong",
            "mo phong vat ly",
            "keo tha",
            "drag and drop",
            "quiz",
            "interactive table",
        ),
    ):
        visual_type = "simulation" if _contains_any(
            normalized,
            ("simulation", "simulate", "simulator", "mo phong", "mo phong vat ly", "keo tha", "drag and drop"),
        ) else None
        return VisualIntentDecision(mode="app", force_tool=True, visual_type=visual_type, reason="app-request")

    if _contains_any(
        normalized,
        (
            "flowchart",
            "timeline",
            "sequence diagram",
            "state diagram",
            "er diagram",
            "mindmap",
            "mind map",
            "so do",
        ),
    ):
        return VisualIntentDecision(mode="mermaid", force_tool=True, reason="diagram-request")

    if _contains_any(
        normalized,
        (
            "animated",
            "animation",
            "animate",
            "hero visual",
            "editorial visual",
            "storyboard",
            "bespoke visual",
            "visual walkthrough",
            "trinh bay dep",
            "trinh bay hien dai",
        ),
    ):
        return VisualIntentDecision(mode="inline_html", force_tool=True, visual_type="concept", reason="bespoke-inline-html")

    if _contains_any(
        normalized,
        (
            "chart",
            "charts",
            "bar chart",
            "line chart",
            "pie chart",
            "doughnut chart",
            "radar chart",
            "trend",
            "xu huong",
            "thong ke",
            "bieu do",
            "phan bo",
            "du lieu so",
            "kpi",
            "explain in charts",
            "explain with charts",
        ),
    ):
        return VisualIntentDecision(mode="template", force_tool=True, visual_type="chart", reason="chart-template")

    if _contains_any(normalized, ("so sanh", "compare", "vs ", "khac nhau", "uu nhuoc diem")):
        return VisualIntentDecision(mode="template", force_tool=True, visual_type="comparison", reason="comparison")

    if _contains_any(normalized, ("quy trinh", "cac buoc", "step by step", "how it works", "process")):
        return VisualIntentDecision(mode="template", force_tool=True, visual_type="process", reason="process")

    if _contains_any(normalized, ("kien truc", "architecture", "he thong", "layer", "stack")):
        return VisualIntentDecision(mode="template", force_tool=True, visual_type="architecture", reason="architecture")

    if _contains_any(normalized, ("ma tran", "matrix", "heatmap", "quadrant", "2x2")):
        return VisualIntentDecision(mode="template", force_tool=True, visual_type="matrix", reason="matrix")

    if _contains_any(normalized, ("infographic", "tong quan nhanh", "facts at a glance", "highlights")):
        return VisualIntentDecision(mode="template", force_tool=True, visual_type="infographic", reason="infographic")

    if _contains_any(
        normalized,
        (
            "concept map",
            "ban do khai niem",
            "khai niem bang so do",
            "explain visually",
            "visualize this concept",
            "truc quan hoa",
        ),
    ):
        return VisualIntentDecision(mode="template", force_tool=True, visual_type="concept", reason="concept")

    return VisualIntentDecision(mode="text", reason="plain-text")
