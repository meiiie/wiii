from unittest.mock import MagicMock

import pytest

from app.engine.runtime import runtime_metrics as rm


def _counter_value(name: str, labels: dict[str, str] | None = None) -> int:
    key = tuple(sorted((k, v) for k, v in (labels or {}).items()))
    return rm.snapshot()["counters"].get(name, {}).get(key, 0)


def _histogram_values(name: str, labels: dict[str, str]) -> list[float]:
    key = tuple(sorted(labels.items()))
    return rm.snapshot()["histograms"].get(name, {}).get(key, [])


@pytest.fixture(autouse=True)
def reset_runtime_metrics():
    rm._reset_for_tests()
    yield
    rm._reset_for_tests()


def _make_settings(**overrides):
    """Create a settings mock with Sprint 210 flags."""
    defaults = {
        "enable_living_agent": True,
        "enable_living_continuity": True,
        "living_agent_heartbeat_interval": 60,
        "living_agent_active_hours_start": 0,
        "living_agent_active_hours_end": 24,
        "living_agent_enable_social_browse": False,
        "living_agent_enable_skill_building": False,
        "living_agent_enable_journal": False,
        "living_agent_require_human_approval": False,
        "living_agent_max_actions_per_heartbeat": 5,
        "living_agent_max_daily_cycles": 48,
        "living_agent_enable_weather": False,
        "living_agent_enable_briefing": False,
        "living_agent_enable_skill_learning": False,
        "living_agent_enable_proactive_messaging": False,
        "living_agent_enable_routine_tracking": False,
        "living_agent_enable_autonomy_graduation": False,
        "living_agent_enable_dynamic_goals": False,
        "living_agent_autonomy_level": 0,
        "enable_identity_core": False,
        "enable_narrative_context": False,
        "enable_natural_conversation": False,
        "enable_skill_tool_bridge": False,
        "enable_skill_metrics": False,
        "default_domain": "maritime",
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


def _make_soul():
    """Create a mock SoulConfig with interests."""
    soul = MagicMock()
    soul.short_term_goals = ["Learn COLREGs"]
    soul.long_term_goals = ["Become maritime expert"]
    soul.interests.primary = ["maritime"]
    soul.interests.exploring = ["AI"]
    soul.interests.wants_to_learn = ["Docker", "Kubernetes", "Rust"]
    return soul
