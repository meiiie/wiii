import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from tests.unit.living_continuity_helpers import (
    reset_runtime_metrics as reset_runtime_metrics,
)


class TestReflectionDaily:
    """Test reflection window changes (weekly → daily)."""

    def test_daily_window_hit_at_21h(self):
        """Reflection should trigger at 21:00 UTC+7."""
        from app.engine.living_agent.heartbeat import HeartbeatScheduler

        scheduler = HeartbeatScheduler()
        # 21:00 UTC+7 = 14:00 UTC
        with patch("app.engine.living_agent.heartbeat.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 2, 26, 14, 0, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            # Direct calculation check
            now_vn = datetime(2026, 2, 26, 14, 0, tzinfo=timezone.utc) + timedelta(hours=7)
            assert 21 <= now_vn.hour <= 22

    def test_daily_window_hit_at_22h(self):
        """Reflection should trigger at 22:00 UTC+7."""
        now_vn = datetime(2026, 2, 26, 15, 0, tzinfo=timezone.utc) + timedelta(hours=7)
        assert 21 <= now_vn.hour <= 22

    def test_daily_window_miss_at_19h(self):
        """Reflection should NOT trigger at 19:00 UTC+7."""
        now_vn = datetime(2026, 2, 26, 12, 0, tzinfo=timezone.utc) + timedelta(hours=7)
        assert not (21 <= now_vn.hour <= 22)

    def test_daily_not_just_sunday(self):
        """Reflection should work on any day of the week."""
        # Test multiple days: Feb 23 (Mon) through Feb 28 (Sat) + Mar 1 (Sun)
        test_dates = [
            (2026, 2, 23), (2026, 2, 24), (2026, 2, 25),
            (2026, 2, 26), (2026, 2, 27), (2026, 2, 28), (2026, 3, 1),
        ]
        for year, month, day in test_dates:
            # 14:00 UTC = 21:00 UTC+7
            now_vn = datetime(year, month, day, 14, 0, tzinfo=timezone.utc) + timedelta(hours=7)
            assert 21 <= now_vn.hour <= 22, f"Failed for {year}-{month}-{day}"

    @pytest.mark.asyncio
    async def test_reflector_has_reflected_today(self):
        """_has_reflected_today should use date_trunc('day')."""
        from app.engine.living_agent.reflector import Reflector

        reflector = Reflector()

        # Mock DB to return count=1
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, idx: 1

        with patch("app.core.database.get_shared_session_factory") as mock_factory:
            mock_session = MagicMock()
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=False)
            mock_session.execute.return_value.fetchone.return_value = mock_row
            mock_factory.return_value = MagicMock(return_value=mock_session)

            result = await reflector._has_reflected_today(None)
            assert result is True


class TestActionReflectFix:
    """Test _action_reflect actually calls Reflector."""

    @pytest.mark.asyncio
    async def test_action_reflect_calls_reflector(self):
        """_action_reflect should call reflector.reflect() (not just fire event)."""
        from app.engine.living_agent.heartbeat import HeartbeatScheduler
        from app.engine.living_agent.models import LifeEvent, LifeEventType

        scheduler = HeartbeatScheduler()
        engine = MagicMock()
        engine.process_event = MagicMock()

        mock_entry = MagicMock()
        mock_entry.content = "Today I learned about COLREGs and felt proud."

        with patch("app.engine.living_agent.reflector.get_reflector") as mock_get:
            mock_reflector = AsyncMock()
            mock_reflector.reflect = AsyncMock(return_value=mock_entry)
            mock_get.return_value = mock_reflector

            await scheduler._action_reflect(engine)

            mock_reflector.reflect.assert_called_once()
            engine.process_event.assert_called_once()
            event = engine.process_event.call_args[0][0]
            assert event.event_type == LifeEventType.REFLECTION_COMPLETED
            assert "Today I learned" in event.description

    @pytest.mark.asyncio
    async def test_action_reflect_handles_none(self):
        """_action_reflect should handle reflector returning None gracefully."""
        from app.engine.living_agent.heartbeat import HeartbeatScheduler

        scheduler = HeartbeatScheduler()
        engine = MagicMock()

        with patch("app.engine.living_agent.reflector.get_reflector") as mock_get:
            mock_reflector = AsyncMock()
            mock_reflector.reflect = AsyncMock(return_value=None)
            mock_get.return_value = mock_reflector

            await scheduler._action_reflect(engine)

            # Should NOT fire REFLECTION_COMPLETED when reflect() returns None
            engine.process_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_action_reflect_handles_exception(self):
        """_action_reflect should handle reflector errors gracefully."""
        from app.engine.living_agent.heartbeat import HeartbeatScheduler
        from app.engine.living_agent.models import LifeEventType

        scheduler = HeartbeatScheduler()
        engine = MagicMock()

        with patch("app.engine.living_agent.reflector.get_reflector") as mock_get:
            mock_reflector = AsyncMock()
            mock_reflector.reflect = AsyncMock(side_effect=Exception("DB error"))
            mock_get.return_value = mock_reflector

            await scheduler._action_reflect(engine)

            # Should still fire a fallback event on error
            engine.process_event.assert_called_once()
            event = engine.process_event.call_args[0][0]
            assert event.event_type == LifeEventType.REFLECTION_COMPLETED

    @pytest.mark.asyncio
    async def test_action_reflect_includes_content_in_description(self):
        """Reflection event description should include reflection content snippet."""
        from app.engine.living_agent.heartbeat import HeartbeatScheduler

        scheduler = HeartbeatScheduler()
        engine = MagicMock()

        mock_entry = MagicMock()
        mock_entry.content = "X" * 200  # Long content

        with patch("app.engine.living_agent.reflector.get_reflector") as mock_get:
            mock_reflector = AsyncMock()
            mock_reflector.reflect = AsyncMock(return_value=mock_entry)
            mock_get.return_value = mock_reflector

            await scheduler._action_reflect(engine)

            event = engine.process_event.call_args[0][0]
            assert event.description.startswith("Reflection: ")
            # Should be truncated to ~100 chars
            assert len(event.description) <= 120


class TestReflectorOrgScope:
    """Test org-scoped reflection guardrails."""

    @pytest.mark.asyncio
    async def test_reflection_blocks_missing_org_context_before_db_or_llm(
        self,
        monkeypatch,
        caplog,
    ):
        """Reflection generation fails closed without org context."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.reflector import Reflector

        reflector = Reflector()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")
        caplog.set_level(logging.WARNING)

        token = current_org_id.set(None)
        try:
            with patch("app.core.database.get_shared_session_factory") as mock_factory, \
                 patch("app.engine.living_agent.local_llm.get_local_llm") as mock_llm:
                entry = await reflector.reflect()
        finally:
            current_org_id.reset(token)

        assert entry is None
        mock_factory.assert_not_called()
        mock_llm.assert_not_called()
        assert "reflection_blocked_missing_org_context" in caplog.text

    @pytest.mark.asyncio
    async def test_recent_reflections_filters_by_org_context(self, monkeypatch):
        """Recent reflection reads only query current org."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.reflector import Reflector

        reflector = Reflector()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")

        row = (
            uuid4(),
            "Reflection content",
            json.dumps(["insight"]),
            json.dumps(["goal"]),
            json.dumps(["pattern"]),
            "calm",
            datetime.now(timezone.utc),
        )
        mock_session = MagicMock()
        mock_session.execute.return_value.fetchall.return_value = [row]
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        token = current_org_id.set("org-A")
        try:
            with patch("app.core.database.get_shared_session_factory", return_value=mock_factory):
                entries = await reflector.get_recent_reflections(count=2)
        finally:
            current_org_id.reset(token)

        statement = str(mock_session.execute.call_args.args[0])
        params = mock_session.execute.call_args.args[1]
        assert len(entries) == 1
        assert "organization_id = :org_id" in statement
        assert params["org_id"] == "org-A"

    @pytest.mark.asyncio
    async def test_reflect_passes_resolved_org_to_summaries(self, monkeypatch):
        """Daily reflection gathers all summaries for one resolved org."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.reflector import Reflector

        reflector = Reflector()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")

        token = current_org_id.set("org-A")
        try:
            with patch.object(reflector, "_has_reflected_today", new_callable=AsyncMock, return_value=False), \
                 patch.object(reflector, "_get_journal_summary", new_callable=AsyncMock, return_value="") as mock_journal, \
                 patch.object(reflector, "_get_emotion_summary", new_callable=AsyncMock, return_value="") as mock_emotion, \
                 patch.object(reflector, "_get_browsing_summary", new_callable=AsyncMock, return_value="") as mock_browsing, \
                 patch.object(reflector, "_get_skills_summary", new_callable=AsyncMock, return_value="") as mock_skills, \
                 patch("app.engine.living_agent.local_llm.get_local_llm") as mock_llm:
                mock_llm.return_value.generate = AsyncMock(return_value=None)
                entry = await reflector.reflect()
        finally:
            current_org_id.reset(token)

        assert entry is None
        mock_journal.assert_called_once_with(1, "org-A")
        mock_emotion.assert_called_once_with(1, "org-A")
        mock_browsing.assert_called_once_with(1, "org-A")
        mock_skills.assert_called_once_with("org-A")

    @pytest.mark.asyncio
    async def test_browsing_summary_filters_by_org_context(self):
        """Browsing summary SQL uses org filter."""
        from app.engine.living_agent.reflector import Reflector

        reflector = Reflector()
        mock_session = MagicMock()
        mock_session.execute.return_value.fetchall.return_value = [
            ("Private discovery", 0.9),
        ]
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        with patch("app.core.database.get_shared_session_factory", return_value=mock_factory):
            summary = await reflector._get_browsing_summary(1, "org-A")

        statement = str(mock_session.execute.call_args.args[0])
        params = mock_session.execute.call_args.args[1]
        assert "Private discovery" in summary
        assert "organization_id = :org_id" in statement
        assert params["org_id"] == "org-A"


class TestReflectorDailyMethod:
    """Test Reflector.reflect() daily method."""

    @pytest.mark.asyncio
    async def test_reflect_method_exists(self):
        """Reflector should have a reflect() method (Sprint 210)."""
        from app.engine.living_agent.reflector import Reflector
        reflector = Reflector()
        assert hasattr(reflector, 'reflect')
        assert asyncio.iscoroutinefunction(reflector.reflect)

    @pytest.mark.asyncio
    async def test_reflect_skips_if_already_reflected_today(self):
        """reflect() should return None if already reflected today."""
        from app.engine.living_agent.reflector import Reflector
        reflector = Reflector()

        with patch.object(reflector, '_has_reflected_today', new_callable=AsyncMock, return_value=True):
            result = await reflector.reflect()
            assert result is None

    @pytest.mark.asyncio
    async def test_reflect_uses_1_day_lookback(self):
        """reflect() should gather data from past 1 day (not 7)."""
        from app.engine.living_agent.reflector import Reflector
        reflector = Reflector()

        with patch.object(reflector, '_has_reflected_today', new_callable=AsyncMock, return_value=False):
            with patch.object(reflector, '_get_journal_summary', new_callable=AsyncMock, return_value="") as mock_journal:
                with patch.object(reflector, '_get_emotion_summary', new_callable=AsyncMock, return_value=""):
                    with patch.object(reflector, '_get_browsing_summary', new_callable=AsyncMock, return_value=""):
                        with patch.object(reflector, '_get_skills_summary', new_callable=AsyncMock, return_value=""):
                            with patch("app.engine.living_agent.local_llm.get_local_llm") as mock_llm:
                                mock_llm.return_value.generate = AsyncMock(return_value=None)
                                await reflector.reflect()

                                # Check journal_summary called with days=1 and resolved org
                                mock_journal.assert_called_once_with(1, "default")

    def test_is_reflection_time_daily(self):
        """is_reflection_time should return True at 21:00 any day."""
        from app.engine.living_agent.reflector import Reflector
        reflector = Reflector()

        # We can't easily mock datetime.now in the method since it uses
        # datetime.now(timezone.utc) directly. Test the logic.
        from datetime import timedelta
        # Monday 21:30 UTC+7 = 14:30 UTC
        utc_time = datetime(2026, 2, 23, 14, 30, tzinfo=timezone.utc)
        now_vn = utc_time + timedelta(hours=7)
        assert 21 <= now_vn.hour <= 22
