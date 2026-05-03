"""Wiii native message types — replaces langchain_core.messages.

Single source of truth for in-flight messages. Adapters at the edge
(``messages_adapters``) convert to provider-specific dict shape. The dict
shape loosely follows OpenAI Chat Completions (which Anthropic and Gemini
also support via their OpenAI-compat endpoints).

Phase 1 of the runtime migration epic (issue #207) introduces these types
to start de-coupling from ``langchain_core.messages``. While ``BaseChatModel``
still exists (Phase 3 owns its removal), consumer call sites convert
``Message`` → OpenAI dict via ``to_openai_dict`` before passing to
``llm.ainvoke([...])``; ``BaseChatModel._convert_input`` then revives the
dicts back into LangChain ``BaseMessage`` subclasses. After Phase 3 the
intermediate revival step disappears.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

MessageRole = Literal["system", "user", "assistant", "tool"]


class ToolCall(BaseModel):
    """A single tool invocation requested by an assistant turn."""

    id: str
    name: str
    arguments: dict = Field(default_factory=dict)


class ToolResult(BaseModel):
    """Result returned to the model from a tool execution."""

    tool_call_id: str
    content: str
    is_error: bool = False


_ROLE_TO_LC_TYPE = {
    "system": "system",
    "user": "human",
    "assistant": "ai",
    "tool": "tool",
}


class Message(BaseModel):
    """Native chat message used across Wiii's runtime."""

    role: MessageRole
    content: str = ""
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[list[ToolCall]] = None

    @property
    def type(self) -> str:
        """LangChain-compatible type alias.

        Some legacy call sites still introspect ``msg.type`` (LC ``BaseMessage``
        attribute). Provide a read-only alias mapping ``role`` → LC ``type`` so
        Phase 9b RECEIVE-coupled paths keep working while the rest of the
        codebase migrates to direct ``role`` checks.
        """
        return _ROLE_TO_LC_TYPE.get(self.role, "human")


__all__ = ["Message", "MessageRole", "ToolCall", "ToolResult"]
