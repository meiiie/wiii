"""
Sprint 107: Tests for feedback API endpoint.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.schemas import FeedbackRating, FeedbackRequest, FeedbackResponse


# ========== Schema Tests ==========

class TestFeedbackSchemas:
    """Test Pydantic feedback schemas."""

    def test_feedback_request_valid_up(self):
        req = FeedbackRequest(
            message_id="msg-123",
            session_id="sess-456",
            rating=FeedbackRating.UP,
        )
        assert req.rating == FeedbackRating.UP
        assert req.comment is None

    def test_feedback_request_valid_down_with_comment(self):
        req = FeedbackRequest(
            message_id="msg-123",
            session_id="sess-456",
            rating=FeedbackRating.DOWN,
            comment="Answer was wrong",
        )
        assert req.rating == FeedbackRating.DOWN
        assert req.comment == "Answer was wrong"

    def test_feedback_request_invalid_rating(self):
        with pytest.raises(ValueError):
            FeedbackRequest(
                message_id="msg-123",
                session_id="sess-456",
                rating="invalid",  # type: ignore[arg-type]
            )

    def test_feedback_request_missing_message_id(self):
        with pytest.raises(ValueError):
            FeedbackRequest(
                session_id="sess-456",
                rating=FeedbackRating.UP,
            )  # type: ignore[call-arg]

    def test_feedback_request_missing_session_id(self):
        with pytest.raises(ValueError):
            FeedbackRequest(
                message_id="msg-123",
                rating=FeedbackRating.UP,
            )  # type: ignore[call-arg]

    def test_feedback_response_serialization(self):
        resp = FeedbackResponse(
            status="success",
            message_id="msg-123",
            rating=FeedbackRating.UP,
        )
        data = resp.model_dump()
        assert data["status"] == "success"
        assert data["message_id"] == "msg-123"
        assert data["rating"] == "up"

    def test_feedback_rating_enum_values(self):
        assert FeedbackRating.UP.value == "up"
        assert FeedbackRating.DOWN.value == "down"

    def test_feedback_comment_max_length(self):
        # Should accept up to 1000 chars
        req = FeedbackRequest(
            message_id="msg-123",
            session_id="sess-456",
            rating=FeedbackRating.UP,
            comment="x" * 1000,
        )
        assert len(req.comment) == 1000

    def test_feedback_comment_exceeds_max_length(self):
        with pytest.raises(ValueError):
            FeedbackRequest(
                message_id="msg-123",
                session_id="sess-456",
                rating=FeedbackRating.UP,
                comment="x" * 1001,
            )


# ========== Endpoint Tests ==========

class TestFeedbackEndpoint:
    """Test feedback endpoint logic."""

    @pytest.mark.asyncio
    async def test_submit_feedback_returns_success(self):
        """Test that submit_feedback returns correct response."""
        from app.api.v1.feedback import submit_feedback

        body = FeedbackRequest(
            message_id="msg-123",
            session_id="sess-456",
            rating=FeedbackRating.UP,
        )
        auth = MagicMock()
        auth.user_id = "user-001"
        request = MagicMock()

        # Mock asyncpg to avoid real DB
        mock_conn = AsyncMock()
        mock_connect = AsyncMock(return_value=mock_conn)

        with patch("app.api.v1.feedback.asyncpg", create=True) as mock_asyncpg_module:
            mock_asyncpg_module.connect = mock_connect
            # Also mock the _table_ensured to skip ensure step
            with patch("app.api.v1.feedback._table_ensured", True):
                result = await submit_feedback(request, body, auth)

        assert result.status == "success"
        assert result.message_id == "msg-123"
        assert result.rating == FeedbackRating.UP

    @pytest.mark.asyncio
    async def test_submit_feedback_down_rating(self):
        """Test down rating."""
        from app.api.v1.feedback import submit_feedback

        body = FeedbackRequest(
            message_id="msg-999",
            session_id="sess-111",
            rating=FeedbackRating.DOWN,
            comment="Not helpful",
        )
        auth = MagicMock()
        auth.user_id = "user-002"
        request = MagicMock()

        with patch("app.api.v1.feedback._table_ensured", True), \
             patch("app.api.v1.feedback.asyncpg", create=True) as mock_pg:
            mock_conn = AsyncMock()
            mock_pg.connect = AsyncMock(return_value=mock_conn)
            result = await submit_feedback(request, body, auth)

        assert result.rating == FeedbackRating.DOWN
        assert result.message_id == "msg-999"

    @pytest.mark.asyncio
    async def test_submit_feedback_db_failure_still_returns_success(self):
        """Feedback endpoint should not fail even if DB is unavailable."""
        from app.api.v1.feedback import submit_feedback

        body = FeedbackRequest(
            message_id="msg-123",
            session_id="sess-456",
            rating=FeedbackRating.UP,
        )
        auth = MagicMock()
        auth.user_id = "user-001"
        request = MagicMock()

        # Make DB connection fail
        with patch("app.api.v1.feedback._table_ensured", True), \
             patch("app.api.v1.feedback.asyncpg", create=True) as mock_pg:
            mock_pg.connect = AsyncMock(side_effect=Exception("DB down"))
            result = await submit_feedback(request, body, auth)

        # Should still return success (fire-and-forget)
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_ensure_table_called_when_not_ensured(self):
        """_ensure_table should execute CREATE TABLE IF NOT EXISTS."""
        import app.api.v1.feedback as feedback_mod

        # Reset the flag
        original = feedback_mod._table_ensured
        feedback_mod._table_ensured = False

        mock_conn = AsyncMock()
        mock_connect = AsyncMock(return_value=mock_conn)

        mock_settings = MagicMock()
        mock_settings.asyncpg_url = "postgresql://test"

        try:
            with patch.dict("sys.modules", {}):
                pass
            import asyncpg as _  # noqa: F401
            with patch("asyncpg.connect", mock_connect), \
                 patch("app.core.config.settings", mock_settings):
                await feedback_mod._ensure_table()

            # Table should now be ensured
            assert feedback_mod._table_ensured is True
            mock_conn.execute.assert_called_once()
            # SQL should contain CREATE TABLE
            sql_arg = mock_conn.execute.call_args[0][0]
            assert "CREATE TABLE IF NOT EXISTS message_feedback" in sql_arg
        finally:
            feedback_mod._table_ensured = original

    @pytest.mark.asyncio
    async def test_ensure_table_skipped_when_already_ensured(self):
        """_ensure_table should be a no-op when already ensured."""
        import app.api.v1.feedback as feedback_mod

        original = feedback_mod._table_ensured
        feedback_mod._table_ensured = True

        try:
            # Should return immediately without any DB call
            await feedback_mod._ensure_table()
            assert feedback_mod._table_ensured is True
        finally:
            feedback_mod._table_ensured = original

    @pytest.mark.asyncio
    async def test_upsert_sql_called_with_correct_params(self):
        """Verify the UPSERT SQL is called with correct parameters."""
        from app.api.v1.feedback import submit_feedback

        body = FeedbackRequest(
            message_id="msg-abc",
            session_id="sess-xyz",
            rating=FeedbackRating.DOWN,
            comment="Needs improvement",
        )
        auth = MagicMock()
        auth.user_id = "user-test"
        request = MagicMock()

        mock_conn = AsyncMock()
        mock_settings = MagicMock()
        mock_settings.asyncpg_url = "postgresql://test"

        with patch("app.api.v1.feedback._table_ensured", True), \
             patch("asyncpg.connect", AsyncMock(return_value=mock_conn)), \
             patch("app.core.config.settings", mock_settings):
            await submit_feedback(request, body, auth)

        # Verify execute was called with the upsert SQL and params
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args[0]
        assert "INSERT INTO message_feedback" in call_args[0]
        assert call_args[1] == "user-test"
        assert call_args[2] == "sess-xyz"
        assert call_args[3] == "msg-abc"
        assert call_args[4] == "down"
        assert call_args[5] == "Needs improvement"
