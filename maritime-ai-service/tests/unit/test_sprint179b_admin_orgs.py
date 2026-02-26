"""
Sprint 179b: "Quản Trị Theo Tổ Chức" — Admin Panel UX Enhancement

Tests:
  1. Dashboard returns organizations list
  2. Feature flags with/without org_id param
  3. Feature flags fallback when service unavailable
"""
import pytest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch


# ─── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def mock_pool():
    """Create mock asyncpg pool with connection context manager."""
    conn = AsyncMock()
    pool = MagicMock()

    @asynccontextmanager
    async def _acquire():
        yield conn

    pool.acquire = _acquire
    return pool, conn


# ─── Dashboard Tests ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dashboard_returns_organizations_list(mock_pool):
    """Dashboard response should include organizations[] with member counts."""
    pool, conn = mock_pool

    # Mock DB responses
    conn.fetchval.side_effect = [
        100,  # total_users
        42,   # active_users
        2,    # total_orgs
        50,   # total_sessions_24h
    ]
    conn.fetchrow.return_value = {"tokens": 5000, "cost": 1.23}
    conn.fetch.return_value = [
        {"id": "maritime-lms", "name": "maritime-lms", "display_name": "Trường Hàng Hải", "member_count": 30, "document_count": 10, "is_active": True},
        {"id": "test-org", "name": "test-org", "display_name": None, "member_count": 5, "document_count": 0, "is_active": False},
    ]

    with patch("app.api.v1.admin_dashboard.settings") as mock_settings, \
         patch("app.core.database.get_asyncpg_pool", new_callable=AsyncMock, return_value=pool):

        mock_settings.enable_admin_module = True
        # Make dir() return some enable_ flags
        type(mock_settings).__dir__ = lambda self: ["enable_mcp", "enable_product_search"]
        mock_settings.enable_mcp = True
        mock_settings.enable_product_search = False

        from app.api.v1.admin_dashboard import admin_dashboard
        auth_mock = MagicMock()
        result = await admin_dashboard(auth=auth_mock)

    assert "organizations" in result
    assert len(result["organizations"]) == 2
    assert result["organizations"][0]["id"] == "maritime-lms"
    assert result["organizations"][0]["member_count"] == 30
    assert result["organizations"][1]["is_active"] is False


@pytest.mark.asyncio
async def test_dashboard_organizations_empty_on_db_error(mock_pool):
    """When organizations query fails, return empty list (graceful)."""
    pool, conn = mock_pool

    # total_users + active_users succeed, orgs query fails
    call_count = 0
    async def fetchval_side_effect(query, *args):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            return 10
        # orgs count + sessions fail
        raise Exception("table does not exist")

    conn.fetchval.side_effect = fetchval_side_effect
    conn.fetchrow.return_value = None
    conn.fetch.side_effect = Exception("table does not exist")

    with patch("app.api.v1.admin_dashboard.settings") as mock_settings, \
         patch("app.core.database.get_asyncpg_pool", new_callable=AsyncMock, return_value=pool):

        mock_settings.enable_admin_module = True
        type(mock_settings).__dir__ = lambda self: []

        from app.api.v1.admin_dashboard import admin_dashboard
        result = await admin_dashboard(auth=MagicMock())

    assert result["organizations"] == []
    assert result["total_organizations"] == 0


# ─── Feature Flags Tests ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_feature_flags_with_org_id():
    """Feature flags endpoint delegates to list_all_flags(org_id=X)."""
    mock_flags = [
        {"key": "enable_mcp", "value": True, "source": "config", "flag_type": "release", "description": None, "owner": None, "expires_at": None},
        {"key": "enable_product_search", "value": False, "source": "db_override", "flag_type": "release", "description": "org override", "owner": None, "expires_at": None},
    ]

    with patch("app.api.v1.admin_dashboard.settings") as mock_settings, \
         patch("app.services.feature_flag_service.list_all_flags", new_callable=AsyncMock, return_value=mock_flags) as mock_list:

        mock_settings.enable_admin_module = True

        from app.api.v1.admin_dashboard import admin_feature_flags_read
        result = await admin_feature_flags_read(auth=MagicMock(), org_id="maritime-lms")

    mock_list.assert_awaited_once_with(org_id="maritime-lms")
    assert len(result) == 2
    assert result[1]["source"] == "db_override"


@pytest.mark.asyncio
async def test_feature_flags_without_org_id():
    """Feature flags without org_id returns global flags."""
    mock_flags = [
        {"key": "enable_mcp", "value": True, "source": "config", "flag_type": "release", "description": None, "owner": None, "expires_at": None},
    ]

    with patch("app.api.v1.admin_dashboard.settings") as mock_settings, \
         patch("app.services.feature_flag_service.list_all_flags", new_callable=AsyncMock, return_value=mock_flags) as mock_list:

        mock_settings.enable_admin_module = True

        from app.api.v1.admin_dashboard import admin_feature_flags_read
        result = await admin_feature_flags_read(auth=MagicMock(), org_id=None)

    mock_list.assert_awaited_once_with(org_id=None)
    assert len(result) == 1


@pytest.mark.asyncio
async def test_feature_flags_fallback_on_service_error():
    """When list_all_flags raises, fall back to config-only flags."""
    with patch("app.api.v1.admin_dashboard.settings") as mock_settings, \
         patch("app.services.feature_flag_service.list_all_flags", new_callable=AsyncMock, side_effect=Exception("DB down")):

        mock_settings.enable_admin_module = True
        # Simulate enable_ attributes
        type(mock_settings).__dir__ = lambda self: ["enable_mcp", "enable_test"]
        mock_settings.enable_mcp = True
        mock_settings.enable_test = False

        from app.api.v1.admin_dashboard import admin_feature_flags_read
        result = await admin_feature_flags_read(auth=MagicMock(), org_id=None)

    assert len(result) == 2
    assert all(f["source"] == "config" for f in result)
    assert result[0]["key"] == "enable_mcp"
    assert result[0]["value"] is True


@pytest.mark.asyncio
async def test_dashboard_org_list_has_correct_fields(mock_pool):
    """Verify each org in list has required fields."""
    pool, conn = mock_pool

    conn.fetchval.side_effect = [5, 3, 1, 10]
    conn.fetchrow.return_value = {"tokens": 0, "cost": 0.0}
    conn.fetch.return_value = [
        {"id": "org-a", "name": "org-a", "display_name": "Org Alpha", "member_count": 7, "document_count": 3, "is_active": True},
    ]

    with patch("app.api.v1.admin_dashboard.settings") as mock_settings, \
         patch("app.core.database.get_asyncpg_pool", new_callable=AsyncMock, return_value=pool):

        mock_settings.enable_admin_module = True
        type(mock_settings).__dir__ = lambda self: []

        from app.api.v1.admin_dashboard import admin_dashboard
        result = await admin_dashboard(auth=MagicMock())

    org = result["organizations"][0]
    assert "id" in org
    assert "name" in org
    assert "display_name" in org
    assert "member_count" in org
    assert "is_active" in org
    assert org["member_count"] == 7
