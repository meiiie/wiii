"""Canonical request object for a single turn through the runtime.

Phase 4 of the runtime migration epic (issue #207). Every edge protocol
adapter — Wiii native, OpenAI Chat Completions, Anthropic Messages —
normalises its incoming request into a ``TurnRequest`` before the runtime
resolver kicks in. Internal services see one shape, never the wire shape.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.engine.messages import Message


class TurnRequest(BaseModel):
    """Single internal request schema for one chat turn.

    The fields below are deliberately minimal — anything provider-specific
    (OpenAI ``temperature``, Anthropic ``top_k``, Gemini ``thinking_budget``)
    rides in ``metadata`` so the canonical type does not balloon.
    """

    messages: list[Message]
    """Full conversation history including the new user turn."""

    user_id: str
    """Stable user identifier — used for rate limiting + memory routing."""

    session_id: str
    """Conversation session — multiple turns within a single chat."""

    org_id: Optional[str] = None
    """Multi-tenant organisation; ``None`` for personal workspace."""

    domain_id: Optional[str] = None
    """Active domain plugin (``maritime``, ``traffic_law``, ...)."""

    role: str = "student"
    """User role (``student`` / ``teacher`` / ``admin``)."""

    requested_streaming: bool = False
    """Caller asked for SSE streaming."""

    requested_capabilities: list[str] = Field(default_factory=list)
    """Caller-requested capability flags such as ``"tools"``,
    ``"structured_output"``, ``"vision"``. Treated as a hint — the resolver
    may upgrade or downgrade depending on the lane."""

    metadata: dict = Field(default_factory=dict)
    """Free-form provider-specific options. Adapters write into this; the
    resolver may read from it to make routing decisions."""


__all__ = ["TurnRequest"]
