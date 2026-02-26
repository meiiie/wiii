"""
Tests for Sprint 171: Heartbeat Audit Logging — persistence of every
heartbeat cycle result.

Sprint 171: "Quyền Tự Chủ" — Safety-first autonomous capabilities.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_settings(**overrides):
    """Create a mock settings object with living_agent defaults."""
    defaults = {
        "enable_living_agent": True,
        "living_agent_heartbeat_interval": 1800,
        "living_agent_active_hours_start": 8,
        "living_agent_active_hours_end": 23,
        "living_agent_enable_social_browse": False,
        "living_agent_enable_skill_building": False,
        "living_agent_enable_journal": False,
        "living_agent_require_human_approval": False,
        "living_agent_max_actions_per_heartbeat": 3,
        "living_agent_max_skills_per_week": 5,
        "living_agent_max_searches_per_heartbeat": 3,
        "living_agent_max_daily_cycles": 48,
        # Flags added in later sprints (default off in tests)
        "living_agent_enable_weather": False,
        "living_agent_enable_briefing": False,
        "living_agent_enable_skill_learning": False,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


def _make_soul():
    """Create a mock SoulConfig."""
    soul = MagicMock()
    soul.short_term_goals = ["Learn Python"]
    soul.long_term_goals = ["Become expert"]
    soul.interests.primary = ["maritime"]
    soul.interests.exploring = ["AI"]
    soul.interests.wants_to_learn = []
    return soul


def _make_engine():
    """Create a mock EmotionEngine."""
    engine = MagicMock()
    engine.mood.value = "curious"
    engine.energy = 0.8
    engine.state.primary_mood.value = "curious"
    engine.state.energy_level = 0.8
    engine.state.social_battery = 0.7
    engine.state.engagement = 0.6
    engine.to_dict.return_value = {}
    # Async methods added in later sprints
    engine.load_state_from_db = AsyncMock()
    engine.save_state_to_db = AsyncMock()
    return engine


# Patch targets: lazy imports → patch at SOURCE module
_SOUL_PATCH = "app.engine.living_agent.soul_loader.get_soul"
_ENGINE_PATCH = "app.engine.living_agent.emotion_engine.get_emotion_engine"
_SETTINGS_PATCH = "app.core.config.settings"


class TestHeartbeatAudit:
    """Tests for heartbeat audit record persistence."""

    @pytest.mark.asyncio
    async def test_saves_audit_record(self):
        """Every heartbeat cycle should save an audit record."""
        from app.engine.living_agent.heartbeat import HeartbeatScheduler

        scheduler = HeartbeatScheduler()
        settings = _make_settings()
        soul = _make_soul()
        engine = _make_engine()

        with patch(_SOUL_PATCH, return_value=soul), \
             patch(_ENGINE_PATCH, return_value=engine), \
             patch(_SETTINGS_PATCH, settings), \
             patch.object(scheduler, "_save_emotional_snapshot", new_callable=AsyncMock), \
             patch.object(scheduler, "_save_heartbeat_audit", new_callable=AsyncMock) as mock_audit, \
             patch.object(scheduler, "_is_journal_time", return_value=False):

            result = await scheduler._execute_heartbeat()

            # Audit should be called exactly once
            mock_audit.assert_called_once()
            # The result passed to audit should match
            audit_result = mock_audit.call_args[0][0]
            assert audit_result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_audit_includes_actions(self):
        """Audit record should include executed actions."""
        from app.engine.living_agent.heartbeat import HeartbeatScheduler

        scheduler = HeartbeatScheduler()
        settings = _make_settings()
        soul = _make_soul()
        engine = _make_engine()

        with patch(_SOUL_PATCH, return_value=soul), \
             patch(_ENGINE_PATCH, return_value=engine), \
             patch(_SETTINGS_PATCH, settings), \
             patch.object(scheduler, "_save_emotional_snapshot", new_callable=AsyncMock), \
             patch.object(scheduler, "_save_heartbeat_audit", new_callable=AsyncMock) as mock_audit, \
             patch.object(scheduler, "_is_journal_time", return_value=False):

            result = await scheduler._execute_heartbeat()

            audit_result = mock_audit.call_args[0][0]
            action_types = [a.action_type.value for a in audit_result.actions_taken]
            assert "check_goals" in action_types

    @pytest.mark.asyncio
    async def test_audit_includes_errors(self):
        """Audit record should include error when cycle fails."""
        from app.engine.living_agent.heartbeat import HeartbeatScheduler

        scheduler = HeartbeatScheduler()
        settings = _make_settings()

        with patch(_SOUL_PATCH, side_effect=RuntimeError("Soul load failed")), \
             patch(_ENGINE_PATCH), \
             patch(_SETTINGS_PATCH, settings), \
             patch.object(scheduler, "_save_heartbeat_audit", new_callable=AsyncMock) as mock_audit:

            result = await scheduler._execute_heartbeat()

            assert result.error is not None
            assert "Soul load failed" in result.error
            mock_audit.assert_called_once()
            audit_result = mock_audit.call_args[0][0]
            assert audit_result.error is not None

    @pytest.mark.asyncio
    async def test_audit_on_noop(self):
        """Audit record should be saved even for NOOP cycles."""
        from app.engine.living_agent.heartbeat import HeartbeatScheduler

        scheduler = HeartbeatScheduler()
        settings = _make_settings()
        soul = _make_soul()
        engine = _make_engine()

        with patch(_SOUL_PATCH, return_value=soul), \
             patch(_ENGINE_PATCH, return_value=engine), \
             patch(_SETTINGS_PATCH, settings), \
             patch.object(scheduler, "_plan_actions", new_callable=AsyncMock, return_value=[]), \
             patch.object(scheduler, "_save_heartbeat_audit", new_callable=AsyncMock) as mock_audit:

            result = await scheduler._execute_heartbeat()

            assert result.is_noop is True
            mock_audit.assert_called_once()
