"""
Tests for Sprint 51: Memory consolidation tasks coverage.

Tests background memory tasks including:
- consolidate_user_memory (success, summarizer error)
- consolidate_all_active_users (success, no users, error)

Note: memory_tasks.py uses lazy imports inside function bodies, so patches
must target the SOURCE modules (app.services.session_summarizer,
app.repositories.thread_repository), not the consuming module.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock


# ============================================================================
# consolidate_user_memory
# ============================================================================


class TestConsolidateUserMemory:
    """Test single-user memory consolidation."""

    @pytest.mark.asyncio
    async def test_success_no_threads(self):
        from app.tasks.memory_tasks import consolidate_user_memory

        mock_summarizer = MagicMock()
        mock_thread_repo = MagicMock()
        mock_thread_repo.list_threads.return_value = []

        with patch("app.services.session_summarizer.get_session_summarizer", return_value=mock_summarizer), \
             patch("app.repositories.thread_repository.get_thread_repository", return_value=mock_thread_repo):
            result = await consolidate_user_memory("user1")

        assert result["user_id"] == "user1"
        assert result["sessions_summarized"] == 0
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_success_with_unsummarized_threads(self):
        from app.tasks.memory_tasks import consolidate_user_memory

        mock_summarizer = MagicMock()
        mock_summarizer.summarize_thread = AsyncMock(return_value="Summary text")
        mock_thread_repo = MagicMock()
        mock_thread_repo.list_threads.return_value = [
            {"thread_id": "t1", "extra_data": {}},
            {"thread_id": "t2", "extra_data": {"summary": "Already summarized"}},
        ]

        with patch("app.services.session_summarizer.get_session_summarizer", return_value=mock_summarizer), \
             patch("app.repositories.thread_repository.get_thread_repository", return_value=mock_thread_repo):
            result = await consolidate_user_memory("user1")

        assert result["sessions_summarized"] == 1
        mock_summarizer.summarize_thread.assert_called_once()

    @pytest.mark.asyncio
    async def test_success_with_none_extra_data(self):
        from app.tasks.memory_tasks import consolidate_user_memory

        mock_summarizer = MagicMock()
        mock_thread_repo = MagicMock()
        mock_thread_repo.list_threads.return_value = [
            {"thread_id": "t1", "extra_data": None},
        ]

        with patch("app.services.session_summarizer.get_session_summarizer", return_value=mock_summarizer), \
             patch("app.repositories.thread_repository.get_thread_repository", return_value=mock_thread_repo):
            result = await consolidate_user_memory("user1")

        # extra_data is None, not a dict, so isinstance check fails -> skip
        assert result["sessions_summarized"] == 0

    @pytest.mark.asyncio
    async def test_summarizer_error(self):
        from app.tasks.memory_tasks import consolidate_user_memory

        with patch("app.services.session_summarizer.get_session_summarizer", side_effect=Exception("Import error")):
            result = await consolidate_user_memory("user1")

        assert len(result["errors"]) == 1
        assert "summarization" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_summarize_returns_none(self):
        from app.tasks.memory_tasks import consolidate_user_memory

        mock_summarizer = MagicMock()
        mock_summarizer.summarize_thread = AsyncMock(return_value=None)
        mock_thread_repo = MagicMock()
        mock_thread_repo.list_threads.return_value = [
            {"thread_id": "t1", "extra_data": {}},
        ]

        with patch("app.services.session_summarizer.get_session_summarizer", return_value=mock_summarizer), \
             patch("app.repositories.thread_repository.get_thread_repository", return_value=mock_thread_repo):
            result = await consolidate_user_memory("user1")

        assert result["sessions_summarized"] == 0


# ============================================================================
# consolidate_all_active_users
# ============================================================================


class TestConsolidateAllActiveUsers:
    """Test batch user consolidation."""

    @pytest.mark.asyncio
    async def test_no_users(self):
        from app.tasks.memory_tasks import consolidate_all_active_users

        mock_repo = MagicMock()
        mock_repo._session_factory = MagicMock()
        mock_session = MagicMock()
        mock_session.__enter__ = lambda s: mock_session
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_repo._session_factory.return_value = mock_session
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        with patch("app.repositories.thread_repository.get_thread_repository", return_value=mock_repo):
            result = await consolidate_all_active_users()

        assert result["users_processed"] == 0
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_repo_error(self):
        from app.tasks.memory_tasks import consolidate_all_active_users

        with patch("app.repositories.thread_repository.get_thread_repository", side_effect=Exception("DB error")):
            result = await consolidate_all_active_users()

        assert result["users_processed"] == 0
        assert len(result["errors"]) == 1

    @pytest.mark.asyncio
    async def test_no_session_factory(self):
        from app.tasks.memory_tasks import consolidate_all_active_users

        mock_repo = MagicMock()
        mock_repo._session_factory = None

        with patch("app.repositories.thread_repository.get_thread_repository", return_value=mock_repo):
            result = await consolidate_all_active_users()

        assert result["users_processed"] == 0

    @pytest.mark.asyncio
    async def test_processes_users(self):
        from app.tasks.memory_tasks import consolidate_all_active_users

        mock_repo = MagicMock()
        mock_session = MagicMock()
        mock_session.__enter__ = lambda s: mock_session
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_repo._session_factory.return_value = mock_session
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("user1",), ("user2",)]
        mock_session.execute.return_value = mock_result

        # consolidate_user_memory is defined at module level, so we CAN patch it here
        with patch("app.repositories.thread_repository.get_thread_repository", return_value=mock_repo), \
             patch("app.tasks.memory_tasks.consolidate_user_memory", new_callable=AsyncMock) as mock_consolidate:
            mock_consolidate.return_value = {"user_id": "test", "errors": []}
            result = await consolidate_all_active_users()

        assert result["users_processed"] == 2

    @pytest.mark.asyncio
    async def test_user_error_continues(self):
        from app.tasks.memory_tasks import consolidate_all_active_users

        mock_repo = MagicMock()
        mock_session = MagicMock()
        mock_session.__enter__ = lambda s: mock_session
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_repo._session_factory.return_value = mock_session
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("user1",), ("user2",)]
        mock_session.execute.return_value = mock_result

        with patch("app.repositories.thread_repository.get_thread_repository", return_value=mock_repo), \
             patch("app.tasks.memory_tasks.consolidate_user_memory", new_callable=AsyncMock) as mock_consolidate:
            mock_consolidate.side_effect = [Exception("User1 error"), {"user_id": "user2", "errors": []}]
            result = await consolidate_all_active_users()

        assert result["users_processed"] == 1
        assert len(result["errors"]) == 1
