"""
Tests for UserPreferencesRepository and Preference Tools.

Sprint 17: Virtual Agent-per-User Architecture.
Tests repository CRUD, validation, format_for_prompt, and LangChain tool wrappers.
"""

import pytest
from unittest.mock import patch, MagicMock

from app.repositories.user_preferences_repository import (
    UserPreferencesRepository,
    DEFAULT_PREFERENCES,
    VALID_LEARNING_STYLES,
    VALID_DIFFICULTIES,
    VALID_PRONOUN_STYLES,
)
from app.engine.tools.preference_tools import (
    tool_update_user_preference,
    tool_get_user_preferences,
    get_preference_tools,
    set_preference_user,
)


# ============================================================================
# Helpers
# ============================================================================

def _make_repo_with_mock_session(fetchone_return=None):
    """Create a repository with mocked database session.

    Returns (repo, mock_session) so tests can inspect SQL calls.
    """
    mock_session = MagicMock()
    mock_session.execute.return_value.fetchone.return_value = fetchone_return
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_session_factory.return_value.__exit__ = MagicMock(return_value=False)

    with patch("app.core.database.get_shared_engine", return_value=MagicMock()), \
         patch("app.core.database.get_shared_session_factory", return_value=mock_session_factory):
        repo = UserPreferencesRepository()
        repo._ensure_initialized()

    return repo, mock_session


# ============================================================================
# UserPreferencesRepository Tests
# ============================================================================


class TestGetPreferences:
    """Test UserPreferencesRepository.get_preferences."""

    def test_returns_defaults_when_not_found(self):
        """When user has no row, return defaults with user_id."""
        repo, _ = _make_repo_with_mock_session(fetchone_return=None)

        result = repo.get_preferences("user-123")

        assert result["user_id"] == "user-123"
        assert result["learning_style"] == DEFAULT_PREFERENCES["learning_style"]
        assert result["difficulty"] == DEFAULT_PREFERENCES["difficulty"]
        assert result["pronoun_style"] == DEFAULT_PREFERENCES["pronoun_style"]
        assert result["language"] == DEFAULT_PREFERENCES["language"]
        assert result["preferred_domain"] == DEFAULT_PREFERENCES["preferred_domain"]

    def test_returns_stored_values_when_found(self):
        """When user row exists, return stored values."""
        row = (
            "user-456",    # user_id
            "Minh",        # display_name
            "traffic_law", # preferred_domain
            "en",          # language
            "formal",      # pronoun_style
            "quiz",        # learning_style
            "advanced",    # difficulty
            "UTC",         # timezone
            {"theme": "dark"},  # extra_prefs
        )
        repo, _ = _make_repo_with_mock_session(fetchone_return=row)

        result = repo.get_preferences("user-456")

        assert result["user_id"] == "user-456"
        assert result["display_name"] == "Minh"
        assert result["preferred_domain"] == "traffic_law"
        assert result["language"] == "en"
        assert result["pronoun_style"] == "formal"
        assert result["learning_style"] == "quiz"
        assert result["difficulty"] == "advanced"
        assert result["timezone"] == "UTC"
        assert result["extra_prefs"] == {"theme": "dark"}

    def test_returns_defaults_when_session_factory_is_none(self):
        """When DB init fails, return defaults gracefully."""
        repo = UserPreferencesRepository()
        # _session_factory stays None (not initialized)

        result = repo.get_preferences("user-999")

        assert result["user_id"] == "user-999"
        assert result["learning_style"] == "mixed"


class TestUpdatePreference:
    """Test UserPreferencesRepository.update_preference."""

    def test_update_known_column_success(self):
        """Valid known column updates return True and commit."""
        # Simulate existing row for upsert check
        mock_session = MagicMock()
        # First execute (exists check) returns a row; second execute is the UPDATE
        mock_session.execute.return_value.fetchone.return_value = (1,)
        mock_session_factory = MagicMock()
        mock_session_factory.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_factory.return_value.__exit__ = MagicMock(return_value=False)

        with patch("app.core.database.get_shared_engine", return_value=MagicMock()), \
             patch("app.core.database.get_shared_session_factory", return_value=mock_session_factory):
            repo = UserPreferencesRepository()
            repo._ensure_initialized()

        result = repo.update_preference("user-1", "learning_style", "quiz")

        assert result is True
        mock_session.commit.assert_called_once()

    def test_update_invalid_learning_style(self):
        """Invalid learning_style value returns False."""
        repo, mock_session = _make_repo_with_mock_session(fetchone_return=None)

        result = repo.update_preference("user-1", "learning_style", "invalid_style")

        assert result is False
        mock_session.commit.assert_not_called()

    def test_update_invalid_difficulty(self):
        """Invalid difficulty value returns False."""
        repo, mock_session = _make_repo_with_mock_session(fetchone_return=None)

        result = repo.update_preference("user-1", "difficulty", "impossible")

        assert result is False

    def test_update_invalid_pronoun_style(self):
        """Invalid pronoun_style value returns False."""
        repo, mock_session = _make_repo_with_mock_session(fetchone_return=None)

        result = repo.update_preference("user-1", "pronoun_style", "slang")

        assert result is False

    def test_update_extra_prefs_field(self):
        """Unknown keys go into extra_prefs JSONB."""
        mock_session = MagicMock()
        mock_session.execute.return_value.fetchone.return_value = (1,)
        mock_session_factory = MagicMock()
        mock_session_factory.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_factory.return_value.__exit__ = MagicMock(return_value=False)

        with patch("app.core.database.get_shared_engine", return_value=MagicMock()), \
             patch("app.core.database.get_shared_session_factory", return_value=mock_session_factory):
            repo = UserPreferencesRepository()
            repo._ensure_initialized()

        result = repo.update_preference("user-1", "custom_key", "custom_value")

        assert result is True
        mock_session.commit.assert_called_once()

    @patch("app.core.database.get_shared_session_factory", return_value=None)
    @patch("app.core.database.get_shared_engine", return_value=None)
    def test_update_returns_false_when_no_session(self, mock_engine, mock_session):
        """When DB not initialized, update returns False."""
        repo = UserPreferencesRepository()

        result = repo.update_preference("user-1", "learning_style", "quiz")

        assert result is False


class TestSetPreferences:
    """Test UserPreferencesRepository.set_preferences (batch update)."""

    def test_set_multiple_preferences(self):
        """Batch update delegates to update_preference for each key."""
        repo = UserPreferencesRepository()
        repo.update_preference = MagicMock(return_value=True)

        result = repo.set_preferences("user-1", {
            "learning_style": "quiz",
            "difficulty": "advanced",
        })

        assert result is True
        assert repo.update_preference.call_count == 2

    def test_set_preferences_skips_user_id_key(self):
        """The user_id key in the dict should be skipped."""
        repo = UserPreferencesRepository()
        repo.update_preference = MagicMock(return_value=True)

        repo.set_preferences("user-1", {
            "user_id": "user-1",
            "learning_style": "visual",
        })

        # Only learning_style should be updated, not user_id
        assert repo.update_preference.call_count == 1
        repo.update_preference.assert_called_once_with("user-1", "learning_style", "visual")

    def test_set_preferences_returns_false_on_any_failure(self):
        """If any single update fails, set_preferences returns False."""
        repo = UserPreferencesRepository()
        repo.update_preference = MagicMock(side_effect=[True, False])

        result = repo.set_preferences("user-1", {
            "learning_style": "quiz",
            "difficulty": "impossible",
        })

        assert result is False


class TestFormatForPrompt:
    """Test UserPreferencesRepository.format_for_prompt."""

    def test_empty_when_all_defaults(self):
        """No prompt text when all preferences are defaults."""
        repo = UserPreferencesRepository()
        repo.get_preferences = MagicMock(return_value={
            **DEFAULT_PREFERENCES,
            "user_id": "user-1",
            "display_name": None,
        })

        result = repo.format_for_prompt("user-1")

        assert result == ""

    def test_includes_non_default_values(self):
        """Non-default values are included in the prompt string."""
        repo = UserPreferencesRepository()
        repo.get_preferences = MagicMock(return_value={
            **DEFAULT_PREFERENCES,
            "user_id": "user-1",
            "display_name": "Minh",
            "learning_style": "quiz",
            "difficulty": "beginner",
            "pronoun_style": "formal",
        })

        result = repo.format_for_prompt("user-1")

        assert "Minh" in result
        assert "quiz" in result or "thích làm quiz" in result
        assert "beginner" in result
        assert "formal" in result


class TestValidationConstants:
    """Test that validation sets have expected values."""

    def test_learning_styles(self):
        assert "quiz" in VALID_LEARNING_STYLES
        assert "visual" in VALID_LEARNING_STYLES
        assert "reading" in VALID_LEARNING_STYLES
        assert "mixed" in VALID_LEARNING_STYLES
        assert "interactive" in VALID_LEARNING_STYLES

    def test_difficulties(self):
        assert "beginner" in VALID_DIFFICULTIES
        assert "intermediate" in VALID_DIFFICULTIES
        assert "advanced" in VALID_DIFFICULTIES
        assert "expert" in VALID_DIFFICULTIES

    def test_pronoun_styles(self):
        assert "auto" in VALID_PRONOUN_STYLES
        assert "formal" in VALID_PRONOUN_STYLES
        assert "casual" in VALID_PRONOUN_STYLES


# ============================================================================
# Preference Tools Tests
# ============================================================================


class TestToolUpdateUserPreference:
    """Test tool_update_user_preference LangChain tool."""

    def test_success(self):
        """Successful update returns Vietnamese confirmation."""
        mock_repo = MagicMock()
        mock_repo.update_preference.return_value = True

        set_preference_user("user-42")
        with patch(
            "app.repositories.user_preferences_repository.get_user_preferences_repository",
            return_value=mock_repo,
        ):
            result = tool_update_user_preference.invoke({
                "key": "learning_style",
                "value": "quiz",
            })

        assert "learning_style" in result
        assert "quiz" in result
        mock_repo.update_preference.assert_called_once_with("user-42", "learning_style", "quiz")

    def test_no_user_id(self):
        """Without user context, returns error message."""
        import app.engine.tools.preference_tools as pt
        # Sprint 26: Reset contextvar to None (no user set)
        pt._preference_user_id.set(None)

        try:
            result = tool_update_user_preference.invoke({
                "key": "learning_style",
                "value": "quiz",
            })
            assert "user_id" in result or "Không" in result
        finally:
            pt._preference_user_id.set(None)


class TestToolGetUserPreferences:
    """Test tool_get_user_preferences LangChain tool."""

    def test_success(self):
        """Returns formatted preference list."""
        mock_repo = MagicMock()
        mock_repo.get_preferences.return_value = {
            "user_id": "user-42",
            "display_name": "Minh",
            "preferred_domain": "maritime",
            "language": "vi",
            "pronoun_style": "formal",
            "learning_style": "quiz",
            "difficulty": "advanced",
            "timezone": "Asia/Ho_Chi_Minh",
            "extra_prefs": {"theme": "dark"},
        }

        set_preference_user("user-42")
        with patch(
            "app.repositories.user_preferences_repository.get_user_preferences_repository",
            return_value=mock_repo,
        ):
            result = tool_get_user_preferences.invoke({})

        assert "learning_style" in result
        assert "quiz" in result
        assert "theme" in result
        assert "dark" in result

    def test_no_user_id(self):
        """Without user context, returns error message."""
        import app.engine.tools.preference_tools as pt
        # Sprint 26: Reset contextvar to None (no user set)
        pt._preference_user_id.set(None)

        try:
            result = tool_get_user_preferences.invoke({})
            assert "user_id" in result or "Không" in result
        finally:
            pt._preference_user_id.set(None)


class TestPreferenceToolRegistration:
    """Test get_preference_tools registration helper."""

    def test_returns_two_tools(self):
        tools = get_preference_tools()
        assert len(tools) == 2

    def test_tool_names(self):
        tools = get_preference_tools()
        names = [t.name for t in tools]
        assert "tool_update_user_preference" in names
        assert "tool_get_user_preferences" in names
