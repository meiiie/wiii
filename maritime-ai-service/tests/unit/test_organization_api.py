"""
Tests for Organization API endpoints.

Sprint 24: Multi-Organization Architecture.

Verifies:
- CRUD endpoints (mock repository)
- Auth: admin required for create/update/delete
- User can list own orgs
- Feature gate: 404 when multi-tenant disabled
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from fastapi import HTTPException

from app.api.v1.organizations import (
    list_organizations,
    get_organization,
    create_organization,
    update_organization,
    delete_organization,
    add_member,
    remove_member,
    list_members,
    my_organizations,
    _require_multi_tenant,
    _require_admin,
)
from app.core.security import AuthenticatedUser
from app.models.organization import (
    AddMemberRequest,
    OrganizationCreate,
    OrganizationResponse,
    OrganizationUpdate,
    UserOrganizationResponse,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_request():
    """Real starlette Request for rate-limited endpoints (slowapi validates type)."""
    from starlette.requests import Request

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/organizations",
        "headers": [],
        "query_string": b"",
        "root_path": "",
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


@pytest.fixture
def admin_user():
    return AuthenticatedUser(
        user_id="admin-1", auth_method="api_key", role="admin"
    )


@pytest.fixture
def student_user():
    return AuthenticatedUser(
        user_id="student-1", auth_method="api_key", role="student"
    )


@pytest.fixture
def sample_org():
    return OrganizationResponse(
        id="lms-hang-hai",
        name="LMS Hang Hai",
        allowed_domains=["maritime"],
        is_active=True,
    )


# =============================================================================
# Feature gate
# =============================================================================


class TestFeatureGate:
    @patch("app.api.v1.organizations.settings")
    def test_require_multi_tenant_disabled(self, mock_settings):
        mock_settings.enable_multi_tenant = False
        with pytest.raises(HTTPException) as exc_info:
            _require_multi_tenant()
        assert exc_info.value.status_code == 404

    @patch("app.api.v1.organizations.settings")
    def test_require_multi_tenant_enabled(self, mock_settings):
        mock_settings.enable_multi_tenant = True
        _require_multi_tenant()  # Should not raise


class TestRequireAdmin:
    def test_admin_passes(self, admin_user):
        _require_admin(admin_user)  # No exception

    def test_student_rejected(self, student_user):
        with pytest.raises(HTTPException) as exc_info:
            _require_admin(student_user)
        assert exc_info.value.status_code == 403


# =============================================================================
# List Organizations
# =============================================================================


class TestListOrganizations:
    @pytest.mark.asyncio
    @patch("app.api.v1.organizations.settings")
    @patch("app.api.v1.organizations.get_organization_repository")
    async def test_admin_sees_all(self, mock_repo_fn, mock_settings, admin_user, sample_org, mock_request):
        mock_settings.enable_multi_tenant = True
        mock_repo = MagicMock()
        mock_repo.list_organizations.return_value = [sample_org]
        mock_repo_fn.return_value = mock_repo

        result = await list_organizations(request=mock_request, auth=admin_user)
        assert len(result) == 1
        mock_repo.list_organizations.assert_called_once_with(active_only=False)

    @pytest.mark.asyncio
    @patch("app.api.v1.organizations.settings")
    @patch("app.api.v1.organizations.get_organization_repository")
    async def test_student_sees_own(self, mock_repo_fn, mock_settings, student_user, sample_org, mock_request):
        mock_settings.enable_multi_tenant = True
        mock_repo = MagicMock()
        uo = UserOrganizationResponse(
            user_id="student-1",
            organization_id="lms-hang-hai",
            organization=sample_org,
        )
        mock_repo.get_user_organizations.return_value = [uo]
        mock_repo_fn.return_value = mock_repo

        result = await list_organizations(request=mock_request, auth=student_user)
        assert len(result) == 1
        assert result[0].id == "lms-hang-hai"


# =============================================================================
# Get Organization
# =============================================================================


class TestGetOrganization:
    @pytest.mark.asyncio
    @patch("app.api.v1.organizations.settings")
    @patch("app.api.v1.organizations.get_organization_repository")
    async def test_admin_get(self, mock_repo_fn, mock_settings, admin_user, sample_org, mock_request):
        mock_settings.enable_multi_tenant = True
        mock_repo = MagicMock()
        mock_repo.get_organization.return_value = sample_org
        mock_repo_fn.return_value = mock_repo

        result = await get_organization(request=mock_request, org_id="lms-hang-hai", auth=admin_user)
        assert result.id == "lms-hang-hai"

    @pytest.mark.asyncio
    @patch("app.api.v1.organizations.settings")
    @patch("app.api.v1.organizations.get_organization_repository")
    async def test_not_found(self, mock_repo_fn, mock_settings, admin_user, mock_request):
        mock_settings.enable_multi_tenant = True
        mock_repo = MagicMock()
        mock_repo.get_organization.return_value = None
        mock_repo_fn.return_value = mock_repo

        with pytest.raises(HTTPException) as exc_info:
            await get_organization(request=mock_request, org_id="nonexistent", auth=admin_user)
        assert exc_info.value.status_code == 404


# =============================================================================
# Create Organization
# =============================================================================


class TestCreateOrganization:
    @pytest.mark.asyncio
    @patch("app.api.v1.organizations.settings")
    @patch("app.api.v1.organizations.get_organization_repository")
    async def test_create_success(self, mock_repo_fn, mock_settings, admin_user, sample_org, mock_request):
        mock_settings.enable_multi_tenant = True
        mock_repo = MagicMock()
        mock_repo.get_organization.return_value = None  # No duplicate
        mock_repo.create_organization.return_value = sample_org
        mock_repo_fn.return_value = mock_repo

        body = OrganizationCreate(id="lms-hang-hai", name="LMS Hang Hai")
        result = await create_organization(request=mock_request, body=body, auth=admin_user)
        assert result.id == "lms-hang-hai"

    @pytest.mark.asyncio
    @patch("app.api.v1.organizations.settings")
    @patch("app.api.v1.organizations.get_organization_repository")
    async def test_create_duplicate(self, mock_repo_fn, mock_settings, admin_user, sample_org, mock_request):
        mock_settings.enable_multi_tenant = True
        mock_repo = MagicMock()
        mock_repo.get_organization.return_value = sample_org  # Already exists
        mock_repo_fn.return_value = mock_repo

        body = OrganizationCreate(id="lms-hang-hai", name="LMS Hang Hai")
        with pytest.raises(HTTPException) as exc_info:
            await create_organization(request=mock_request, body=body, auth=admin_user)
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    @patch("app.api.v1.organizations.settings")
    async def test_create_not_admin(self, mock_settings, student_user, mock_request):
        mock_settings.enable_multi_tenant = True
        body = OrganizationCreate(id="x", name="Y")
        with pytest.raises(HTTPException) as exc_info:
            await create_organization(request=mock_request, body=body, auth=student_user)
        assert exc_info.value.status_code == 403


# =============================================================================
# Delete Organization
# =============================================================================


class TestDeleteOrganization:
    @pytest.mark.asyncio
    @patch("app.api.v1.organizations.settings")
    @patch("app.api.v1.organizations.get_organization_repository")
    async def test_delete_success(self, mock_repo_fn, mock_settings, admin_user, mock_request):
        mock_settings.enable_multi_tenant = True
        mock_repo = MagicMock()
        mock_repo.delete_organization.return_value = True
        mock_repo_fn.return_value = mock_repo

        await delete_organization(request=mock_request, org_id="org-1", auth=admin_user)

    @pytest.mark.asyncio
    @patch("app.api.v1.organizations.settings")
    async def test_delete_default_rejected(self, mock_settings, admin_user, mock_request):
        mock_settings.enable_multi_tenant = True
        with pytest.raises(HTTPException) as exc_info:
            await delete_organization(request=mock_request, org_id="default", auth=admin_user)
        assert exc_info.value.status_code == 400


# =============================================================================
# Membership
# =============================================================================


class TestMembership:
    @pytest.mark.asyncio
    @patch("app.api.v1.organizations.settings")
    @patch("app.api.v1.organizations.get_organization_repository")
    async def test_add_member(self, mock_repo_fn, mock_settings, admin_user, sample_org, mock_request):
        mock_settings.enable_multi_tenant = True
        mock_repo = MagicMock()
        mock_repo.get_organization.return_value = sample_org
        mock_repo.add_user_to_org.return_value = True
        mock_repo_fn.return_value = mock_repo

        body = AddMemberRequest(user_id="user-1")
        result = await add_member(request=mock_request, org_id="lms-hang-hai", body=body, auth=admin_user)
        assert result["user_id"] == "user-1"

    @pytest.mark.asyncio
    @patch("app.api.v1.organizations.settings")
    @patch("app.api.v1.organizations.get_organization_repository")
    async def test_remove_member_not_found(self, mock_repo_fn, mock_settings, admin_user, mock_request):
        mock_settings.enable_multi_tenant = True
        mock_repo = MagicMock()
        mock_repo.remove_user_from_org.return_value = False
        mock_repo_fn.return_value = mock_repo

        with pytest.raises(HTTPException) as exc_info:
            await remove_member(request=mock_request, org_id="org-1", user_id="user-x", auth=admin_user)
        assert exc_info.value.status_code == 404
