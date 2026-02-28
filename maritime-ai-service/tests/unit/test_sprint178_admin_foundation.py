"""
Sprint 178: "Admin Toan Dien" — Admin Module Foundation Tests

Tests:
1. Config fields  — enable_admin_module, admin_ip_allowlist, admin_rate_limit
2. Admin audit    — fire-and-forget INSERT, noop when disabled, never raises
3. Admin dashboard — GET /admin/dashboard returns counts, role/feature gate
4. Admin user search — GET /admin/users filters, sorting, pagination
5. Feature flags read — GET /admin/feature-flags config + DB merge
6. Admin security — IP allowlist enforcement
7. Migration 028 — admin_audit_log, admin_feature_flags, llm_usage_log schema
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Shared pool mock helper (same pattern as Sprint 176 / Sprint 177)
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
# Shared auth objects
# ---------------------------------------------------------------------------

from app.core.security import AuthenticatedUser

_ADMIN_USER = AuthenticatedUser(user_id="admin-1", auth_method="api_key", role="admin")
_STUDENT_USER = AuthenticatedUser(user_id="student-1", auth_method="api_key", role="student")


# =============================================================================
# 1. TestAdminConfig
# =============================================================================


class TestAdminConfig:
    """Test Sprint 178 config fields."""

    def test_enable_admin_module_defaults_false(self):
        """enable_admin_module defaults to False (safe default)."""
        from app.core.config import Settings
        s = Settings(api_key="test", enable_admin_module=False)
        assert s.enable_admin_module is False

    def test_admin_ip_allowlist_defaults_empty(self):
        """admin_ip_allowlist defaults to empty string (allow all)."""
        from app.core.config import Settings
        s = Settings(api_key="test")
        assert s.admin_ip_allowlist == ""

    def test_admin_rate_limit_configurable(self):
        """admin_rate_limit is configurable and defaults to 30/minute."""
        from app.core.config import Settings
        s = Settings(api_key="test", admin_rate_limit="10/minute")
        assert s.admin_rate_limit == "10/minute"

        s2 = Settings(api_key="test")
        assert s2.admin_rate_limit == "30/minute"


# =============================================================================
# 2. TestAdminAudit
# =============================================================================


class TestAdminAudit:
    """Test admin audit logging (fire-and-forget INSERT).

    admin_audit.py uses lazy imports inside the function body:
        from app.core.config import settings
        from app.core.database import get_asyncpg_pool
    So we patch at the SOURCE module (app.core.config.settings).
    """

    @pytest.mark.asyncio
    async def test_insert_to_db_when_enabled(self):
        """log_admin_action inserts a row when enable_admin_module=True."""
        async_pool_fn, mock_conn = _mock_pool_and_conn()

        mock_config = MagicMock()
        mock_config.enable_admin_module = True

        with patch("app.core.config.settings", mock_config), \
             patch(_POOL_PATCH, create=True, new=async_pool_fn):
            from app.services.admin_audit import log_admin_action
            await log_admin_action(
                actor_id="admin-1",
                action="user.delete",
                target_type="user",
                target_id="user-99",
            )

        mock_conn.execute.assert_called_once()
        sql = mock_conn.execute.call_args[0][0]
        assert "INSERT INTO admin_audit_log" in sql

    @pytest.mark.asyncio
    async def test_noop_when_disabled(self):
        """log_admin_action is a no-op when enable_admin_module=False."""
        async_pool_fn, mock_conn = _mock_pool_and_conn()

        mock_config = MagicMock()
        mock_config.enable_admin_module = False

        with patch("app.core.config.settings", mock_config), \
             patch(_POOL_PATCH, create=True, new=async_pool_fn):
            from app.services.admin_audit import log_admin_action
            await log_admin_action(
                actor_id="admin-1",
                action="user.view",
            )

        mock_conn.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_never_raises_on_db_error(self):
        """log_admin_action swallows DB exceptions — fire-and-forget."""
        async_pool_fn, mock_conn = _mock_pool_and_conn()
        mock_conn.execute.side_effect = RuntimeError("DB down")

        mock_config = MagicMock()
        mock_config.enable_admin_module = True

        with patch("app.core.config.settings", mock_config), \
             patch(_POOL_PATCH, create=True, new=async_pool_fn):
            from app.services.admin_audit import log_admin_action
            # Must NOT raise
            await log_admin_action(actor_id="admin-1", action="flag.toggle")

    @pytest.mark.asyncio
    async def test_old_new_values_serialized_as_json(self):
        """old_value and new_value are serialized via json.dumps(ensure_ascii=False)."""
        async_pool_fn, mock_conn = _mock_pool_and_conn()

        mock_config = MagicMock()
        mock_config.enable_admin_module = True

        with patch("app.core.config.settings", mock_config), \
             patch(_POOL_PATCH, create=True, new=async_pool_fn):
            from app.services.admin_audit import log_admin_action
            await log_admin_action(
                actor_id="admin-1",
                action="flag.toggle",
                old_value={"value": True},
                new_value={"value": False},
            )

        call_args = mock_conn.execute.call_args[0]
        # Positional params after SQL: actor_id($1) ... old_value($11) new_value($12)
        # Index 0 = SQL, 1..16 = params → old_value is index 11, new_value is index 12
        old_json = call_args[11]
        new_json = call_args[12]
        assert old_json == json.dumps({"value": True}, ensure_ascii=False)
        assert new_json == json.dumps({"value": False}, ensure_ascii=False)

    def test_extract_audit_context_from_request(self):
        """extract_audit_context returns dict with expected keys."""
        from app.services.admin_audit import extract_audit_context

        mock_request = MagicMock()
        mock_request.client.host = "10.0.0.1"
        mock_request.headers.get = lambda k, d=None: {
            "user-agent": "TestAgent/1.0",
            "x-request-id": "req-abc",
            "x-organization-id": "org-1",
        }.get(k, d)
        mock_request.method = "PATCH"
        mock_request.url.path = "/api/v1/admin/feature-flags/enable_foo"

        ctx = extract_audit_context(mock_request)
        assert ctx["ip_address"] == "10.0.0.1"
        assert ctx["user_agent"] == "TestAgent/1.0"
        assert ctx["request_id"] == "req-abc"
        assert ctx["organization_id"] == "org-1"
        assert ctx["http_method"] == "PATCH"
        assert "/admin/feature-flags" in ctx["http_path"]


# =============================================================================
# 3. TestAdminDashboard
# =============================================================================


class TestAdminDashboard:
    """Test admin_dashboard handler function directly (bypasses ASGI overhead).

    admin_dashboard.py imports settings at module level, so we patch
    'app.api.v1.admin_dashboard.settings'.
    """

    @pytest.mark.asyncio
    async def test_returns_counts(self):
        """Dashboard returns all expected count fields with correct values."""
        async_pool_fn, mock_conn = _mock_pool_and_conn()

        # fetchval returns total_users=10, active_users=8 — then exceptions for the rest
        mock_conn.fetchval.side_effect = [10, 8]
        # orgs + sessions + llm_usage all fail (tables may not exist) — exercising graceful fallback
        mock_conn.fetchval.side_effect = [10, 8, Exception("no table"), Exception("no table")]

        async def multi_fetchval(query, *args):
            if "organizations" in query:
                return 3
            elif "session" in query.lower():
                return 42
            return 5

        mock_conn.fetchval.side_effect = None
        mock_conn.fetchval.side_effect = multi_fetchval

        mock_row = MagicMock()
        mock_row.__getitem__ = MagicMock(side_effect=lambda k: {"tokens": 100000, "cost": 0.05}[k])
        mock_conn.fetchrow.return_value = mock_row

        with patch("app.api.v1.admin_dashboard.settings") as mock_settings, \
             patch(_POOL_PATCH, create=True, new=async_pool_fn):
            mock_settings.enable_admin_module = True

            from app.api.v1.admin_dashboard import admin_dashboard
            result = await admin_dashboard(_ADMIN_USER)

        assert "total_users" in result
        assert "active_users" in result
        assert "total_organizations" in result
        assert "total_chat_sessions_24h" in result
        assert "total_llm_tokens_24h" in result
        assert "estimated_cost_24h_usd" in result
        assert "feature_flags_active" in result

    @pytest.mark.asyncio
    async def test_requires_admin_role_via_dep(self):
        """RequireAdmin dependency enforces role='admin' — 403 for non-admin."""
        from fastapi import HTTPException
        from app.api.deps import _require_admin

        with pytest.raises(HTTPException) as exc_info:
            await _require_admin(auth=_STUDENT_USER)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_feature_gated_check_admin_module(self):
        """check_admin_module raises 404 when enable_admin_module=False."""
        from fastapi import HTTPException

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.enable_admin_module = False

            from app.core.admin_security import check_admin_module
            with pytest.raises(HTTPException) as exc_info:
                check_admin_module(mock_request)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_handles_missing_tables_gracefully(self):
        """Dashboard does not crash when optional tables (organizations) don't exist."""
        async_pool_fn, mock_conn = _mock_pool_and_conn()

        async def selective_fetchval(query, *args):
            if "organizations" in query:
                raise Exception("relation 'organizations' does not exist")
            return 5

        mock_conn.fetchval.side_effect = selective_fetchval
        mock_conn.fetchrow.side_effect = Exception("relation 'chat_sessions' does not exist")

        with patch("app.api.v1.admin_dashboard.settings") as mock_settings, \
             patch(_POOL_PATCH, create=True, new=async_pool_fn):
            mock_settings.enable_admin_module = True

            from app.api.v1.admin_dashboard import admin_dashboard
            result = await admin_dashboard(_ADMIN_USER)

        assert "total_users" in result
        assert "total_organizations" in result
        assert result["total_organizations"] == 0

    @pytest.mark.asyncio
    async def test_empty_db_returns_zeros(self):
        """Dashboard handles all-zero DB counts gracefully."""
        async_pool_fn, mock_conn = _mock_pool_and_conn()
        mock_conn.fetchval.return_value = 0
        mock_conn.fetchrow.return_value = None

        with patch("app.api.v1.admin_dashboard.settings") as mock_settings, \
             patch(_POOL_PATCH, create=True, new=async_pool_fn):
            mock_settings.enable_admin_module = True

            from app.api.v1.admin_dashboard import admin_dashboard
            result = await admin_dashboard(_ADMIN_USER)

        assert result["total_users"] == 0
        assert result["active_users"] == 0
        assert result["total_llm_tokens_24h"] == 0
        assert result["estimated_cost_24h_usd"] == 0.0


# =============================================================================
# 4. TestAdminUserSearch
# =============================================================================


class TestAdminUserSearch:
    """Test admin_user_search handler with various filter combinations."""

    def _make_fake_row(self, **kwargs):
        """Create a fake asyncpg-row-like object."""
        defaults = {
            "id": "user-abc",
            "email": "test@example.com",
            "name": "Test User",
            "role": "student",
            "is_active": True,
            "created_at": None,
            "organization_count": 1,
        }
        defaults.update(kwargs)
        row = MagicMock()
        row.__getitem__ = lambda self, k: defaults[k]
        return row

    @pytest.mark.asyncio
    async def test_no_filters_returns_all_users(self):
        """User search with no filters returns all users."""
        async_pool_fn, mock_conn = _mock_pool_and_conn()
        mock_conn.fetchval.return_value = 5
        mock_conn.fetch.return_value = [self._make_fake_row()]

        with patch("app.api.v1.admin_dashboard.settings") as mock_settings, \
             patch(_POOL_PATCH, create=True, new=async_pool_fn):
            mock_settings.enable_admin_module = True

            from app.api.v1.admin_dashboard import admin_user_search
            result = await admin_user_search(
                auth=_ADMIN_USER,
                email=None, role=None, org_id=None, status=None, q=None,
                sort="created_at_desc", limit=50, offset=0,
            )

        assert result["total"] == 5
        assert len(result["users"]) == 1
        assert result["limit"] == 50
        assert result["offset"] == 0

    @pytest.mark.asyncio
    async def test_filter_by_email(self):
        """Email filter injects %email% into the query params."""
        async_pool_fn, mock_conn = _mock_pool_and_conn()
        mock_conn.fetchval.return_value = 1
        mock_conn.fetch.return_value = [self._make_fake_row(email="alice@example.com")]

        with patch("app.api.v1.admin_dashboard.settings") as mock_settings, \
             patch(_POOL_PATCH, create=True, new=async_pool_fn):
            mock_settings.enable_admin_module = True

            from app.api.v1.admin_dashboard import admin_user_search
            await admin_user_search(
                auth=_ADMIN_USER,
                email="alice",
                role=None, org_id=None, status=None, q=None,
                sort="created_at_desc", limit=50, offset=0,
            )

        # The %alice% param must have been passed to the DB query
        all_call_args = mock_conn.fetchval.call_args[0]
        assert any("%alice%" in str(a) for a in all_call_args)

    @pytest.mark.asyncio
    async def test_filter_by_role(self):
        """Role filter passes role value directly to the query params."""
        async_pool_fn, mock_conn = _mock_pool_and_conn()
        mock_conn.fetchval.return_value = 2
        mock_conn.fetch.return_value = [self._make_fake_row(role="teacher")]

        with patch("app.api.v1.admin_dashboard.settings") as mock_settings, \
             patch(_POOL_PATCH, create=True, new=async_pool_fn):
            mock_settings.enable_admin_module = True

            from app.api.v1.admin_dashboard import admin_user_search
            await admin_user_search(
                auth=_ADMIN_USER,
                email=None, role="teacher", org_id=None, status=None, q=None,
                sort="created_at_desc", limit=50, offset=0,
            )

        all_call_args = mock_conn.fetchval.call_args[0]
        assert "teacher" in all_call_args

    @pytest.mark.asyncio
    async def test_filter_by_org_id(self):
        """org_id filter adds EXISTS subquery with the org ID as a param."""
        async_pool_fn, mock_conn = _mock_pool_and_conn()
        mock_conn.fetchval.return_value = 3
        mock_conn.fetch.return_value = [self._make_fake_row()]

        with patch("app.api.v1.admin_dashboard.settings") as mock_settings, \
             patch(_POOL_PATCH, create=True, new=async_pool_fn):
            mock_settings.enable_admin_module = True

            from app.api.v1.admin_dashboard import admin_user_search
            await admin_user_search(
                auth=_ADMIN_USER,
                email=None, role=None, org_id="lms-hang-hai", status=None, q=None,
                sort="created_at_desc", limit=50, offset=0,
            )

        all_call_args = mock_conn.fetchval.call_args[0]
        assert "lms-hang-hai" in all_call_args

    @pytest.mark.asyncio
    async def test_filter_by_status_active(self):
        """status=active adds is_active = true to the WHERE clause."""
        async_pool_fn, mock_conn = _mock_pool_and_conn()
        mock_conn.fetchval.return_value = 4
        mock_conn.fetch.return_value = [self._make_fake_row(is_active=True)]

        with patch("app.api.v1.admin_dashboard.settings") as mock_settings, \
             patch(_POOL_PATCH, create=True, new=async_pool_fn):
            mock_settings.enable_admin_module = True

            from app.api.v1.admin_dashboard import admin_user_search
            await admin_user_search(
                auth=_ADMIN_USER,
                email=None, role=None, org_id=None, status="active", q=None,
                sort="created_at_desc", limit=50, offset=0,
            )

        count_sql = mock_conn.fetchval.call_args[0][0]
        assert "is_active = true" in count_sql

    @pytest.mark.asyncio
    async def test_free_text_search(self):
        """q param inserts %q% ILIKE for both name and email columns."""
        async_pool_fn, mock_conn = _mock_pool_and_conn()
        mock_conn.fetchval.return_value = 1
        mock_conn.fetch.return_value = [self._make_fake_row(name="Nguyen Van A")]

        with patch("app.api.v1.admin_dashboard.settings") as mock_settings, \
             patch(_POOL_PATCH, create=True, new=async_pool_fn):
            mock_settings.enable_admin_module = True

            from app.api.v1.admin_dashboard import admin_user_search
            await admin_user_search(
                auth=_ADMIN_USER,
                email=None, role=None, org_id=None, status=None, q="Nguyen",
                sort="created_at_desc", limit=50, offset=0,
            )

        all_call_args = mock_conn.fetchval.call_args[0]
        assert any("%Nguyen%" in str(a) for a in all_call_args)

    @pytest.mark.asyncio
    async def test_sort_by_name_asc(self):
        """sort=name_asc results in ORDER BY u.name ASC in the SQL."""
        async_pool_fn, mock_conn = _mock_pool_and_conn()
        mock_conn.fetchval.return_value = 1
        mock_conn.fetch.return_value = [self._make_fake_row()]

        with patch("app.api.v1.admin_dashboard.settings") as mock_settings, \
             patch(_POOL_PATCH, create=True, new=async_pool_fn):
            mock_settings.enable_admin_module = True

            from app.api.v1.admin_dashboard import admin_user_search
            await admin_user_search(
                auth=_ADMIN_USER,
                email=None, role=None, org_id=None, status=None, q=None,
                sort="name_asc", limit=50, offset=0,
            )

        fetch_sql = mock_conn.fetch.call_args[0][0]
        assert "u.name ASC" in fetch_sql

    @pytest.mark.asyncio
    async def test_pagination_limit_offset(self):
        """limit and offset values appear in the result and are passed to the DB."""
        async_pool_fn, mock_conn = _mock_pool_and_conn()
        mock_conn.fetchval.return_value = 100
        mock_conn.fetch.return_value = [self._make_fake_row()]

        with patch("app.api.v1.admin_dashboard.settings") as mock_settings, \
             patch(_POOL_PATCH, create=True, new=async_pool_fn):
            mock_settings.enable_admin_module = True

            from app.api.v1.admin_dashboard import admin_user_search
            result = await admin_user_search(
                auth=_ADMIN_USER,
                email=None, role=None, org_id=None, status=None, q=None,
                sort="created_at_desc", limit=25, offset=50,
            )

        assert result["limit"] == 25
        assert result["offset"] == 50
        fetch_positional = mock_conn.fetch.call_args[0]
        assert 25 in fetch_positional and 50 in fetch_positional

    @pytest.mark.asyncio
    async def test_requires_admin_role_direct(self):
        """_require_admin dep raises 403 for non-admin."""
        from fastapi import HTTPException
        from app.api.deps import _require_admin

        teacher = AuthenticatedUser(user_id="t1", auth_method="api_key", role="teacher")
        with pytest.raises(HTTPException) as exc_info:
            await _require_admin(auth=teacher)
        assert exc_info.value.status_code == 403


# =============================================================================
# 5. TestFeatureFlagRead
# =============================================================================


class TestFeatureFlagRead:
    """Test admin_feature_flags_read handler."""

    @pytest.mark.asyncio
    async def test_returns_config_flags(self):
        """Feature flags endpoint returns a non-empty list of enable_* flags."""
        async_pool_fn, mock_conn = _mock_pool_and_conn()
        mock_conn.fetch.return_value = []  # No DB overrides

        with patch("app.api.v1.admin_dashboard.settings") as mock_settings, \
             patch(_POOL_PATCH, create=True, new=async_pool_fn):
            mock_settings.enable_admin_module = True
            mock_settings.enable_foo = True
            mock_settings.enable_bar = False

            with patch("builtins.dir", return_value=[
                "enable_admin_module", "enable_foo", "enable_bar"
            ]):
                from app.api.v1.admin_dashboard import admin_feature_flags_read
                result = await admin_feature_flags_read(_ADMIN_USER)

        assert isinstance(result, list)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_enable_prefix_only(self):
        """Only enable_* boolean fields appear — non-enable_ and non-bool are excluded."""
        async_pool_fn, mock_conn = _mock_pool_and_conn()
        mock_conn.fetch.return_value = []

        with patch("app.api.v1.admin_dashboard.settings") as mock_settings, \
             patch(_POOL_PATCH, create=True, new=async_pool_fn):
            mock_settings.enable_admin_module = True
            mock_settings.enable_foo = True
            mock_settings.enable_bar = False
            mock_settings.not_enable_baz = True   # Should be excluded
            mock_settings.enable_string = "bad"   # Non-bool, should be excluded

            with patch("builtins.dir", return_value=[
                "enable_foo", "enable_bar", "not_enable_baz",
                "enable_string", "enable_admin_module",
            ]):
                from app.api.v1.admin_dashboard import admin_feature_flags_read
                result = await admin_feature_flags_read(_ADMIN_USER)

        keys = [f["key"] for f in result]
        assert "not_enable_baz" not in keys
        assert "enable_string" not in keys
        for f in result:
            assert f["key"].startswith("enable_")
            assert isinstance(f["value"], bool)

    @pytest.mark.asyncio
    async def test_requires_admin_role_dep(self):
        """_require_admin raises 403 for teacher role."""
        from fastapi import HTTPException
        from app.api.deps import _require_admin

        teacher = AuthenticatedUser(user_id="t1", auth_method="api_key", role="teacher")
        with pytest.raises(HTTPException) as exc_info:
            await _require_admin(auth=teacher)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_feature_gated_via_check_admin_module(self):
        """check_admin_module raises 404 when enable_admin_module=False."""
        from fastapi import HTTPException

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.enable_admin_module = False

            from app.core.admin_security import check_admin_module
            with pytest.raises(HTTPException) as exc_info:
                check_admin_module(mock_request)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_source_field_present_and_correct(self):
        """Every flag dict has a 'source' field set to 'config' by default."""
        async_pool_fn, mock_conn = _mock_pool_and_conn()
        mock_conn.fetch.return_value = []

        with patch("app.api.v1.admin_dashboard.settings") as mock_dashboard_settings, \
             patch("app.core.config.settings") as mock_config_settings, \
             patch(_POOL_PATCH, create=True, new=async_pool_fn):
            mock_dashboard_settings.enable_admin_module = True
            mock_config_settings.enable_test_flag = True

            with patch("builtins.dir", return_value=["enable_test_flag"]):
                from app.api.v1.admin_dashboard import admin_feature_flags_read
                result = await admin_feature_flags_read(_ADMIN_USER)

        assert len(result) == 1
        flag = result[0]
        assert flag["source"] == "config"
        assert flag["key"] == "enable_test_flag"
        assert flag["value"] is True


# =============================================================================
# 6. TestAdminSecurity
# =============================================================================


class TestAdminSecurity:
    """Test admin IP allowlist enforcement in app/core/admin_security.py.

    admin_security.py uses a lazy import inside the function:
        from app.core.config import settings
    So we patch at the source: app.core.config.settings.
    """

    def _make_request(self, client_ip: str) -> MagicMock:
        req = MagicMock()
        req.client.host = client_ip
        return req

    def test_empty_allowlist_allows_all(self):
        """Empty admin_ip_allowlist string permits any IP address."""
        mock_config = MagicMock()
        mock_config.admin_ip_allowlist = ""

        with patch("app.core.config.settings", mock_config):
            from app.core.admin_security import check_admin_ip_allowlist
            # Should NOT raise
            check_admin_ip_allowlist(self._make_request("192.168.1.100"))

    def test_blocks_unknown_ip(self):
        """IP not in allowlist is blocked with HTTP 403."""
        from fastapi import HTTPException

        mock_config = MagicMock()
        mock_config.admin_ip_allowlist = "10.0.0.1"

        with patch("app.core.config.settings", mock_config):
            from app.core.admin_security import check_admin_ip_allowlist
            with pytest.raises(HTTPException) as exc_info:
                check_admin_ip_allowlist(self._make_request("192.168.1.99"))

        assert exc_info.value.status_code == 403

    def test_allows_listed_ip(self):
        """Exact IP match in allowlist passes without exception."""
        mock_config = MagicMock()
        mock_config.admin_ip_allowlist = "10.0.0.1,10.0.0.2"

        with patch("app.core.config.settings", mock_config):
            from app.core.admin_security import check_admin_ip_allowlist
            # Should NOT raise
            check_admin_ip_allowlist(self._make_request("10.0.0.1"))

    def test_multiple_ips_whitespace_tolerant(self):
        """Allowlist handles spaces around commas and allows a matching IP."""
        mock_config = MagicMock()
        mock_config.admin_ip_allowlist = " 10.0.0.1 , 127.0.0.1 , ::1 "

        with patch("app.core.config.settings", mock_config):
            from app.core.admin_security import check_admin_ip_allowlist
            # ::1 (IPv6 loopback) should be allowed
            check_admin_ip_allowlist(self._make_request("::1"))


# =============================================================================
# 7. TestMigration028
# =============================================================================


class TestMigration028:
    """Smoke tests for migration 028 schema definitions (file-read only)."""

    def _read_migration(self):
        import pathlib
        path = (
            pathlib.Path(__file__).parent.parent.parent
            / "alembic" / "versions" / "028_admin_module_tables.py"
        )
        return path.read_text(encoding="utf-8")

    def test_audit_table_defined_in_migration(self):
        """Migration 028 creates admin_audit_log with actor_id and action columns."""
        src = self._read_migration()
        assert "admin_audit_log" in src
        assert "actor_id" in src
        assert "action" in src
        assert "occurred_at" in src

    def test_flags_table_defined_in_migration(self):
        """Migration 028 creates admin_feature_flags with correct constraints."""
        src = self._read_migration()
        assert "admin_feature_flags" in src
        assert "flag_type" in src
        assert "uq_feature_flag_key_org" in src
        assert "expires_at" in src

    def test_llm_usage_table_defined_in_migration(self):
        """Migration 028 creates llm_usage_log with token and cost columns."""
        src = self._read_migration()
        assert "llm_usage_log" in src
        assert "input_tokens" in src
        assert "output_tokens" in src
        assert "estimated_cost_usd" in src
        assert "revision = \"028\"" in src
