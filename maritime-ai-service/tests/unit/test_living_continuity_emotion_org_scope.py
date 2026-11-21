import json
import logging
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from tests.unit.living_continuity_helpers import (
    _make_settings,
    reset_runtime_metrics as reset_runtime_metrics,
)


class TestEmotionEngineOrgScope:
    """Test org-scoped emotional persistence and relationship cache guardrails."""

    @pytest.mark.asyncio
    async def test_emotion_state_save_blocks_missing_org_context_before_db(
        self,
        monkeypatch,
        caplog,
    ):
        """Persistent emotion saves fail closed without org context."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.emotion_engine import EmotionEngine

        engine = EmotionEngine()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")
        caplog.set_level(logging.WARNING)

        token = current_org_id.set(None)
        try:
            with patch("app.core.database.get_shared_session_factory") as mock_factory:
                await engine.save_state_to_db()
        finally:
            current_org_id.reset(token)

        mock_factory.assert_not_called()
        assert "emotion_state_blocked_missing_org_context" in caplog.text

    @pytest.mark.asyncio
    async def test_emotion_state_save_filters_persistent_state_by_org_context(
        self,
        monkeypatch,
    ):
        """Persistent state replacement only deletes/inserts current-org rows."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.emotion_engine import EmotionEngine

        engine = EmotionEngine()
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
                await engine.save_state_to_db()
        finally:
            current_org_id.reset(token)

        delete_statement = str(mock_session.execute.call_args_list[0].args[0])
        delete_params = mock_session.execute.call_args_list[0].args[1]
        insert_statement = str(mock_session.execute.call_args_list[1].args[0])
        insert_params = mock_session.execute.call_args_list[1].args[1]
        assert "AND organization_id = :org_id" in delete_statement
        assert delete_params["org_id"] == "org-A"
        assert "organization_id" in insert_statement
        assert insert_params["org_id"] == "org-A"

    @pytest.mark.asyncio
    async def test_emotion_state_load_filters_by_org_context(self, monkeypatch):
        """Persistent emotion loads only read current-org state."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.engine.living_agent.emotion_engine import EmotionEngine

        engine = EmotionEngine()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")

        mock_session = MagicMock()
        mock_session.execute.return_value.fetchone.return_value = None
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        token = current_org_id.set("org-A")
        try:
            with patch("app.core.database.get_shared_session_factory", return_value=mock_factory):
                loaded = await engine.load_state_from_db()
        finally:
            current_org_id.reset(token)

        statement = str(mock_session.execute.call_args.args[0])
        params = mock_session.execute.call_args.args[1]
        assert loaded is False
        assert "AND organization_id = :org_id" in statement
        assert params["org_id"] == "org-A"

    def test_known_user_cache_refresh_blocks_missing_org_context_before_db(
        self,
        monkeypatch,
        caplog,
    ):
        """Known-user cache refresh fails closed without org context."""
        import app.engine.living_agent.emotion_engine as mod
        from app.core.config import settings
        from app.core.org_context import current_org_id

        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")
        caplog.set_level(logging.WARNING)

        token = current_org_id.set(None)
        try:
            with patch("app.core.database.get_shared_session_factory") as mock_factory:
                count = mod.refresh_known_user_cache()
        finally:
            current_org_id.reset(token)

        assert count == 0
        mock_factory.assert_not_called()
        assert "known_user_cache_blocked_missing_org_context" in caplog.text

    def test_known_user_cache_refresh_filters_by_org_context(self, monkeypatch):
        """Known-user cache refresh only reads current-org routines."""
        import app.engine.living_agent.emotion_engine as mod
        from app.core.config import settings
        from app.core.org_context import current_org_id

        old_cache = mod._known_user_cache
        old_by_org = dict(mod._known_user_cache_by_org)
        mod._known_user_cache = set()
        mod._known_user_cache_by_org = {}
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")

        mock_session = MagicMock()
        mock_session.execute.return_value.fetchall.return_value = [("user-a",), ("user-b",)]
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)
        app_settings = _make_settings(living_agent_known_user_threshold=50)

        token = current_org_id.set("org-A")
        try:
            with patch("app.core.database.get_shared_session_factory", return_value=mock_factory), \
                 patch("app.core.config.get_settings", return_value=app_settings):
                count = mod.refresh_known_user_cache()
                scoped_cache = dict(mod._known_user_cache_by_org)
                legacy_cache = set(mod._known_user_cache)
        finally:
            current_org_id.reset(token)
            mod._known_user_cache = old_cache
            mod._known_user_cache_by_org = old_by_org

        statement = str(mock_session.execute.call_args.args[0])
        params = mock_session.execute.call_args.args[1]
        assert count == 2
        assert "AND organization_id = :org_id" in statement
        assert params["org_id"] == "org-A"
        assert scoped_cache["org-A"] == {"user-a", "user-b"}
        assert "user-a" not in legacy_cache

    def test_known_user_tier_uses_org_scoped_cache(self):
        """Known-user tier ignores legacy/global cache for explicit org lookups."""
        import app.engine.living_agent.emotion_engine as mod

        old_cache = mod._known_user_cache
        old_by_org = dict(mod._known_user_cache_by_org)
        try:
            mod._known_user_cache = {"global-known-user"}
            mod._known_user_cache_by_org = {
                "org-A": {"user-a"},
                "org-B": {"user-b"},
            }
            app_settings = _make_settings(living_agent_creator_user_ids="")

            with patch("app.core.config.get_settings", return_value=app_settings):
                assert mod.get_relationship_tier(
                    "user-a",
                    "student",
                    organization_id="org-A",
                ) == mod.TIER_KNOWN
                assert mod.get_relationship_tier(
                    "user-a",
                    "student",
                    organization_id="org-B",
                ) == mod.TIER_OTHER
                assert mod.get_relationship_tier(
                    "global-known-user",
                    "student",
                    organization_id="org-A",
                ) == mod.TIER_OTHER
        finally:
            mod._known_user_cache = old_cache
            mod._known_user_cache_by_org = old_by_org


class TestEmotionalStateRepositoryOrgScope:
    """Test org-scoped emotional snapshot repository guardrails."""

    def test_emotional_repo_save_blocks_missing_org_context_before_db(
        self,
        monkeypatch,
        caplog,
    ):
        """Snapshot writes fail closed without org context."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.repositories.emotional_state_repository import EmotionalStateRepository

        repo = EmotionalStateRepository()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")
        caplog.set_level(logging.WARNING)

        token = current_org_id.set(None)
        try:
            with patch("app.repositories.emotional_state_repository.get_shared_session_factory") as mock_factory:
                snapshot_id = repo.save_snapshot(
                    primary_mood="private",
                    energy_level=0.5,
                    social_battery=0.5,
                    engagement=0.5,
                    state_json={"private": True},
                )
        finally:
            current_org_id.reset(token)

        assert snapshot_id == ""
        mock_factory.assert_not_called()
        assert "emotional_state_repository_blocked_missing_org_context" in caplog.text
        assert "private" not in caplog.text

    def test_emotional_repo_save_includes_org_context(self, monkeypatch):
        """Snapshot inserts include resolved org scope."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.repositories.emotional_state_repository import EmotionalStateRepository

        repo = EmotionalStateRepository()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        token = current_org_id.set("org-A")
        try:
            with patch("app.repositories.emotional_state_repository.get_shared_session_factory", return_value=mock_factory):
                snapshot_id = repo.save_snapshot(
                    primary_mood="happy",
                    energy_level=0.8,
                    social_battery=0.7,
                    engagement=0.6,
                )
        finally:
            current_org_id.reset(token)

        statement = str(mock_session.execute.call_args.args[0])
        params = mock_session.execute.call_args.args[1]
        assert snapshot_id
        assert "organization_id" in statement
        assert params["org_id"] == "org-A"

    def test_emotional_repo_latest_filters_by_org_context(self, monkeypatch):
        """Latest snapshot reads are scoped by current org."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.repositories.emotional_state_repository import EmotionalStateRepository

        repo = EmotionalStateRepository()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")

        now = datetime.now(timezone.utc)
        mock_session = MagicMock()
        mock_session.execute.return_value.fetchone.return_value = (
            "snapshot-1",
            "calm",
            0.6,
            0.7,
            0.8,
            "heartbeat_cycle",
            now,
            json.dumps({"primary_mood": "calm"}),
        )
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        token = current_org_id.set("org-A")
        try:
            with patch("app.repositories.emotional_state_repository.get_shared_session_factory", return_value=mock_factory):
                latest = repo.get_latest()
        finally:
            current_org_id.reset(token)

        statement = str(mock_session.execute.call_args.args[0])
        params = mock_session.execute.call_args.args[1]
        assert latest["id"] == "snapshot-1"
        assert "WHERE organization_id = :org_id" in statement
        assert params["org_id"] == "org-A"

    def test_emotional_repo_history_filters_by_org_context(self, monkeypatch):
        """History reads are scoped by current org."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.repositories.emotional_state_repository import EmotionalStateRepository

        repo = EmotionalStateRepository()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")

        now = datetime.now(timezone.utc)
        mock_session = MagicMock()
        mock_session.execute.return_value.fetchall.return_value = [
            ("snapshot-1", "calm", 0.6, 0.7, 0.8, "heartbeat_cycle", now),
        ]
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        token = current_org_id.set("org-A")
        try:
            with patch("app.repositories.emotional_state_repository.get_shared_session_factory", return_value=mock_factory):
                history = repo.get_history(hours=2)
        finally:
            current_org_id.reset(token)

        statement = str(mock_session.execute.call_args.args[0])
        params = mock_session.execute.call_args.args[1]
        assert len(history) == 1
        assert "AND organization_id = :org_id" in statement
        assert params["org_id"] == "org-A"
        assert params["hours"] == 2

    def test_emotional_repo_cleanup_filters_by_org_context(self, monkeypatch):
        """Snapshot cleanup cannot delete another org's history."""
        from app.core.config import settings
        from app.core.org_context import current_org_id
        from app.repositories.emotional_state_repository import EmotionalStateRepository

        repo = EmotionalStateRepository()
        monkeypatch.setattr(settings, "enable_multi_tenant", True)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "default_organization_id", "default")

        result = MagicMock()
        result.rowcount = 3
        mock_session = MagicMock()
        mock_session.execute.return_value = result
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        token = current_org_id.set("org-A")
        try:
            with patch("app.repositories.emotional_state_repository.get_shared_session_factory", return_value=mock_factory):
                deleted = repo.cleanup_old_snapshots(keep_days=7)
        finally:
            current_org_id.reset(token)

        statement = str(mock_session.execute.call_args.args[0])
        params = mock_session.execute.call_args.args[1]
        assert deleted == 3
        assert "AND organization_id = :org_id" in statement
        assert params["org_id"] == "org-A"
        assert params["keep_days"] == 7
