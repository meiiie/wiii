"""Shared code-studio reasoning cues and reflections."""

from __future__ import annotations

from app.engine.multi_agent.direct_intent import _needs_analysis_tool, _normalize_for_intent
from app.engine.multi_agent.state import AgentState
from app.engine.multi_agent.tool_collection import _needs_browser_snapshot


def _infer_code_studio_reasoning_cue(
    query: str,
    tool_names: list[str] | None = None,
) -> str:
    """Map code-studio requests into stable reasoning cues."""
    tool_names = tool_names or []
    normalized = _normalize_for_intent(query)
    tool_set = set(tool_names)

    if "tool_create_visual_code" in tool_set:
        return "visual"
    if "tool_browser_snapshot_url" in tool_set or _needs_browser_snapshot(query):
        return "browser"
    if "tool_generate_html_file" in tool_set or any(
        token in normalized for token in ("html", "landing page", "website", "web app", "microsite")
    ):
        return "html"
    if "tool_generate_excel_file" in tool_set or any(
        token in normalized for token in ("excel", "xlsx", "spreadsheet")
    ):
        return "spreadsheet"
    if "tool_generate_word_document" in tool_set or any(
        token in normalized for token in ("word", "docx", "memo", "proposal", "report")
    ):
        return "document"
    if "tool_execute_python" in tool_set or _needs_analysis_tool(query):
        if any(token in normalized for token in ("bieu do", "chart", "plot", "matplotlib", "seaborn", "png", "svg")):
            return "chart"
        return "python"
    return "build"


async def _build_code_studio_reasoning_summary(
    query: str,
    state: AgentState,
    tool_names: list[str] | None,
    *,
    render_reasoning_fast,
) -> str:
    """Build safe code-studio reasoning summary for UI display."""
    cue = _infer_code_studio_reasoning_cue(query, tool_names)
    opening = await render_reasoning_fast(
        state=state,
        node="code_studio_agent",
        phase="attune",
        cue=cue,
        tool_names=tool_names,
        style_tags=["code-studio", "summary"],
    )
    closing = await render_reasoning_fast(
        state=state,
        node="code_studio_agent",
        phase="synthesize",
        cue=cue,
        tool_names=tool_names,
        style_tags=["code-studio", "summary"],
    )
    if closing.summary and closing.summary.strip() and closing.summary != opening.summary:
        return closing.summary
    return opening.summary


async def _build_code_studio_tool_reflection(
    state: AgentState,
    tool_name: str,
    result: object,
) -> str:
    """Return a small user-safe progress beat for Code Studio execution."""
    del state, result
    normalized_tool = str(tool_name or "").strip().lower()
    if normalized_tool == "tool_create_visual_code":
        return "Khung dựng đầu tiên đã ra hình; giờ mình chốt lại để bạn mở là dùng được."
    if normalized_tool == "tool_generate_visual":
        return "Phần trực quan đã lên được bộ khung chính; giờ mình gọt lại cho gọn và có hồn."
    if normalized_tool.startswith("tool_generate_"):
        return "Đầu ra kỹ thuật đã có thêm một mảnh rõ ràng; mình đang khâu nó lại cho liền mạch."
    return "Mình vừa có thêm một mảnh dựng mới và đang lắp nó vào bản cuối."
