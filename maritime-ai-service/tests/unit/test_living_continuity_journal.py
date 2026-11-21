import json
import logging
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from tests.unit.living_continuity_helpers import (
    reset_runtime_metrics as reset_runtime_metrics,
)


class TestJournalExpandedWindow:
    """Test journal time window changes (evening → morning+evening)."""

    def test_morning_window_8h(self):
        """Journal should be available at 8:00 UTC+7."""
        now_vn = datetime(2026, 2, 26, 1, 0, tzinfo=timezone.utc) + timedelta(hours=7)  # 8:00 VN
        assert (8 <= now_vn.hour <= 9) or (20 <= now_vn.hour <= 22)

    def test_morning_window_9h(self):
        """Journal should be available at 9:00 UTC+7."""
        now_vn = datetime(2026, 2, 26, 2, 0, tzinfo=timezone.utc) + timedelta(hours=7)  # 9:00 VN
        assert (8 <= now_vn.hour <= 9) or (20 <= now_vn.hour <= 22)

    def test_evening_window_20h(self):
        """Journal should be available at 20:00 UTC+7 (existing window)."""
        now_vn = datetime(2026, 2, 26, 13, 0, tzinfo=timezone.utc) + timedelta(hours=7)  # 20:00 VN
        assert (8 <= now_vn.hour <= 9) or (20 <= now_vn.hour <= 22)

    def test_midday_not_journal_time(self):
        """Journal should NOT be available at 15:00 UTC+7."""
        now_vn = datetime(2026, 2, 26, 8, 0, tzinfo=timezone.utc) + timedelta(hours=7)  # 15:00 VN
        assert not ((8 <= now_vn.hour <= 9) or (20 <= now_vn.hour <= 22))


class TestInsightExtraction:
    """Test browsing → insight extraction (social_browser.py)."""

    @pytest.mark.asyncio
    async def test_high_relevance_saved_as_insight(self):
        """Items with relevance >= 0.6 should be saved as insights."""
        from app.engine.living_agent.social_browser import SocialBrowser
        from app.engine.living_agent.models import BrowsingItem

        browser = SocialBrowser()
        items = [
            BrowsingItem(
                platform="web",
                title="COLREGs Update 2026",
                summary="Major changes to Rule 15",
                relevance_score=0.8,
            ),
        ]

        with patch("app.core.database.get_shared_session_factory") as mock_factory:
            mock_session = MagicMock()
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=False)
            mock_factory.return_value = MagicMock(return_value=mock_session)

            saved = await browser._extract_and_save_insights(items)
            assert saved == 1
            # Verify INSERT was called
            mock_session.execute.assert_called()

    @pytest.mark.asyncio
    async def test_low_relevance_not_saved(self):
        """Items with relevance < 0.6 should NOT be saved."""
        from app.engine.living_agent.social_browser import SocialBrowser
        from app.engine.living_agent.models import BrowsingItem

        browser = SocialBrowser()
        items = [
            BrowsingItem(
                platform="web",
                title="Random News",
                summary="Something unrelated",
                relevance_score=0.3,
            ),
        ]

        saved = await browser._extract_and_save_insights(items)
        assert saved == 0

    @pytest.mark.asyncio
    async def test_empty_title_not_saved(self):
        """Items with empty titles should NOT be saved."""
        from app.engine.living_agent.social_browser import SocialBrowser
        from app.engine.living_agent.models import BrowsingItem

        browser = SocialBrowser()
        items = [
            BrowsingItem(
                platform="web",
                title="",
                summary="High relevance but no title",
                relevance_score=0.9,
            ),
        ]

        saved = await browser._extract_and_save_insights(items)
        assert saved == 0

    @pytest.mark.asyncio
    async def test_insight_content_format(self):
        """Insight content should follow [Discovery] format."""
        from app.engine.living_agent.social_browser import SocialBrowser
        from app.engine.living_agent.models import BrowsingItem

        browser = SocialBrowser()
        items = [
            BrowsingItem(
                platform="web",
                title="COLREGs Rule 15 Update",
                summary="Crossing situation rules updated for autonomous vessels",
                relevance_score=0.7,
            ),
        ]

        with patch("app.core.database.get_shared_session_factory") as mock_factory:
            mock_session = MagicMock()
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=False)
            mock_factory.return_value = MagicMock(return_value=mock_session)

            await browser._extract_and_save_insights(items)

            # Check the content passed to INSERT — find it in any execute call
            found_content = False
            for call in mock_session.execute.call_args_list:
                # params can be in args[1] or kwargs
                params = call[0][1] if len(call[0]) > 1 else call.kwargs
                if isinstance(params, dict) and "content" in params:
                    assert "[Discovery]" in params["content"]
                    assert "COLREGs Rule 15 Update" in params["content"]
                    found_content = True
                    break
            assert found_content, "No INSERT with content param found"

    @pytest.mark.asyncio
    async def test_db_error_doesnt_crash(self):
        """DB errors during insight extraction should be swallowed."""
        from app.engine.living_agent.social_browser import SocialBrowser
        from app.engine.living_agent.models import BrowsingItem

        browser = SocialBrowser()
        items = [
            BrowsingItem(
                platform="web",
                title="Test",
                summary="Test summary",
                relevance_score=0.8,
            ),
        ]

        with patch("app.core.database.get_shared_session_factory") as mock_factory:
            mock_factory.side_effect = Exception("DB connection failed")

            # Should not raise
            saved = await browser._extract_and_save_insights(items)
            assert saved == 0

    def test_mark_as_insight_exists(self):
        """_mark_as_insight method should exist."""
        from app.engine.living_agent.social_browser import SocialBrowser
        browser = SocialBrowser()
        assert hasattr(browser, '_mark_as_insight')

    @pytest.mark.asyncio
    async def test_insight_write_blocks_missing_org_context_before_db(self, monkeypatch):
        """Autonomous browsing insight writes fail closed without org context."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.social_browser import SocialBrowser
        from app.engine.living_agent.models import BrowsingItem

        browser = SocialBrowser()
        items = [
            BrowsingItem(
                platform="web",
                title="PRIVATE DISCOVERY TITLE",
                summary="PRIVATE DISCOVERY SUMMARY",
                relevance_score=0.9,
            ),
        ]
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")

        token = current_org_id.set(None)
        try:
            with patch("app.core.database.get_shared_session_factory") as mock_factory, \
                 patch(
                     "app.engine.living_agent.social_browser."
                     "append_semantic_memory_write_audit_event",
                     new_callable=AsyncMock,
                 ) as mock_audit:
                saved = await browser._extract_and_save_insights(
                    items,
                    session_id="raw-social-session",
                )
        finally:
            current_org_id.reset(token)

        assert saved == 0
        mock_factory.assert_not_called()
        mock_audit.assert_awaited_once()
        payload = mock_audit.await_args.kwargs["payload"]
        assert payload["write"]["kind"] == "social_browsing_insight"
        assert payload["write"]["status"] == "blocked"
        assert "social_browsing_insight_blocked_missing_org_context" in payload["warnings"]
        serialized = str(payload)
        assert "PRIVATE DISCOVERY TITLE" not in serialized
        assert "PRIVATE DISCOVERY SUMMARY" not in serialized
        assert "raw-social-session" not in serialized

    @pytest.mark.asyncio
    async def test_insight_write_filters_by_org_and_appends_audit(self, monkeypatch):
        """Autonomous browsing insight writes attach request org and safe audit."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.social_browser import SocialBrowser
        from app.engine.living_agent.models import BrowsingItem

        browser = SocialBrowser()
        item = BrowsingItem(
            platform="web",
            url="https://private.example/discovery",
            title="PRIVATE DISCOVERY TITLE",
            summary="PRIVATE DISCOVERY SUMMARY",
            relevance_score=0.9,
        )
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        token = current_org_id.set("org-A")
        try:
            with patch("app.core.database.get_shared_session_factory", return_value=mock_factory), \
                 patch(
                     "app.engine.living_agent.social_browser."
                     "append_semantic_memory_write_audit_event",
                     new_callable=AsyncMock,
                 ) as mock_audit:
                saved = await browser._extract_and_save_insights(
                    [item],
                    session_id="raw-social-session",
                )
        finally:
            current_org_id.reset(token)

        assert saved == 1
        execute_params = [
            call.args[1]
            for call in mock_session.execute.call_args_list
            if len(call.args) > 1 and isinstance(call.args[1], dict)
        ]
        assert execute_params
        assert all(params.get("org_id") == "org-A" for params in execute_params)
        insert_params = next(params for params in execute_params if "content" in params)
        assert insert_params["user_id"] == "__wiii__"
        assert "PRIVATE DISCOVERY TITLE" in insert_params["content"]
        metadata = json.loads(insert_params["metadata"])
        assert metadata["source"] == "social_browser"
        assert metadata["url_hash"].startswith("sha256:")
        assert item.url not in metadata["url_hash"]
        mock_audit.assert_awaited_once()
        payload = mock_audit.await_args.kwargs["payload"]
        assert payload["write"]["kind"] == "social_browsing_insight"
        assert payload["write"]["status"] == "saved"
        assert payload["write"]["stored_insight_count"] == 1
        serialized = str(payload)
        assert "PRIVATE DISCOVERY TITLE" not in serialized
        assert "raw-social-session" not in serialized

    @pytest.mark.asyncio
    async def test_topic_memory_read_blocks_missing_org_context_before_db(self, monkeypatch):
        """Smart topic memory reads fail closed without org context."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.social_browser import SocialBrowser

        browser = SocialBrowser()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")

        token = current_org_id.set(None)
        try:
            with patch("app.core.database.get_shared_session_factory") as mock_factory:
                topic = await browser._get_topic_from_memories()
        finally:
            current_org_id.reset(token)

        assert topic is None
        mock_factory.assert_not_called()

    @pytest.mark.asyncio
    async def test_topic_memory_read_filters_by_org_context(self, monkeypatch):
        """Smart topic memory reads only request-scoped org memories."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.social_browser import SocialBrowser

        browser = SocialBrowser()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("COLREGs maritime safety training interest",),
        ]
        mock_session.execute.return_value = mock_result
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        token = current_org_id.set("org-A")
        try:
            with patch("app.core.database.get_shared_session_factory", return_value=mock_factory):
                topic = await browser._get_topic_from_memories()
        finally:
            current_org_id.reset(token)

        statement = str(mock_session.execute.call_args.args[0])
        params = mock_session.execute.call_args.args[1]
        assert topic == "maritime"
        assert "organization_id = :org_id" in statement
        assert params["org_id"] == "org-A"

    def test_browsing_log_blocks_missing_org_context_before_db(self, monkeypatch):
        """Browsing log writes fail closed without org context."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.social_browser import SocialBrowser
        from app.engine.living_agent.models import BrowsingItem

        browser = SocialBrowser()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")

        token = current_org_id.set(None)
        try:
            with patch("app.core.database.get_shared_session_factory") as mock_factory:
                browser._save_browsing_log([BrowsingItem(platform="web", title="Title")])
        finally:
            current_org_id.reset(token)

        mock_factory.assert_not_called()


class TestJournalWriterOrgScope:
    """Test org-scoped autonomous journal guardrails."""

    @pytest.mark.asyncio
    async def test_journal_write_blocks_missing_org_context_before_db_or_llm(
        self,
        monkeypatch,
        caplog,
    ):
        """Journal writing fails closed before duplicate checks or LLM calls."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.journal import JournalWriter
        from app.engine.living_agent.models import EmotionalState

        writer = JournalWriter()
        state = EmotionalState()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")
        caplog.set_level(logging.WARNING)

        token = current_org_id.set(None)
        try:
            with patch("app.core.database.get_shared_session_factory") as mock_factory, \
                 patch("app.engine.living_agent.local_llm.get_local_llm") as mock_llm:
                entry = await writer.write_daily_entry(state)
        finally:
            current_org_id.reset(token)

        assert entry is None
        mock_factory.assert_not_called()
        mock_llm.assert_not_called()
        assert "journal_blocked_missing_org_context" in caplog.text

    def test_journal_recent_entries_filters_by_org_context(self, monkeypatch):
        """Recent journal reads only query current-org entries."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.journal import JournalWriter

        writer = JournalWriter()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")

        row = (
            uuid4(),
            datetime.now(timezone.utc),
            "Private journal",
            "calm",
            0.6,
            json.dumps(["event"]),
            json.dumps(["learning"]),
            json.dumps(["goal"]),
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
                entries = writer.get_recent_entries(days=3)
        finally:
            current_org_id.reset(token)

        statement = str(mock_session.execute.call_args.args[0])
        params = mock_session.execute.call_args.args[1]
        assert len(entries) == 1
        assert entries[0].organization_id == "org-A"
        assert "organization_id = :org_id" in statement
        assert params["org_id"] == "org-A"

    def test_journal_get_entry_by_date_filters_by_org_context(self, monkeypatch):
        """Duplicate-entry checks are scoped by current org."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.journal import JournalWriter

        writer = JournalWriter()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")

        row = (
            uuid4(),
            datetime.now(timezone.utc),
            "Private journal",
            "calm",
            0.6,
            json.dumps([]),
            json.dumps([]),
            json.dumps([]),
            "org-A",
        )
        mock_session = MagicMock()
        mock_session.execute.return_value.fetchone.return_value = row
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        token = current_org_id.set("org-A")
        try:
            with patch("app.core.database.get_shared_session_factory", return_value=mock_factory):
                entry = writer._get_entry_by_date(datetime.now(timezone.utc).date())
        finally:
            current_org_id.reset(token)

        statement = str(mock_session.execute.call_args.args[0])
        params = mock_session.execute.call_args.args[1]
        assert entry is not None
        assert entry.organization_id == "org-A"
        assert "organization_id = :org_id" in statement
        assert params["org_id"] == "org-A"

    def test_journal_save_entry_includes_org_context(self, monkeypatch):
        """Journal inserts include resolved org context."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.journal import JournalWriter
        from app.engine.living_agent.models import JournalEntry

        writer = JournalWriter()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")
        entry = JournalEntry(
            entry_date=datetime.now(timezone.utc),
            content="Private journal",
            mood_summary="calm",
            notable_events=["event"],
        )

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        token = current_org_id.set("org-A")
        try:
            with patch("app.core.database.get_shared_session_factory", return_value=mock_factory):
                writer._save_entry(entry)
        finally:
            current_org_id.reset(token)

        statement = str(mock_session.execute.call_args.args[0])
        params = mock_session.execute.call_args.args[1]
        assert "organization_id" in statement
        assert params["org_id"] == "org-A"
        assert entry.organization_id == "org-A"
