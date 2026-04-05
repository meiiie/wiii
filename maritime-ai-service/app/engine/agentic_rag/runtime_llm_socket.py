"""Runtime LLM socket helpers for agentic RAG components."""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional
from unittest.mock import Mock

from app.engine.llm_factory import ThinkingTier
from app.engine.llm_pool import ainvoke_with_failover, get_llm_for_provider

logger = logging.getLogger(__name__)


def resolve_agentic_rag_llm(
    *,
    tier: ThinkingTier,
    cached_llm: Any = None,
    fallback_factory: Optional[Callable[[], Any]] = None,
    component: str = "agentic_rag",
) -> Any:
    """Resolve the request-time LLM for an agentic RAG component.

    Preference order:
    1. Shared runtime-selectable route from the LLM pool
    2. Existing cached instance
    3. Legacy fallback factory for compatibility/test seams
    """

    if isinstance(cached_llm, Mock):
        return cached_llm

    if isinstance(fallback_factory, Mock):
        try:
            return fallback_factory()
        except Exception as exc:
            logger.warning(
                "[%s] Mocked %s-tier fallback unavailable: %s",
                component,
                getattr(tier, "value", str(tier)),
                exc,
            )
            return cached_llm

    try:
        llm = get_llm_for_provider(None, default_tier=tier)
        if llm is not None:
            return llm
    except Exception as exc:
        logger.warning(
            "[%s] Runtime %s-tier LLM unavailable: %s",
            component,
            getattr(tier, "value", str(tier)),
            exc,
        )

    if cached_llm is not None:
        return cached_llm

    if fallback_factory is not None:
        try:
            return fallback_factory()
        except Exception as exc:
            logger.warning(
                "[%s] Legacy %s-tier fallback unavailable: %s",
                component,
                getattr(tier, "value", str(tier)),
                exc,
            )

    return None


def _normalize_tier_name(tier: ThinkingTier | str) -> str:
    return str(getattr(tier, "value", tier) or "moderate").strip().lower() or "moderate"


async def ainvoke_agentic_rag_llm(
    *,
    llm: Any,
    messages: Any,
    tier: ThinkingTier | str,
    component: str = "agentic_rag",
    provider: Optional[str] = None,
    timeout_profile: Optional[str] = None,
    primary_timeout: Optional[float] = None,
) -> Any:
    """Invoke an agentic RAG LLM through the shared failover socket.

    This keeps async agentic-RAG callsites provider-agnostic at invocation
    time instead of only at object-selection time.
    """

    if llm is None:
        raise RuntimeError(f"{component} LLM is unavailable")

    if isinstance(llm, Mock):
        return await llm.ainvoke(messages)

    tier_name = _normalize_tier_name(tier)
    try:
        return await ainvoke_with_failover(
            llm,
            messages,
            tier=tier_name,
            provider=provider,
            failover_mode="auto",
            prefer_selectable_fallback=provider in {None, "", "auto"},
            primary_timeout=primary_timeout,
            timeout_profile=timeout_profile,
        )
    except Exception as exc:
        logger.warning(
            "[%s] %s-tier invoke failed via runtime failover: %s",
            component,
            tier_name,
            exc,
        )
        raise
