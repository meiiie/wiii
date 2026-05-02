"""Lane-aware timeout/SLA policies for user-facing Wiii turns."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.engine.multi_agent.direct_intent import (
    _looks_emotional_support_turn,
    _looks_identity_selfhood_turn,
    _looks_selfhood_followup_turn,
    _normalize_for_intent,
)
from app.engine.multi_agent.direct_reasoning import _infer_direct_thinking_mode


@dataclass(frozen=True, slots=True)
class LaneTimeoutPolicy:
    """Resolved timeout strategy for one runtime lane/turn."""

    timeout_profile: str | None = None
    primary_timeout: float | None = None
    reason: str | None = None


_DIRECT_ORIGIN_MARKERS: tuple[str, ...] = (
    "sinh ra",
    "duoc sinh ra",
    "duoc tao",
    "nguon goc",
    "ra doi",
    "the wiii lab",
    "dem mua",
)

_PRODUCT_COMPARE_MARKERS: tuple[str, ...] = (
    "so sanh",
    "compare",
    "gia",
    "price",
    "re nhat",
    "duoi",
    "top",
)


def _normalize_provider_name(provider_name: str | None) -> str:
    return str(provider_name or "").strip().lower()


def _is_host_ui_navigation_route(state: object | None) -> bool:
    if not isinstance(state, dict):
        return False
    metadata = state.get("routing_metadata")
    if not isinstance(metadata, dict):
        return False
    return str(metadata.get("intent") or "").strip().lower() == "host_ui_navigation"


def _looks_origin_probe(query: str) -> bool:
    normalized = _normalize_for_intent(query)
    if not normalized:
        return False
    return any(marker in normalized for marker in _DIRECT_ORIGIN_MARKERS)


def resolve_direct_lane_timeout_policy_impl(
    *,
    provider_name: str | None,
    query: str,
    state: object | None,
    is_identity_turn: bool,
    is_short_house_chatter: bool,
    use_house_voice_direct: bool,
    tools_bound: bool,
) -> LaneTimeoutPolicy:
    """Return a provider-aware timeout policy for direct no-tool turns."""
    from app.engine.llm_pool import TIMEOUT_PROFILE_STRUCTURED

    if _is_host_ui_navigation_route(state):
        return LaneTimeoutPolicy(
            timeout_profile=TIMEOUT_PROFILE_STRUCTURED,
            primary_timeout=8.0,
            reason="host_ui_navigation",
        )

    if tools_bound:
        return LaneTimeoutPolicy(reason="tool_bound")

    normalized_provider = _normalize_provider_name(provider_name)
    if normalized_provider != "zhipu":
        return LaneTimeoutPolicy(reason="provider_default")

    if _looks_emotional_support_turn(query):
        return LaneTimeoutPolicy(
            timeout_profile=TIMEOUT_PROFILE_STRUCTURED,
            primary_timeout=8.0,
            reason="zhipu_emotional_support",
        )

    if is_identity_turn or _looks_selfhood_followup_turn(query, state):
        if _looks_origin_probe(query) or _looks_selfhood_followup_turn(query, state):
            return LaneTimeoutPolicy(
                timeout_profile=TIMEOUT_PROFILE_STRUCTURED,
                primary_timeout=18.0,
                reason="zhipu_selfhood_story",
            )
        return LaneTimeoutPolicy(
            timeout_profile=TIMEOUT_PROFILE_STRUCTURED,
            primary_timeout=10.0,
            reason="zhipu_identity",
        )

    thinking_mode = _infer_direct_thinking_mode(query, state or {}, [])
    if thinking_mode == "analytical_math":
        return LaneTimeoutPolicy(
            primary_timeout=18.0,
            reason="zhipu_analytical_math",
        )
    if thinking_mode in {"analytical_market", "analytical_general"}:
        return LaneTimeoutPolicy(
            primary_timeout=12.0,
            reason=f"zhipu_{thinking_mode}",
        )

    if is_short_house_chatter or use_house_voice_direct:
        return LaneTimeoutPolicy(
            timeout_profile=TIMEOUT_PROFILE_STRUCTURED,
            primary_timeout=3.0,
            reason="zhipu_house_chatter",
        )

    return LaneTimeoutPolicy(reason="provider_default")


def resolve_direct_fallback_provider_allowlist_impl(
    *,
    provider_name: str | None,
    query: str,
    state: object | None,
    is_identity_turn: bool,
    is_short_house_chatter: bool,
    use_house_voice_direct: bool,
    tools_bound: bool,
) -> tuple[str, ...] | None:
    """Restrict cross-provider fallback for Wiii-critical direct turns.

    Selfhood and emotional-support turns should stay on Wiii-safe providers.
    If Zhipu cannot complete them, prefer the local Ollama path before
    accepting a lower-fidelity generic cloud fallback.
    """
    if tools_bound or is_short_house_chatter or use_house_voice_direct:
        return None

    normalized_provider = _normalize_provider_name(provider_name)
    if normalized_provider != "zhipu":
        return None

    if _looks_emotional_support_turn(query):
        return ("ollama",)

    if is_identity_turn or _looks_selfhood_followup_turn(query, state):
        return ("ollama",)

    return None


def resolve_product_curation_timeout_impl(
    *,
    provider_name: str | None,
    query: str,
    total_products: int,
    requested_timeout: float | None = None,
) -> float:
    """Choose a bounded curation timeout without over-waiting on slow providers."""
    if requested_timeout is not None:
        return float(requested_timeout)

    normalized_provider = _normalize_provider_name(provider_name)
    if normalized_provider != "zhipu":
        return 10.0

    normalized_query = _normalize_for_intent(query)
    is_compare_turn = any(marker in normalized_query for marker in _PRODUCT_COMPARE_MARKERS)

    if total_products >= 40 or is_compare_turn:
        return 8.0
    if total_products >= 20:
        return 7.0
    return 6.0
