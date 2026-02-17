"""
Tests for session_id normalization in ChatHistoryRepository.

Tests cover:
  1. _normalize_session_id — UUID passthrough, string conversion, uuid5 fallback,
     determinism, edge cases (empty, None, int, composite thread IDs)
  2. save_message — normalization integration for both new and legacy schemas
  3. get_recent_messages — normalization integration for both schemas

Windows: run with `set PYTHONIOENCODING=utf-8 && pytest tests/unit/test_session_id_normalization.py -v -p no:capture`
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call
from uuid import NAMESPACE_DNS, UUID, uuid4, uuid5


# =============================================================================
# _normalize_session_id Tests
# =============================================================================


class TestNormalizeSessionId:
    """Tests for the module-level _normalize_session_id function."""

    def test_uuid_object_passes_through_unchanged(self):
        """A UUID object should be returned as-is, identical object."""
        from app.repositories.chat_history_repository import _normalize_session_id

        original = uuid4()
        result = _normalize_session_id(original)
        assert result is original

    def test_valid_uuid_string_converted_to_uuid(self):
        """A valid UUID string should be converted to the equivalent UUID object."""
        from app.repositories.chat_history_repository import _normalize_session_id

        uuid_str = "12345678-1234-5678-1234-567812345678"
        result = _normalize_session_id(uuid_str)
        assert isinstance(result, UUID)
        assert result == UUID(uuid_str)

    def test_valid_uuid_string_preserves_value(self):
        """A valid UUID string should produce the SAME UUID, not a remapped uuid5."""
        from app.repositories.chat_history_repository import _normalize_session_id

        original = uuid4()
        uuid_str = str(original)
        result = _normalize_session_id(uuid_str)
        assert result == original
        # Verify it's NOT a uuid5 remapping
        assert result != uuid5(NAMESPACE_DNS, uuid_str)

    def test_non_uuid_string_gets_uuid5_mapping(self):
        """A non-UUID string should be mapped via uuid5(NAMESPACE_DNS, value)."""
        from app.repositories.chat_history_repository import _normalize_session_id

        session_str = "my-custom-session"
        result = _normalize_session_id(session_str)
        expected = uuid5(NAMESPACE_DNS, session_str)
        assert isinstance(result, UUID)
        assert result == expected

    def test_deterministic_same_input_same_output(self):
        """Same input should always produce the same output UUID."""
        from app.repositories.chat_history_repository import _normalize_session_id

        input_val = "test-session-abc"
        result1 = _normalize_session_id(input_val)
        result2 = _normalize_session_id(input_val)
        result3 = _normalize_session_id(input_val)
        assert result1 == result2 == result3

    def test_different_inputs_produce_different_outputs(self):
        """Different inputs should produce different UUIDs."""
        from app.repositories.chat_history_repository import _normalize_session_id

        result_a = _normalize_session_id("session-alpha")
        result_b = _normalize_session_id("session-beta")
        assert result_a != result_b

    def test_empty_string_produces_valid_uuid(self):
        """Empty string should still produce a valid UUID (via uuid5)."""
        from app.repositories.chat_history_repository import _normalize_session_id

        result = _normalize_session_id("")
        assert isinstance(result, UUID)
        assert result == uuid5(NAMESPACE_DNS, "")

    def test_none_produces_valid_uuid(self):
        """None input should produce a valid UUID via str(None) -> 'None' -> uuid5."""
        from app.repositories.chat_history_repository import _normalize_session_id

        result = _normalize_session_id(None)
        assert isinstance(result, UUID)
        # str(None) == "None", which is not a valid UUID string,
        # so it falls through to uuid5(NAMESPACE_DNS, "None")
        assert result == uuid5(NAMESPACE_DNS, "None")

    def test_composite_thread_id_format(self):
        """Composite thread IDs like 'user_123__session_abc' should work."""
        from app.repositories.chat_history_repository import _normalize_session_id

        thread_id = "user_123__session_abc"
        result = _normalize_session_id(thread_id)
        assert isinstance(result, UUID)
        assert result == uuid5(NAMESPACE_DNS, thread_id)

    def test_sprint_style_session_id(self):
        """Test-style session IDs like 'test-sprint78-context' should work."""
        from app.repositories.chat_history_repository import _normalize_session_id

        session_id = "test-sprint78-context"
        result = _normalize_session_id(session_id)
        assert isinstance(result, UUID)
        assert result == uuid5(NAMESPACE_DNS, session_id)

    def test_integer_input_coerced_to_string(self):
        """Integer input should be coerced to string and produce valid UUID."""
        from app.repositories.chat_history_repository import _normalize_session_id

        result = _normalize_session_id(42)
        assert isinstance(result, UUID)
        # int 42 -> str(42) == "42", which is not a valid UUID -> uuid5
        assert result == uuid5(NAMESPACE_DNS, "42")

    def test_org_prefixed_thread_id(self):
        """Org-prefixed thread IDs should be normalized deterministically."""
        from app.repositories.chat_history_repository import _normalize_session_id

        thread_id = "org_lms-hang-hai__user_student-123__session_abc"
        result = _normalize_session_id(thread_id)
        assert isinstance(result, UUID)
        assert result == uuid5(NAMESPACE_DNS, thread_id)


# =============================================================================
# Helpers for repository tests
# =============================================================================


def _make_repo(**overrides):
    """Create a ChatHistoryRepository with mocked DB connection.

    Bypasses __init__ DB connection by patching _init_connection, then
    sets internal state directly.
    """
    with patch(
        "app.repositories.chat_history_repository.ChatHistoryRepository._init_connection"
    ):
        from app.repositories.chat_history_repository import ChatHistoryRepository

        repo = ChatHistoryRepository()

    repo._available = overrides.get("available", True)
    repo._use_new_schema = overrides.get("use_new_schema", True)
    repo._session_factory = overrides.get("session_factory", MagicMock())
    repo._engine = overrides.get("engine", MagicMock())
    return repo


def _mock_session_context(repo):
    """Set up a mock session factory that returns a context manager with a mock session.

    Returns the mock db_session object for assertions.
    """
    mock_db_session = MagicMock()
    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_db_session)
    mock_ctx.__exit__ = MagicMock(return_value=False)
    repo._session_factory = MagicMock(return_value=mock_ctx)
    return mock_db_session


# =============================================================================
# save_message normalization tests
# =============================================================================


class TestSaveMessageNormalization:
    """Tests that save_message correctly normalizes session_id."""

    def test_save_message_normalizes_non_uuid_string_new_schema(self):
        """Non-UUID session_id should not raise; normalization converts it to UUID."""
        from app.repositories.chat_history_repository import _normalize_session_id

        repo = _make_repo(use_new_schema=True)
        mock_db = _mock_session_context(repo)

        result = repo.save_message(
            session_id="test-sprint78-context",
            role="user",
            content="Hello",
            user_id="student-1",
        )

        # Should not return None (would mean failure)
        assert result is not None
        # The session_id on the returned message should be the normalized UUID
        expected_uuid = _normalize_session_id("test-sprint78-context")
        assert result.session_id == expected_uuid

    def test_save_message_uses_normalized_uuid_in_insert_new_schema(self):
        """Verify the normalized UUID is passed to the SQL INSERT."""
        from app.repositories.chat_history_repository import _normalize_session_id

        repo = _make_repo(use_new_schema=True)
        mock_db = _mock_session_context(repo)

        non_uuid_id = "user_123__session_abc"
        repo.save_message(
            session_id=non_uuid_id,
            role="assistant",
            content="Hi there",
            user_id="user_123",
        )

        # The execute call should have been called with the normalized UUID string
        expected_norm = str(_normalize_session_id(non_uuid_id))
        execute_call = mock_db.execute.call_args
        assert execute_call is not None
        params = execute_call[0][1] if len(execute_call[0]) > 1 else execute_call[1]
        assert params["session_id"] == expected_norm

    def test_save_message_legacy_schema_calls_ensure_session_exists(self):
        """Legacy schema path should call _ensure_session_exists with normalized UUID."""
        from app.repositories.chat_history_repository import _normalize_session_id

        repo = _make_repo(use_new_schema=False)
        mock_db = _mock_session_context(repo)

        # Mock _ensure_session_exists
        repo._ensure_session_exists = MagicMock()

        # Mock the add/commit to avoid issues
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()

        non_uuid_id = "my-test-session"
        expected_norm = _normalize_session_id(non_uuid_id)

        repo.save_message(
            session_id=non_uuid_id,
            role="user",
            content="Test message",
            user_id="user-1",
        )

        repo._ensure_session_exists.assert_called_once_with(
            mock_db, expected_norm, "user-1"
        )

    def test_save_message_uuid_object_not_remapped(self):
        """A proper UUID object should pass through without being remapped."""
        repo = _make_repo(use_new_schema=True)
        mock_db = _mock_session_context(repo)

        original_uuid = uuid4()
        result = repo.save_message(
            session_id=original_uuid,
            role="user",
            content="Test",
            user_id="user-1",
        )

        assert result is not None
        assert result.session_id == original_uuid

    def test_save_message_returns_none_when_unavailable(self):
        """When repository is unavailable, save_message returns None without error."""
        repo = _make_repo(available=False)

        result = repo.save_message(
            session_id="anything",
            role="user",
            content="Test",
        )
        assert result is None


# =============================================================================
# get_recent_messages normalization tests
# =============================================================================


class TestGetRecentMessagesNormalization:
    """Tests that get_recent_messages correctly normalizes session_id."""

    def test_get_recent_normalizes_non_uuid_new_schema(self):
        """Non-UUID session_id should be normalized in the query (new schema)."""
        from app.repositories.chat_history_repository import _normalize_session_id

        repo = _make_repo(use_new_schema=True)
        mock_db = _mock_session_context(repo)

        # Mock the execute to return empty results
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        non_uuid_id = "test-sprint78-context"
        expected_norm = _normalize_session_id(non_uuid_id)

        messages = repo.get_recent_messages(session_id=non_uuid_id)

        # Should not raise
        assert messages == []

        # Verify the normalized UUID string was passed to the query
        execute_call = mock_db.execute.call_args
        params = execute_call[0][1] if len(execute_call[0]) > 1 else execute_call[1]
        assert params["query_value"] == str(expected_norm)

    def test_get_recent_normalizes_non_uuid_legacy_schema(self):
        """Non-UUID session_id should be normalized in the query (legacy schema)."""
        from app.repositories.chat_history_repository import _normalize_session_id

        repo = _make_repo(use_new_schema=False)
        mock_db = _mock_session_context(repo)

        # Mock the execute chain for legacy ORM query
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_execute_result

        non_uuid_id = "user_123__session_abc"
        expected_norm = _normalize_session_id(non_uuid_id)

        messages = repo.get_recent_messages(session_id=non_uuid_id)
        assert messages == []

        # The execute call's select statement should use the normalized UUID
        # We verify by checking the call was made (no exception from non-UUID)
        assert mock_db.execute.called

    def test_get_recent_uuid_string_preserves_value(self):
        """A valid UUID string should be normalized to the same UUID value."""
        from app.repositories.chat_history_repository import _normalize_session_id

        repo = _make_repo(use_new_schema=True)
        mock_db = _mock_session_context(repo)

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        original_uuid = uuid4()
        uuid_str = str(original_uuid)

        repo.get_recent_messages(session_id=uuid_str)

        execute_call = mock_db.execute.call_args
        params = execute_call[0][1] if len(execute_call[0]) > 1 else execute_call[1]
        # Should use the same UUID value, not a uuid5 remap
        assert params["query_value"] == str(original_uuid)

    def test_get_recent_with_user_id_new_schema(self):
        """When user_id is provided in new schema, query should use user_id field."""
        repo = _make_repo(use_new_schema=True)
        mock_db = _mock_session_context(repo)

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        repo.get_recent_messages(
            session_id="test-session",
            user_id="student-123",
        )

        execute_call = mock_db.execute.call_args
        params = execute_call[0][1] if len(execute_call[0]) > 1 else execute_call[1]
        assert params["query_value"] == "student-123"

    def test_get_recent_returns_empty_when_unavailable(self):
        """When repository is unavailable, returns empty list without error."""
        repo = _make_repo(available=False)

        result = repo.get_recent_messages(session_id="anything")
        assert result == []
