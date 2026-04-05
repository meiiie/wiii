from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_pool():
    pool = MagicMock()
    conn = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx
    return pool, conn


def test_build_connector_grant_key_is_stable():
    from app.repositories.connector_grant_repository import build_connector_grant_key

    assert build_connector_grant_key("lms-main") == "lms-main:*:*"
    assert (
        build_connector_grant_key(
            "lms-main",
            host_user_id="teacher-1",
            host_workspace_id="course-authoring",
        )
        == "lms-main:teacher-1:course-authoring"
    )


@pytest.mark.asyncio
async def test_upsert_connector_grant_missing_table_fails_open():
    pool, conn = _make_pool()
    conn.fetchrow.side_effect = Exception('relation "connector_grants" does not exist')

    with patch(
        "app.repositories.connector_grant_repository._get_pool",
        new_callable=AsyncMock,
        return_value=pool,
    ):
        from app.repositories.connector_grant_repository import upsert_connector_grant

        result = await upsert_connector_grant(
            user_id="user-1",
            connector_id="holilihu-lms",
            host_type="lms",
        )

    assert result is None


@pytest.mark.asyncio
async def test_list_connector_grants_formats_rows():
    pool, conn = _make_pool()
    now = datetime.now(timezone.utc)
    conn.fetch.return_value = [
        {
            "id": "grant-1",
            "user_id": "user-1",
            "connector_id": "holilihu-lms",
            "grant_key": "holilihu-lms:teacher-1:org-1",
            "host_type": "lms",
            "host_name": "Holilihu LMS",
            "host_user_id": "teacher-1",
            "host_workspace_id": "org-1",
            "host_organization_id": "org-1",
            "organization_id": "org-1",
            "granted_capabilities": {"host_actions": True},
            "auth_metadata": {"role_source": "lms_host"},
            "status": "active",
            "created_at": now,
            "updated_at": now,
            "last_connected_at": now,
            "last_used_at": now,
        }
    ]

    with patch(
        "app.repositories.connector_grant_repository._get_pool",
        new_callable=AsyncMock,
        return_value=pool,
    ):
        from app.repositories.connector_grant_repository import list_connector_grants_for_user

        grants = await list_connector_grants_for_user("user-1")

    assert len(grants) == 1
    assert grants[0]["connector_id"] == "holilihu-lms"
    assert grants[0]["granted_capabilities"]["host_actions"] is True
    assert isinstance(grants[0]["last_used_at"], str)


@pytest.mark.asyncio
async def test_count_connector_grants_missing_table_returns_zero():
    pool, conn = _make_pool()
    conn.fetchval.side_effect = Exception('relation "connector_grants" does not exist')

    with patch(
        "app.repositories.connector_grant_repository._get_pool",
        new_callable=AsyncMock,
        return_value=pool,
    ):
        from app.repositories.connector_grant_repository import count_connector_grants_for_user

        count = await count_connector_grants_for_user("user-1")

    assert count == 0
