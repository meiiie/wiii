"""
Sprint 158: "Tài Khoản" — User Management tests.

Tests:
  - find_or_create_by_provider (6 tests)
  - User CRUD operations (8 tests)
  - Identity management (4 tests)
  - Token auth_method fix (2 tests)

Total: 20 tests
"""
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(user_id=None, email="test@example.com", name="Test", role="student"):
    """Create a mock user dict."""
    return {
        "id": user_id or str(uuid.uuid4()),
        "email": email,
        "name": name,
        "avatar_url": None,
        "role": role,
        "is_active": True,
    }


def _make_pool():
    """Create a mock asyncpg pool with proper async context manager."""
    pool = MagicMock()
    conn = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx
    return pool, conn


# ===========================================================================
# TestFindOrCreateByProvider
# ===========================================================================


class TestFindOrCreateByProvider:
    """Test the generalized find_or_create_by_provider function."""

    @pytest.mark.asyncio
    async def test_provider_match_returns_existing_user(self):
        """When provider identity matches, return existing user without creating."""
        existing = _make_user()
        with patch("app.auth.user_service.find_user_by_provider", new_callable=AsyncMock, return_value=existing):
            from app.auth.user_service import find_or_create_by_provider
            result = await find_or_create_by_provider("google", "sub123", email="test@example.com")
            assert result["id"] == existing["id"]

    @pytest.mark.asyncio
    async def test_email_match_auto_links(self):
        """When email matches existing user AND email_verified=True, auto-link identity."""
        existing = _make_user()
        with (
            patch("app.auth.user_service.find_user_by_provider", new_callable=AsyncMock, return_value=None),
            patch("app.auth.user_service.find_user_by_email", new_callable=AsyncMock, return_value=existing),
            patch("app.auth.user_service.link_identity", new_callable=AsyncMock) as mock_link,
        ):
            from app.auth.user_service import find_or_create_by_provider
            result = await find_or_create_by_provider("lms", "lms-user-1", email="test@example.com", name="LMS User", email_verified=True)
            assert result["id"] == existing["id"]
            mock_link.assert_called_once()
            assert mock_link.call_args.kwargs["provider"] == "lms"

    @pytest.mark.asyncio
    async def test_creates_new_user(self):
        """When no match, create new user and link identity."""
        new_user = _make_user()
        with (
            patch("app.auth.user_service.find_user_by_provider", new_callable=AsyncMock, return_value=None),
            patch("app.auth.user_service.find_user_by_email", new_callable=AsyncMock, return_value=None),
            patch("app.auth.user_service.create_user", new_callable=AsyncMock, return_value=new_user),
            patch("app.auth.user_service.link_identity", new_callable=AsyncMock) as mock_link,
        ):
            from app.auth.user_service import find_or_create_by_provider
            result = await find_or_create_by_provider("google", "new-sub", email="new@example.com")
            assert result["id"] == new_user["id"]
            mock_link.assert_called_once()

    @pytest.mark.asyncio
    async def test_auto_create_false_returns_none(self):
        """When auto_create=False and no match, return None."""
        with (
            patch("app.auth.user_service.find_user_by_provider", new_callable=AsyncMock, return_value=None),
            patch("app.auth.user_service.find_user_by_email", new_callable=AsyncMock, return_value=None),
        ):
            from app.auth.user_service import find_or_create_by_provider
            result = await find_or_create_by_provider("lms", "unknown", auto_create=False)
            assert result is None

    @pytest.mark.asyncio
    async def test_lms_with_issuer(self):
        """LMS provider uses provider_issuer for connector isolation."""
        existing = _make_user()
        with patch("app.auth.user_service.find_user_by_provider", new_callable=AsyncMock, return_value=existing) as mock_find:
            from app.auth.user_service import find_or_create_by_provider
            result = await find_or_create_by_provider(
                "lms", "student-42", provider_issuer="maritime-lms",
            )
            assert result is not None
            mock_find.assert_called_once_with("lms", "student-42", "maritime-lms")

    @pytest.mark.asyncio
    async def test_google_compat_wrapper(self):
        """find_or_create_by_google still works as backward-compat wrapper."""
        new_user = _make_user()
        with patch("app.auth.user_service.find_or_create_by_provider", new_callable=AsyncMock, return_value=new_user) as mock_provider:
            from app.auth.user_service import find_or_create_by_google
            result = await find_or_create_by_google("google-sub", "user@gmail.com", name="Test")
            assert result["id"] == new_user["id"]
            mock_provider.assert_called_once()
            assert mock_provider.call_args.kwargs["provider"] == "google"


# ===========================================================================
# TestUserCRUD
# ===========================================================================


class TestUserCRUD:
    """Test user CRUD operations."""

    @pytest.mark.asyncio
    async def test_get_user_found(self):
        """get_user returns user dict when found."""
        now = datetime.now(timezone.utc)
        pool, conn = _make_pool()
        conn.fetchrow.return_value = {
            "id": "u1", "email": "a@b.com", "name": "A", "avatar_url": None,
            "role": "student", "is_active": True, "created_at": now, "updated_at": now,
        }
        with patch("app.auth.user_service._get_pool", new_callable=AsyncMock, return_value=pool):
            from app.auth.user_service import get_user
            result = await get_user("u1")
            assert result is not None
            assert result["id"] == "u1"
            assert isinstance(result["created_at"], str)  # converted to ISO

    @pytest.mark.asyncio
    async def test_get_user_not_found(self):
        """get_user returns None when not found."""
        pool, conn = _make_pool()
        conn.fetchrow.return_value = None
        with patch("app.auth.user_service._get_pool", new_callable=AsyncMock, return_value=pool):
            from app.auth.user_service import get_user
            result = await get_user("nonexistent")
            assert result is None

    @pytest.mark.asyncio
    async def test_update_user_name(self):
        """update_user changes name and returns updated user."""
        pool, conn = _make_pool()
        conn.execute.return_value = "UPDATE 1"
        now = datetime.now(timezone.utc)
        with (
            patch("app.auth.user_service._get_pool", new_callable=AsyncMock, return_value=pool),
            patch("app.auth.user_service.get_user", new_callable=AsyncMock, return_value={
                "id": "u1", "email": "a@b.com", "name": "New Name", "avatar_url": None,
                "role": "student", "is_active": True, "created_at": now.isoformat(), "updated_at": now.isoformat(),
            }),
        ):
            from app.auth.user_service import update_user
            result = await update_user("u1", name="New Name")
            assert result is not None
            assert result["name"] == "New Name"

    @pytest.mark.asyncio
    async def test_update_user_not_found(self):
        """update_user returns None when user doesn't exist."""
        pool, conn = _make_pool()
        conn.execute.return_value = "UPDATE 0"
        with patch("app.auth.user_service._get_pool", new_callable=AsyncMock, return_value=pool):
            from app.auth.user_service import update_user
            result = await update_user("nonexistent", name="X")
            assert result is None

    @pytest.mark.asyncio
    async def test_role_valid(self):
        """update_user_role accepts valid roles."""
        pool, conn = _make_pool()
        conn.execute.return_value = "UPDATE 1"
        with (
            patch("app.auth.user_service._get_pool", new_callable=AsyncMock, return_value=pool),
            patch("app.auth.user_service.get_user", new_callable=AsyncMock, return_value=_make_user(role="teacher")),
        ):
            from app.auth.user_service import update_user_role
            result = await update_user_role("u1", "teacher")
            assert result is not None
            assert result["role"] == "teacher"

    @pytest.mark.asyncio
    async def test_role_invalid_raises(self):
        """update_user_role raises ValueError for invalid roles."""
        from app.auth.user_service import update_user_role
        with pytest.raises(ValueError, match="Invalid role"):
            await update_user_role("u1", "superadmin")

    @pytest.mark.asyncio
    async def test_deactivate_user(self):
        """deactivate_user sets is_active=false and revokes tokens."""
        pool, conn = _make_pool()
        conn.execute.return_value = "UPDATE 1"
        with (
            patch("app.auth.user_service._get_pool", new_callable=AsyncMock, return_value=pool),
            patch("app.auth.user_service.get_user", new_callable=AsyncMock, return_value={
                **_make_user(), "is_active": False
            }),
            patch("app.auth.token_service.revoke_user_tokens", new_callable=AsyncMock, return_value=2) as mock_revoke,
        ):
            from app.auth.user_service import deactivate_user
            result = await deactivate_user("u1")
            assert result is not None
            assert result["is_active"] is False
            mock_revoke.assert_called_once_with("u1")

    @pytest.mark.asyncio
    async def test_list_users_paginated(self):
        """list_users returns paginated results."""
        pool, conn = _make_pool()
        now = datetime.now(timezone.utc)
        conn.fetchval.return_value = 25
        conn.fetch.return_value = [
            {"id": "u1", "email": "a@b.com", "name": "A", "avatar_url": None, "role": "student", "is_active": True, "created_at": now},
            {"id": "u2", "email": "c@d.com", "name": "B", "avatar_url": None, "role": "teacher", "is_active": True, "created_at": now},
        ]
        with patch("app.auth.user_service._get_pool", new_callable=AsyncMock, return_value=pool):
            from app.auth.user_service import list_users
            users, total = await list_users(limit=10, offset=0)
            assert total == 25
            assert len(users) == 2


# ===========================================================================
# TestIdentityManagement
# ===========================================================================


class TestIdentityManagement:
    """Test identity link/unlink operations."""

    @pytest.mark.asyncio
    async def test_list_identities(self):
        """list_user_identities returns formatted identity list."""
        pool, conn = _make_pool()
        now = datetime.now(timezone.utc)
        conn.fetch.return_value = [
            {"id": "i1", "provider": "google", "provider_sub": "sub1", "provider_issuer": None,
             "email": "a@b.com", "display_name": "A", "avatar_url": None, "linked_at": now, "last_used_at": now},
        ]
        with patch("app.auth.user_service._get_pool", new_callable=AsyncMock, return_value=pool):
            from app.auth.user_service import list_user_identities
            result = await list_user_identities("u1")
            assert len(result) == 1
            assert result[0]["provider"] == "google"
            assert isinstance(result[0]["linked_at"], str)  # ISO format

    @pytest.mark.asyncio
    async def test_unlink_success(self):
        """unlink_identity removes identity when user has >= 2."""
        pool, conn = _make_pool()
        conn.fetchval.return_value = 2  # has 2 identities
        conn.execute.return_value = "DELETE 1"
        with patch("app.auth.user_service._get_pool", new_callable=AsyncMock, return_value=pool):
            from app.auth.user_service import unlink_identity
            result = await unlink_identity("u1", "i1")
            assert result is True

    @pytest.mark.asyncio
    async def test_unlink_last_refused(self):
        """unlink_identity raises ValueError when it's the last identity."""
        pool, conn = _make_pool()
        conn.fetchval.return_value = 1  # only 1 identity
        with patch("app.auth.user_service._get_pool", new_callable=AsyncMock, return_value=pool):
            from app.auth.user_service import unlink_identity
            with pytest.raises(ValueError, match="Cannot unlink the last identity"):
                await unlink_identity("u1", "i1")

    @pytest.mark.asyncio
    async def test_unlink_not_found(self):
        """unlink_identity returns False when identity doesn't exist."""
        pool, conn = _make_pool()
        conn.fetchval.return_value = 3
        conn.execute.return_value = "DELETE 0"
        with patch("app.auth.user_service._get_pool", new_callable=AsyncMock, return_value=pool):
            from app.auth.user_service import unlink_identity
            result = await unlink_identity("u1", "nonexistent")
            assert result is False


# ===========================================================================
# TestTokenAuthMethodFix
# ===========================================================================


class TestTokenAuthMethodFix:
    """Test the auth_method bug fix in token_service."""

    def test_access_token_has_auth_method(self):
        """create_access_token includes auth_method in JWT claims."""
        with patch("app.auth.token_service.settings") as mock_settings:
            mock_settings.jwt_secret_key = "test-secret-key-minimum-length-32chars"
            mock_settings.jwt_algorithm = "HS256"
            mock_settings.jwt_expire_minutes = 30
            from app.auth.token_service import create_access_token, verify_access_token
            token = create_access_token("u1", auth_method="lms")
            payload = verify_access_token(token)
            assert payload.auth_method == "lms"

    @pytest.mark.asyncio
    async def test_refresh_preserves_auth_method(self):
        """refresh_access_token uses stored auth_method, not hardcoded 'google'."""
        now = datetime.now(timezone.utc)
        pool, conn = _make_pool()

        # asyncpg Record supports dict-like access
        row_data = {
            "id": "rt1",
            "user_id": "u1",
            "expires_at": now + timedelta(days=30),
            "revoked_at": None,
            "auth_method": "lms",
            "email": "a@b.com",
            "name": "Test",
            "role": "student",
        }
        # Make the row support both row["key"] and row.get("key")
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: row_data[key]
        mock_row.get = lambda key, default=None: row_data.get(key, default)
        conn.fetchrow.return_value = mock_row
        conn.execute.return_value = "UPDATE 1"

        mock_token = MagicMock(
            access_token="new-at",
            refresh_token="new-rt",
            token_type="bearer",
            expires_in=1800,
        )

        with (
            patch("app.core.database.get_asyncpg_pool", new_callable=AsyncMock, return_value=pool, create=True),
            patch("app.auth.token_service.create_token_pair", new_callable=AsyncMock, return_value=mock_token) as mock_create,
        ):
            from app.auth.token_service import refresh_access_token
            result = await refresh_access_token("old-refresh-token")
            assert result is not None
            # Verify auth_method="lms" was passed (not "google")
            mock_create.assert_called_once()
            assert mock_create.call_args.kwargs["auth_method"] == "lms"
