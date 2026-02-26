"""
Tests for Sprint 177 Feature B: Cross-Platform Memory Sync.

Covers:
- Config: enable_cross_platform_memory, cross_platform_context_max_items
- CrossPlatformMemory: merge, conflict resolution, summary, activity
- OTP Linking: Memory merge trigger after link_identity()
- InputProcessor: Cross-platform context injection
- Channel Detection: _detect_channel() helper
"""

import json
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


# =============================================================================
# Config Tests
# =============================================================================

class TestCrossPlatformConfig:
    """Test new config flags."""

    def test_defaults(self):
        from app.core.config import Settings
        # Explicitly set to False to test code defaults (env may override)
        s = Settings(api_key="test", enable_cross_platform_memory=False)
        assert s.enable_cross_platform_memory is False
        assert s.cross_platform_context_max_items == 3

    def test_enabled(self):
        from app.core.config import Settings
        s = Settings(
            api_key="test",
            enable_cross_platform_memory=True,
            cross_platform_context_max_items=5,
        )
        assert s.enable_cross_platform_memory is True
        assert s.cross_platform_context_max_items == 5


# =============================================================================
# Channel Detection Tests
# =============================================================================

class TestDetectChannel:
    """Test _detect_channel() helper."""

    def test_messenger_prefix(self):
        from app.engine.semantic_memory.cross_platform import _detect_channel
        assert _detect_channel("messenger_12345") == "messenger"

    def test_zalo_prefix(self):
        from app.engine.semantic_memory.cross_platform import _detect_channel
        assert _detect_channel("zalo_abc123") == "zalo"

    def test_telegram_prefix(self):
        from app.engine.semantic_memory.cross_platform import _detect_channel
        assert _detect_channel("telegram_xyz") == "telegram"

    def test_desktop_format_user_session(self):
        from app.engine.semantic_memory.cross_platform import _detect_channel
        assert _detect_channel("user_abc__session_def") == "desktop"

    def test_desktop_format_user_only(self):
        from app.engine.semantic_memory.cross_platform import _detect_channel
        assert _detect_channel("user_abc") == "desktop"

    def test_empty_string(self):
        from app.engine.semantic_memory.cross_platform import _detect_channel
        assert _detect_channel("") == ""

    def test_unknown_format(self):
        from app.engine.semantic_memory.cross_platform import _detect_channel
        assert _detect_channel("random-session-id") == ""

    def test_session_in_middle(self):
        from app.engine.semantic_memory.cross_platform import _detect_channel
        assert _detect_channel("org_1__session_abc") == ""


# =============================================================================
# Conflict Resolution Tests
# =============================================================================

class TestConflictResolution:
    """Test fact conflict resolution logic."""

    def test_higher_importance_wins(self):
        from app.engine.semantic_memory.cross_platform import CrossPlatformMemory
        merger = CrossPlatformMemory()
        result = merger.resolve_fact_conflict(
            canonical_importance=0.5,
            incoming_importance=0.8,
        )
        assert result == "incoming"

    def test_lower_importance_loses(self):
        from app.engine.semantic_memory.cross_platform import CrossPlatformMemory
        merger = CrossPlatformMemory()
        result = merger.resolve_fact_conflict(
            canonical_importance=0.9,
            incoming_importance=0.3,
        )
        assert result == "canonical"

    def test_tie_break_by_recency_incoming_newer(self):
        from app.engine.semantic_memory.cross_platform import CrossPlatformMemory
        merger = CrossPlatformMemory()
        now = datetime.now(timezone.utc)
        result = merger.resolve_fact_conflict(
            canonical_importance=0.5,
            incoming_importance=0.5,
            canonical_created=now - timedelta(hours=2),
            incoming_created=now - timedelta(hours=1),
        )
        assert result == "incoming"

    def test_tie_break_by_recency_canonical_newer(self):
        from app.engine.semantic_memory.cross_platform import CrossPlatformMemory
        merger = CrossPlatformMemory()
        now = datetime.now(timezone.utc)
        result = merger.resolve_fact_conflict(
            canonical_importance=0.5,
            incoming_importance=0.5,
            canonical_created=now - timedelta(hours=1),
            incoming_created=now - timedelta(hours=2),
        )
        assert result == "canonical"

    def test_tie_no_dates_canonical_wins(self):
        from app.engine.semantic_memory.cross_platform import CrossPlatformMemory
        merger = CrossPlatformMemory()
        result = merger.resolve_fact_conflict(
            canonical_importance=0.5,
            incoming_importance=0.5,
        )
        assert result == "canonical"


# =============================================================================
# Memory Merge Tests
# =============================================================================

class TestMemoryMerge:
    """Test merge_memories() logic."""

    @pytest.mark.asyncio
    async def test_merge_no_legacy_memories(self):
        from app.engine.semantic_memory.cross_platform import CrossPlatformMemory
        merger = CrossPlatformMemory()

        mock_session = MagicMock()
        mock_session.execute.return_value.fetchall.return_value = []
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_session)

        with patch("app.core.database.get_shared_session_factory", return_value=mock_factory):
            result = await merger.merge_memories("canonical-1", "messenger_123", "messenger")

        assert result["migrated"] == 0
        assert result["duplicates_resolved"] == 0

    @pytest.mark.asyncio
    async def test_merge_migrates_unique_memories(self):
        from app.engine.semantic_memory.cross_platform import CrossPlatformMemory
        merger = CrossPlatformMemory()

        legacy_id = str(uuid4())
        legacy_rows = [
            (legacy_id, "A fact about user", 0.7, "fact", {}, datetime.now(timezone.utc)),
        ]
        canonical_rows = []

        mock_session = MagicMock()
        call_count = [0]

        def side_effect(*args, **kwargs):
            result = MagicMock()
            if call_count[0] == 0:
                result.fetchall.return_value = legacy_rows
            else:
                result.fetchall.return_value = canonical_rows
            call_count[0] += 1
            return result

        mock_session.execute.side_effect = side_effect
        mock_session.commit = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_session)

        with patch("app.core.database.get_shared_session_factory", return_value=mock_factory):
            result = await merger.merge_memories("canonical-1", "messenger_123", "messenger")

        assert result["migrated"] == 1
        assert result["duplicates_resolved"] == 0

    @pytest.mark.asyncio
    async def test_merge_resolves_duplicate_incoming_wins(self):
        from app.engine.semantic_memory.cross_platform import CrossPlatformMemory
        merger = CrossPlatformMemory()

        now = datetime.now(timezone.utc)
        legacy_id = str(uuid4())
        canonical_id = str(uuid4())

        legacy_rows = [
            (legacy_id, "Same fact", 0.9, "fact", {}, now),  # Higher importance
        ]
        canonical_rows = [
            (canonical_id, "Same fact", 0.5, "fact", {}, now - timedelta(hours=1)),
        ]

        mock_session = MagicMock()
        call_count = [0]

        def side_effect(*args, **kwargs):
            result = MagicMock()
            if call_count[0] == 0:
                result.fetchall.return_value = legacy_rows
            else:
                result.fetchall.return_value = canonical_rows
            call_count[0] += 1
            return result

        mock_session.execute.side_effect = side_effect
        mock_session.commit = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_session)

        with patch("app.core.database.get_shared_session_factory", return_value=mock_factory):
            result = await merger.merge_memories("canonical-1", "messenger_123", "messenger")

        assert result["duplicates_resolved"] == 1

    @pytest.mark.asyncio
    async def test_merge_handles_db_error_gracefully(self):
        from app.engine.semantic_memory.cross_platform import CrossPlatformMemory
        merger = CrossPlatformMemory()

        with patch("app.core.database.get_shared_session_factory", side_effect=Exception("DB down")):
            result = await merger.merge_memories("canonical-1", "messenger_123")

        assert result["migrated"] == 0
        assert result["duplicates_resolved"] == 0

    @pytest.mark.asyncio
    async def test_merge_handles_json_string_metadata(self):
        from app.engine.semantic_memory.cross_platform import CrossPlatformMemory
        merger = CrossPlatformMemory()

        legacy_id = str(uuid4())
        legacy_rows = [
            (legacy_id, "A fact", 0.7, "fact", '{"key": "value"}', datetime.now(timezone.utc)),
        ]
        canonical_rows = []

        mock_session = MagicMock()
        call_count = [0]

        def side_effect(*args, **kwargs):
            result = MagicMock()
            if call_count[0] == 0:
                result.fetchall.return_value = legacy_rows
            else:
                result.fetchall.return_value = canonical_rows
            call_count[0] += 1
            return result

        mock_session.execute.side_effect = side_effect
        mock_session.commit = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_session)

        with patch("app.core.database.get_shared_session_factory", return_value=mock_factory):
            result = await merger.merge_memories("canonical-1", "messenger_123")

        assert result["migrated"] == 1


# =============================================================================
# Cross-Platform Summary Tests
# =============================================================================

class TestCrossPlatformSummary:
    """Test get_cross_platform_summary()."""

    @pytest.mark.asyncio
    async def test_summary_filters_current_channel(self):
        from app.engine.semantic_memory.cross_platform import CrossPlatformMemory
        merger = CrossPlatformMemory()

        now = datetime.now(timezone.utc)
        rows = [
            ("Hỏi về COLREGs", "messenger_abc", "fact", now - timedelta(hours=1)),
            ("Desktop question", "user_123__session_456", "fact", now - timedelta(hours=2)),
        ]

        mock_session = MagicMock()
        mock_session.execute.return_value.fetchall.return_value = rows
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_session)

        with patch("app.core.database.get_shared_session_factory", return_value=mock_factory), \
             patch("app.core.config.settings") as mock_settings:
            mock_settings.cross_platform_context_max_items = 3
            summary = await merger.get_cross_platform_summary("user-1", "desktop")

        # Should include messenger but NOT desktop
        assert "Messenger" in summary
        assert "Desktop" not in summary

    @pytest.mark.asyncio
    async def test_summary_empty_when_no_other_platforms(self):
        from app.engine.semantic_memory.cross_platform import CrossPlatformMemory
        merger = CrossPlatformMemory()

        now = datetime.now(timezone.utc)
        rows = [
            ("Question", "user_1__session_2", "fact", now),
        ]

        mock_session = MagicMock()
        mock_session.execute.return_value.fetchall.return_value = rows
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_session)

        with patch("app.core.database.get_shared_session_factory", return_value=mock_factory), \
             patch("app.core.config.settings") as mock_settings:
            mock_settings.cross_platform_context_max_items = 3
            summary = await merger.get_cross_platform_summary("user-1", "desktop")

        assert summary == ""

    @pytest.mark.asyncio
    async def test_summary_empty_when_no_rows(self):
        from app.engine.semantic_memory.cross_platform import CrossPlatformMemory
        merger = CrossPlatformMemory()

        mock_session = MagicMock()
        mock_session.execute.return_value.fetchall.return_value = []
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_session)

        with patch("app.core.database.get_shared_session_factory", return_value=mock_factory), \
             patch("app.core.config.settings") as mock_settings:
            mock_settings.cross_platform_context_max_items = 3
            summary = await merger.get_cross_platform_summary("user-1", "desktop")

        assert summary == ""

    @pytest.mark.asyncio
    async def test_summary_handles_db_error(self):
        from app.engine.semantic_memory.cross_platform import CrossPlatformMemory
        merger = CrossPlatformMemory()

        with patch("app.core.database.get_shared_session_factory", side_effect=Exception("DB down")):
            summary = await merger.get_cross_platform_summary("user-1", "desktop")

        assert summary == ""

    @pytest.mark.asyncio
    async def test_summary_respects_max_items(self):
        from app.engine.semantic_memory.cross_platform import CrossPlatformMemory
        merger = CrossPlatformMemory()

        now = datetime.now(timezone.utc)
        rows = [
            (f"Fact {i}", f"messenger_{i}", "fact", now - timedelta(hours=i))
            for i in range(10)
        ]

        mock_session = MagicMock()
        mock_session.execute.return_value.fetchall.return_value = rows
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_session)

        with patch("app.core.database.get_shared_session_factory", return_value=mock_factory), \
             patch("app.core.config.settings") as mock_settings:
            mock_settings.cross_platform_context_max_items = 2
            summary = await merger.get_cross_platform_summary("user-1", "desktop", max_items=2)

        lines = summary.strip().split("\n")
        assert len(lines) <= 2


# =============================================================================
# Platform Activity Tests
# =============================================================================

class TestPlatformActivity:
    """Test get_platform_activity()."""

    @pytest.mark.asyncio
    async def test_platform_activity_aggregates(self):
        from app.engine.semantic_memory.cross_platform import CrossPlatformMemory
        merger = CrossPlatformMemory()

        rows = [
            ("messenger_abc", 5),
            ("messenger_def", 3),
            ("user_1__session_2", 10),
        ]

        mock_session = MagicMock()
        mock_session.execute.return_value.fetchall.return_value = rows
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_session)

        with patch("app.core.database.get_shared_session_factory", return_value=mock_factory):
            activity = await merger.get_platform_activity("user-1")

        assert activity.get("messenger") == 8
        assert activity.get("desktop") == 10

    @pytest.mark.asyncio
    async def test_platform_activity_handles_error(self):
        from app.engine.semantic_memory.cross_platform import CrossPlatformMemory
        merger = CrossPlatformMemory()

        with patch("app.core.database.get_shared_session_factory", side_effect=Exception("err")):
            activity = await merger.get_platform_activity("user-1")

        assert activity == {}


# =============================================================================
# Time Formatting Tests
# =============================================================================

class TestFormatTimeAgo:
    """Test Vietnamese relative time formatting."""

    def test_minutes(self):
        from app.engine.semantic_memory.cross_platform import CrossPlatformMemory
        merger = CrossPlatformMemory()
        dt = datetime.now(timezone.utc) - timedelta(minutes=30)
        result = merger._format_time_ago(dt)
        assert "30 phút trước" == result

    def test_hours(self):
        from app.engine.semantic_memory.cross_platform import CrossPlatformMemory
        merger = CrossPlatformMemory()
        dt = datetime.now(timezone.utc) - timedelta(hours=3)
        result = merger._format_time_ago(dt)
        assert "3h trước" == result

    def test_days(self):
        from app.engine.semantic_memory.cross_platform import CrossPlatformMemory
        merger = CrossPlatformMemory()
        dt = datetime.now(timezone.utc) - timedelta(days=2)
        result = merger._format_time_ago(dt)
        assert "2 ngày trước" == result

    def test_none_input(self):
        from app.engine.semantic_memory.cross_platform import CrossPlatformMemory
        merger = CrossPlatformMemory()
        result = merger._format_time_ago(None)
        assert result == ""

    def test_naive_datetime(self):
        from app.engine.semantic_memory.cross_platform import CrossPlatformMemory
        merger = CrossPlatformMemory()
        # Naive datetime (no timezone)
        dt = datetime.now() - timedelta(hours=1)
        result = merger._format_time_ago(dt)
        assert "1h trước" == result


# =============================================================================
# OTP Linking — Memory Merge Trigger
# =============================================================================

def _make_mock_asyncpg_pool(row_data=None):
    """Create a mock asyncpg pool for DB-backed OTP tests."""
    mock_conn = AsyncMock()
    if row_data:
        mock_conn.fetchrow = AsyncMock(return_value=row_data)
    else:
        mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_conn.execute = AsyncMock()

    # pool.acquire() returns an async context manager (not a coroutine)
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_pool = MagicMock()
    mock_pool.acquire.return_value = mock_ctx
    return mock_pool


class TestOTPLinkingMergeTrigger:
    """Test memory merge after OTP link_identity."""

    @pytest.mark.asyncio
    async def test_merge_triggered_on_otp_link_success(self):
        from app.auth.otp_linking import verify_and_link

        # DB row returned for valid OTP
        row_data = {
            "user_id": "canonical-uuid",
            "channel_type": "messenger",
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
            "used_at": None,
            "failed_attempts": 0,
            "updated_at": None,
        }
        mock_pool = _make_mock_asyncpg_pool(row_data)

        mock_merger = MagicMock()
        mock_merger.merge_memories = AsyncMock(return_value={"migrated": 3, "duplicates_resolved": 1})

        with patch("app.core.database.get_asyncpg_pool", create=True, new_callable=AsyncMock, return_value=mock_pool), \
             patch("app.auth.user_service.link_identity", new_callable=AsyncMock), \
             patch("app.core.config.settings") as mock_settings, \
             patch("app.engine.semantic_memory.cross_platform.get_cross_platform_memory", return_value=mock_merger):
            mock_settings.enable_cross_platform_memory = True
            mock_settings.otp_max_verify_attempts = 5
            success, user_id = await verify_and_link("123456", "messenger", "fb_sender_123")

        assert success is True
        assert user_id == "canonical-uuid"
        mock_merger.merge_memories.assert_called_once_with(
            canonical_user_id="canonical-uuid",
            legacy_user_id="messenger_fb_sender_123",
            channel_type="messenger",
        )

    @pytest.mark.asyncio
    async def test_merge_not_triggered_when_disabled(self):
        from app.auth.otp_linking import verify_and_link

        row_data = {
            "user_id": "canonical-uuid",
            "channel_type": "zalo",
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
            "used_at": None,
            "failed_attempts": 0,
            "updated_at": None,
        }
        mock_pool = _make_mock_asyncpg_pool(row_data)

        with patch("app.core.database.get_asyncpg_pool", create=True, new_callable=AsyncMock, return_value=mock_pool), \
             patch("app.auth.user_service.link_identity", new_callable=AsyncMock), \
             patch("app.core.config.settings") as mock_settings:
            mock_settings.enable_cross_platform_memory = False
            mock_settings.otp_max_verify_attempts = 5
            success, user_id = await verify_and_link("654321", "zalo", "zalo_user_1")

        assert success is True

    @pytest.mark.asyncio
    async def test_merge_failure_does_not_break_linking(self):
        from app.auth.otp_linking import verify_and_link

        row_data = {
            "user_id": "canonical-uuid",
            "channel_type": "messenger",
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
            "used_at": None,
            "failed_attempts": 0,
            "updated_at": None,
        }
        mock_pool = _make_mock_asyncpg_pool(row_data)

        mock_merger = MagicMock()
        mock_merger.merge_memories = AsyncMock(side_effect=Exception("Merge failed"))

        with patch("app.core.database.get_asyncpg_pool", create=True, new_callable=AsyncMock, return_value=mock_pool), \
             patch("app.auth.user_service.link_identity", new_callable=AsyncMock), \
             patch("app.core.config.settings") as mock_settings, \
             patch("app.engine.semantic_memory.cross_platform.get_cross_platform_memory", return_value=mock_merger):
            mock_settings.enable_cross_platform_memory = True
            mock_settings.otp_max_verify_attempts = 5
            success, user_id = await verify_and_link("111111", "messenger", "fb_123")

        # Linking still succeeds even though merge failed
        assert success is True
        assert user_id == "canonical-uuid"


# =============================================================================
# InputProcessor — Cross-Platform Context Injection
# =============================================================================

class TestInputProcessorCrossPlatform:
    """Test cross-platform context injection in build_context."""

    @pytest.mark.asyncio
    async def test_context_injection_when_enabled(self):
        from app.services.input_processor import InputProcessor
        from app.models.schemas import UserRole

        processor = InputProcessor.__new__(InputProcessor)
        processor._semantic_memory = None
        processor._chat_history = None
        processor._learning_graph = None
        processor._memory_summarizer = None
        processor._conversation_analyzer = None
        processor._guardian_agent = None
        processor._guardrails = None

        mock_merger = MagicMock()
        mock_merger.get_cross_platform_summary = AsyncMock(
            return_value="Trên Messenger: Bạn hỏi về COLREGs (1h trước)"
        )

        mock_request = MagicMock()
        mock_request.user_id = "user-1"
        mock_request.message = "Hello world test message"
        mock_request.role = UserRole.STUDENT
        mock_request.user_context = None

        session_id = uuid4()

        with patch("app.services.input_processor.settings") as mock_settings, \
             patch("app.engine.semantic_memory.cross_platform.get_cross_platform_memory", return_value=mock_merger), \
             patch("app.engine.semantic_memory.cross_platform._detect_channel", return_value="desktop"):
            mock_settings.enable_cross_platform_memory = True
            context = await processor.build_context(mock_request, session_id)

        assert "Hoạt động đa nền tảng" in context.semantic_context
        assert "Messenger" in context.semantic_context


# =============================================================================
# Singleton Tests
# =============================================================================

class TestCrossPlatformSingleton:
    """Test singleton pattern."""

    def test_get_cross_platform_memory_singleton(self):
        from app.engine.semantic_memory import cross_platform
        cross_platform._xp_memory_instance = None
        instance1 = cross_platform.get_cross_platform_memory()
        instance2 = cross_platform.get_cross_platform_memory()
        assert instance1 is instance2
        cross_platform._xp_memory_instance = None  # Cleanup
