"""
Sprint 180: "Quản Trị Hoàn Thiện" — Admin panel completion tests.

Tests:
- reactivate_user() service function
- POST /users/{id}/reactivate endpoint
- Self-deactivation protection (regression)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from app.auth.user_router import router

# ---------------------------------------------------------------------------
# Test app for endpoint tests
# ---------------------------------------------------------------------------

app = FastAPI()
app.include_router(router)

# ---------------------------------------------------------------------------
# Shared pool mock helper (same pattern as Sprint 176 / Sprint 178)
# ---------------------------------------------------------------------------

_POOL_PATCH = "app.core.database.get_asyncpg_pool"


def _mock_pool_and_conn():
    """Create standard mock pool + connection for async DB tests.

    Returns (async_pool_fn, mock_conn) where async_pool_fn is an AsyncMock
    that when awaited returns a pool with a working acquire() context manager.
    """
    mock_conn = AsyncMock()
    mock_pool = MagicMock()
    acm = AsyncMock()
    acm.__aenter__ = AsyncMock(return_value=mock_conn)
    acm.__aexit__ = AsyncMock(return_value=False)
    mock_pool.acquire.return_value = acm
    async_pool_fn = AsyncMock(return_value=mock_pool)
    return async_pool_fn, mock_conn


# ---------------------------------------------------------------------------
# Shared JWT mock helpers
# ---------------------------------------------------------------------------

_ADMIN_JWT = {"sub": "admin-1", "email": "admin@test.com", "name": "Admin", "role": "admin"}
_STUDENT_JWT = {"sub": "student-1", "email": "student@test.com", "name": "Student", "role": "student"}

_EXTRACT_JWT_PATCH = "app.auth.user_router._extract_jwt_user"


# =============================================================================
# 1. TestReactivateUserService — unit tests for reactivate_user()
# =============================================================================


class TestReactivateUserService:
    """Test reactivate_user() in user_service.py."""

    @pytest.mark.asyncio
    async def test_reactivate_user_success(self):
        """reactivate_user sets is_active=true and returns user dict."""
        async_pool_fn, mock_conn = _mock_pool_and_conn()
        mock_conn.execute.return_value = "UPDATE 1"

        reactivated_user = {
            "id": "user-42",
            "email": "reactivated@test.com",
            "name": "Reactivated User",
            "avatar_url": None,
            "role": "student",
            "is_active": True,
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-02-23T00:00:00",
        }

        with patch(_POOL_PATCH, async_pool_fn):
            # get_user is called after the UPDATE succeeds — mock it to return user dict
            with patch("app.auth.user_service.get_user", new_callable=AsyncMock, return_value=reactivated_user) as mock_get:
                from app.auth.user_service import reactivate_user

                result = await reactivate_user("user-42")

                assert result is not None
                assert result["id"] == "user-42"
                assert result["is_active"] is True
                mock_conn.execute.assert_called_once()
                mock_get.assert_awaited_once_with("user-42")

    @pytest.mark.asyncio
    async def test_reactivate_user_not_found(self):
        """reactivate_user returns None when user ID does not exist (UPDATE 0)."""
        async_pool_fn, mock_conn = _mock_pool_and_conn()
        mock_conn.execute.return_value = "UPDATE 0"

        with patch(_POOL_PATCH, async_pool_fn):
            from app.auth.user_service import reactivate_user

            result = await reactivate_user("nonexistent-user")

            assert result is None
            mock_conn.execute.assert_called_once()


# =============================================================================
# 2. TestReactivateEndpoint — endpoint tests for POST /users/{id}/reactivate
# =============================================================================


class TestReactivateEndpoint:
    """Test POST /users/{id}/reactivate admin endpoint."""

    @pytest.mark.asyncio
    async def test_reactivate_endpoint_success(self):
        """Admin can reactivate a user — returns 200 with user profile."""
        reactivated_user = {
            "id": "test-id",
            "email": "user@test.com",
            "name": "Test User",
            "avatar_url": None,
            "role": "student",
            "is_active": True,
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-02-23T00:00:00",
        }

        with patch(_EXTRACT_JWT_PATCH, return_value=_ADMIN_JWT):
            with patch("app.auth.user_service.reactivate_user", new_callable=AsyncMock, return_value=reactivated_user):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    resp = await client.post(
                        "/users/test-id/reactivate",
                        headers={"Authorization": "Bearer fake"},
                    )

                assert resp.status_code == 200
                data = resp.json()
                assert data["id"] == "test-id"
                assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_reactivate_endpoint_not_found(self):
        """Reactivating a nonexistent user returns 404."""
        with patch(_EXTRACT_JWT_PATCH, return_value=_ADMIN_JWT):
            with patch("app.auth.user_service.reactivate_user", new_callable=AsyncMock, return_value=None):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    resp = await client.post(
                        "/users/nonexistent/reactivate",
                        headers={"Authorization": "Bearer fake"},
                    )

                assert resp.status_code == 404
                assert "not found" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_reactivate_endpoint_requires_admin(self):
        """Non-admin (student) gets 403 when attempting to reactivate."""
        with patch(_EXTRACT_JWT_PATCH, return_value=_STUDENT_JWT):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/users/test-id/reactivate",
                    headers={"Authorization": "Bearer fake"},
                )

            assert resp.status_code == 403
            assert "admin" in resp.json()["detail"].lower()


# =============================================================================
# 3. TestDeactivateSelfBlocked — regression test
# =============================================================================


class TestDeactivateSelfBlocked:
    """Regression: self-deactivation must be blocked."""

    @pytest.mark.asyncio
    async def test_deactivate_self_blocked(self):
        """POST /users/{self_id}/deactivate returns 400 when admin tries to deactivate themselves."""
        admin_id = _ADMIN_JWT["sub"]  # "admin-1"

        with patch(_EXTRACT_JWT_PATCH, return_value=_ADMIN_JWT):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    f"/users/{admin_id}/deactivate",
                    headers={"Authorization": "Bearer fake"},
                )

            assert resp.status_code == 400
            assert "yourself" in resp.json()["detail"].lower()
