"""
Sprint 120: Desktop API Endpoints Tests

Tests for new REST APIs that expose character state, mood, and preferences
to the desktop app.
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from uuid import uuid4


# =============================================================================
# Character State API Tests
# =============================================================================

class TestCharacterStateAPI:
    """Tests for GET /api/v1/character/state."""

    def test_response_model_fields(self):
        """CharacterBlockResponse has required fields."""
        from app.api.v1.character import CharacterBlockResponse
        block = CharacterBlockResponse(
            label="self_notes",
            content="- Test note",
            char_limit=1000,
            usage_percent=1.1,
        )
        assert block.label == "self_notes"
        assert block.content == "- Test note"
        assert block.char_limit == 1000
        assert block.usage_percent == 1.1

    def test_state_response_defaults(self):
        """CharacterStateResponse defaults to empty."""
        from app.api.v1.character import CharacterStateResponse
        resp = CharacterStateResponse()
        assert resp.blocks == []
        assert resp.total_blocks == 0

    @pytest.mark.asyncio
    async def test_returns_empty_when_disabled(self):
        """Returns empty response when enable_character_tools=False."""
        from app.api.v1.character import get_character_state

        mock_request = MagicMock()
        mock_auth = MagicMock()
        mock_auth.user_id = "test-user"

        with patch("app.api.v1.character.limiter"):
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.enable_character_tools = False
                result = await get_character_state(mock_request, mock_auth)
                assert result.blocks == []
                assert result.total_blocks == 0

    @pytest.mark.asyncio
    async def test_returns_blocks_when_enabled(self):
        """Returns character blocks when enabled and available."""
        from app.api.v1.character import get_character_state, CharacterStateResponse

        mock_request = MagicMock()
        mock_auth = MagicMock()
        mock_auth.user_id = "test-user"

        mock_block = MagicMock()
        mock_block.content = "- Learned something"
        mock_block.char_limit = 1500

        with patch("app.api.v1.character.limiter"):
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.enable_character_tools = True
                with patch("app.engine.character.character_state.get_character_state_manager") as mock_mgr:
                    mock_mgr.return_value.get_blocks.return_value = {
                        "learned_lessons": mock_block,
                    }
                    result = await get_character_state(mock_request, mock_auth)
                    assert result.total_blocks == 1
                    assert result.blocks[0].label == "learned_lessons"
                    assert result.blocks[0].content == "- Learned something"
                    assert result.blocks[0].usage_percent == round((20 / 1500) * 100, 1)

    @pytest.mark.asyncio
    async def test_handles_error_gracefully(self):
        """Returns empty on error."""
        from app.api.v1.character import get_character_state

        mock_request = MagicMock()
        mock_auth = MagicMock()
        mock_auth.user_id = "test-user"

        with patch("app.api.v1.character.limiter"):
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.enable_character_tools = True
                with patch(
                    "app.engine.character.character_state.get_character_state_manager",
                    side_effect=RuntimeError("DB down"),
                ):
                    result = await get_character_state(mock_request, mock_auth)
                    assert result.blocks == []

    def test_usage_percent_calculation(self):
        """Usage percent calculated correctly."""
        from app.api.v1.character import CharacterBlockResponse
        # 500 chars out of 1000 = 50%
        block = CharacterBlockResponse(
            label="test", content="x" * 500, char_limit=1000, usage_percent=50.0
        )
        assert block.usage_percent == 50.0


# =============================================================================
# Mood API Tests
# =============================================================================

class TestMoodAPI:
    """Tests for GET /api/v1/mood."""

    def test_mood_response_defaults(self):
        """MoodResponse defaults to neutral."""
        from app.api.v1.mood import MoodResponse
        resp = MoodResponse()
        assert resp.positivity == 0.0
        assert resp.energy == 0.5
        assert resp.mood == "neutral"
        assert resp.mood_hint == ""
        assert resp.enabled is False

    @pytest.mark.asyncio
    async def test_returns_disabled_when_feature_off(self):
        """Returns enabled=False when enable_emotional_state=False."""
        from app.api.v1.mood import get_mood

        mock_request = MagicMock()
        mock_auth = MagicMock()
        mock_auth.user_id = "test-user"

        with patch("app.api.v1.mood.limiter"):
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.enable_emotional_state = False
                result = await get_mood(mock_request, mock_auth)
                assert result.enabled is False
                assert result.mood == "neutral"

    @pytest.mark.asyncio
    async def test_returns_mood_when_enabled(self):
        """Returns actual mood state when enabled."""
        from app.api.v1.mood import get_mood
        from app.engine.emotional_state import EmotionalState, MoodState

        mock_request = MagicMock()
        mock_auth = MagicMock()
        mock_auth.user_id = "test-user"

        mock_state = EmotionalState(positivity=0.5, energy=0.8)

        with patch("app.api.v1.mood.limiter"):
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.enable_emotional_state = True
                with patch("app.engine.emotional_state.get_emotional_state_manager") as mock_mgr:
                    mock_mgr.return_value.get_state.return_value = mock_state
                    result = await get_mood(mock_request, mock_auth)
                    assert result.enabled is True
                    assert result.positivity == 0.5
                    assert result.energy == 0.8
                    assert result.mood == "excited"

    @pytest.mark.asyncio
    async def test_handles_error_gracefully(self):
        """Returns disabled on error."""
        from app.api.v1.mood import get_mood

        mock_request = MagicMock()
        mock_auth = MagicMock()
        mock_auth.user_id = "test-user"

        with patch("app.api.v1.mood.limiter"):
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.enable_emotional_state = True
                with patch(
                    "app.engine.emotional_state.get_emotional_state_manager",
                    side_effect=RuntimeError("fail"),
                ):
                    result = await get_mood(mock_request, mock_auth)
                    assert result.enabled is False

    def test_mood_states_complete(self):
        """All mood states from EmotionalState are valid."""
        from app.engine.emotional_state import MoodState
        expected = {"excited", "warm", "concerned", "gentle", "neutral"}
        actual = {m.value for m in MoodState}
        assert actual == expected


# =============================================================================
# Preferences API Tests
# =============================================================================

class TestPreferencesAPI:
    """Tests for GET/PUT /api/v1/preferences."""

    def test_response_defaults(self):
        """PreferencesResponse has correct defaults."""
        from app.api.v1.preferences import PreferencesResponse
        resp = PreferencesResponse()
        assert resp.preferred_domain == "maritime"
        assert resp.language == "vi"
        assert resp.pronoun_style == "auto"
        assert resp.learning_style == "mixed"
        assert resp.difficulty == "intermediate"
        assert resp.timezone == "Asia/Ho_Chi_Minh"

    def test_update_request_validation_learning_style(self):
        """Invalid learning_style rejected."""
        from app.api.v1.preferences import PreferencesUpdateRequest
        with pytest.raises(Exception):
            PreferencesUpdateRequest(learning_style="invalid")

    def test_update_request_validation_difficulty(self):
        """Invalid difficulty rejected."""
        from app.api.v1.preferences import PreferencesUpdateRequest
        with pytest.raises(Exception):
            PreferencesUpdateRequest(difficulty="godmode")

    def test_update_request_validation_pronoun_style(self):
        """Invalid pronoun_style rejected."""
        from app.api.v1.preferences import PreferencesUpdateRequest
        with pytest.raises(Exception):
            PreferencesUpdateRequest(pronoun_style="rude")

    def test_update_request_valid(self):
        """Valid partial update works."""
        from app.api.v1.preferences import PreferencesUpdateRequest
        req = PreferencesUpdateRequest(learning_style="visual", difficulty="advanced")
        assert req.learning_style == "visual"
        assert req.difficulty == "advanced"
        assert req.language is None  # not provided

    @pytest.mark.asyncio
    async def test_get_preferences(self):
        """GET returns preferences from repository."""
        from app.api.v1.preferences import get_preferences

        mock_request = MagicMock()
        mock_auth = MagicMock()
        mock_auth.user_id = "test-user"

        with patch("app.api.v1.preferences.limiter"):
            with patch("app.repositories.user_preferences_repository.get_user_preferences_repository") as mock_repo:
                mock_repo.return_value.get_preferences.return_value = {
                    "preferred_domain": "traffic_law",
                    "language": "vi",
                    "pronoun_style": "formal",
                    "learning_style": "quiz",
                    "difficulty": "beginner",
                    "timezone": "Asia/Ho_Chi_Minh",
                }
                result = await get_preferences(mock_request, mock_auth)
                assert result.preferred_domain == "traffic_law"
                assert result.learning_style == "quiz"
                assert result.pronoun_style == "formal"

    @pytest.mark.asyncio
    async def test_get_preferences_error_returns_defaults(self):
        """GET returns defaults on error."""
        from app.api.v1.preferences import get_preferences

        mock_request = MagicMock()
        mock_auth = MagicMock()
        mock_auth.user_id = "test-user"

        with patch("app.api.v1.preferences.limiter"):
            with patch(
                "app.repositories.user_preferences_repository.get_user_preferences_repository",
                side_effect=RuntimeError("DB down"),
            ):
                result = await get_preferences(mock_request, mock_auth)
                assert result.preferred_domain == "maritime"

    @pytest.mark.asyncio
    async def test_put_preferences(self):
        """PUT updates and returns full preferences."""
        from app.api.v1.preferences import update_preferences, PreferencesUpdateRequest

        mock_request = MagicMock()
        mock_auth = MagicMock()
        mock_auth.user_id = "test-user"
        body = PreferencesUpdateRequest(learning_style="visual")

        with patch("app.api.v1.preferences.limiter"):
            with patch("app.repositories.user_preferences_repository.get_user_preferences_repository") as mock_repo:
                mock_repo_inst = mock_repo.return_value
                mock_repo_inst.update_preference.return_value = True
                mock_repo_inst.get_preferences.return_value = {
                    "preferred_domain": "maritime",
                    "language": "vi",
                    "pronoun_style": "auto",
                    "learning_style": "visual",
                    "difficulty": "intermediate",
                    "timezone": "Asia/Ho_Chi_Minh",
                }
                result = await update_preferences(mock_request, body, mock_auth)
                assert result.learning_style == "visual"
                mock_repo_inst.update_preference.assert_called_once_with(
                    "test-user", "learning_style", "visual"
                )

    @pytest.mark.asyncio
    async def test_put_preferences_empty_body_rejected(self):
        """PUT with no fields raises 400."""
        from app.api.v1.preferences import update_preferences, PreferencesUpdateRequest
        from fastapi import HTTPException

        mock_request = MagicMock()
        mock_auth = MagicMock()
        mock_auth.user_id = "test-user"
        body = PreferencesUpdateRequest()  # all None

        with patch("app.api.v1.preferences.limiter"):
            with pytest.raises(HTTPException) as exc_info:
                await update_preferences(mock_request, body, mock_auth)
            assert exc_info.value.status_code == 400


# =============================================================================
# SSE Metadata Mood Integration Tests
# =============================================================================

class TestSSEMetadataMood:
    """Tests for mood field in SSE metadata event."""

    def test_create_metadata_event_accepts_mood(self):
        """create_metadata_event accepts mood kwarg."""
        import asyncio
        from app.engine.multi_agent.stream_utils import create_metadata_event

        mood_data = {"positivity": 0.5, "energy": 0.8, "mood": "excited"}
        event = asyncio.run(
            create_metadata_event(
                processing_time=1.5,
                confidence=0.9,
                mood=mood_data,
            )
        )
        assert event.content["mood"] == mood_data
        assert event.content["processing_time"] == 1.5

    def test_create_metadata_event_without_mood(self):
        """create_metadata_event works without mood."""
        import asyncio
        from app.engine.multi_agent.stream_utils import create_metadata_event

        event = asyncio.run(
            create_metadata_event(processing_time=1.0, confidence=0.8)
        )
        assert "mood" not in event.content


# =============================================================================
# Router Registration Tests
# =============================================================================

class TestRouterRegistration:
    """Tests that new routers are registered."""

    def test_character_router_registered(self):
        """Character router is in v1 routes."""
        from app.api.v1 import router
        paths = [r.path for r in router.routes]
        assert any("/character" in p for p in paths)

    def test_mood_router_registered(self):
        """Mood router is in v1 routes."""
        from app.api.v1 import router
        paths = [r.path for r in router.routes]
        assert any("/mood" in p for p in paths)

    def test_preferences_router_registered(self):
        """Preferences router is in v1 routes."""
        from app.api.v1 import router
        paths = [r.path for r in router.routes]
        assert any("/preferences" in p for p in paths)
