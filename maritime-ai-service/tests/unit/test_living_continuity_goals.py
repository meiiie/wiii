import json
import logging
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from tests.unit.living_continuity_helpers import (
    _make_soul,
    reset_runtime_metrics as reset_runtime_metrics,
)


class TestGoalManagerOrgScope:
    """Test org-scoped dynamic goal guardrails."""

    @pytest.mark.asyncio
    async def test_goal_create_blocks_missing_org_context_before_db(
        self,
        monkeypatch,
        caplog,
    ):
        """Goal creation fails closed without org context."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.goal_manager import GoalManager

        manager = GoalManager()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")
        caplog.set_level(logging.WARNING)

        token = current_org_id.set(None)
        try:
            with patch("app.core.database.get_shared_session_factory") as mock_factory:
                goal = await manager.create_goal(
                    "PRIVATE GOAL TITLE",
                    description="PRIVATE GOAL BODY",
                )
        finally:
            current_org_id.reset(token)

        assert goal is None
        mock_factory.assert_not_called()
        assert "goal_manager_blocked_missing_org_context" in caplog.text
        assert "PRIVATE GOAL TITLE" not in caplog.text
        assert "PRIVATE GOAL BODY" not in caplog.text

    @pytest.mark.asyncio
    async def test_goal_query_filters_by_org_context(self, monkeypatch):
        """Goal queries always include current org filter."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.goal_manager import GoalManager

        manager = GoalManager()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")

        row = (
            uuid4(),
            "Goal title",
            "Goal body",
            "active",
            "medium",
            0.2,
            "reflection",
            json.dumps(["m1"]),
            json.dumps([]),
            datetime.now(timezone.utc),
            None,
            None,
            "org-A",
        )
        mock_session = MagicMock()
        mock_session.execute.return_value.fetchall.return_value = [row]
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        token = current_org_id.set("org-A")
        try:
            with patch("app.core.database.get_shared_session_factory", return_value=mock_factory):
                goals = await manager.get_active_goals()
        finally:
            current_org_id.reset(token)

        statement = str(mock_session.execute.call_args.args[0])
        params = mock_session.execute.call_args.args[1]
        assert len(goals) == 1
        assert "organization_id = :org_id" in statement
        assert params["org_id"] == "org-A"

    @pytest.mark.asyncio
    async def test_goal_update_progress_filters_by_org_context(self, monkeypatch):
        """Progress updates cannot update another org's goal id."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.goal_manager import GoalManager

        manager = GoalManager()
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
                updated = await manager.update_progress("raw-goal-id", 0.7)
        finally:
            current_org_id.reset(token)

        statement = str(mock_session.execute.call_args.args[0])
        params = mock_session.execute.call_args.args[1]
        assert updated is True
        assert "AND organization_id = :org_id" in statement
        assert params["org_id"] == "org-A"

    @pytest.mark.asyncio
    async def test_goal_review_stale_filters_by_org_context(self, monkeypatch):
        """Stale-goal review only mutates current-org rows."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.goal_manager import GoalManager

        manager = GoalManager()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")

        result = MagicMock()
        result.rowcount = 2
        mock_session = MagicMock()
        mock_session.execute.return_value = result
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        token = current_org_id.set("org-A")
        try:
            with patch("app.core.database.get_shared_session_factory", return_value=mock_factory):
                count = await manager.review_stale_goals(stale_days=14)
        finally:
            current_org_id.reset(token)

        statement = str(mock_session.execute.call_args.args[0])
        params = mock_session.execute.call_args.args[1]
        assert count == 2
        assert "AND organization_id = :org_id" in statement
        assert params["org_id"] == "org-A"


class TestGoalSeeding:
    """Test goal seeding from soul definition."""

    @pytest.mark.asyncio
    async def test_seeds_from_wants_to_learn(self):
        """seed_initial_goals should create goals from wants_to_learn."""
        from app.engine.living_agent.goal_manager import GoalManager

        manager = GoalManager()
        soul = _make_soul()

        with patch.object(manager, 'get_active_goals', new_callable=AsyncMock, return_value=[]):
            with patch.object(manager, 'create_goal', new_callable=AsyncMock) as mock_create:
                mock_create.return_value = MagicMock()
                seeded = await manager.seed_initial_goals(soul)

                # 3 from wants_to_learn + 1 meta-goal = 4
                assert seeded == 4
                assert mock_create.call_count == 4

    @pytest.mark.asyncio
    async def test_idempotent_with_existing_goals(self):
        """seed_initial_goals should return 0 if goals already exist."""
        from app.engine.living_agent.goal_manager import GoalManager

        manager = GoalManager()
        soul = _make_soul()

        existing_goal = MagicMock()
        with patch.object(manager, 'get_active_goals', new_callable=AsyncMock, return_value=[existing_goal]):
            seeded = await manager.seed_initial_goals(soul)
            assert seeded == 0

    @pytest.mark.asyncio
    async def test_meta_goal_always_created(self):
        """Meta-goal about helping students should always be created."""
        from app.engine.living_agent.goal_manager import GoalManager

        manager = GoalManager()
        soul = MagicMock()
        soul.interests.wants_to_learn = []  # No topics

        with patch.object(manager, 'get_active_goals', new_callable=AsyncMock, return_value=[]):
            with patch.object(manager, 'create_goal', new_callable=AsyncMock) as mock_create:
                mock_create.return_value = MagicMock()
                seeded = await manager.seed_initial_goals(soul)

                assert seeded == 1  # Only meta-goal
                call_args = mock_create.call_args
                assert "sinh viên hàng hải" in call_args[1]["title"]

    @pytest.mark.asyncio
    async def test_max_3_learning_goals(self):
        """Should limit to first 3 wants_to_learn topics."""
        from app.engine.living_agent.goal_manager import GoalManager

        manager = GoalManager()
        soul = MagicMock()
        soul.interests.wants_to_learn = ["A", "B", "C", "D", "E"]

        with patch.object(manager, 'get_active_goals', new_callable=AsyncMock, return_value=[]):
            with patch.object(manager, 'create_goal', new_callable=AsyncMock) as mock_create:
                mock_create.return_value = MagicMock()
                seeded = await manager.seed_initial_goals(soul)

                # 3 learning + 1 meta = 4
                assert seeded == 4

    @pytest.mark.asyncio
    async def test_goals_use_soul_seed_source(self):
        """Seeded goals should have source='soul_seed'."""
        from app.engine.living_agent.goal_manager import GoalManager

        manager = GoalManager()
        soul = _make_soul()

        with patch.object(manager, 'get_active_goals', new_callable=AsyncMock, return_value=[]):
            with patch.object(manager, 'create_goal', new_callable=AsyncMock) as mock_create:
                mock_create.return_value = MagicMock()
                await manager.seed_initial_goals(soul)

                for call in mock_create.call_args_list:
                    assert call[1]["source"] == "soul_seed"
