"""
Tests for app.engine.semantic_memory.importance_decay

Sprint 73: Importance Decay — Ebbinghaus forgetting curve with access reinforcement.

Covers:
- Category mapping for all 15 fact types + unknown
- Stability hours per category
- Importance floors per category
- Retention formula (calculate_retention)
- Effective importance with floor clamping
- Timestamp-based convenience wrapper
- Pruning logic
- Edge cases (zero hours, negative hours, zero access, inf stability)
"""

import math
from datetime import datetime, timedelta, timezone

import pytest

from app.engine.semantic_memory.importance_decay import (
    ACCESS_BOOST_FACTOR,
    IMPORTANCE_FLOORS,
    STABILITY_HOURS,
    calculate_effective_importance,
    calculate_effective_importance_from_timestamps,
    calculate_retention,
    get_decay_category,
    get_importance_floor,
    get_stability_hours,
    should_prune,
)


# ─── 1. Category mapping ──────────────────────────────────────────────

class TestGetDecayCategory:
    """Category mapping for all 15 fact types + unknown fallback."""

    @pytest.mark.parametrize("fact_type", ["name", "age"])
    def test_identity_fact_types(self, fact_type: str):
        assert get_decay_category(fact_type) == "identity"

    @pytest.mark.parametrize("fact_type", ["role", "level", "location", "organization"])
    def test_professional_fact_types(self, fact_type: str):
        assert get_decay_category(fact_type) == "professional"

    @pytest.mark.parametrize("fact_type", ["goal", "preference", "weakness", "strength", "learning_style"])
    def test_learning_fact_types(self, fact_type: str):
        assert get_decay_category(fact_type) == "learning"

    @pytest.mark.parametrize("fact_type", ["hobby", "interest"])
    def test_personal_fact_types(self, fact_type: str):
        assert get_decay_category(fact_type) == "personal"

    @pytest.mark.parametrize("fact_type", ["emotion", "recent_topic"])
    def test_volatile_fact_types(self, fact_type: str):
        assert get_decay_category(fact_type) == "volatile"

    def test_unknown_fact_type_falls_back_to_learning(self):
        """Unknown fact types default to 'learning' (moderate decay)."""
        assert get_decay_category("unknown_xyz") == "learning"
        assert get_decay_category("") == "learning"


# ─── 2. Stability hours ───────────────────────────────────────────────

class TestGetStabilityHours:
    """Stability hours for each category and volatile sub-types."""

    def test_identity_stability_is_infinite(self):
        assert get_stability_hours("name") == float("inf")
        assert get_stability_hours("age") == float("inf")

    def test_professional_stability_720h(self):
        assert get_stability_hours("role") == 720.0
        assert get_stability_hours("organization") == 720.0

    def test_learning_stability_168h(self):
        assert get_stability_hours("goal") == 168.0
        assert get_stability_hours("learning_style") == 168.0

    def test_personal_stability_360h(self):
        assert get_stability_hours("hobby") == 360.0

    def test_volatile_emotion_stability_24h(self):
        assert get_stability_hours("emotion") == 24.0

    def test_volatile_recent_topic_stability_48h(self):
        """recent_topic has longer stability (48h) than emotion (24h)."""
        assert get_stability_hours("recent_topic") == 48.0

    def test_unknown_type_gets_learning_stability(self):
        """Unknown types map to 'learning' category -> 168h."""
        assert get_stability_hours("something_unknown") == 168.0


# ─── 3. Importance floors ─────────────────────────────────────────────

class TestGetImportanceFloor:
    """Minimum importance floor per category."""

    def test_identity_floor_080(self):
        assert get_importance_floor("name") == 0.8

    def test_professional_floor_020(self):
        assert get_importance_floor("role") == 0.2

    def test_learning_floor_015(self):
        assert get_importance_floor("goal") == 0.15

    def test_personal_floor_010(self):
        assert get_importance_floor("hobby") == 0.1

    def test_volatile_floor_000(self):
        assert get_importance_floor("emotion") == 0.0
        assert get_importance_floor("recent_topic") == 0.0

    def test_unknown_type_floor_defaults_to_010(self):
        """Unknown category falls back to IMPORTANCE_FLOORS default (0.1)."""
        # Unknown -> category "learning" -> IMPORTANCE_FLOORS["learning"] = 0.15
        assert get_importance_floor("unknown_type") == 0.15


# ─── 4-8. Retention calculation ────────────────────────────────────────

class TestCalculateRetention:
    """Ebbinghaus retention: e^(-t / (stability * (1 + access * 0.3)))."""

    def test_retention_at_zero_hours_is_one(self):
        """retention(0) = 1.0 regardless of stability."""
        assert calculate_retention(0, 168.0) == 1.0
        assert calculate_retention(0, 24.0, access_count=5) == 1.0

    def test_retention_with_infinite_stability_is_one(self):
        """Identity facts (inf stability) never decay."""
        assert calculate_retention(1000.0, float("inf")) == 1.0
        assert calculate_retention(999999.0, float("inf"), access_count=0) == 1.0

    def test_retention_decays_over_time(self):
        """Non-identity facts decay as time passes."""
        r1 = calculate_retention(10.0, 168.0)
        r2 = calculate_retention(100.0, 168.0)
        r3 = calculate_retention(500.0, 168.0)

        assert r1 < 1.0
        assert r2 < r1
        assert r3 < r2
        assert r3 > 0.0

    def test_retention_formula_exact_value(self):
        """Verify the exact formula: e^(-t / (S * (1 + n * 0.3)))."""
        hours = 48.0
        stability = 24.0
        access = 0

        expected = math.exp(-48.0 / (24.0 * (1 + 0 * 0.3)))
        actual = calculate_retention(hours, stability, access)
        assert actual == pytest.approx(expected, rel=1e-10)

    def test_access_count_boosts_retention(self):
        """More accesses -> higher retention (slower decay)."""
        hours = 100.0
        stability = 168.0

        r_no_access = calculate_retention(hours, stability, access_count=0)
        r_some_access = calculate_retention(hours, stability, access_count=3)
        r_many_access = calculate_retention(hours, stability, access_count=10)

        assert r_some_access > r_no_access
        assert r_many_access > r_some_access

    def test_access_boost_factor_matches_constant(self):
        """Confirm ACCESS_BOOST_FACTOR=0.3 is used in the formula."""
        assert ACCESS_BOOST_FACTOR == 0.3

        hours = 50.0
        stability = 100.0
        access = 2

        expected = math.exp(-hours / (stability * (1 + access * 0.3)))
        assert calculate_retention(hours, stability, access) == pytest.approx(expected)

    def test_negative_hours_returns_one(self):
        """Negative elapsed time (future timestamp) treated as no decay."""
        assert calculate_retention(-10.0, 168.0) == 1.0

    def test_zero_or_negative_stability_returns_one(self):
        """Zero or negative stability returns 1.0 (guard against division by zero)."""
        assert calculate_retention(100.0, 0.0) == 1.0
        assert calculate_retention(100.0, -5.0) == 1.0


# ─── 9-10. Effective importance ────────────────────────────────────────

class TestCalculateEffectiveImportance:
    """effective = max(base * retention, floor)."""

    def test_identity_never_below_080(self):
        """Identity facts have floor=0.8, so even with huge time, stays >= 0.8."""
        result = calculate_effective_importance(1.0, "name", 999999.0)
        # Identity has inf stability -> retention=1.0 -> effective=1.0
        assert result == 1.0

    def test_identity_low_base_clamped_to_floor(self):
        """Even if base_importance is low, identity floor applies."""
        result = calculate_effective_importance(0.5, "name", 0.0)
        # retention=1.0 (inf stability) -> 0.5*1.0=0.5 but floor=0.8 -> 0.8
        assert result == 0.8

    def test_volatile_can_reach_zero(self):
        """Volatile facts have floor=0.0, so they can fully decay."""
        result = calculate_effective_importance(0.5, "emotion", 10000.0)
        # After 10000h with stability=24h, retention ~ 0 -> floor=0.0
        assert result == pytest.approx(0.0, abs=1e-10)

    def test_professional_respects_floor(self):
        """Professional facts decay but never below 0.2."""
        result = calculate_effective_importance(1.0, "role", 50000.0)
        assert result == 0.2

    def test_learning_respects_floor(self):
        """Learning facts decay but never below 0.15."""
        result = calculate_effective_importance(1.0, "goal", 50000.0)
        assert result == 0.15

    def test_no_decay_at_zero_hours(self):
        """At t=0, effective importance = base (or floor if base < floor)."""
        assert calculate_effective_importance(0.9, "preference", 0.0) == 0.9
        assert calculate_effective_importance(0.9, "emotion", 0.0) == 0.9

    def test_access_count_slows_effective_decay(self):
        """Higher access count -> less decay -> higher effective importance."""
        eff_no_access = calculate_effective_importance(0.8, "hobby", 300.0, access_count=0)
        eff_high_access = calculate_effective_importance(0.8, "hobby", 300.0, access_count=10)
        assert eff_high_access > eff_no_access


# ─── 11. Timestamp-based wrapper ──────────────────────────────────────

class TestCalculateEffectiveImportanceFromTimestamps:
    """Convenience wrapper computing hours from datetime objects."""

    def test_with_last_accessed(self):
        """Uses last_accessed as reference time."""
        now = datetime(2026, 2, 13, 12, 0, 0, tzinfo=timezone.utc)
        last_accessed = datetime(2026, 2, 12, 12, 0, 0, tzinfo=timezone.utc)  # 24h ago

        result = calculate_effective_importance_from_timestamps(
            base_importance=0.8,
            fact_type="emotion",
            last_accessed=last_accessed,
            created_at=None,
            access_count=0,
            now=now,
        )
        # hours_elapsed=24, stability=24 -> retention=e^(-1) ~ 0.3679
        expected = max(0.8 * math.exp(-1.0), 0.0)
        assert result == pytest.approx(expected, rel=1e-6)

    def test_falls_back_to_created_at(self):
        """When last_accessed is None, uses created_at."""
        now = datetime(2026, 2, 13, 12, 0, 0, tzinfo=timezone.utc)
        created = datetime(2026, 2, 6, 12, 0, 0, tzinfo=timezone.utc)  # 7 days = 168h ago

        result = calculate_effective_importance_from_timestamps(
            base_importance=1.0,
            fact_type="goal",
            last_accessed=None,
            created_at=created,
            access_count=0,
            now=now,
        )
        # hours_elapsed=168, stability=168 -> retention=e^(-1) ~ 0.3679
        expected = max(1.0 * math.exp(-1.0), 0.15)
        assert result == pytest.approx(expected, rel=1e-6)

    def test_no_timestamps_gives_zero_elapsed(self):
        """When both timestamps are None, uses 0 hours -> no decay."""
        result = calculate_effective_importance_from_timestamps(
            base_importance=0.7,
            fact_type="hobby",
            last_accessed=None,
            created_at=None,
            access_count=0,
            now=datetime.now(timezone.utc),
        )
        assert result == 0.7

    def test_naive_datetime_treated_as_utc(self):
        """Naive datetimes get timezone.utc attached."""
        now = datetime(2026, 2, 13, 12, 0, 0)  # naive
        created = datetime(2026, 2, 12, 12, 0, 0)  # naive, 24h ago

        result = calculate_effective_importance_from_timestamps(
            base_importance=0.9,
            fact_type="preference",
            last_accessed=None,
            created_at=created,
            access_count=0,
            now=now,
        )
        # hours_elapsed=24, stability=168 -> retention=e^(-24/168)
        expected = max(0.9 * math.exp(-24.0 / 168.0), 0.15)
        assert result == pytest.approx(expected, rel=1e-6)

    def test_future_timestamp_no_decay(self):
        """If reference time is in the future, hours_elapsed=0 (clamped)."""
        now = datetime(2026, 2, 13, 12, 0, 0, tzinfo=timezone.utc)
        future = datetime(2026, 2, 14, 12, 0, 0, tzinfo=timezone.utc)

        result = calculate_effective_importance_from_timestamps(
            base_importance=0.6,
            fact_type="emotion",
            last_accessed=future,
            created_at=None,
            access_count=0,
            now=now,
        )
        # delta is negative -> hours_elapsed clamped to 0 -> retention=1.0
        assert result == 0.6


# ─── 12-13. Pruning logic ─────────────────────────────────────────────

class TestShouldPrune:
    """Pruning: effective importance < prune_threshold."""

    def test_decayed_volatile_is_pruned(self):
        """Volatile fact that has fully decayed should be pruned."""
        # emotion with base=0.5, after 10000 hours -> effective ~ 0.0 < 0.1
        assert should_prune(0.5, "emotion", 10000.0) is True

    def test_identity_never_pruned(self):
        """Identity facts never decay below 0.8 -> never pruned (threshold=0.1)."""
        assert should_prune(1.0, "name", 999999.0) is False
        assert should_prune(0.5, "age", 999999.0) is False  # floor=0.8 > 0.1

    def test_fresh_fact_not_pruned(self):
        """Fresh fact (0 hours) retains full importance -> not pruned."""
        assert should_prune(0.5, "emotion", 0.0) is False

    def test_custom_prune_threshold(self):
        """Custom threshold can make more facts pruneable."""
        # Professional fact decayed to floor 0.2
        # With threshold=0.3, should be pruned
        assert should_prune(1.0, "role", 50000.0, prune_threshold=0.3) is True
        # With default threshold=0.1, should NOT be pruned (floor=0.2 > 0.1)
        assert should_prune(1.0, "role", 50000.0, prune_threshold=0.1) is False

    def test_access_count_prevents_pruning(self):
        """High access count slows decay enough to prevent pruning."""
        hours = 100.0
        # With 0 accesses, emotion decays significantly
        pruned_no_access = should_prune(0.5, "emotion", hours, access_count=0)
        # With many accesses, retention is much higher
        pruned_high_access = should_prune(0.5, "emotion", hours, access_count=20)

        assert pruned_no_access is True  # 0.5*e^(-100/24) ~ 0.0 < 0.1
        assert pruned_high_access is False  # 0.5*e^(-100/(24*7)) ~ 0.27 > 0.1


# ─── 14. Constants validation ─────────────────────────────────────────

class TestConstants:
    """Verify module-level constants are correctly defined."""

    def test_stability_hours_dict_keys(self):
        assert set(STABILITY_HOURS.keys()) == {
            "identity", "professional", "learning", "personal", "volatile", "volatile_topic"
        }

    def test_importance_floors_dict_keys(self):
        assert set(IMPORTANCE_FLOORS.keys()) == {
            "identity", "professional", "learning", "personal", "volatile"
        }

    def test_access_boost_factor_value(self):
        assert ACCESS_BOOST_FACTOR == 0.3
