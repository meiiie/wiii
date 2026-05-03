"""Resolved capability + policy view of a ``TurnRequest``.

Phase 4 of the runtime migration epic (issue #207). The intent object
sits between ``TurnRequest`` (what the caller asked for) and
``ExecutionLane`` (where the turn will run). It collapses caller hints,
org policy, and content sniffing into a single dataclass the lane
resolver can read without re-parsing the request.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from .turn_request import TurnRequest


class RuntimeIntent(BaseModel):
    """Capability + policy resolution for a single turn."""

    needs_streaming: bool = False
    """Caller asked for SSE; sets the dispatch shape."""

    needs_tools: bool = False
    """Turn likely needs tool/function calling — driven by request hint
    or downstream routing decision."""

    needs_structured_output: bool = False
    """Turn expects a JSON-Schema-validated response."""

    needs_vision: bool = False
    """Turn includes image content blocks."""

    preferred_provider: Optional[str] = None
    """Caller or org-policy preferred provider (``"google"`` etc.).
    The resolver may override based on lane availability."""

    fallback_chain: list[str] = Field(
        default_factory=lambda: ["google", "openai", "ollama"]
    )
    """Provider failover order. Fixed in this minimal scaffold; later
    phases pull from ``settings.llm_failover_chain``."""

    org_policy: dict = Field(default_factory=dict)
    """Org-level overrides (allowed providers, region restrictions,
    cost ceilings). Empty by default for personal workspace."""


def _has_vision_content(messages: list) -> bool:
    """Detect image/vision blocks in any message content list."""
    for msg in messages:
        content = getattr(msg, "content", None) or ""
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") in {
                    "image",
                    "image_url",
                    "input_image",
                }:
                    return True
    return False


def derive_intent(request: TurnRequest) -> RuntimeIntent:
    """Build a ``RuntimeIntent`` from a ``TurnRequest``.

    Reads only request-local signals — caller hints, content shape — and
    produces a deterministic intent. Org policy enrichment happens in a
    follow-up step (the resolver will merge ``settings`` / membership
    data on top before returning a final lane).
    """
    caps = {c.lower() for c in request.requested_capabilities}
    return RuntimeIntent(
        needs_streaming=request.requested_streaming,
        needs_tools="tools" in caps or "tool_use" in caps,
        needs_structured_output="structured_output" in caps
        or "json" in caps
        or "json_schema" in caps,
        needs_vision="vision" in caps or _has_vision_content(request.messages),
        preferred_provider=request.metadata.get("preferred_provider"),
    )


__all__ = ["RuntimeIntent", "derive_intent"]
