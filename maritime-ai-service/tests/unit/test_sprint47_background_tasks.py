"""
Tests for Sprint 47: BackgroundTaskRunner coverage.

Tests background task management including:
- BackgroundTaskRunner init
- schedule_all (with/without dependencies)
- save_message (normal, blocked)
- _store_semantic_interaction, _summarize_memory, _update_profile_stats
- Error handling in private methods
- Singleton get_background_runner, init_background_runner

NOTE: _save_messages removed in Sprint 83 (double-save fix H7).
Message persistence now handled exclusively by ChatOrchestrator.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch, call
from uuid import uuid4


# ============================================================================
# BackgroundTaskRunner init
# ============================================================================


class TestBackgroundTaskRunnerInit:
    """Test BackgroundTaskRunner initialization."""

    def test_init_no_deps(self):
        from app.services.background_tasks import BackgroundTaskRunner
        runner = BackgroundTaskRunner()
        assert runner._chat_history is None
        assert runner._semantic_memory is None
        assert runner._memory_summarizer is None
        assert runner._profile_repo is None

    def test_init_with_deps(self):
        from app.services.background_tasks import BackgroundTaskRunner
        mock_ch = MagicMock()
        mock_sm = MagicMock()
        mock_ms = MagicMock()
        mock_pr = MagicMock()
        runner = BackgroundTaskRunner(
            chat_history=mock_ch,
            semantic_memory=mock_sm,
            memory_summarizer=mock_ms,
            profile_repo=mock_pr
        )
        assert runner._chat_history is mock_ch
        assert runner._semantic_memory is mock_sm


# ============================================================================
# schedule_all
# ============================================================================


class TestScheduleAll:
    """Test schedule_all background task scheduling."""

    def test_all_deps_available(self):
        from app.services.background_tasks import BackgroundTaskRunner
        mock_ch = MagicMock()
        mock_ch.is_available.return_value = True
        mock_sm = MagicMock()
        mock_sm.is_available.return_value = True
        mock_ms = MagicMock()
        mock_pr = MagicMock()
        mock_pr.is_available.return_value = True

        runner = BackgroundTaskRunner(
            chat_history=mock_ch,
            semantic_memory=mock_sm,
            memory_summarizer=mock_ms,
            profile_repo=mock_pr
        )
        background_save = MagicMock()
        session_id = uuid4()

        runner.schedule_all(background_save, "user1", session_id, "Hello", "Hi there")
        # Should schedule 4 tasks (semantic memory, summarizer, profile stats, character reflection)
        # NOTE: message saving is handled by ChatOrchestrator, not here (Sprint 83)
        # Sprint 97: +1 for character reflection (enabled by default)
        assert background_save.call_count == 4

    def test_no_deps_schedules_reflection_only(self):
        """Sprint 97: Character reflection always runs (no repo dependency)."""
        from app.services.background_tasks import BackgroundTaskRunner
        runner = BackgroundTaskRunner()
        background_save = MagicMock()
        runner.schedule_all(background_save, "user1", uuid4(), "msg", "resp")
        assert background_save.call_count == 1  # Character reflection only

    def test_partial_deps_chat_history_only(self):
        """Chat history alone: only character reflection (Sprint 97)."""
        from app.services.background_tasks import BackgroundTaskRunner
        mock_ch = MagicMock()
        mock_ch.is_available.return_value = True
        runner = BackgroundTaskRunner(chat_history=mock_ch)
        background_save = MagicMock()
        runner.schedule_all(background_save, "user1", uuid4(), "msg", "resp")
        # Sprint 97: +1 character reflection (always runs)
        assert background_save.call_count == 1

    def test_unavailable_deps_skipped(self):
        """Unavailable deps skip their tasks; character reflection still runs (Sprint 97)."""
        from app.services.background_tasks import BackgroundTaskRunner
        mock_ch = MagicMock()
        mock_ch.is_available.return_value = False
        runner = BackgroundTaskRunner(chat_history=mock_ch)
        background_save = MagicMock()
        runner.schedule_all(background_save, "user1", uuid4(), "msg", "resp")
        assert background_save.call_count == 1  # Character reflection only


# ============================================================================
# save_message
# ============================================================================


class TestSaveMessage:
    """Test save_message."""

    def test_normal_message(self):
        from app.services.background_tasks import BackgroundTaskRunner
        mock_ch = MagicMock()
        mock_ch.is_available.return_value = True
        runner = BackgroundTaskRunner(chat_history=mock_ch)
        background_save = MagicMock()
        session_id = uuid4()

        runner.save_message(background_save, session_id, "user", "Hello")
        background_save.assert_called_once()

    def test_blocked_message_saves_sync(self):
        from app.services.background_tasks import BackgroundTaskRunner
        mock_ch = MagicMock()
        mock_ch.is_available.return_value = True
        runner = BackgroundTaskRunner(chat_history=mock_ch)
        background_save = MagicMock()
        session_id = uuid4()

        runner.save_message(
            background_save, session_id, "user", "Bad content",
            user_id="user1", is_blocked=True, block_reason="Offensive"
        )
        # Blocked messages saved synchronously, not via background_save
        background_save.assert_not_called()
        mock_ch.save_message.assert_called_once()

    def test_no_chat_history(self):
        from app.services.background_tasks import BackgroundTaskRunner
        runner = BackgroundTaskRunner()
        background_save = MagicMock()
        runner.save_message(background_save, uuid4(), "user", "Hello")
        background_save.assert_not_called()


# ============================================================================
# _store_semantic_interaction
# ============================================================================


class TestStoreSemanticInteraction:
    """Test _store_semantic_interaction."""

    @pytest.mark.asyncio
    async def test_stores_interaction(self):
        from app.services.background_tasks import BackgroundTaskRunner
        mock_sm = AsyncMock()
        mock_sm.extract_and_store_insights = AsyncMock(return_value=[])
        mock_sm.store_interaction = AsyncMock()
        mock_sm.check_and_summarize = AsyncMock()
        runner = BackgroundTaskRunner(semantic_memory=mock_sm)
        await runner._store_semantic_interaction("user1", "msg", "resp", "session1")
        mock_sm.store_interaction.assert_called_once()
        mock_sm.check_and_summarize.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_handling(self):
        from app.services.background_tasks import BackgroundTaskRunner
        mock_sm = AsyncMock()
        mock_sm.extract_and_store_insights = AsyncMock(side_effect=Exception("fail"))
        runner = BackgroundTaskRunner(semantic_memory=mock_sm)
        # Should not raise
        await runner._store_semantic_interaction("user1", "msg", "resp", "session1")


# ============================================================================
# _summarize_memory
# ============================================================================


class TestSummarizeMemory:
    """Test _summarize_memory."""

    @pytest.mark.asyncio
    async def test_adds_messages(self):
        from app.services.background_tasks import BackgroundTaskRunner
        mock_ms = AsyncMock()
        runner = BackgroundTaskRunner(memory_summarizer=mock_ms)
        await runner._summarize_memory("session1", "msg", "resp")
        assert mock_ms.add_message_async.call_count == 2

    @pytest.mark.asyncio
    async def test_error_handling(self):
        from app.services.background_tasks import BackgroundTaskRunner
        mock_ms = AsyncMock()
        mock_ms.add_message_async.side_effect = Exception("fail")
        runner = BackgroundTaskRunner(memory_summarizer=mock_ms)
        await runner._summarize_memory("session1", "msg", "resp")


# ============================================================================
# _update_profile_stats
# ============================================================================


class TestUpdateProfileStats:
    """Test _update_profile_stats."""

    @pytest.mark.asyncio
    async def test_increments_stats(self):
        from app.services.background_tasks import BackgroundTaskRunner
        mock_pr = AsyncMock()
        runner = BackgroundTaskRunner(profile_repo=mock_pr)
        await runner._update_profile_stats("user1")
        mock_pr.increment_stats.assert_called_once_with("user1", messages=2)

    @pytest.mark.asyncio
    async def test_error_handling(self):
        from app.services.background_tasks import BackgroundTaskRunner
        mock_pr = AsyncMock()
        mock_pr.increment_stats.side_effect = Exception("fail")
        runner = BackgroundTaskRunner(profile_repo=mock_pr)
        await runner._update_profile_stats("user1")


# ============================================================================
# Singleton
# ============================================================================


class TestSingleton:
    """Test singleton functions."""

    def test_get_background_runner(self):
        import app.services.background_tasks as mod
        mod._background_runner = None
        runner1 = mod.get_background_runner()
        runner2 = mod.get_background_runner()
        assert runner1 is runner2
        mod._background_runner = None  # Cleanup

    def test_init_background_runner(self):
        import app.services.background_tasks as mod
        mod._background_runner = None
        mock_ch = MagicMock()
        runner = mod.init_background_runner(chat_history=mock_ch)
        assert runner._chat_history is mock_ch
        mod._background_runner = None  # Cleanup
