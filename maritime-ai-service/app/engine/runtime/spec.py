"""Canonical resolved runtime config.

Resolves provider/model/endpoint/auth/capability AT ROUTE TIME, not
request time. Borrowed from Unsloth ``ModelConfig`` pattern.

Phase 0: minimal stub (this file). Phase 4 will:
- Add capability detection from real metadata (chat templates, model
  config) rather than static booleans
- Add a resolver factory that builds ``RuntimeModelSpec`` from a
  ``TurnRequest`` + ``RuntimeIntent`` + provider registry state
- Wire the resolver into ``LLMPool`` so every dispatch path sees the
  same canonical object
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True, slots=True)
class RuntimeModelSpec:
    """One authoritative object for a turn's resolved runtime contract.

    Wiii's equivalent of Unsloth's ``ModelConfig``, but tuned for
    cloud-provider routing instead of local-model loading.

    All capability flags default to ``True`` for cloud chat models and
    are narrowed by the resolver based on the lane and provider.
    """

    provider: str
    """Provider key matching ``LLMPool`` registry, e.g. ``"google"``,
    ``"openai"``, ``"ollama"``, ``"anthropic"``."""

    model: str
    """Concrete model name as the provider expects it,
    e.g. ``"gemini-3.1-flash-lite-preview"``."""

    endpoint: Optional[str] = None
    """Override base URL for OpenAI-compatible endpoints. ``None`` means
    the provider's official endpoint."""

    tier: str = "moderate"
    """One of ``"deep"``, ``"moderate"``, ``"light"``. Drives
    ``LLMPool`` failover semantics."""

    supports_streaming: bool = True
    supports_tools: bool = True
    supports_structured_output: bool = True
    supports_vision: bool = False
    supports_reasoning: bool = False
    """``reasoning`` here means the model exposes a separate thinking
    channel (Claude extended thinking, OpenAI o-series). Distinct from
    chain-of-thought in the user-visible response."""

    context_window: int = 0
    """Effective context window in tokens. ``0`` = unknown (Phase 4
    will populate from a model catalog)."""

    timeout_profile: Optional[str] = None
    """Optional timeout profile name (e.g.
    ``TIMEOUT_PROFILE_STRUCTURED``) consumed by lane resolvers when
    bounding LLM calls."""
