import asyncio
import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.unit.living_continuity_helpers import (
    _make_soul,
    reset_runtime_metrics as reset_runtime_metrics,
)


class TestHeartbeatRuntimeOrgScope:
    """Test org-scoped heartbeat persistence guardrails."""

    @pytest.mark.asyncio
    async def test_heartbeat_queue_blocks_missing_org_context_before_db(
        self,
        monkeypatch,
        caplog,
    ):
        """Pending action queueing fails closed without org context."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.heartbeat_runtime_support import queue_pending_actions_impl
        from app.engine.living_agent.models import ActionType, HeartbeatAction

        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")
        caplog.set_level(logging.WARNING)

        token = current_org_id.set(None)
        try:
            with patch("app.core.database.get_shared_session_factory") as mock_factory:
                await queue_pending_actions_impl([
                    HeartbeatAction(action_type=ActionType.BROWSE_SOCIAL, target="private"),
                ])
        finally:
            current_org_id.reset(token)

        mock_factory.assert_not_called()
        assert "heartbeat_runtime_blocked_missing_org_context" in caplog.text
        assert "private" not in caplog.text

    @pytest.mark.asyncio
    async def test_heartbeat_pending_load_filters_by_org_context(self, monkeypatch):
        """Approved pending action reads are scoped to the current org."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.heartbeat_runtime_support import load_pending_action_impl

        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")

        mock_session = MagicMock()
        mock_session.execute.return_value.fetchone.return_value = (
            "browse_social",
            "private",
            0.8,
            json.dumps({"reason": "test"}),
        )
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        token = current_org_id.set("org-A")
        try:
            with patch("app.core.database.get_shared_session_factory", return_value=mock_factory):
                action = await load_pending_action_impl("raw-action-id")
        finally:
            current_org_id.reset(token)

        statement = str(mock_session.execute.call_args.args[0])
        params = mock_session.execute.call_args.args[1]
        assert action is not None
        assert "AND organization_id = :org_id" in statement
        assert params["org_id"] == "org-A"

    @pytest.mark.asyncio
    async def test_heartbeat_pending_completion_filters_by_org_context(self, monkeypatch):
        """Pending action completion cannot update another org's action id."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.heartbeat_runtime_support import mark_action_completed_impl

        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        token = current_org_id.set("org-A")
        try:
            with patch("app.core.database.get_shared_session_factory", return_value=mock_factory):
                await mark_action_completed_impl("raw-action-id")
        finally:
            current_org_id.reset(token)

        statement = str(mock_session.execute.call_args.args[0])
        params = mock_session.execute.call_args.args[1]
        assert "AND organization_id = :org_id" in statement
        assert params["org_id"] == "org-A"

    @pytest.mark.asyncio
    async def test_heartbeat_audit_blocks_missing_org_context_before_db(
        self,
        monkeypatch,
        caplog,
    ):
        """Heartbeat audit writes fail closed without org context."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.heartbeat_runtime_support import save_heartbeat_audit_impl
        from app.engine.living_agent.models import HeartbeatResult

        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")
        caplog.set_level(logging.WARNING)

        token = current_org_id.set(None)
        try:
            with patch("app.core.database.get_shared_session_factory") as mock_factory:
                await save_heartbeat_audit_impl(1, HeartbeatResult(error="PRIVATE ERROR"))
        finally:
            current_org_id.reset(token)

        mock_factory.assert_not_called()
        assert "heartbeat_runtime_blocked_missing_org_context" in caplog.text
        assert "PRIVATE ERROR" not in caplog.text

    @pytest.mark.asyncio
    async def test_heartbeat_audit_insert_includes_org_context(self, monkeypatch):
        """Heartbeat audit rows include the resolved org context."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.heartbeat_runtime_support import save_heartbeat_audit_impl
        from app.engine.living_agent.models import ActionType, HeartbeatAction, HeartbeatResult

        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")
        result = HeartbeatResult(
            actions_taken=[HeartbeatAction(action_type=ActionType.REFLECT, target="private")],
            insights_gained=1,
            duration_ms=12,
        )

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        token = current_org_id.set("org-A")
        try:
            with patch("app.core.database.get_shared_session_factory", return_value=mock_factory):
                await save_heartbeat_audit_impl(5, result)
        finally:
            current_org_id.reset(token)

        statement = str(mock_session.execute.call_args.args[0])
        params = mock_session.execute.call_args.args[1]
        assert "organization_id" in statement
        assert params["org_id"] == "org-A"


class TestLLMTimeout:
    """Test 60s timeout protection in heartbeat actions."""

    @pytest.mark.asyncio
    async def test_timeout_wraps_action(self):
        """_execute_action should have 60s timeout."""
        from app.engine.living_agent.heartbeat import HeartbeatScheduler
        from app.engine.living_agent.models import HeartbeatAction, ActionType

        scheduler = HeartbeatScheduler()
        action = HeartbeatAction(action_type=ActionType.REST, priority=0.5)
        soul = _make_soul()
        engine = MagicMock()

        # REST does nothing, should complete instantly
        await scheduler._execute_action(action, soul, engine)
        # No error — pass

    @pytest.mark.asyncio
    async def test_timeout_on_slow_action(self):
        """Action exceeding 60s should be cancelled, not crash."""
        from app.engine.living_agent.heartbeat import HeartbeatScheduler
        from app.engine.living_agent.models import HeartbeatAction, ActionType

        scheduler = HeartbeatScheduler()

        async def slow_dispatch(action, soul, engine):
            await asyncio.sleep(100)  # Simulate very slow action

        action = HeartbeatAction(action_type=ActionType.REST, priority=0.5)
        soul = _make_soul()
        engine = MagicMock()

        with patch.object(scheduler, '_dispatch_action', side_effect=slow_dispatch):
            # Should not raise — timeout is caught internally
            await scheduler._execute_action(action, soul, engine)

    @pytest.mark.asyncio
    async def test_action_continues_after_timeout(self):
        """Heartbeat should continue processing after one action times out."""
        from app.engine.living_agent.heartbeat import HeartbeatScheduler
        from app.engine.living_agent.models import HeartbeatAction, ActionType

        scheduler = HeartbeatScheduler()
        call_count = 0

        async def track_dispatch(action, soul, engine):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                await asyncio.sleep(100)  # First action times out
            # Second action completes

        action1 = HeartbeatAction(action_type=ActionType.REFLECT, priority=0.5)
        action2 = HeartbeatAction(action_type=ActionType.REST, priority=0.5)
        soul = _make_soul()
        engine = MagicMock()

        with patch.object(scheduler, '_dispatch_action', side_effect=track_dispatch):
            await scheduler._execute_action(action1, soul, engine)
            await scheduler._execute_action(action2, soul, engine)

        assert call_count == 2  # Both dispatched, first timed out

    @pytest.mark.asyncio
    async def test_dispatch_action_exists(self):
        """_dispatch_action should exist as the internal handler."""
        from app.engine.living_agent.heartbeat import HeartbeatScheduler
        scheduler = HeartbeatScheduler()
        assert hasattr(scheduler, '_dispatch_action')


class TestHeartbeatGoalSeeding:
    """Test goal seeding wired into heartbeat _action_check_goals."""

    @pytest.mark.asyncio
    async def test_check_goals_seeds_once(self):
        """_action_check_goals should seed goals on first call."""
        from app.engine.living_agent.heartbeat import HeartbeatScheduler

        scheduler = HeartbeatScheduler()
        soul = _make_soul()

        mock_manager = AsyncMock()
        mock_manager.seed_initial_goals = AsyncMock(return_value=4)
        mock_manager.get_active_goals = AsyncMock(return_value=[MagicMock()])

        with patch("app.engine.living_agent.goal_manager.get_goal_manager", return_value=mock_manager):
            await scheduler._action_check_goals(soul)

            mock_manager.seed_initial_goals.assert_called_once_with(soul)
            assert scheduler._goals_seeded is True

    @pytest.mark.asyncio
    async def test_check_goals_idempotent(self):
        """_action_check_goals should NOT re-seed on subsequent calls."""
        from app.engine.living_agent.heartbeat import HeartbeatScheduler

        scheduler = HeartbeatScheduler()
        scheduler._goals_seeded = True  # Already seeded
        soul = _make_soul()

        mock_manager = AsyncMock()
        mock_manager.get_active_goals = AsyncMock(return_value=[])

        with patch("app.engine.living_agent.goal_manager.get_goal_manager", return_value=mock_manager):
            await scheduler._action_check_goals(soul)

            mock_manager.seed_initial_goals.assert_not_called()
