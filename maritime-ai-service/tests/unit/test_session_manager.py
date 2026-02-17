"""
Tests for SessionManager — Session lifecycle and state management.

Verifies:
- SessionState: phrase tracking, name usage frequency, pronoun style
- SessionContext: initialization, default state creation
- SessionManager: get_or_create_session, state tracking, thread support
- Singleton: get_session_manager factory
"""

import pytest
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

from app.services.session_manager import (
    SessionState,
    SessionContext,
    SessionManager,
)


# =============================================================================
# SessionState
# =============================================================================

class TestSessionState:
    """Tests for SessionState dataclass."""

    def test_initial_state(self):
        """New session state has correct defaults."""
        sid = uuid4()
        state = SessionState(session_id=sid)

        assert state.session_id == sid
        assert state.recent_phrases == []
        assert state.name_usage_count == 0
        assert state.total_responses == 0
        assert state.is_first_message is True
        assert state.pronoun_style is None

    def test_add_phrase(self):
        """Phrases are tracked in order."""
        state = SessionState(session_id=uuid4())
        state.add_phrase("Chào bạn!")
        state.add_phrase("Rất vui!")

        assert len(state.recent_phrases) == 2
        assert state.recent_phrases[0] == "Chào bạn!"
        assert state.recent_phrases[1] == "Rất vui!"

    def test_add_phrase_max_five(self):
        """Only last 5 phrases are kept (sliding window)."""
        state = SessionState(session_id=uuid4())
        for i in range(7):
            state.add_phrase(f"phrase-{i}")

        assert len(state.recent_phrases) == 5
        assert state.recent_phrases[0] == "phrase-2"
        assert state.recent_phrases[-1] == "phrase-6"

    def test_increment_response_no_name(self):
        """Increment without name usage."""
        state = SessionState(session_id=uuid4())
        state.increment_response(used_name=False)

        assert state.total_responses == 1
        assert state.name_usage_count == 0
        assert state.is_first_message is False

    def test_increment_response_with_name(self):
        """Increment with name usage."""
        state = SessionState(session_id=uuid4())
        state.increment_response(used_name=True)

        assert state.total_responses == 1
        assert state.name_usage_count == 1
        assert state.is_first_message is False

    def test_should_use_name_first_response(self):
        """First response should always use name."""
        state = SessionState(session_id=uuid4())
        assert state.should_use_name() is True

    def test_should_use_name_under_threshold(self):
        """Should use name when ratio < 25%."""
        state = SessionState(session_id=uuid4())
        # 10 responses, 1 with name = 10% → should use
        state.total_responses = 10
        state.name_usage_count = 1
        assert state.should_use_name() is True

    def test_should_not_use_name_over_threshold(self):
        """Should not use name when ratio >= 25%."""
        state = SessionState(session_id=uuid4())
        # 4 responses, 2 with name = 50% → should not
        state.total_responses = 4
        state.name_usage_count = 2
        assert state.should_use_name() is False

    def test_should_use_name_at_boundary(self):
        """At exactly 25%, should not use name (< 0.25 check)."""
        state = SessionState(session_id=uuid4())
        state.total_responses = 4
        state.name_usage_count = 1  # 25% → not < 0.25
        assert state.should_use_name() is False

    def test_update_pronoun_style(self):
        """Pronoun style is updated when provided."""
        state = SessionState(session_id=uuid4())
        style = {"user": "em", "bot": "anh"}
        state.update_pronoun_style(style)

        assert state.pronoun_style == {"user": "em", "bot": "anh"}

    def test_update_pronoun_style_none(self):
        """None pronoun style does not overwrite existing."""
        state = SessionState(session_id=uuid4())
        state.pronoun_style = {"user": "mình", "bot": "cậu"}
        state.update_pronoun_style(None)

        assert state.pronoun_style == {"user": "mình", "bot": "cậu"}


# =============================================================================
# SessionContext
# =============================================================================

class TestSessionContext:
    """Tests for SessionContext dataclass."""

    def test_default_state_created(self):
        """SessionContext creates default SessionState if none provided."""
        sid = uuid4()
        ctx = SessionContext(session_id=sid, user_id="user-1")

        assert ctx.state is not None
        assert isinstance(ctx.state, SessionState)
        assert ctx.state.session_id == sid

    def test_explicit_state(self):
        """SessionContext uses explicit state when provided."""
        sid = uuid4()
        state = SessionState(session_id=sid, total_responses=5)
        ctx = SessionContext(session_id=sid, user_id="user-1", state=state)

        assert ctx.state.total_responses == 5

    def test_optional_fields(self):
        """Optional fields default to None."""
        sid = uuid4()
        ctx = SessionContext(session_id=sid, user_id="user-1")

        assert ctx.thread_id is None
        assert ctx.user_name is None

    def test_all_fields(self):
        """All fields are stored correctly."""
        sid = uuid4()
        ctx = SessionContext(
            session_id=sid,
            user_id="user-1",
            thread_id="thread-abc",
            user_name="Nguyễn Văn A",
        )

        assert ctx.session_id == sid
        assert ctx.user_id == "user-1"
        assert ctx.thread_id == "thread-abc"
        assert ctx.user_name == "Nguyễn Văn A"


# =============================================================================
# SessionManager
# =============================================================================

class TestSessionManager:
    """Tests for SessionManager service."""

    @pytest.fixture
    def mock_chat_history(self):
        """Create a mock ChatHistoryRepository."""
        repo = MagicMock()
        repo.is_available.return_value = False
        return repo

    @pytest.fixture
    def manager(self, mock_chat_history):
        """Create SessionManager with mocked chat history."""
        return SessionManager(chat_history=mock_chat_history)

    def test_init(self, manager):
        """Manager initializes with empty session maps."""
        assert manager._sessions == {}
        assert manager._session_states == {}

    def test_is_available(self, manager):
        """Manager is always available."""
        assert manager.is_available() is True

    # ---- get_or_create_session (no thread_id, no DB) ----

    def test_get_or_create_session_new_user(self, manager):
        """Creates new session for new user (in-memory fallback)."""
        ctx = manager.get_or_create_session(user_id="user-1")

        assert isinstance(ctx, SessionContext)
        assert ctx.user_id == "user-1"
        assert ctx.session_id is not None
        assert ctx.state.is_first_message is True

    def test_get_or_create_session_same_user(self, manager):
        """Same user gets same session ID."""
        ctx1 = manager.get_or_create_session(user_id="user-1")
        ctx2 = manager.get_or_create_session(user_id="user-1")

        assert ctx1.session_id == ctx2.session_id

    def test_get_or_create_session_different_users(self, manager):
        """Different users get different session IDs."""
        ctx1 = manager.get_or_create_session(user_id="user-1")
        ctx2 = manager.get_or_create_session(user_id="user-2")

        assert ctx1.session_id != ctx2.session_id

    # ---- get_or_create_session (with thread_id) ----

    def test_thread_id_valid_uuid(self, manager):
        """Valid UUID thread_id is used as session_id."""
        thread_id = str(uuid4())
        ctx = manager.get_or_create_session(user_id="user-1", thread_id=thread_id)

        assert ctx.session_id == UUID(thread_id)
        assert ctx.thread_id == thread_id

    def test_thread_id_invalid_uuid_fallback(self, manager):
        """Invalid UUID thread_id falls back to in-memory session."""
        ctx = manager.get_or_create_session(
            user_id="user-1", thread_id="not-a-uuid"
        )

        # Should still get a valid session, just not from thread_id
        assert isinstance(ctx.session_id, UUID)

    # ---- get_or_create_session (with DB available) ----

    def test_session_from_chat_history(self, mock_chat_history):
        """When DB is available, uses chat history session."""
        mock_chat_history.is_available.return_value = True
        mock_session = MagicMock()
        mock_session.session_id = uuid4()
        mock_chat_history.get_or_create_session.return_value = mock_session
        mock_chat_history.get_user_name.return_value = "Nguyễn Văn A"

        manager = SessionManager(chat_history=mock_chat_history)
        ctx = manager.get_or_create_session(user_id="user-1")

        assert ctx.session_id == mock_session.session_id
        assert ctx.user_name == "Nguyễn Văn A"
        mock_chat_history.get_or_create_session.assert_called_once_with("user-1")

    def test_session_from_chat_history_returns_none(self, mock_chat_history):
        """When DB is available but returns None, falls back to in-memory."""
        mock_chat_history.is_available.return_value = True
        mock_chat_history.get_or_create_session.return_value = None
        mock_chat_history.get_user_name.return_value = None

        manager = SessionManager(chat_history=mock_chat_history)
        ctx = manager.get_or_create_session(user_id="user-1")

        # Falls through to in-memory
        assert isinstance(ctx.session_id, UUID)

    # ---- State management ----

    def test_get_state(self, manager):
        """get_state returns or creates SessionState."""
        sid = uuid4()
        state = manager.get_state(sid)

        assert isinstance(state, SessionState)
        assert state.session_id == sid

    def test_get_state_same_session(self, manager):
        """Same session_id returns same state instance."""
        sid = uuid4()
        s1 = manager.get_state(sid)
        s2 = manager.get_state(sid)

        assert s1 is s2

    def test_update_state_phrase(self, manager):
        """update_state tracks phrases."""
        sid = uuid4()
        manager.update_state(sid, phrase="Chào bạn!")

        state = manager.get_state(sid)
        assert "Chào bạn!" in state.recent_phrases
        assert state.total_responses == 1

    def test_update_state_name_usage(self, manager):
        """update_state tracks name usage."""
        sid = uuid4()
        manager.update_state(sid, used_name=True)

        state = manager.get_state(sid)
        assert state.name_usage_count == 1

    def test_update_state_pronoun_style(self, manager):
        """update_state updates pronoun style."""
        sid = uuid4()
        style = {"user": "em", "bot": "anh"}
        manager.update_state(sid, pronoun_style=style)

        state = manager.get_state(sid)
        assert state.pronoun_style == style

    def test_update_state_all_at_once(self, manager):
        """update_state with all params at once."""
        sid = uuid4()
        manager.update_state(
            sid,
            phrase="Xin chào!",
            used_name=True,
            pronoun_style={"user": "tôi", "bot": "bạn"},
        )

        state = manager.get_state(sid)
        assert "Xin chào!" in state.recent_phrases
        assert state.name_usage_count == 1
        assert state.total_responses == 1
        assert state.pronoun_style == {"user": "tôi", "bot": "bạn"}

    def test_update_state_no_phrase(self, manager):
        """update_state without phrase still increments response."""
        sid = uuid4()
        manager.update_state(sid)

        state = manager.get_state(sid)
        assert state.total_responses == 1
        assert len(state.recent_phrases) == 0

    # ---- update_user_name ----

    def test_update_user_name_with_db(self, mock_chat_history):
        """update_user_name calls chat history when available."""
        mock_chat_history.is_available.return_value = True
        manager = SessionManager(chat_history=mock_chat_history)

        sid = uuid4()
        manager.update_user_name(sid, "Trần Thị B")

        mock_chat_history.update_user_name.assert_called_once_with(sid, "Trần Thị B")

    def test_update_user_name_no_db(self, manager, mock_chat_history):
        """update_user_name is a no-op when DB is unavailable."""
        sid = uuid4()
        manager.update_user_name(sid, "Trần Thị B")

        mock_chat_history.update_user_name.assert_not_called()

    # ---- State persistence across sessions ----

    def test_state_persists_within_manager(self, manager):
        """State changes persist when accessed again from same manager."""
        ctx = manager.get_or_create_session(user_id="user-1")
        manager.update_state(ctx.session_id, phrase="test", used_name=True)

        ctx2 = manager.get_or_create_session(user_id="user-1")
        assert ctx2.state.total_responses == 1
        assert ctx2.state.name_usage_count == 1
        assert "test" in ctx2.state.recent_phrases
