"""
HostContext & HostCapabilities -- generic host application context models.
Sprint 222: Universal Context Engine.
MCP-compatible schema: Resources (context) + Tools (actions).
"""
import json
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator

MAX_SNIPPET_LENGTH = 2000


class HostContext(BaseModel):
    """Generic context from any host application."""
    host_type: str = Field(..., description="Host app type: lms | ecommerce | trading | crm | custom")
    host_name: Optional[str] = Field(default=None, description="Human-readable host name")
    resource_uri: str = Field(default="host://current-page", description="MCP Resource URI")
    page: dict[str, Any] = Field(..., description="Current page: {type, title?, url?, metadata?}")
    user_state: Optional[dict[str, Any]] = Field(default=None, description="User interaction state")
    content: Optional[dict[str, Any]] = Field(default=None, description="Content: {snippet?, structured?}")
    available_actions: Optional[list[dict[str, Any]]] = Field(default=None, description="Host-declared actions")

    @field_validator("content", mode="before")
    @classmethod
    def truncate_snippet(cls, v):
        if v and isinstance(v, dict) and "snippet" in v:
            snippet = v.get("snippet")
            if snippet and len(snippet) > MAX_SNIPPET_LENGTH:
                v = {**v, "snippet": snippet[:MAX_SNIPPET_LENGTH]}
        return v


class HostCapabilities(BaseModel):
    """Capability declaration from host app (sent once on iframe load)."""
    host_type: str
    host_name: Optional[str] = None
    resources: list[str] = Field(default_factory=list)
    tools: list[dict[str, Any]] = Field(default_factory=list)


def from_legacy_page_context(
    page_context: dict,
    student_state=None,
    available_actions=None,
) -> HostContext:
    """Convert Sprint 221 PageContext dict to HostContext (backward compat)."""
    page_type = page_context.get("page_type", "unknown")
    page_title = page_context.get("page_title")

    metadata = {}
    for key in ("course_id", "course_name", "lesson_id", "lesson_name",
                "chapter_name", "content_type", "quiz_question", "quiz_options",
                "assignment_description"):
        val = page_context.get(key)
        if val is not None:
            metadata[key] = val

    page = {"type": page_type, "title": page_title, "metadata": metadata}

    content = None
    snippet = page_context.get("content_snippet")
    if snippet:
        content = {"snippet": snippet}

    user_state_dict = None
    if student_state:
        if isinstance(student_state, dict):
            user_state_dict = student_state
        elif hasattr(student_state, "model_dump"):
            user_state_dict = student_state.model_dump(exclude_none=True)
        else:
            user_state_dict = dict(student_state)

    actions_list = None
    if available_actions:
        actions_list = [
            a if isinstance(a, dict) else a.model_dump() if hasattr(a, "model_dump") else dict(a)
            for a in available_actions
        ]

    return HostContext(
        host_type="lms",
        page=page,
        user_state=user_state_dict,
        content=content,
        available_actions=actions_list,
    )


# ── Structured Data Formatters (Sprint 223) ──

_STATUS_VN = {
    "active": "Đang học",
    "completed": "Hoàn thành",
    "NOT_STARTED": "Chưa bắt đầu",
    "IN_PROGRESS": "Đang làm",
    "SUBMITTED": "Đã nộp",
    "GRADED": "Đã chấm",
    "OVERDUE": "Quá hạn",
}


def _format_grades(data: dict) -> str:
    lines = []
    for i, c in enumerate(data.get("courses", []), 1):
        status = _STATUS_VN.get(c.get("status", ""), c.get("status", ""))
        grade_str = f", điểm {c['grade']}" if c.get("grade") is not None else ""
        lines.append(
            f"  {i}. {c.get('code', '')} — {c.get('name', '')}: "
            f"tiến độ {c.get('progress', 0)}%, {status}{grade_str}"
        )
    summary = data.get("summary", {})
    lines.append(
        f"  Tổng kết: {summary.get('total', 0)} khóa, "
        f"{summary.get('completed', 0)} hoàn thành, "
        f"tiến độ TB {summary.get('avg_progress', 0)}%"
    )
    return "\n".join(lines)


def _format_assignment_list(data: dict) -> str:
    lines = []
    for i, a in enumerate(data.get("assignments", []), 1):
        status = _STATUS_VN.get(a.get("status", ""), a.get("status", ""))
        due = a.get("due_date", "")[:10] if a.get("due_date") else "không rõ"
        lines.append(
            f"  {i}. {a.get('name', '')} ({a.get('course_name', '')}) — "
            f"hạn {due}, {status}"
        )
    summary = data.get("summary", {})
    lines.append(
        f"  Tổng: {summary.get('total', 0)} bài tập, "
        f"{summary.get('pending', 0)} cần làm, "
        f"{summary.get('overdue', 0)} quá hạn"
    )
    return "\n".join(lines)


def _format_lesson(data: dict) -> str:
    lines = [
        f"  Khóa: {data.get('course_name', '')} / {data.get('chapter_name', '')}",
        f"  Bài: {data.get('lesson_title', '')}",
        f"  Tiến độ: {data.get('progress', 0)}%",
    ]
    if data.get("media_types"):
        lines.append(f"  Nội dung: {', '.join(data['media_types'])}")
    if data.get("content_text"):
        lines.append(f"  Nội dung bài học: {data['content_text'][:2000]}")
    return "\n".join(lines)


def _format_quiz(data: dict) -> str:
    lines = [
        f"  Bài kiểm tra: {data.get('quiz_title', '')}",
        f"  Câu hỏi {data.get('question_number', '?')}/{data.get('total_questions', '?')}",
        f"  Nội dung: {data.get('question_text', '')}",
    ]
    if data.get("options"):
        for j, opt in enumerate(data["options"]):
            lines.append(f"    {chr(65 + j)}) {opt}")
    if data.get("attempts_used") is not None:
        lines.append(f"  Số lần thử: {data['attempts_used']}")
    if data.get("time_remaining_seconds") is not None:
        mins = data["time_remaining_seconds"] // 60
        lines.append(f"  Thời gian còn: {mins} phút")
    return "\n".join(lines)


def _format_course_overview(data: dict) -> str:
    lines = [
        f"  Khóa: {data.get('course_code', '')} — {data.get('course_name', '')}",
        f"  Giảng viên: {data.get('instructor', '')}",
        f"  Tiến độ: {data.get('total_progress', 0)}%",
    ]
    for ch in data.get("chapters", []):
        lines.append(
            f"    - {ch.get('name', '')}: "
            f"{ch.get('completed', 0)}/{ch.get('lesson_count', 0)} bài"
        )
    return "\n".join(lines)


_FORMATTERS = {
    "grades": _format_grades,
    "assignment_list": _format_assignment_list,
    "lesson": _format_lesson,
    "quiz": _format_quiz,
    "course_overview": _format_course_overview,
}


def format_structured_data_for_prompt(ctx: "HostContext") -> str:
    """Format structured page data as Vietnamese text for prompt injection.

    Sprint 223: Hybrid Visual Context Engine -- Path A.
    Returns empty string if no structured data available.
    """
    if not ctx.content or not isinstance(ctx.content, dict):
        return ""
    structured = ctx.content.get("structured")
    if not structured or not isinstance(structured, dict):
        return ""

    data_type = structured.get("_type", "")
    formatter = _FORMATTERS.get(data_type)
    if formatter:
        return formatter(structured)

    # Fallback: JSON dump for unknown types
    return json.dumps(structured, ensure_ascii=False, indent=2)
