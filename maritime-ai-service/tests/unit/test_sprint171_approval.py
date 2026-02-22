"""
Tests for Sprint 171: Approval Gate — Human approval enforcement for
external heartbeat actions.

Sprint 171: "Quyền Tự Chủ" — Safety-first autonomous capabilities.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone


def _make_settings(**overrides):
    """Create a mock settings object with living_agent defaults."""
    defaults = {
        "enable_living_agent": True,
        "living_agent_heartbeat_interval": 1800,
        "living_agent_active_hours_start": 8,
        "living_agent_active_hours_end": 23,
        "living_agent_enable_social_browse": True,
        "living_agent_enable_skill_building": True,
        "living_agent_enable_journal": True,
        "living_agent_require_human_approval": True,
        "living_agent_max_actions_per_heartbeat": 3,
        "living_agent_max_skills_per_week": 5,
        "living_agent_max_searches_per_heartbeat": 3,
        "living_agent_max_daily_cycles": 48,
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
    soul.interests.wants_to_learn = ["Docker"]
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
    engine.get_behavior_modifiers.return_value = {"mood_label": "tò mò"}
    engine.to_dict.return_value = {}
    return engine


# Patch targets: lazy imports → patch at SOURCE module
_SOUL_PATCH = "app.engine.living_agent.soul_loader.get_soul"
_ENGINE_PATCH = "app.engine.living_agent.emotion_engine.get_emotion_engine"
_SETTINGS_PATCH = "app.core.config.settings"


class TestApprovalGate:
    """Tests for the human approval gate in heartbeat execution."""

    @pytest.mark.asyncio
    async def test_approval_gate_queues_browse_action(self):
        """BROWSE_SOCIAL should be queued when require_human_approval=True."""
        from app.engine.living_agent.heartbeat import HeartbeatScheduler

        scheduler = HeartbeatScheduler()
        settings = _make_settings(
            living_agent_require_human_approval=True,
            living_agent_enable_social_browse=True,
            living_agent_enable_skill_building=False,
        )
        soul = _make_soul()
        engine = _make_engine()

        with patch(_SOUL_PATCH, return_value=soul), \
             patch(_ENGINE_PATCH, return_value=engine), \
             patch(_SETTINGS_PATCH, settings), \
             patch.object(scheduler, "_queue_pending_actions", new_callable=AsyncMock) as mock_queue, \
             patch.object(scheduler, "_save_emotional_snapshot", new_callable=AsyncMock), \
             patch.object(scheduler, "_save_heartbeat_audit", new_callable=AsyncMock), \
             patch.object(scheduler, "_is_journal_time", return_value=False):

            result = await scheduler._execute_heartbeat()

            # BROWSE_SOCIAL should have been queued, not executed
            mock_queue.assert_called_once()
            queued_actions = mock_queue.call_args[0][0]
            queued_types = [a.action_type.value for a in queued_actions]
            assert "browse_social" in queued_types

            # CHECK_GOALS should have been auto-approved and executed
            executed_types = [a.action_type.value for a in result.actions_taken]
            assert "check_goals" in executed_types
            assert "browse_social" not in executed_types

    @pytest.mark.asyncio
    async def test_approval_gate_auto_approves_reflect(self):
        """REFLECT should execute immediately (no external I/O)."""
        from app.engine.living_agent.heartbeat import HeartbeatScheduler

        scheduler = HeartbeatScheduler()
        settings = _make_settings(
            living_agent_require_human_approval=True,
            living_agent_enable_social_browse=False,
            living_agent_enable_skill_building=False,
        )
        soul = _make_soul()
        engine = _make_engine()
        engine.energy = 0.4  # Medium energy → REFLECT

        with patch(_SOUL_PATCH, return_value=soul), \
             patch(_ENGINE_PATCH, return_value=engine), \
             patch(_SETTINGS_PATCH, settings), \
             patch.object(scheduler, "_queue_pending_actions", new_callable=AsyncMock) as mock_queue, \
             patch.object(scheduler, "_save_emotional_snapshot", new_callable=AsyncMock), \
             patch.object(scheduler, "_save_heartbeat_audit", new_callable=AsyncMock), \
             patch.object(scheduler, "_is_journal_time", return_value=False):

            result = await scheduler._execute_heartbeat()

            # REFLECT should be auto-approved (no queue call for it)
            executed_types = [a.action_type.value for a in result.actions_taken]
            assert "reflect" in executed_types

    @pytest.mark.asyncio
    async def test_approval_gate_auto_approves_check_goals(self):
        """CHECK_GOALS should always execute immediately."""
        from app.engine.living_agent.heartbeat import HeartbeatScheduler

        scheduler = HeartbeatScheduler()
        settings = _make_settings(living_agent_require_human_approval=True)
        soul = _make_soul()
        engine = _make_engine()

        with patch(_SOUL_PATCH, return_value=soul), \
             patch(_ENGINE_PATCH, return_value=engine), \
             patch(_SETTINGS_PATCH, settings), \
             patch.object(scheduler, "_queue_pending_actions", new_callable=AsyncMock), \
             patch.object(scheduler, "_save_emotional_snapshot", new_callable=AsyncMock), \
             patch.object(scheduler, "_save_heartbeat_audit", new_callable=AsyncMock), \
             patch.object(scheduler, "_is_journal_time", return_value=False):

            result = await scheduler._execute_heartbeat()
            executed_types = [a.action_type.value for a in result.actions_taken]
            assert "check_goals" in executed_types

    @pytest.mark.asyncio
    async def test_approval_gate_disabled_executes_all(self):
        """When require_human_approval=False, all actions execute directly."""
        from app.engine.living_agent.heartbeat import HeartbeatScheduler

        scheduler = HeartbeatScheduler()
        settings = _make_settings(
            living_agent_require_human_approval=False,
            living_agent_enable_social_browse=True,
        )
        soul = _make_soul()
        engine = _make_engine()

        with patch(_SOUL_PATCH, return_value=soul), \
             patch(_ENGINE_PATCH, return_value=engine), \
             patch(_SETTINGS_PATCH, settings), \
             patch.object(scheduler, "_queue_pending_actions", new_callable=AsyncMock) as mock_queue, \
             patch.object(scheduler, "_save_emotional_snapshot", new_callable=AsyncMock), \
             patch.object(scheduler, "_save_heartbeat_audit", new_callable=AsyncMock), \
             patch.object(scheduler, "_is_journal_time", return_value=False), \
             patch.object(scheduler, "_action_browse", new_callable=AsyncMock):

            result = await scheduler._execute_heartbeat()

            # No actions should be queued
            mock_queue.assert_not_called()

            # BROWSE_SOCIAL should be in executed actions
            executed_types = [a.action_type.value for a in result.actions_taken]
            assert "browse_social" in executed_types


class TestDailyCycleLimit:
    """Tests for the daily heartbeat cycle cap."""

    def test_daily_limit_enforced(self):
        """Should return False when daily limit reached."""
        from app.engine.living_agent.heartbeat import HeartbeatScheduler

        scheduler = HeartbeatScheduler()
        settings = _make_settings(living_agent_max_daily_cycles=5)

        with patch(_SETTINGS_PATCH, settings):
            # Simulate reaching the limit
            scheduler._daily_cycle_count = 5
            scheduler._daily_reset_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            assert scheduler._check_daily_limit() is False

    def test_daily_limit_allows_under(self):
        """Should return True when under daily limit."""
        from app.engine.living_agent.heartbeat import HeartbeatScheduler

        scheduler = HeartbeatScheduler()
        settings = _make_settings(living_agent_max_daily_cycles=48)

        with patch(_SETTINGS_PATCH, settings):
            scheduler._daily_cycle_count = 10
            scheduler._daily_reset_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            assert scheduler._check_daily_limit() is True

    def test_daily_limit_resets_at_midnight(self):
        """Counter should reset when date changes."""
        from app.engine.living_agent.heartbeat import HeartbeatScheduler

        scheduler = HeartbeatScheduler()
        settings = _make_settings(living_agent_max_daily_cycles=48)

        with patch(_SETTINGS_PATCH, settings):
            scheduler._daily_cycle_count = 100
            scheduler._daily_reset_date = "2020-01-01"  # Old date

            # Should reset and allow
            assert scheduler._check_daily_limit() is True
            assert scheduler._daily_cycle_count == 0
