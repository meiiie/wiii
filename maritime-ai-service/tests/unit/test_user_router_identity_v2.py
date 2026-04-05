from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_get_my_profile_returns_platform_identity_and_workspace_count():
    from app.auth.user_router import get_my_profile
    from app.core.security import AuthenticatedUser

    auth = AuthenticatedUser(
        user_id="user-1",
        auth_method="jwt",
        role="teacher",
        platform_role="user",
        organization_role="member",
        host_role=None,
        role_source="jwt",
        organization_id="org-wiii",
        connector_id=None,
        identity_version="2",
    )

    with (
        patch("app.auth.user_router._extract_jwt_user", return_value={"sub": "user-1"}),
        patch(
            "app.auth.user_service.get_user",
            new_callable=AsyncMock,
            return_value={
                "id": "user-1",
                "email": "user@example.com",
                "name": "Wiii User",
                "avatar_url": None,
                "role": "student",
                "platform_role": "user",
                "is_active": True,
            },
        ),
        patch(
            "app.auth.user_router._count_connected_workspaces",
            new_callable=AsyncMock,
            return_value=3,
        ),
    ):
        result = await get_my_profile(request=MagicMock(), auth=auth)

    assert result.platform_role == "user"
    assert result.organization_role == "member"
    assert result.active_organization_id == "org-wiii"
    assert result.connected_workspaces_count == 3
    assert result.legacy_role == "student"


@pytest.mark.asyncio
async def test_list_my_connected_workspaces_returns_grants():
    from app.auth.user_router import list_my_connected_workspaces
    from app.core.security import AuthenticatedUser

    auth = AuthenticatedUser(
        user_id="user-1",
        auth_method="jwt",
        role="teacher",
        platform_role="user",
        role_source="jwt",
        identity_version="2",
    )

    grants = [
        {
            "id": "grant-1",
            "connector_id": "holilihu-lms",
            "grant_key": "holilihu-lms:teacher-1:org-1",
            "host_type": "lms",
            "host_name": "Holilihu LMS",
            "host_user_id": "teacher-1",
            "host_workspace_id": "org-1",
            "host_organization_id": "org-1",
            "organization_id": "org-1",
            "granted_capabilities": {"course_generation": True},
            "auth_metadata": {"role_source": "lms_host"},
            "status": "active",
            "created_at": None,
            "updated_at": None,
            "last_connected_at": None,
            "last_used_at": None,
        }
    ]

    with patch(
        "app.repositories.connector_grant_repository.list_connector_grants_for_user",
        new_callable=AsyncMock,
        return_value=grants,
    ):
        result = await list_my_connected_workspaces(auth=auth)

    assert len(result) == 1
    assert result[0].connector_id == "holilihu-lms"
    assert result[0].granted_capabilities["course_generation"] is True
