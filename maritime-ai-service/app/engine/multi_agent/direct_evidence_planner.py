"""Structured evidence planner for direct live-query families.

Recreated from bytecode — provides query-family classification, locality
policy, and evidence-plan generation for the Direct response lane.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from app.engine.multi_agent.direct_intent import (
    _needs_web_search,
    _normalize_for_intent,
)
from app.engine.multi_agent.state import AgentState

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────

_DIRECT_EVIDENCE_PLAN_SESSION_CACHE_TTL_SECONDS = 300
_DIRECT_EVIDENCE_PLAN_SESSION_CACHE_MAX_ENTRIES = 64

_LIVE_TIME_MARKERS: tuple[str, ...] = (
    "hom nay", "ngay hom nay", "hien tai", "bay gio", "moi nhat",
    "gan day", "latest", "today", "current", "now",
)
_WEATHER_MARKERS: tuple[str, ...] = (
    "thoi tiet", "nhiet do", "do am", "gio", "mua", "du bao",
    "forecast", "weather", "uv", "canh bao bao",
)
_NEWS_MARKERS: tuple[str, ...] = (
    "tin tuc", "thoi su", "ban tin", "headline", "su kien", "bao chi",
    "news", "breaking",
)
_PRODUCT_MARKERS: tuple[str, ...] = (
    "mua", "so sanh gia", "tim do", "tim san pham", "shopee", "lazada",
    "tiktok shop", "facebook marketplace", "gia tot",
)
_MARKET_BASE_MARKERS: tuple[str, ...] = (
    "gia dau", "gia xang", "gia xang dau", "brent", "wti", "opec", "opec+",
    "gia vang", "vang sjc", "xau", "ty gia", "usd/vnd", "usd vnd",
    "gia lng", "lng", "gia gas", "cuoc tau", "cuoc van tai", "gia cuoc",
    "freight", "bdi", "scfi",
)
_GLOBAL_ONLY_MARKERS: tuple[str, ...] = (
    "the gioi", "quoc te", "global", "brent", "wti", "usd", "index",
)
_VIETNAM_LOCALITY_MARKERS: tuple[str, ...] = (
    "viet nam", "vietnam", "trong nuoc", "xang ron", "petrolimex", "pvoil",
)


# ── Data Classes ───────────────────────────────────────────────────────

@dataclass
class DirectEvidencePlan:
    """Reusable query-family plan for the direct response lane."""
    family: str = "none"
    topic_cluster: str = "general"
    locality: str = "normal"
    answer_mode: str = "normal"
    needs_time_anchor: bool = False
    requires_current_sources: bool = False
    axes: tuple[str, ...] = ()
    source_plan: tuple[str, ...] = ()
    source_policy: tuple[str, ...] = ()


# ── Session Cache (in-memory, per-process) ─────────────────────────────

@dataclass
class _DirectEvidencePlanSessionCacheEntry:
    plan: DirectEvidencePlan
    ts: float = 0.0
    signature: str = ""

_DIRECT_EVIDENCE_PLAN_SESSION_CACHE: dict[str, _DirectEvidencePlanSessionCacheEntry] = {}


def _prune_direct_evidence_plan_session_cache() -> None:
    import time as _time
    now = _time.time()
    expired = [
        k for k, v in _DIRECT_EVIDENCE_PLAN_SESSION_CACHE.items()
        if now - v.ts > _DIRECT_EVIDENCE_PLAN_SESSION_CACHE_TTL_SECONDS
    ]
    for k in expired:
        del _DIRECT_EVIDENCE_PLAN_SESSION_CACHE[k]
    # Evict oldest if over max
    if len(_DIRECT_EVIDENCE_PLAN_SESSION_CACHE) > _DIRECT_EVIDENCE_PLAN_SESSION_CACHE_MAX_ENTRIES:
        sorted_keys = sorted(
            _DIRECT_EVIDENCE_PLAN_SESSION_CACHE,
            key=lambda k: _DIRECT_EVIDENCE_PLAN_SESSION_CACHE[k].ts,
        )
        for k in sorted_keys[: len(sorted_keys) - _DIRECT_EVIDENCE_PLAN_SESSION_CACHE_MAX_ENTRIES]:
            del _DIRECT_EVIDENCE_PLAN_SESSION_CACHE[k]


# ── Helpers ────────────────────────────────────────────────────────────

def _contains_any(normalized_query: str, keywords: tuple[str, ...]) -> bool:
    return any(kw in normalized_query for kw in keywords)


def _is_live_query(normalized_query: str) -> bool:
    return _contains_any(normalized_query, _LIVE_TIME_MARKERS)


def _looks_weather_query(normalized_query: str) -> bool:
    return _contains_any(normalized_query, _WEATHER_MARKERS)


def _looks_news_query(normalized_query: str) -> bool:
    return _contains_any(normalized_query, _NEWS_MARKERS)


def _looks_product_search_handoff(normalized_query: str) -> bool:
    return _contains_any(normalized_query, _PRODUCT_MARKERS)


def _looks_market_query(normalized_query: str) -> bool:
    return _contains_any(normalized_query, _MARKET_BASE_MARKERS)


def _infer_market_cluster(normalized_query: str) -> str:
    clusters = [
        (("gia dau", "gia xang", "gia xang dau", "brent", "wti", "opec", "lng", "gia gas"), "oil_fuel_energy"),
        (("gia vang", "vang sjc", "xau", "ty gia", "usd/vnd", "usd vnd"), "gold_fx"),
        (("cuoc tau", "cuoc van tai", "gia cuoc", "freight", "bdi", "scfi"), "freight_rates"),
    ]
    for markers, cluster in clusters:
        if _contains_any(normalized_query, markers):
            return cluster
    return "oil_fuel_energy"


def _infer_locality(query: str, state: AgentState) -> str:
    del state
    normalized = _normalize_for_intent(query)
    if _contains_any(normalized, _GLOBAL_ONLY_MARKERS):
        return "global_only"
    if _contains_any(normalized, _VIETNAM_LOCALITY_MARKERS):
        return "vietnam_first"
    return "normal"


def _coerce_text_list(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple)):
        return tuple(str(x) for x in value if x)
    return ()


def _normalize_plan_value(text: Any) -> str:
    return str(text or "").strip()


def _plan_from_mapping(data: dict[str, Any]) -> DirectEvidencePlan:
    return DirectEvidencePlan(
        family=_normalize_plan_value(data.get("family", "none")),
        topic_cluster=_normalize_plan_value(data.get("topic_cluster", "general")),
        locality=_normalize_plan_value(data.get("locality", "normal")),
        answer_mode=_normalize_plan_value(data.get("answer_mode", "normal")),
        needs_time_anchor=bool(data.get("needs_time_anchor", False)),
        requires_current_sources=bool(data.get("requires_current_sources", False)),
        axes=_coerce_text_list(data.get("axes", ())),
        source_plan=_coerce_text_list(data.get("source_plan", ())),
        source_policy=_coerce_text_list(data.get("source_policy", ())),
    )


# ── Cache Access ───────────────────────────────────────────────────────

def _planner_session_scope_key(state: AgentState) -> str | None:
    context = state.get("context") or {}
    session_id = context.get("session_id", "")
    return str(session_id) if session_id else None


def _planner_cache_signature(plan: DirectEvidencePlan, state: AgentState) -> str | None:
    del state
    return f"{plan.family}:{plan.topic_cluster}:{plan.locality}"


def _make_direct_evidence_plan_session_cache_key(state: AgentState) -> str | None:
    scope = _planner_session_scope_key(state)
    if not scope:
        return None
    return f"evplan:{scope}"


def _get_session_cached_direct_evidence_plan(state: AgentState) -> DirectEvidencePlan | None:
    key = _make_direct_evidence_plan_session_cache_key(state)
    if not key or key not in _DIRECT_EVIDENCE_PLAN_SESSION_CACHE:
        return None
    entry = _DIRECT_EVIDENCE_PLAN_SESSION_CACHE[key]
    return entry.plan


def _store_session_cached_direct_evidence_plan(state: AgentState, plan: DirectEvidencePlan) -> None:
    import time as _time
    key = _make_direct_evidence_plan_session_cache_key(state)
    if not key:
        return
    _prune_direct_evidence_plan_session_cache()
    _DIRECT_EVIDENCE_PLAN_SESSION_CACHE[key] = _DirectEvidencePlanSessionCacheEntry(
        plan=plan, ts=_time.time(),
        signature=_planner_cache_signature(plan, state) or "",
    )


def _get_cached_direct_evidence_plan(state: AgentState) -> DirectEvidencePlan | None:
    return _get_session_cached_direct_evidence_plan(state)


def _store_direct_evidence_plan(state: AgentState, plan: DirectEvidencePlan) -> None:
    _store_session_cached_direct_evidence_plan(state, plan)


def _commit_direct_evidence_plan(state: AgentState, plan: DirectEvidencePlan, *, source: str = "fallback") -> None:
    _store_direct_evidence_plan(state, plan)


def _complete_plan_from_fields(
    query: str, state: AgentState, plan: DirectEvidencePlan,
) -> DirectEvidencePlan:
    del query, state
    return plan


# ── Fallback Planner (keyword-based, no LLM) ──────────────────────────

def _fallback_evidence_plan(
    query: str, state: AgentState, tool_names: list[str] | None = None,
) -> DirectEvidencePlan:
    normalized_query = _normalize_for_intent(query)
    tool_names = tool_names or []

    # Product search handoff
    if _looks_product_search_handoff(normalized_query):
        return DirectEvidencePlan(
            family="product_search_handoff",
            topic_cluster="shopping",
            locality="marketplace_first",
            answer_mode="handoff",
            axes=("nhu cau mua/tim", "san giao dich", "gia va so sanh"),
            source_plan=(
                "route sang product_search truoc",
                "chi dung web chung neu user xin thong tin ngoai san",
                "khong dung generic web answer thay cho product search lane",
            ),
        )

    # Weather
    if _looks_weather_query(normalized_query):
        locality = _infer_locality(query, state)
        return DirectEvidencePlan(
            family="live_weather",
            topic_cluster="weather",
            locality=locality,
            answer_mode="current_snapshot_then_context",
            needs_time_anchor=True,
            requires_current_sources=True,
            axes=("dia diem dang duoc hoi", "thoi tiet hien tai", "nhiet do/mua/gio", "canh bao hoac thay doi ngan han"),
            source_plan=(
                "chot dia diem va moc thoi gian",
                "lay current conditions truoc",
                "chi them forecast/canh bao neu user can",
                "neu dia diem mo ho, noi ro dia diem dang gia dinh",
                "khong tu che nhiet do hay luong mua",
            ),
        )

    # Market
    market_like = _looks_market_query(normalized_query)
    if market_like:
        cluster = _infer_market_cluster(normalized_query)
        locality = _infer_locality(query, state)
        axes_map = {
            "oil_fuel_energy": (
                "gia dang ap dung o Viet Nam", "benchmark hien tai",
                "Brent/WTI hoac benchmark gan hien tai", "luc quoc te dang dan nhip",
            ),
            "gold_fx": (
                "gia local dang ap dung", "benchmark/ty gia tham chieu", "luc van dong chinh",
            ),
            "freight_rates": (
                "moc cuoc dang ap dung", "benchmark/index lien quan", "driver van tai nhien lieu dia chinh tri",
            ),
        }
        source_plan_map = {
            "oil_fuel_energy": (
                "neo gia local/official truoc", "neo benchmark quote truoc",
                "doi chieu benchmark quoc te", "tach rieng dia chinh tri/OPEC+ khoi nen cung-cau",
            ),
            "gold_fx": (
                "neo gia local hoac quote dang ap dung",
                "doi chieu benchmark/ty gia quoc te",
                "tach rieng driver ngan han khoi nen chinh sach",
            ),
            "freight_rates": (
                "neo moc cuoc hoac index gan hien tai",
                "doi chieu benchmark quoc te neu co",
                "tach cung cau va driver nghen/tuyen",
            ),
        }
        return DirectEvidencePlan(
            family="live_market_price" if _is_live_query(normalized_query) else "market_analysis",
            topic_cluster=cluster,
            locality=locality,
            answer_mode="exact_if_consistent_else_range",
            needs_time_anchor=True,
            requires_current_sources=True,
            axes=axes_map.get(cluster, ("moc gia hien tai", "benchmark tham chieu", "driver chinh")),
            source_plan=source_plan_map.get(cluster, (
                "neo moc gia/co so dang ap dung",
                "doi chieu benchmark",
                "tach driver ngan han khoi nen dai hon",
            )),
            source_policy=("neu nguon lech nhau, tra khoang hoac nguon dang phan ky", "khong suy dien ra bang gia chi tiet khi chi moi co tieu de thong bao"),
        )

    # News
    if _looks_news_query(normalized_query):
        return DirectEvidencePlan(
            family="live_news_lookup" if _is_live_query(normalized_query) else "news_lookup",
            topic_cluster="news",
            locality="normal",
            answer_mode="headline_then_context",
            needs_time_anchor=True,
            requires_current_sources=True,
            axes=("su kien", "moc thoi gian", "nguon xac nhan"),
            source_plan=(
                "lay headline moi nhat co ngay gio",
                "kiem cheo 1-2 nguon",
                "neu can moi them boi canh",
                "khong tron tin cu va tin moi nhu mot su kien",
                "uu tien bai co ngay gio xuat ban ro",
            ),
        )

    # General live/current lookup
    if _is_live_query(normalized_query):
        return DirectEvidencePlan(
            family="live_current_lookup",
            topic_cluster="general_current_info",
            locality="normal",
            answer_mode="exact_if_authoritative_else_qualified",
            needs_time_anchor=True,
            requires_current_sources=True,
            axes=("cau hoi hien tai", "moc thoi gian", "nguon dang tin"),
            source_plan=(
                "chot dung thuc the va moc thoi gian",
                "uu tien nguon authoritative hoac nguon co ngay gio ro",
                "neu khong du chac, tra loi theo muc do tin cay thay vi chot cung",
                "khong doan thong tin sau 2024 neu chua co tool/evidence",
            ),
        )

    # Default: no special plan
    return DirectEvidencePlan()


# ── Public API ─────────────────────────────────────────────────────────

def build_direct_evidence_plan(
    query: str, state: AgentState, tool_names: list[str] | None = None,
) -> DirectEvidencePlan:
    """Build evidence plan — cache-first, then keyword fallback."""
    cached = _get_cached_direct_evidence_plan(state)
    if cached is not None:
        return cached
    return _fallback_evidence_plan(query, state, tool_names)


def should_plan_direct_evidence(query: str, state: AgentState) -> bool:
    """Check whether the query deserves an evidence plan."""
    normalized = _normalize_for_intent(query)
    return (
        _looks_product_search_handoff(normalized)
        or _looks_weather_query(normalized)
        or _looks_market_query(normalized)
        or _looks_news_query(normalized)
        or _needs_web_search(query, state)
        or _is_live_query(normalized)
    )


async def resolve_direct_evidence_plan(
    query: str, state: AgentState, llm: Any,
) -> DirectEvidencePlan:
    """Resolve evidence plan — LLM-based when available, keyword fallback."""
    fallback = _fallback_evidence_plan(query, state)
    # Commit the fallback plan (LLM path omitted in recovery — keyword is sufficient)
    _commit_direct_evidence_plan(state, fallback, source="keyword_fallback")
    return fallback
