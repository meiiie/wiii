"""Capability-aware planner for parallel subagent orchestration.

This is a lightweight runtime planner inspired by AgentSkillOS/ToolOrchestra:
- cheap intent priors instead of another full LLM hop
- handbook competence/cost signals to bias target selection
- stable mapping from living capabilities to concrete subagents
"""

from __future__ import annotations

import unicodedata
from typing import Dict, Optional

from app.engine.skills.skill_handbook import SkillHandbookEntry, get_skill_handbook

_PRIMARY_ROUTE_TO_TARGET = {
    "rag_agent": "rag",
    "tutor_agent": "tutor",
    "product_search_agent": "search",
}

_INTENT_PRIORS: Dict[str, Dict[str, float]] = {
    "lookup": {"rag": 1.15, "tutor": 0.6},
    "learning": {"tutor": 1.15, "rag": 0.9},
    "product_search": {"search": 1.2, "rag": 0.55, "tutor": 0.3},
    "web_search": {"rag": 0.8, "tutor": 0.25},
}

_QUERY_HINTS = [
    (("giai thich", "vi sao", "how", "why", "huong dan", "de hieu"), {"tutor": 0.4}),
    (("quy dinh", "rule", "dieu", "tai lieu", "nguon", "colreg", "solas", "imo"), {"rag": 0.45}),
    (("gia", "re", "cheap", "shop", "mua", "san pham", "marketplace", "so sanh"), {"search": 0.5}),
]


def _normalize(text: str) -> str:
    text = (text or "").strip().lower()
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).replace("đ", "d")


def _score_entry(entry: SkillHandbookEntry, rank: int) -> float:
    latency_factor = 0.08
    if entry.avg_latency_ms > 0:
        latency_factor = 1.0 / (1.0 + entry.avg_latency_ms / 1500.0)

    cost_factor = 0.05
    if entry.avg_cost_usd > 0:
        cost_factor = 1.0 / (1.0 + entry.avg_cost_usd * 80.0)

    rank_bonus = max(0.0, 0.22 - (rank * 0.04))
    return (entry.competence_score * 0.55) + (latency_factor * 0.15) + (cost_factor * 0.08) + rank_bonus


def _target_from_handbook_entry(entry: SkillHandbookEntry) -> str:
    selector_category = (entry.selector_category or "").strip().lower()
    capability_parts = {part.strip().lower() for part in entry.capability_path}

    if selector_category == "product_search" or capability_parts.intersection({"commerce", "shopping", "comparison", "sourcing", "vision"}):
        return "search"
    if selector_category in {"learning", "assessment"} or capability_parts.intersection({"learning", "assessment", "teaching", "analysis"}):
        return "tutor"
    return "rag"


def plan_parallel_targets(
    query: str,
    primary_agent: str,
    *,
    intent: Optional[str] = None,
    max_targets: int = 2,
) -> list[str]:
    """Pick the best parallel subagents for a complex query."""
    primary_target = _PRIMARY_ROUTE_TO_TARGET.get(primary_agent)
    if not primary_target:
        return []

    scores = {"rag": 0.0, "tutor": 0.0, "search": 0.0}
    scores[primary_target] += 1.0

    normalized_intent = (intent or "").strip().lower()
    for target, boost in _INTENT_PRIORS.get(normalized_intent, {}).items():
        scores[target] += boost

    normalized_query = _normalize(query)
    for keywords, boosts in _QUERY_HINTS:
        if any(keyword in normalized_query for keyword in keywords):
            for target, boost in boosts.items():
                scores[target] += boost

    try:
        suggestions = get_skill_handbook().suggest_for_query(
            query,
            intent=normalized_intent or None,
            max_entries=6,
        )
    except Exception:
        suggestions = []

    for rank, entry in enumerate(suggestions):
        target = _target_from_handbook_entry(entry)
        scores[target] += _score_entry(entry, rank)

    targets = [primary_target]
    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    primary_score = scores.get(primary_target, 1.0)

    for target, score in ordered:
        if target in targets:
            continue
        if len(targets) >= max_targets:
            break
        if score < 0.75:
            continue
        if score < (primary_score * 0.35):
            continue
        targets.append(target)

    return targets
