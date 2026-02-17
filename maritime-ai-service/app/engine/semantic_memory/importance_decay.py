"""
Importance Decay — FadeMem-inspired Ebbinghaus Forgetting Curve

Sprint 73: Living Memory System

Calculates effective importance of stored facts using time-based decay
with access reinforcement. Identity facts never decay; volatile facts
(emotion, recent_topic) decay within hours.

Formula:
  effective_importance = base_importance × retention(t)
  retention(t) = e^(-t / (stability × (1 + access_count × 0.3)))

SOTA Reference (Feb 2026):
  - FadeMem: Ebbinghaus curves — 82% retention at 55% storage
  - LangMem: Temporal decay with access reinforcement
  - Letta/MemGPT: Core memory immutable, archival decays
"""

import logging
import math
from datetime import datetime, timezone
from typing import Optional

from app.models.semantic_memory import (
    IDENTITY_FACT_TYPES,
    LEARNING_FACT_TYPES,
    PERSONAL_FACT_TYPES,
    PROFESSIONAL_FACT_TYPES,
    VOLATILE_FACT_TYPES,
)

logger = logging.getLogger(__name__)

# Access reinforcement factor: each access boosts stability by this fraction
ACCESS_BOOST_FACTOR = 0.3

# Stability in hours per category
STABILITY_HOURS = {
    "identity": float("inf"),   # Never decay
    "professional": 720.0,      # 30 days
    "learning": 168.0,          # 7 days
    "personal": 360.0,          # 15 days
    "volatile": 24.0,           # 1 day (emotion)
    "volatile_topic": 48.0,     # 2 days (recent_topic)
}

# Floor importance per category (never drops below this)
IMPORTANCE_FLOORS = {
    "identity": 0.8,
    "professional": 0.2,
    "learning": 0.15,
    "personal": 0.1,
    "volatile": 0.0,
}


def get_decay_category(fact_type: str) -> str:
    """
    Map a fact_type string to its decay category.

    Args:
        fact_type: One of the 15 FactType values

    Returns:
        Category string: identity, professional, learning, personal, volatile
    """
    if fact_type in IDENTITY_FACT_TYPES:
        return "identity"
    if fact_type in PROFESSIONAL_FACT_TYPES:
        return "professional"
    if fact_type in LEARNING_FACT_TYPES:
        return "learning"
    if fact_type in PERSONAL_FACT_TYPES:
        return "personal"
    if fact_type in VOLATILE_FACT_TYPES:
        return "volatile"
    # Unknown → treat as learning (moderate decay)
    return "learning"


def get_stability_hours(fact_type: str) -> float:
    """
    Get stability duration in hours for a fact type.

    Volatile facts differentiate: emotion=24h, recent_topic=48h.

    Returns:
        Stability in hours. float('inf') for identity facts.
    """
    category = get_decay_category(fact_type)
    if category == "volatile":
        if fact_type == "recent_topic":
            return STABILITY_HOURS["volatile_topic"]
        return STABILITY_HOURS["volatile"]
    return STABILITY_HOURS.get(category, 168.0)


def get_importance_floor(fact_type: str) -> float:
    """
    Get minimum importance floor for a fact type.

    Identity facts never drop below 0.8.
    Volatile facts can decay to 0.0.
    """
    category = get_decay_category(fact_type)
    return IMPORTANCE_FLOORS.get(category, 0.1)


def calculate_retention(
    hours_elapsed: float,
    stability_hours: float,
    access_count: int = 0,
) -> float:
    """
    Calculate retention factor using Ebbinghaus forgetting curve.

    retention(t) = e^(-t / (stability × (1 + access_count × 0.3)))

    Args:
        hours_elapsed: Hours since fact was last accessed or created
        stability_hours: Base stability in hours
        access_count: Number of times fact was retrieved

    Returns:
        Retention factor between 0.0 and 1.0
    """
    if stability_hours == float("inf") or stability_hours <= 0:
        return 1.0

    if hours_elapsed <= 0:
        return 1.0

    effective_stability = stability_hours * (1 + access_count * ACCESS_BOOST_FACTOR)
    return math.exp(-hours_elapsed / effective_stability)


def calculate_effective_importance(
    base_importance: float,
    fact_type: str,
    hours_elapsed: float,
    access_count: int = 0,
) -> float:
    """
    Calculate effective importance with time decay.

    effective_importance = max(base × retention, floor)

    Args:
        base_importance: Original importance score (0.0-1.0)
        fact_type: FactType string value
        hours_elapsed: Hours since last access
        access_count: Number of accesses

    Returns:
        Effective importance (0.0-1.0), never below type floor
    """
    stability = get_stability_hours(fact_type)
    retention = calculate_retention(hours_elapsed, stability, access_count)
    floor = get_importance_floor(fact_type)

    effective = base_importance * retention
    return max(effective, floor)


def calculate_effective_importance_from_timestamps(
    base_importance: float,
    fact_type: str,
    last_accessed: Optional[datetime] = None,
    created_at: Optional[datetime] = None,
    access_count: int = 0,
    now: Optional[datetime] = None,
) -> float:
    """
    Convenience wrapper that computes hours_elapsed from timestamps.

    Uses last_accessed if available, else created_at.
    Falls back to 0 hours if neither is available.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    reference_time = last_accessed or created_at
    if reference_time is None:
        return calculate_effective_importance(base_importance, fact_type, 0, access_count)

    # Ensure timezone-aware comparison
    if reference_time.tzinfo is None:
        reference_time = reference_time.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    delta = now - reference_time
    hours_elapsed = max(delta.total_seconds() / 3600.0, 0.0)

    return calculate_effective_importance(base_importance, fact_type, hours_elapsed, access_count)


def should_prune(
    base_importance: float,
    fact_type: str,
    hours_elapsed: float,
    access_count: int = 0,
    prune_threshold: float = 0.1,
) -> bool:
    """
    Check if a fact should be pruned (decayed below threshold).

    Args:
        prune_threshold: Minimum effective importance to keep

    Returns:
        True if fact should be pruned
    """
    effective = calculate_effective_importance(
        base_importance, fact_type, hours_elapsed, access_count
    )
    return effective < prune_threshold
