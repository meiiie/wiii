"""
HostContext & HostCapabilities -- generic host application context models.
Sprint 222: Universal Context Engine.
MCP-compatible schema: Resources (context) + Tools (actions).
"""
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
