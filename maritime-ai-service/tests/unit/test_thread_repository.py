"""
Tests for ThreadRepository (Sprint 16).

Verifies:
- upsert_thread: insert new + update existing
- list_threads: with/without results, ownership filtering
- get_thread: found + not found
- delete_thread: success + not found
- rename_thread: success + not found
- count_threads
- is_available (true/false)
- Singleton get_thread_repository()
- Graceful degradation when database unavailable
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_singleton():
    """Reset the ThreadRepository singleton between tests."""
    import app.repositories.thread_repository as mod
    mod._thread_repo = None


def _make_repo_with_mock_session():
    """
    Create a ThreadRepository with mocked database.

    Returns:
        (repo, mock_session) — repo is initialized, mock_session is the
        context-managed session object.
    """
    from app.repositories.thread_repository import ThreadRepository

    repo = ThreadRepository()

    mock_session = MagicMock()
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_session_factory.return_value.__exit__ = MagicMock(return_value=False)

    # Bypass lazy init — inject directly
    repo._engine = MagicMock()
    repo._session_factory = mock_session_factory
    repo._initialized = True

    return repo, mock_session


def _make_thread_row(
    thread_id="user_1__session_abc",
    user_id="user_1",
    domain_id="maritime",
    title="Test thread",
    message_count=5,
    last_message_at=None,
    created_at=None,
    updated_at=None,
    extra_data=None,
    is_deleted=False,
):
    """Create a fake database row tuple matching SELECT column order."""
    now = datetime.now(timezone.utc)
    return (
        thread_id,
        user_id,
        domain_id,
        title,
        message_count,
        last_message_at or now,
        created_at or now,
        updated_at or now,
        extra_data or {},
        is_deleted,
    )


# ===========================================================================
# Tests: upsert_thread
# ===========================================================================

class TestUpsertThread:
    """Test upsert_thread — insert new and update existing."""

    def test_upsert_inserts_new_thread(self):
        """When thread does not exist, INSERT is executed."""
        repo, mock_session = _make_repo_with_mock_session()

        # First SELECT returns None (thread not found)
        mock_session.execute.return_value.fetchone.return_value = None

        result = repo.upsert_thread(
            thread_id="user_1__session_new",
            user_id="user_1",
            domain_id="maritime",
            title="New conversation",
        )

        assert result is not None
        assert result["thread_id"] == "user_1__session_new"
        assert result["user_id"] == "user_1"
        assert result["title"] == "New conversation"

        # Should have called execute twice: SELECT + INSERT
        assert mock_session.execute.call_count == 2
        mock_session.commit.assert_called_once()

    def test_upsert_updates_existing_thread(self):
        """When thread exists, UPDATE is executed with incremented count."""
        repo, mock_session = _make_repo_with_mock_session()

        # First SELECT returns an existing row (thread_id, message_count, extra_data)
        mock_session.execute.return_value.fetchone.return_value = (
            "user_1__session_old",
            10,
            {"key": "value"},
        )

        result = repo.upsert_thread(
            thread_id="user_1__session_old",
            user_id="user_1",
            domain_id="maritime",
            title="Updated title",
            message_count_increment=2,
            extra_data={"new_key": "new_val"},
        )

        assert result is not None
        assert result["thread_id"] == "user_1__session_old"
        assert result["title"] == "Updated title"

        # SELECT + UPDATE = 2 calls
        assert mock_session.execute.call_count == 2
        mock_session.commit.assert_called_once()

    def test_upsert_returns_default_title_when_none(self):
        """When title is None, uses Vietnamese default title."""
        repo, mock_session = _make_repo_with_mock_session()
        mock_session.execute.return_value.fetchone.return_value = None

        result = repo.upsert_thread(
            thread_id="user_1__session_x",
            user_id="user_1",
        )

        assert result is not None
        assert result["title"] == "Cuộc trò chuyện mới"

    def test_upsert_returns_none_when_not_initialized(self):
        """When session factory is None, returns None."""
        from app.repositories.thread_repository import ThreadRepository

        repo = ThreadRepository()
        repo._initialized = True
        repo._session_factory = None

        result = repo.upsert_thread("tid", "uid")
        assert result is None

    def test_upsert_returns_none_on_exception(self):
        """When database raises, returns None gracefully."""
        repo, mock_session = _make_repo_with_mock_session()
        mock_session.execute.side_effect = Exception("DB error")

        result = repo.upsert_thread("tid", "uid")
        assert result is None


# ===========================================================================
# Tests: list_threads
# ===========================================================================

class TestListThreads:
    """Test list_threads — with/without results, ownership."""

    def test_list_threads_returns_results(self):
        """Returns list of thread dicts for a user."""
        repo, mock_session = _make_repo_with_mock_session()

        row1 = _make_thread_row(thread_id="t1", title="Thread 1")
        row2 = _make_thread_row(thread_id="t2", title="Thread 2")
        mock_session.execute.return_value.fetchall.return_value = [row1, row2]

        result = repo.list_threads(user_id="user_1")

        assert len(result) == 2
        assert result[0]["thread_id"] == "t1"
        assert result[1]["thread_id"] == "t2"

    def test_list_threads_empty(self):
        """Returns empty list when user has no threads."""
        repo, mock_session = _make_repo_with_mock_session()
        mock_session.execute.return_value.fetchall.return_value = []

        result = repo.list_threads(user_id="user_no_threads")
        assert result == []

    def test_list_threads_returns_empty_when_not_initialized(self):
        """When session factory is None, returns empty list."""
        from app.repositories.thread_repository import ThreadRepository

        repo = ThreadRepository()
        repo._initialized = True
        repo._session_factory = None

        result = repo.list_threads("user_1")
        assert result == []

    def test_list_threads_on_exception(self):
        """When database raises, returns empty list gracefully."""
        repo, mock_session = _make_repo_with_mock_session()
        mock_session.execute.side_effect = Exception("Connection lost")

        result = repo.list_threads("user_1")
        assert result == []


# ===========================================================================
# Tests: get_thread
# ===========================================================================

class TestGetThread:
    """Test get_thread — found and not found."""

    def test_get_thread_found(self):
        """Returns thread dict when found and owned by user."""
        repo, mock_session = _make_repo_with_mock_session()

        row = _make_thread_row(
            thread_id="user_1__session_abc",
            user_id="user_1",
            title="My Thread",
            message_count=7,
        )
        mock_session.execute.return_value.fetchone.return_value = row

        result = repo.get_thread("user_1__session_abc", "user_1")

        assert result is not None
        assert result["thread_id"] == "user_1__session_abc"
        assert result["title"] == "My Thread"
        assert result["message_count"] == 7

    def test_get_thread_not_found(self):
        """Returns None when thread does not exist or wrong owner."""
        repo, mock_session = _make_repo_with_mock_session()
        mock_session.execute.return_value.fetchone.return_value = None

        result = repo.get_thread("nonexistent", "user_1")
        assert result is None

    def test_get_thread_returns_none_when_not_initialized(self):
        """When session factory is None, returns None."""
        from app.repositories.thread_repository import ThreadRepository

        repo = ThreadRepository()
        repo._initialized = True
        repo._session_factory = None

        result = repo.get_thread("tid", "uid")
        assert result is None


# ===========================================================================
# Tests: delete_thread
# ===========================================================================

class TestDeleteThread:
    """Test delete_thread — success and not found."""

    def test_delete_thread_success(self):
        """Returns True when soft-delete succeeds (rowcount > 0)."""
        repo, mock_session = _make_repo_with_mock_session()
        mock_session.execute.return_value.rowcount = 1

        result = repo.delete_thread("user_1__session_abc", "user_1")

        assert result is True
        mock_session.commit.assert_called_once()

    def test_delete_thread_not_found(self):
        """Returns False when thread not found or not owned (rowcount = 0)."""
        repo, mock_session = _make_repo_with_mock_session()
        mock_session.execute.return_value.rowcount = 0

        result = repo.delete_thread("nonexistent", "user_1")

        assert result is False
        mock_session.commit.assert_called_once()

    def test_delete_thread_returns_false_when_not_initialized(self):
        """When session factory is None, returns False."""
        from app.repositories.thread_repository import ThreadRepository

        repo = ThreadRepository()
        repo._initialized = True
        repo._session_factory = None

        result = repo.delete_thread("tid", "uid")
        assert result is False


# ===========================================================================
# Tests: rename_thread
# ===========================================================================

class TestRenameThread:
    """Test rename_thread — success and not found."""

    def test_rename_thread_success(self):
        """Returns True when rename succeeds (rowcount > 0)."""
        repo, mock_session = _make_repo_with_mock_session()
        mock_session.execute.return_value.rowcount = 1

        result = repo.rename_thread("user_1__session_abc", "user_1", "New Title")

        assert result is True
        mock_session.commit.assert_called_once()

    def test_rename_thread_not_found(self):
        """Returns False when thread not found or not owned (rowcount = 0)."""
        repo, mock_session = _make_repo_with_mock_session()
        mock_session.execute.return_value.rowcount = 0

        result = repo.rename_thread("nonexistent", "user_1", "Title")

        assert result is False

    def test_rename_thread_on_exception(self):
        """When database raises, returns False gracefully."""
        repo, mock_session = _make_repo_with_mock_session()
        mock_session.execute.side_effect = Exception("DB error")

        result = repo.rename_thread("tid", "uid", "title")
        assert result is False


# ===========================================================================
# Tests: count_threads
# ===========================================================================

class TestCountThreads:
    """Test count_threads."""

    def test_count_threads_returns_count(self):
        """Returns the scalar count of active threads."""
        repo, mock_session = _make_repo_with_mock_session()
        mock_session.execute.return_value.scalar.return_value = 42

        result = repo.count_threads("user_1")
        assert result == 42

    def test_count_threads_returns_zero_when_none(self):
        """Returns 0 when scalar returns None."""
        repo, mock_session = _make_repo_with_mock_session()
        mock_session.execute.return_value.scalar.return_value = None

        result = repo.count_threads("user_1")
        assert result == 0

    def test_count_threads_returns_zero_on_exception(self):
        """Returns 0 on database error."""
        repo, mock_session = _make_repo_with_mock_session()
        mock_session.execute.side_effect = Exception("Timeout")

        result = repo.count_threads("user_1")
        assert result == 0

    def test_count_threads_returns_zero_when_not_initialized(self):
        """When session factory is None, returns 0."""
        from app.repositories.thread_repository import ThreadRepository

        repo = ThreadRepository()
        repo._initialized = True
        repo._session_factory = None

        result = repo.count_threads("user_1")
        assert result == 0


# ===========================================================================
# Tests: is_available
# ===========================================================================

class TestIsAvailable:
    """Test is_available — true and false."""

    def test_is_available_true(self):
        """Returns True when database responds to SELECT 1."""
        repo, mock_session = _make_repo_with_mock_session()

        assert repo.is_available() is True
        mock_session.execute.assert_called_once()

    def test_is_available_false_on_exception(self):
        """Returns False when database raises."""
        repo, mock_session = _make_repo_with_mock_session()
        mock_session.execute.side_effect = Exception("Connection refused")

        assert repo.is_available() is False

    def test_is_available_false_when_not_initialized(self):
        """Returns False when initialization fails."""
        from app.repositories.thread_repository import ThreadRepository

        repo = ThreadRepository()
        # Simulate failed init: _ensure_initialized sets _initialized but no session_factory
        repo._initialized = True
        repo._session_factory = None

        assert repo.is_available() is False


# ===========================================================================
# Tests: Singleton get_thread_repository()
# ===========================================================================

class TestSingleton:
    """Test the get_thread_repository() singleton."""

    @pytest.fixture(autouse=True)
    def reset(self):
        _reset_singleton()
        yield
        _reset_singleton()

    def test_returns_thread_repository_instance(self):
        """Returns a ThreadRepository instance."""
        from app.repositories.thread_repository import (
            get_thread_repository,
            ThreadRepository,
        )

        repo = get_thread_repository()
        assert isinstance(repo, ThreadRepository)

    def test_returns_same_instance(self):
        """Second call returns the same cached instance."""
        from app.repositories.thread_repository import get_thread_repository

        repo1 = get_thread_repository()
        repo2 = get_thread_repository()
        assert repo1 is repo2

    def test_reset_creates_new_instance(self):
        """After resetting singleton, a new instance is created."""
        from app.repositories.thread_repository import get_thread_repository

        repo1 = get_thread_repository()
        _reset_singleton()
        repo2 = get_thread_repository()
        assert repo1 is not repo2


# ===========================================================================
# Tests: Lazy initialization (_ensure_initialized)
# ===========================================================================

class TestLazyInit:
    """Test _ensure_initialized() lazy database connection."""

    def test_ensure_initialized_calls_database_singletons(self):
        """_ensure_initialized calls get_shared_engine and get_shared_session_factory."""
        from app.repositories.thread_repository import ThreadRepository

        repo = ThreadRepository()
        assert repo._initialized is False

        mock_engine = MagicMock()
        mock_factory = MagicMock()

        with patch(
            "app.core.database.get_shared_engine", return_value=mock_engine
        ) as mock_get_engine, patch(
            "app.core.database.get_shared_session_factory",
            return_value=mock_factory,
        ) as mock_get_factory:
            repo._ensure_initialized()

        assert repo._initialized is True
        assert repo._engine is mock_engine
        assert repo._session_factory is mock_factory
        mock_get_engine.assert_called_once()
        mock_get_factory.assert_called_once()

    def test_ensure_initialized_handles_import_error(self):
        """_ensure_initialized handles database import errors gracefully."""
        from app.repositories.thread_repository import ThreadRepository

        repo = ThreadRepository()

        with patch(
            "app.core.database.get_shared_engine",
            side_effect=Exception("No database configured"),
        ):
            repo._ensure_initialized()

        # Should not crash; remains uninitialized
        assert repo._initialized is False
        assert repo._session_factory is None

    def test_ensure_initialized_skips_if_already_done(self):
        """_ensure_initialized is a no-op when already initialized."""
        from app.repositories.thread_repository import ThreadRepository

        repo = ThreadRepository()
        repo._initialized = True
        repo._engine = "existing_engine"
        repo._session_factory = "existing_factory"

        with patch("app.core.database.get_shared_engine") as mock_get:
            repo._ensure_initialized()

        # Should NOT have called get_shared_engine again
        mock_get.assert_not_called()
        assert repo._engine == "existing_engine"


# ===========================================================================
# Tests: _row_to_dict
# ===========================================================================

class TestRowToDict:
    """Test the static _row_to_dict helper."""

    def test_row_to_dict_full_row(self):
        """Converts a full 10-element row tuple to dict."""
        from app.repositories.thread_repository import ThreadRepository

        now = datetime(2026, 2, 9, 12, 0, 0, tzinfo=timezone.utc)
        row = (
            "thread_1",
            "user_1",
            "maritime",
            "My Title",
            15,
            now,
            now,
            now,
            {"summary": "hello"},
            False,
        )

        result = ThreadRepository._row_to_dict(row)

        assert result["thread_id"] == "thread_1"
        assert result["user_id"] == "user_1"
        assert result["domain_id"] == "maritime"
        assert result["title"] == "My Title"
        assert result["message_count"] == 15
        assert result["extra_data"] == {"summary": "hello"}
        assert result["is_deleted"] is False
        assert "2026-02-09" in result["last_message_at"]

    def test_row_to_dict_none_timestamps(self):
        """Handles None timestamps gracefully."""
        from app.repositories.thread_repository import ThreadRepository

        row = ("t1", "u1", "maritime", "Title", 0, None, None, None, None, False)

        result = ThreadRepository._row_to_dict(row)

        assert result["last_message_at"] is None
        assert result["created_at"] is None
        assert result["updated_at"] is None
        assert result["extra_data"] == {}
