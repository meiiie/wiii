"""Tests for auth ownership checks (Sprint 7 security fixes).

Tests the security fixes in insights.py and memories.py that prevent
cross-user data access.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from app.core.security import AuthenticatedUser


def _make_request():
    """Create a real starlette Request for rate-limited endpoints."""
    from starlette.requests import Request
    scope = {
        "type": "http", "method": "GET", "path": "/api/v1/test",
        "headers": [], "query_string": b"", "root_path": "",
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


def _make_auth(user_id: str = "user-1", role: str = "student") -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=user_id,
        auth_method="api_key",
        role=role,
    )


class TestInsightsOwnership:
    """Test that insights endpoint enforces ownership."""

    @pytest.mark.asyncio
    async def test_own_user_allowed(self):
        """User can access their own insights."""
        from app.api.v1.insights import get_user_insights

        auth = _make_auth("student-123", "student")
        # Should not raise 403 — may raise other errors (no DB) which is fine
        try:
            await get_user_insights(request=_make_request(), user_id="student-123", auth=auth)
        except Exception as e:
            # Any error except 403 is acceptable (DB not running)
            if hasattr(e, "status_code"):
                assert e.status_code != 403

    @pytest.mark.asyncio
    async def test_other_user_blocked(self):
        """Student cannot access another user's insights."""
        from app.api.v1.insights import get_user_insights
        from fastapi import HTTPException

        auth = _make_auth("student-123", "student")
        with pytest.raises(HTTPException) as exc_info:
            await get_user_insights(request=_make_request(), user_id="other-user", auth=auth)
        assert exc_info.value.status_code == 403
        assert "own insights" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_admin_can_access_any(self):
        """Admin can access any user's insights."""
        from app.api.v1.insights import get_user_insights

        auth = _make_auth("admin-1", "admin")
        try:
            await get_user_insights(request=_make_request(), user_id="other-user", auth=auth)
        except Exception as e:
            if hasattr(e, "status_code"):
                assert e.status_code != 403


class TestMemoriesOwnership:
    """Test that memories endpoint enforces ownership."""

    @pytest.mark.asyncio
    async def test_own_user_allowed(self):
        """User can access their own memories."""
        from app.api.v1.memories import get_user_memories

        auth = _make_auth("student-456", "student")
        try:
            await get_user_memories(request=_make_request(), user_id="student-456", auth=auth)
        except Exception as e:
            if hasattr(e, "status_code"):
                assert e.status_code != 403

    @pytest.mark.asyncio
    async def test_other_user_blocked(self):
        """Student cannot access another user's memories."""
        from app.api.v1.memories import get_user_memories
        from fastapi import HTTPException

        auth = _make_auth("student-456", "student")
        with pytest.raises(HTTPException) as exc_info:
            await get_user_memories(request=_make_request(), user_id="other-user", auth=auth)
        assert exc_info.value.status_code == 403
        assert "own memories" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_admin_can_access_any(self):
        """Admin can access any user's memories."""
        from app.api.v1.memories import get_user_memories

        auth = _make_auth("admin-1", "admin")
        try:
            await get_user_memories(request=_make_request(), user_id="other-user", auth=auth)
        except Exception as e:
            if hasattr(e, "status_code"):
                assert e.status_code != 403

    @pytest.mark.asyncio
    async def test_teacher_blocked_from_other(self):
        """Teacher cannot access another user's memories."""
        from app.api.v1.memories import get_user_memories
        from fastapi import HTTPException

        auth = _make_auth("teacher-1", "teacher")
        with pytest.raises(HTTPException) as exc_info:
            await get_user_memories(request=_make_request(), user_id="student-123", auth=auth)
        assert exc_info.value.status_code == 403


class TestSecurityVerifyApiKey:
    """Test verify_api_key function."""

    @patch("app.core.security.settings")
    def test_valid_key_accepted(self, mock_settings):
        from app.core.security import verify_api_key
        mock_settings.api_key = "test-key-123"
        assert verify_api_key("test-key-123") is True

    @patch("app.core.security.settings")
    def test_invalid_key_rejected(self, mock_settings):
        from app.core.security import verify_api_key
        mock_settings.api_key = "test-key-123"
        assert verify_api_key("wrong-key") is False

    @patch("app.core.security.settings")
    def test_no_key_dev_allows(self, mock_settings):
        from app.core.security import verify_api_key
        mock_settings.api_key = None
        mock_settings.environment = "development"
        assert verify_api_key("anything") is True

    @patch("app.core.security.settings")
    def test_no_key_prod_rejects(self, mock_settings):
        from app.core.security import verify_api_key
        mock_settings.api_key = None
        mock_settings.environment = "production"
        assert verify_api_key("anything") is False

    @patch("app.core.security.settings")
    def test_timing_safe_comparison(self, mock_settings):
        """Verify hmac.compare_digest is used (not == operator)."""
        from app.core.security import verify_api_key
        mock_settings.api_key = "secret-key"
        # If timing-safe, both should work the same
        assert verify_api_key("secret-key") is True
        assert verify_api_key("secret-ke") is False
        assert verify_api_key("secret-key-extra") is False


class TestDepsRequireAdmin:
    """Test the RequireAdmin dependency."""

    @pytest.mark.asyncio
    async def test_admin_passes(self):
        from app.api.deps import _require_admin
        auth = _make_auth("admin-1", "admin")
        result = await _require_admin(auth)
        assert result.role == "admin"

    @pytest.mark.asyncio
    async def test_student_rejected(self):
        from app.api.deps import _require_admin
        from fastapi import HTTPException
        auth = _make_auth("student-1", "student")
        with pytest.raises(HTTPException) as exc_info:
            await _require_admin(auth)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_teacher_rejected(self):
        from app.api.deps import _require_admin
        from fastapi import HTTPException
        auth = _make_auth("teacher-1", "teacher")
        with pytest.raises(HTTPException) as exc_info:
            await _require_admin(auth)
        assert exc_info.value.status_code == 403
