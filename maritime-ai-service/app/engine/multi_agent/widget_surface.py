"""Structured visual and legacy widget surface helpers."""

from __future__ import annotations

import re
from typing import Any

from app.engine.multi_agent.visual_intent_resolver import resolve_visual_intent

_STRUCTURED_VISUAL_MARKER_RE = re.compile(
    r"\{visual-[a-f0-9]+\}|<!--\s*WiiiVisualBridge:[^>]+-->|"
    r"\[Biểu đồ[^\]]*\]|\[Bieu do[^\]]*\]|\[Chart[^\]]*\]|\[Visual[^\]]*\]",
    re.IGNORECASE,
)
_STRUCTURED_VISUAL_PLACEHOLDER_MD_RE = re.compile(
    r"!\[[^\]]*\]\((?:https?://example\.com/[^)\s]+|https?://[^)\s]*chart-placeholder[^)\s]*|sandbox:[^)]+)\)",
    re.IGNORECASE,
)


def _has_structured_visual_event(tool_call_events: list[dict] | None) -> bool:
    """Detect whether the turn already emitted a structured inline visual."""
    return any(
        (
            event.get("type") in {"visual_open", "visual_patch", "visual_commit", "visual_dispose"}
            or event.get("name") == "tool_generate_visual"
        )
        for event in (tool_call_events or [])
        if isinstance(event, dict)
    )


def _sanitize_structured_visual_answer_text(
    value: str,
    *,
    tool_call_events: list[dict] | None = None,
) -> str:
    """Remove duplicate visual placeholders once SSE visual events already exist."""
    cleaned = str(value or "")
    if not cleaned:
        return cleaned
    if not _has_structured_visual_event(tool_call_events):
        return cleaned.strip()

    cleaned = _STRUCTURED_VISUAL_PLACEHOLDER_MD_RE.sub("", cleaned)
    cleaned = _STRUCTURED_VISUAL_MARKER_RE.sub("", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned or str(value or "").strip()


def _inject_widget_blocks_from_tool_results(
    llm_response: Any,
    tool_call_events: list,
    *,
    query: str = "",
    structured_visuals_enabled: bool = False,
):
    """Inject legacy widget blocks only when the turn is not on the structured figure lane."""
    from app.engine.messages import Message

    raw_content = llm_response.content if hasattr(llm_response, "content") else str(llm_response)
    if isinstance(raw_content, list):
        response_text = "\n".join(
            part.get("text", "") if isinstance(part, dict) else str(part) for part in raw_content
        )
    else:
        response_text = str(raw_content)

    def _build_response(value: str):
        if hasattr(llm_response, "content"):
            return Message(role="assistant", content=value)
        return value

    def _strip_widget_blocks(value: str) -> str:
        return re.sub(r"\n?```widget[ \t]*\n[\s\S]*?\n```\n?", "\n\n", value).strip()

    visual_decision = resolve_visual_intent(query) if query else None
    has_structured_visual_events = _has_structured_visual_event(tool_call_events)

    if has_structured_visual_events:
        cleaned = _sanitize_structured_visual_answer_text(
            _strip_widget_blocks(response_text),
            tool_call_events=tool_call_events,
        )
        if cleaned != response_text:
            llm_response = _build_response(cleaned)
            response_text = cleaned

    if (
        structured_visuals_enabled
        and visual_decision
        and visual_decision.force_tool
        and visual_decision.mode in {"template", "inline_html"}
    ):
        return llm_response

    if "```widget" in response_text:
        return llm_response

    widget_blocks: list[str] = []
    for event in tool_call_events:
        if event.get("type") != "result":
            continue
        result_text = event.get("result", "")
        matches = re.findall(r"(```widget\n.+?```)", result_text, re.DOTALL)
        widget_blocks.extend(matches)

    if not widget_blocks:
        return llm_response

    injected = "\n\n".join(widget_blocks) + "\n\n" + response_text
    return _build_response(injected)
