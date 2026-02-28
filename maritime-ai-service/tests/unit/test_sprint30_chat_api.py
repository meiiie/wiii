"""
Tests for Sprint 30: Chat API endpoint coverage.

Covers:
- _classify_query_type: Vietnamese + English keyword detection
- _generate_suggested_questions: context-based suggestions
- _get_tool_description: tool usage info formatting
- get_chat_history: limit clamping, offset validation
- delete_chat_history: role-based access control
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


# =============================================================================
# _classify_query_type
# =============================================================================


class TestClassifyQueryType:
    """Test query type classification for LMS analytics."""

    def test_procedural_vietnamese(self):
        from app.api.v1.chat import _classify_query_type
        assert _classify_query_type("Làm thế nào để neo tàu?") == "procedural"

    def test_procedural_english(self):
        from app.api.v1.chat import _classify_query_type
        assert _classify_query_type("How to anchor a ship?") == "procedural"

    def test_procedural_cach(self):
        from app.api.v1.chat import _classify_query_type
        assert _classify_query_type("Cách tính khoảng cách?") == "procedural"

    def test_procedural_quy_trinh(self):
        from app.api.v1.chat import _classify_query_type
        assert _classify_query_type("Quy trình xử lý sự cố?") == "procedural"

    def test_factual_la_gi(self):
        from app.api.v1.chat import _classify_query_type
        assert _classify_query_type("COLREGs là gì?") == "factual"

    def test_factual_dieu(self):
        from app.api.v1.chat import _classify_query_type
        assert _classify_query_type("Điều 10 nói gì?") == "factual"

    def test_factual_english(self):
        from app.api.v1.chat import _classify_query_type
        assert _classify_query_type("What is SOLAS regulation?") == "factual"

    def test_factual_quy_dinh(self):
        from app.api.v1.chat import _classify_query_type
        assert _classify_query_type("Quy định về phòng cháy?") == "factual"

    def test_default_conceptual(self):
        from app.api.v1.chat import _classify_query_type
        assert _classify_query_type("Giải thích cho tôi về hàng hải") == "conceptual"

    def test_empty_string(self):
        from app.api.v1.chat import _classify_query_type
        assert _classify_query_type("") == "conceptual"

    def test_procedural_takes_priority(self):
        """Procedural checked before factual."""
        from app.api.v1.chat import _classify_query_type
        # "Cách" (procedural) + "quy định" (factual) → procedural wins
        assert _classify_query_type("Cách áp dụng quy định này?") == "procedural"


# =============================================================================
# _generate_suggested_questions
# =============================================================================


class TestGenerateSuggestedQuestions:
    """Test suggested follow-up question generation."""

    def test_returns_three_questions(self):
        from app.api.v1.chat import _generate_suggested_questions
        result = _generate_suggested_questions("Hello", "World")
        assert len(result) == 3

    def test_rule_context(self):
        from app.api.v1.chat import _generate_suggested_questions
        result = _generate_suggested_questions("test", "Quy tắc 10 nói rằng...")
        assert any("quy tắc" in q.lower() or "ngoại lệ" in q.lower() for q in result)

    def test_safety_context(self):
        from app.api.v1.chat import _generate_suggested_questions
        result = _generate_suggested_questions("test", "An toàn hàng hải yêu cầu thiết bị...")
        assert any("yêu cầu" in q.lower() or "tiêu chuẩn" in q.lower() for q in result)

    def test_learning_context(self):
        from app.api.v1.chat import _generate_suggested_questions
        result = _generate_suggested_questions("Tôi muốn học COLREGs", "Đây là nội dung bài học")
        assert any("tìm hiểu" in q.lower() or "thực hành" in q.lower() for q in result)

    def test_generic_fallback(self):
        from app.api.v1.chat import _generate_suggested_questions
        result = _generate_suggested_questions("random", "random response no keywords")
        assert len(result) == 3
        assert all(isinstance(q, str) for q in result)


# =============================================================================
# _get_tool_description
# =============================================================================


class TestGetToolDescription:
    """Test tool description formatting."""

    def test_knowledge_search_with_query(self):
        from app.api.v1.chat import _get_tool_description
        result = _get_tool_description({"name": "tool_knowledge_search", "args": {"query": "COLREGs"}})
        assert "COLREGs" in result

    def test_knowledge_search_no_query(self):
        from app.api.v1.chat import _get_tool_description
        result = _get_tool_description({"name": "tool_knowledge_search", "args": {}})
        assert result == "Tra cứu kiến thức"

    def test_maritime_search(self):
        from app.api.v1.chat import _get_tool_description
        result = _get_tool_description({"name": "tool_maritime_search", "args": {"query": "SOLAS"}})
        assert "SOLAS" in result

    def test_save_user_info(self):
        from app.api.v1.chat import _get_tool_description
        result = _get_tool_description({"name": "tool_save_user_info", "args": {"key": "name", "value": "Minh"}})
        assert "name" in result and "Minh" in result

    def test_save_user_info_no_key(self):
        from app.api.v1.chat import _get_tool_description
        result = _get_tool_description({"name": "tool_save_user_info", "args": {}})
        assert result == "Lưu thông tin người dùng"

    def test_get_user_info(self):
        from app.api.v1.chat import _get_tool_description
        result = _get_tool_description({"name": "tool_get_user_info", "args": {"key": "name"}})
        assert "name" in result

    def test_unknown_tool_with_result(self):
        from app.api.v1.chat import _get_tool_description
        result = _get_tool_description({"name": "custom_tool", "result": "some output"})
        assert result == "some output"

    def test_unknown_tool_no_result(self):
        from app.api.v1.chat import _get_tool_description
        result = _get_tool_description({"name": "custom_tool"})
        assert "custom_tool" in result


# =============================================================================
# get_chat_history — limit/offset clamping
# =============================================================================


class TestGetChatHistory:
    """Test chat history retrieval."""

    @pytest.mark.asyncio
    async def test_limit_clamped_to_100(self):
        from app.api.v1.chat import get_chat_history

        mock_repo = MagicMock()
        mock_repo.get_user_history.return_value = ([], 0)
        mock_auth = MagicMock()
        mock_auth.user_id = "user-1"  # Match path param for ownership check

        # Lazy import inside function body — patch at source module
        with patch("app.repositories.chat_history_repository.get_chat_history_repository", return_value=mock_repo):
            result = await get_chat_history("user-1", auth=mock_auth, limit=999, offset=0)

        # Limit should be clamped to 100
        mock_repo.get_user_history.assert_called_once_with("user-1", 100, 0)

    @pytest.mark.asyncio
    async def test_limit_below_1_set_to_20(self):
        from app.api.v1.chat import get_chat_history

        mock_repo = MagicMock()
        mock_repo.get_user_history.return_value = ([], 0)
        mock_auth = MagicMock()
        mock_auth.user_id = "user-1"  # Match path param for ownership check

        with patch("app.repositories.chat_history_repository.get_chat_history_repository", return_value=mock_repo):
            result = await get_chat_history("user-1", auth=mock_auth, limit=-5, offset=0)

        mock_repo.get_user_history.assert_called_once_with("user-1", 20, 0)

    @pytest.mark.asyncio
    async def test_negative_offset_set_to_zero(self):
        from app.api.v1.chat import get_chat_history

        mock_repo = MagicMock()
        mock_repo.get_user_history.return_value = ([], 0)
        mock_auth = MagicMock()
        mock_auth.user_id = "user-1"  # Match path param for ownership check

        with patch("app.repositories.chat_history_repository.get_chat_history_repository", return_value=mock_repo):
            result = await get_chat_history("user-1", auth=mock_auth, limit=10, offset=-1)

        mock_repo.get_user_history.assert_called_once_with("user-1", 10, 0)

    @pytest.mark.asyncio
    async def test_returns_messages(self):
        from app.api.v1.chat import get_chat_history
        from datetime import datetime, timezone

        mock_msg = MagicMock()
        mock_msg.role = "user"
        mock_msg.content = "Hello"
        mock_msg.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

        mock_repo = MagicMock()
        mock_repo.get_user_history.return_value = ([mock_msg], 1)
        mock_auth = MagicMock()
        mock_auth.user_id = "user-1"  # Match path param for ownership check

        with patch("app.repositories.chat_history_repository.get_chat_history_repository", return_value=mock_repo):
            result = await get_chat_history("user-1", auth=mock_auth, limit=20, offset=0)

        assert len(result.data) == 1
        assert result.pagination.total == 1

    @pytest.mark.asyncio
    async def test_auth_param_exists(self):
        import inspect
        from app.api.v1.chat import get_chat_history
        sig = inspect.signature(get_chat_history)
        assert "auth" in sig.parameters


# =============================================================================
# delete_chat_history — access control
# =============================================================================


class TestDeleteChatHistory:
    """Test chat history deletion with role-based access."""

    @pytest.mark.asyncio
    async def test_admin_can_delete_any(self):
        from app.api.v1.chat import delete_chat_history

        mock_auth = MagicMock()
        mock_auth.role = "admin"
        mock_auth.user_id = "admin-1"

        mock_request = MagicMock()
        mock_request.requesting_user_id = "admin-1"
        mock_request.role = "admin"

        mock_repo = MagicMock()
        mock_repo.delete_user_history.return_value = 5

        with patch("app.repositories.chat_history_repository.get_chat_history_repository", return_value=mock_repo):
            result = await delete_chat_history("user-2", mock_request, auth=mock_auth)

        assert result.status == "deleted"
        assert result.messages_deleted == 5

    @pytest.mark.asyncio
    async def test_student_cannot_delete_others(self):
        from app.api.v1.chat import delete_chat_history

        mock_auth = MagicMock()
        mock_auth.role = "student"
        mock_auth.user_id = "user-1"

        mock_request = MagicMock()
        mock_request.requesting_user_id = "user-1"
        mock_request.role = "student"

        result = await delete_chat_history("user-2", mock_request, auth=mock_auth)

        # Should return 403 JSONResponse
        assert result.status_code == 403

    @pytest.mark.asyncio
    async def test_student_can_delete_own(self):
        from app.api.v1.chat import delete_chat_history

        mock_auth = MagicMock()
        mock_auth.role = "student"
        mock_auth.user_id = "user-1"

        mock_request = MagicMock()
        mock_request.requesting_user_id = "user-1"
        mock_request.role = "student"

        mock_repo = MagicMock()
        mock_repo.delete_user_history.return_value = 3

        with patch("app.repositories.chat_history_repository.get_chat_history_repository", return_value=mock_repo):
            result = await delete_chat_history("user-1", mock_request, auth=mock_auth)

        assert result.status == "deleted"

    @pytest.mark.asyncio
    async def test_unknown_role_returns_403(self):
        from app.api.v1.chat import delete_chat_history

        mock_auth = MagicMock()
        mock_auth.role = "unknown"
        mock_auth.user_id = "user-1"

        mock_request = MagicMock()

        result = await delete_chat_history("user-1", mock_request, auth=mock_auth)
        assert result.status_code == 403

    @pytest.mark.asyncio
    async def test_auth_param_exists(self):
        import inspect
        from app.api.v1.chat import delete_chat_history
        sig = inspect.signature(delete_chat_history)
        assert "auth" in sig.parameters
