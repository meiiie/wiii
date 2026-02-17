"""
Tests for Sprint 26: Memory API user self-service DELETE and clear all.

Covers:
- DELETE /memories/{user_id}/{memory_id} — user can delete own memory
- DELETE /memories/{user_id}/{memory_id} — non-owner gets 403
- DELETE /memories/{user_id} — user can clear own memories
- DELETE /memories/{user_id} — non-owner gets 403
- Admin can delete/clear any user's memories
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

import httpx


def _make_request():
    """Create a real starlette Request for rate-limited endpoints."""
    from starlette.requests import Request
    scope = {
        "type": "http", "method": "DELETE", "path": "/api/v1/memories/user-1",
        "headers": [], "query_string": b"", "root_path": "",
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


def _make_auth(user_id: str = "user-1", role: str = "student"):
    """Create a mock auth object."""
    auth = MagicMock()
    auth.user_id = user_id
    auth.role = role
    return auth


class TestDeleteUserMemory:
    """Test DELETE /memories/{user_id}/{memory_id} endpoint."""

    @pytest.mark.asyncio
    async def test_user_can_delete_own_memory(self):
        """Users should be able to delete their own memories."""
        from app.api.v1.memories import delete_user_memory

        mock_repo = MagicMock()
        mock_repo.delete_memory.return_value = True

        auth = _make_auth(user_id="user-1", role="student")

        with patch(
            "app.api.v1.memories.SemanticMemoryRepository",
            return_value=mock_repo,
        ):
            result = await delete_user_memory(
                request=_make_request(),
                user_id="user-1",
                memory_id="mem-abc",
                auth=auth,
            )

        assert result.success is True
        mock_repo.delete_memory.assert_called_once_with("user-1", "mem-abc")

    @pytest.mark.asyncio
    async def test_non_owner_gets_403(self):
        """Non-owner non-admin should get 403."""
        from app.api.v1.memories import delete_user_memory
        from fastapi import HTTPException

        auth = _make_auth(user_id="other-user", role="student")

        with pytest.raises(HTTPException) as exc_info:
            await delete_user_memory(
                request=_make_request(),
                user_id="user-1",
                memory_id="mem-abc",
                auth=auth,
            )

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_can_delete_any_user(self):
        """Admin can delete any user's memory."""
        from app.api.v1.memories import delete_user_memory

        mock_repo = MagicMock()
        mock_repo.delete_memory.return_value = True

        auth = _make_auth(user_id="admin-1", role="admin")

        with patch(
            "app.api.v1.memories.SemanticMemoryRepository",
            return_value=mock_repo,
        ):
            result = await delete_user_memory(
                request=_make_request(),
                user_id="user-1",
                memory_id="mem-abc",
                auth=auth,
            )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_memory_not_found(self):
        """Should return 404 when memory doesn't exist."""
        from app.api.v1.memories import delete_user_memory
        from fastapi import HTTPException

        mock_repo = MagicMock()
        mock_repo.delete_memory.return_value = False

        auth = _make_auth(user_id="user-1", role="student")

        with patch(
            "app.api.v1.memories.SemanticMemoryRepository",
            return_value=mock_repo,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await delete_user_memory(
                    request=_make_request(),
                    user_id="user-1",
                    memory_id="nonexistent",
                    auth=auth,
                )

            assert exc_info.value.status_code == 404


class TestClearUserMemories:
    """Test DELETE /memories/{user_id} endpoint (Sprint 26: new)."""

    @pytest.mark.asyncio
    async def test_user_can_clear_own_memories(self):
        """Users should be able to clear all their own memories."""
        from app.api.v1.memories import clear_user_memories

        mock_repo = MagicMock()
        mock_repo.delete_all_user_memories.return_value = 10

        auth = _make_auth(user_id="user-1", role="student")

        with patch(
            "app.api.v1.memories.SemanticMemoryRepository",
            return_value=mock_repo,
        ):
            result = await clear_user_memories(request=_make_request(), user_id="user-1", auth=auth)

        assert result.success is True
        assert result.deleted_count == 10
        mock_repo.delete_all_user_memories.assert_called_once_with("user-1")

    @pytest.mark.asyncio
    async def test_non_owner_gets_403(self):
        """Non-owner non-admin should get 403."""
        from app.api.v1.memories import clear_user_memories
        from fastapi import HTTPException

        auth = _make_auth(user_id="other-user", role="student")

        with pytest.raises(HTTPException) as exc_info:
            await clear_user_memories(request=_make_request(), user_id="user-1", auth=auth)

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_can_clear_any_user(self):
        """Admin can clear any user's memories."""
        from app.api.v1.memories import clear_user_memories

        mock_repo = MagicMock()
        mock_repo.delete_all_user_memories.return_value = 5

        auth = _make_auth(user_id="admin-1", role="admin")

        with patch(
            "app.api.v1.memories.SemanticMemoryRepository",
            return_value=mock_repo,
        ):
            result = await clear_user_memories(request=_make_request(), user_id="user-1", auth=auth)

        assert result.success is True
        assert result.deleted_count == 5

    @pytest.mark.asyncio
    async def test_clear_returns_zero_when_no_memories(self):
        """Should succeed even with zero memories to clear."""
        from app.api.v1.memories import clear_user_memories

        mock_repo = MagicMock()
        mock_repo.delete_all_user_memories.return_value = 0

        auth = _make_auth(user_id="user-1", role="student")

        with patch(
            "app.api.v1.memories.SemanticMemoryRepository",
            return_value=mock_repo,
        ):
            result = await clear_user_memories(request=_make_request(), user_id="user-1", auth=auth)

        assert result.success is True
        assert result.deleted_count == 0
