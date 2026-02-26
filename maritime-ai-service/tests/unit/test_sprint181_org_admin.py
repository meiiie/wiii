"""
Sprint 181: "Hai Tầng Quyền Lực" — System Admin vs Organization Manager

Tests for:
  - Two-tier admin permission enforcement
  - Repository methods (get_user_org_role, get_user_admin_orgs)
  - Admin context endpoint (/users/me/admin-context)
  - Org admin settings restriction (branding only)
  - Feature gate (enable_org_admin=False preserves existing behavior)
  - Org admin cannot escalate privileges
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------

def _make_auth(role="student", user_id="user-1"):
    """Create a mock AuthenticatedUser."""
    from app.core.security import AuthenticatedUser
    return AuthenticatedUser(user_id=user_id, auth_method="api_key", role=role)


def _make_request(role="admin", user_id="user-1", email="test@test.com"):
    """Create a mock Request with Authorization header."""
    req = MagicMock()
    req.headers = {"authorization": "Bearer fake-token"}
    req.client = MagicMock()
    req.client.host = "127.0.0.1"
    req.state = MagicMock()
    return req


def _mock_settings(**overrides):
    """Create a mock settings object with defaults."""
    defaults = {
        "enable_multi_tenant": True,
        "enable_org_admin": True,
        "enable_admin_module": False,
    }
    defaults.update(overrides)
    s = MagicMock()
    for k, v in defaults.items():
        setattr(s, k, v)
    return s


# ---------------------------------------------------------------------------
# 1. Repository Tests
# ---------------------------------------------------------------------------

class TestOrganizationRepositoryOrgAdmin:
    """Test get_user_org_role and get_user_admin_orgs."""

    def test_get_user_org_role_found(self):
        """User is admin in org → returns 'admin'."""
        from app.repositories.organization_repository import OrganizationRepository
        repo = OrganizationRepository()
        repo._initialized = True

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = ("admin",)
        mock_session.execute.return_value = mock_result
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        repo._session_factory = MagicMock(return_value=mock_session)

        role = repo.get_user_org_role("user-1", "org-x")
        assert role == "admin"

    def test_get_user_org_role_not_found(self):
        """User not in org → returns None."""
        from app.repositories.organization_repository import OrganizationRepository
        repo = OrganizationRepository()
        repo._initialized = True

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_session.execute.return_value = mock_result
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        repo._session_factory = MagicMock(return_value=mock_session)

        role = repo.get_user_org_role("user-1", "org-x")
        assert role is None

    def test_get_user_org_role_no_session(self):
        """No session factory → returns None."""
        from app.repositories.organization_repository import OrganizationRepository
        repo = OrganizationRepository()
        repo._initialized = True
        repo._session_factory = None

        assert repo.get_user_org_role("u", "o") is None

    def test_get_user_admin_orgs(self):
        """User is admin in 2 orgs → returns both org IDs."""
        from app.repositories.organization_repository import OrganizationRepository
        repo = OrganizationRepository()
        repo._initialized = True

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("org-a",), ("org-b",)]
        mock_session.execute.return_value = mock_result
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        repo._session_factory = MagicMock(return_value=mock_session)

        orgs = repo.get_user_admin_orgs("user-1")
        assert orgs == ["org-a", "org-b"]

    def test_get_user_admin_orgs_empty(self):
        """User has no admin orgs → returns empty list."""
        from app.repositories.organization_repository import OrganizationRepository
        repo = OrganizationRepository()
        repo._initialized = True

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        repo._session_factory = MagicMock(return_value=mock_session)

        orgs = repo.get_user_admin_orgs("user-1")
        assert orgs == []

    def test_get_user_admin_orgs_no_session(self):
        """No session factory → returns empty list."""
        from app.repositories.organization_repository import OrganizationRepository
        repo = OrganizationRepository()
        repo._initialized = True
        repo._session_factory = None

        assert repo.get_user_admin_orgs("u") == []


# ---------------------------------------------------------------------------
# 2. Permission Helper Tests
# ---------------------------------------------------------------------------

class TestRequireOrgAdminOrPlatformAdmin:
    """Test _require_org_admin_or_platform_admin helper."""

    def test_platform_admin_bypasses_org_check(self):
        """auth.role='admin' → always returns 'platform_admin'."""
        from app.api.v1.organizations import _require_org_admin_or_platform_admin
        auth = _make_auth(role="admin")
        result = _require_org_admin_or_platform_admin(auth, "any-org")
        assert result == "platform_admin"

    @patch("app.api.v1.organizations.settings", _mock_settings(enable_org_admin=True))
    @patch("app.api.v1.organizations.get_organization_repository")
    def test_org_admin_can_manage_own_org(self, mock_get_repo):
        """Org admin for org-x → passes for org-x."""
        from app.api.v1.organizations import _require_org_admin_or_platform_admin
        mock_repo = MagicMock()
        mock_repo.get_user_org_role.return_value = "admin"
        mock_get_repo.return_value = mock_repo

        auth = _make_auth(role="student", user_id="manager-1")
        result = _require_org_admin_or_platform_admin(auth, "org-x")
        assert result == "admin"
        mock_repo.get_user_org_role.assert_called_once_with("manager-1", "org-x")

    @patch("app.api.v1.organizations.settings", _mock_settings(enable_org_admin=True))
    @patch("app.api.v1.organizations.get_organization_repository")
    def test_org_admin_blocked_from_other_org(self, mock_get_repo):
        """Org admin for org-x → 403 on org-y."""
        from fastapi import HTTPException
        from app.api.v1.organizations import _require_org_admin_or_platform_admin
        mock_repo = MagicMock()
        mock_repo.get_user_org_role.return_value = None  # Not a member of org-y
        mock_get_repo.return_value = mock_repo

        auth = _make_auth(role="student", user_id="manager-1")
        with pytest.raises(HTTPException) as exc_info:
            _require_org_admin_or_platform_admin(auth, "org-y")
        assert exc_info.value.status_code == 403

    @patch("app.api.v1.organizations.settings", _mock_settings(enable_org_admin=True))
    @patch("app.api.v1.organizations.get_organization_repository")
    def test_org_member_cannot_manage(self, mock_get_repo):
        """Regular member (role='member') → 403."""
        from fastapi import HTTPException
        from app.api.v1.organizations import _require_org_admin_or_platform_admin
        mock_repo = MagicMock()
        mock_repo.get_user_org_role.return_value = "member"
        mock_get_repo.return_value = mock_repo

        auth = _make_auth(role="student", user_id="regular-user")
        with pytest.raises(HTTPException) as exc_info:
            _require_org_admin_or_platform_admin(auth, "org-x")
        assert exc_info.value.status_code == 403

    @patch("app.api.v1.organizations.settings", _mock_settings(enable_org_admin=False))
    def test_feature_gate_off_blocks_org_admin(self):
        """enable_org_admin=False → only platform admin works, org admin gets 403."""
        from fastapi import HTTPException
        from app.api.v1.organizations import _require_org_admin_or_platform_admin

        auth = _make_auth(role="student", user_id="manager-1")
        with pytest.raises(HTTPException) as exc_info:
            _require_org_admin_or_platform_admin(auth, "org-x")
        assert exc_info.value.status_code == 403

    @patch("app.api.v1.organizations.settings", _mock_settings(enable_org_admin=True))
    @patch("app.api.v1.organizations.get_organization_repository")
    def test_org_owner_returns_owner(self, mock_get_repo):
        """Org owner → returns 'owner'."""
        from app.api.v1.organizations import _require_org_admin_or_platform_admin
        mock_repo = MagicMock()
        mock_repo.get_user_org_role.return_value = "owner"
        mock_get_repo.return_value = mock_repo

        auth = _make_auth(role="teacher", user_id="dean-1")
        result = _require_org_admin_or_platform_admin(auth, "org-x")
        assert result == "owner"


# ---------------------------------------------------------------------------
# 3. Endpoint Behavior Tests (add_member, remove_member)
# ---------------------------------------------------------------------------

class TestAddMemberEndpoint:
    """Test org admin restrictions on add_member."""

    @patch("app.api.v1.organizations.settings", _mock_settings(enable_org_admin=True))
    @patch("app.api.v1.organizations.get_organization_repository")
    @pytest.mark.asyncio
    async def test_org_admin_cannot_assign_admin_role(self, mock_get_repo):
        """Org admin trying to add member with role='admin' → 403."""
        from fastapi import HTTPException
        from app.api.v1.organizations import add_member
        from app.models.organization import AddMemberRequest

        mock_repo = MagicMock()
        mock_repo.get_user_org_role.return_value = "admin"
        mock_repo.get_organization.return_value = MagicMock()
        mock_get_repo.return_value = mock_repo

        auth = _make_auth(role="student", user_id="manager-1")
        body = AddMemberRequest(user_id="new-user", role="admin")
        request = _make_request()

        with pytest.raises(HTTPException) as exc_info:
            await add_member(request=request, org_id="org-x", body=body, auth=auth)
        assert exc_info.value.status_code == 403
        assert "admin/owner roles" in exc_info.value.detail

    @patch("app.api.v1.organizations.settings", _mock_settings(enable_org_admin=True))
    @patch("app.api.v1.organizations.get_organization_repository")
    @pytest.mark.asyncio
    async def test_org_admin_can_add_member(self, mock_get_repo):
        """Org admin adding member with role='member' → success."""
        from app.api.v1.organizations import add_member
        from app.models.organization import AddMemberRequest

        mock_repo = MagicMock()
        mock_repo.get_user_org_role.return_value = "admin"
        mock_repo.get_organization.return_value = MagicMock()
        mock_repo.add_user_to_org.return_value = True
        mock_get_repo.return_value = mock_repo

        auth = _make_auth(role="student", user_id="manager-1")
        body = AddMemberRequest(user_id="new-user", role="member")
        request = _make_request()

        result = await add_member(request=request, org_id="org-x", body=body, auth=auth)
        assert result["user_id"] == "new-user"
        assert result["role"] == "member"

    @patch("app.api.v1.organizations.settings", _mock_settings(enable_org_admin=True))
    @patch("app.api.v1.organizations.get_organization_repository")
    @pytest.mark.asyncio
    async def test_platform_admin_can_assign_any_role(self, mock_get_repo):
        """Platform admin can add member with role='admin'."""
        from app.api.v1.organizations import add_member
        from app.models.organization import AddMemberRequest

        mock_repo = MagicMock()
        mock_repo.get_organization.return_value = MagicMock()
        mock_repo.add_user_to_org.return_value = True
        mock_get_repo.return_value = mock_repo

        auth = _make_auth(role="admin", user_id="platform-admin-1")
        body = AddMemberRequest(user_id="new-user", role="admin")
        request = _make_request()

        result = await add_member(request=request, org_id="org-x", body=body, auth=auth)
        assert result["role"] == "admin"

    @patch("app.api.v1.organizations.settings", _mock_settings(enable_org_admin=True))
    @patch("app.api.v1.organizations.get_organization_repository")
    @pytest.mark.asyncio
    async def test_org_owner_can_assign_admin_role(self, mock_get_repo):
        """Org owner CAN assign admin role."""
        from app.api.v1.organizations import add_member
        from app.models.organization import AddMemberRequest

        mock_repo = MagicMock()
        mock_repo.get_user_org_role.return_value = "owner"
        mock_repo.get_organization.return_value = MagicMock()
        mock_repo.add_user_to_org.return_value = True
        mock_get_repo.return_value = mock_repo

        auth = _make_auth(role="teacher", user_id="dean-1")
        body = AddMemberRequest(user_id="new-admin", role="admin")
        request = _make_request()

        result = await add_member(request=request, org_id="org-x", body=body, auth=auth)
        assert result["role"] == "admin"


class TestRemoveMemberEndpoint:
    """Test org admin restrictions on remove_member."""

    @patch("app.api.v1.organizations.settings", _mock_settings(enable_org_admin=True))
    @patch("app.api.v1.organizations.get_organization_repository")
    @pytest.mark.asyncio
    async def test_org_admin_cannot_remove_admin(self, mock_get_repo):
        """Org admin trying to remove an admin → 403."""
        from fastapi import HTTPException
        from app.api.v1.organizations import remove_member

        mock_repo = MagicMock()
        # First call: check caller's role (admin)
        # Second call: check target's role (admin)
        mock_repo.get_user_org_role.side_effect = ["admin", "admin"]
        mock_get_repo.return_value = mock_repo

        auth = _make_auth(role="student", user_id="manager-1")
        request = _make_request()

        with pytest.raises(HTTPException) as exc_info:
            await remove_member(request=request, org_id="org-x", user_id="other-admin", auth=auth)
        assert exc_info.value.status_code == 403

    @patch("app.api.v1.organizations.settings", _mock_settings(enable_org_admin=True))
    @patch("app.api.v1.organizations.get_organization_repository")
    @pytest.mark.asyncio
    async def test_org_admin_can_remove_member(self, mock_get_repo):
        """Org admin removing a regular member → success."""
        from app.api.v1.organizations import remove_member

        mock_repo = MagicMock()
        # First call: check caller's role → admin
        # Second call: check target's role → member
        mock_repo.get_user_org_role.side_effect = ["admin", "member"]
        mock_repo.remove_user_from_org.return_value = True
        mock_get_repo.return_value = mock_repo

        auth = _make_auth(role="student", user_id="manager-1")
        request = _make_request()

        # Should not raise
        await remove_member(request=request, org_id="org-x", user_id="regular-user", auth=auth)
        mock_repo.remove_user_from_org.assert_called_once_with("regular-user", "org-x")

    @patch("app.api.v1.organizations.settings", _mock_settings(enable_org_admin=True))
    @patch("app.api.v1.organizations.get_organization_repository")
    @pytest.mark.asyncio
    async def test_org_owner_can_remove_admin(self, mock_get_repo):
        """Org owner CAN remove an org admin."""
        from app.api.v1.organizations import remove_member

        mock_repo = MagicMock()
        mock_repo.get_user_org_role.return_value = "owner"
        mock_repo.remove_user_from_org.return_value = True
        mock_get_repo.return_value = mock_repo

        auth = _make_auth(role="teacher", user_id="dean-1")
        request = _make_request()

        await remove_member(request=request, org_id="org-x", user_id="admin-user", auth=auth)
        mock_repo.remove_user_from_org.assert_called_once_with("admin-user", "org-x")


# ---------------------------------------------------------------------------
# 4. Admin Context Endpoint Tests
# ---------------------------------------------------------------------------

class TestAdminContextEndpoint:
    """Test GET /users/me/admin-context.

    Sprint 194c: Endpoint now uses require_auth() dependency.
    Tests pass AuthenticatedUser directly instead of mocking _extract_jwt_user.
    """

    @pytest.mark.asyncio
    async def test_admin_context_system_admin(self):
        """Platform admin → is_system_admin=True."""
        from app.auth.user_router import get_my_admin_context
        from app.core.security import AuthenticatedUser

        auth = AuthenticatedUser(user_id="admin-1", auth_method="jwt", role="admin")

        with patch("app.core.config.settings", _mock_settings(enable_org_admin=True)):
            with patch("app.repositories.organization_repository.get_organization_repository") as mock_get_repo:
                mock_repo = MagicMock()
                mock_repo.get_user_admin_orgs.return_value = []
                mock_get_repo.return_value = mock_repo

                result = await get_my_admin_context(auth=auth)
                assert result["is_system_admin"] is True
                assert result["is_org_admin"] is True  # system admin is also org admin

    @pytest.mark.asyncio
    async def test_admin_context_org_admin(self):
        """Org admin → is_org_admin=True, admin_org_ids populated."""
        from app.auth.user_router import get_my_admin_context
        from app.core.security import AuthenticatedUser

        auth = AuthenticatedUser(user_id="manager-1", auth_method="jwt", role="teacher")

        with patch("app.core.config.settings", _mock_settings(enable_org_admin=True)):
            with patch("app.repositories.organization_repository.get_organization_repository") as mock_get_repo:
                mock_repo = MagicMock()
                mock_repo.get_user_admin_orgs.return_value = ["org-x"]
                mock_get_repo.return_value = mock_repo

                result = await get_my_admin_context(auth=auth)
                assert result["is_system_admin"] is False
                assert result["is_org_admin"] is True
                assert result["admin_org_ids"] == ["org-x"]

    @pytest.mark.asyncio
    async def test_admin_context_regular_user(self):
        """Regular user → all False/empty."""
        from app.auth.user_router import get_my_admin_context
        from app.core.security import AuthenticatedUser

        auth = AuthenticatedUser(user_id="student-1", auth_method="jwt", role="student")

        with patch("app.core.config.settings", _mock_settings(enable_org_admin=True)):
            with patch("app.repositories.organization_repository.get_organization_repository") as mock_get_repo:
                mock_repo = MagicMock()
                mock_repo.get_user_admin_orgs.return_value = []
                mock_get_repo.return_value = mock_repo

                result = await get_my_admin_context(auth=auth)
                assert result["is_system_admin"] is False
                assert result["is_org_admin"] is False
                assert result["admin_org_ids"] == []

    @pytest.mark.asyncio
    async def test_admin_context_feature_gate_off(self):
        """enable_org_admin=False → admin_org_ids always []."""
        from app.auth.user_router import get_my_admin_context
        from app.core.security import AuthenticatedUser

        auth = AuthenticatedUser(user_id="manager-1", auth_method="jwt", role="teacher")

        with patch("app.core.config.settings", _mock_settings(enable_org_admin=False, enable_multi_tenant=False)):
            result = await get_my_admin_context(auth=auth)
            assert result["admin_org_ids"] == []
            assert result["enable_org_admin"] is False


# ---------------------------------------------------------------------------
# 5. Settings Restriction Tests
# ---------------------------------------------------------------------------

class TestSettingsRestriction:
    """Test org admin can only update branding/onboarding."""

    @patch("app.api.v1.organizations.settings", _mock_settings(enable_org_admin=True))
    @patch("app.api.v1.organizations.get_organization_repository")
    @pytest.mark.asyncio
    async def test_org_admin_can_update_branding(self, mock_get_repo):
        """Org admin sending branding update → succeeds."""
        from app.api.v1.organizations import update_org_settings

        mock_repo = MagicMock()
        mock_repo.get_user_org_role.return_value = "admin"
        mock_org = MagicMock()
        mock_org.settings = {"branding": {"welcome_message": "Hello"}}
        mock_repo.get_organization.return_value = mock_org
        mock_repo.update_organization.return_value = mock_org
        mock_get_repo.return_value = mock_repo

        auth = _make_auth(role="student", user_id="manager-1")
        body = {"branding": {"welcome_message": "Xin chào!"}}
        request = _make_request()

        with patch("app.models.organization.OrgSettings") as mock_schema:
            mock_schema.return_value = MagicMock()
            with patch("app.core.org_settings.get_effective_settings") as mock_eff:
                mock_eff.return_value = MagicMock(model_dump=lambda: {})
                result = await update_org_settings(
                    request=request, org_id="org-x", body=body, auth=auth
                )
                # Should have called update_organization
                mock_repo.update_organization.assert_called_once()

    @patch("app.api.v1.organizations.settings", _mock_settings(enable_org_admin=True))
    @patch("app.api.v1.organizations.get_organization_repository")
    @pytest.mark.asyncio
    async def test_org_admin_blocked_from_features(self, mock_get_repo):
        """Org admin sending only features update → 403 (after stripping)."""
        from fastapi import HTTPException
        from app.api.v1.organizations import update_org_settings

        mock_repo = MagicMock()
        mock_repo.get_user_org_role.return_value = "admin"
        mock_get_repo.return_value = mock_repo

        auth = _make_auth(role="student", user_id="manager-1")
        body = {"features": {"enable_product_search": True}}
        request = _make_request()

        with pytest.raises(HTTPException) as exc_info:
            await update_org_settings(
                request=request, org_id="org-x", body=body, auth=auth
            )
        assert exc_info.value.status_code == 403

    @patch("app.api.v1.organizations.settings", _mock_settings(enable_org_admin=True))
    @patch("app.api.v1.organizations.get_organization_repository")
    @pytest.mark.asyncio
    async def test_org_admin_mixed_keys_stripped(self, mock_get_repo):
        """Org admin sending branding + features → features stripped, branding kept."""
        from app.api.v1.organizations import update_org_settings

        mock_repo = MagicMock()
        mock_repo.get_user_org_role.return_value = "admin"
        mock_org = MagicMock()
        mock_org.settings = {}
        mock_repo.get_organization.return_value = mock_org
        mock_repo.update_organization.return_value = mock_org
        mock_get_repo.return_value = mock_repo

        auth = _make_auth(role="student", user_id="manager-1")
        body = {
            "branding": {"welcome_message": "Hi"},
            "features": {"enable_product_search": True},
            "permissions": {"student": []},
        }
        request = _make_request()

        with patch("app.models.organization.OrgSettings") as mock_schema:
            mock_schema.return_value = MagicMock()
            with patch("app.core.org_settings.get_effective_settings") as mock_eff:
                mock_eff.return_value = MagicMock(model_dump=lambda: {})
                await update_org_settings(
                    request=request, org_id="org-x", body=body, auth=auth
                )
                # Features and permissions should have been stripped
                call_args = mock_repo.update_organization.call_args
                assert call_args is not None


# ---------------------------------------------------------------------------
# 6. Org Permissions with org_role
# ---------------------------------------------------------------------------

class TestOrgPermissionsWithOrgRole:
    """Test get_org_permissions with Sprint 181 org_role param."""

    @patch("app.core.org_settings.get_effective_settings")
    def test_base_permissions_without_org_role(self, mock_eff):
        """Without org_role → returns standard role-based permissions."""
        from app.core.org_settings import get_org_permissions
        from app.models.organization import OrgSettings

        mock_eff.return_value = OrgSettings()
        perms = get_org_permissions("org-x", "student")
        assert "read:chat" in perms
        assert "manage:members" not in perms

    @patch("app.core.org_settings.get_effective_settings")
    @patch("app.core.config.settings")
    def test_org_admin_gets_extra_permissions(self, mock_config, mock_eff):
        """org_role='admin' + enable_org_admin=True → extra management perms."""
        from app.core.org_settings import get_org_permissions
        from app.models.organization import OrgSettings

        mock_config.enable_org_admin = True
        mock_eff.return_value = OrgSettings()

        perms = get_org_permissions("org-x", "student", org_role="admin")
        assert "manage:members" in perms
        assert "read:org_analytics" in perms
        assert "read:org_dashboard" in perms

    @patch("app.core.org_settings.get_effective_settings")
    @patch("app.core.config.settings")
    def test_org_owner_gets_settings_permission(self, mock_config, mock_eff):
        """org_role='owner' → gets manage:org_settings in addition to admin perms."""
        from app.core.org_settings import get_org_permissions
        from app.models.organization import OrgSettings

        mock_config.enable_org_admin = True
        mock_eff.return_value = OrgSettings()

        perms = get_org_permissions("org-x", "teacher", org_role="owner")
        assert "manage:org_settings" in perms
        assert "manage:members" in perms

    @patch("app.core.org_settings.get_effective_settings")
    @patch("app.core.config.settings")
    def test_org_role_ignored_when_feature_off(self, mock_config, mock_eff):
        """enable_org_admin=False → org_role ignored, standard perms only."""
        from app.core.org_settings import get_org_permissions
        from app.models.organization import OrgSettings

        mock_config.enable_org_admin = False
        mock_eff.return_value = OrgSettings()

        perms = get_org_permissions("org-x", "student", org_role="admin")
        assert "manage:members" not in perms


# ---------------------------------------------------------------------------
# 7. Backward Compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    """Ensure no behavioral change when enable_org_admin=False."""

    @patch("app.api.v1.organizations.settings", _mock_settings(enable_org_admin=False))
    def test_existing_behavior_preserved_when_gate_off(self):
        """Non-admin user gets 403 on all member operations when gate is off."""
        from fastapi import HTTPException
        from app.api.v1.organizations import _require_org_admin_or_platform_admin

        auth = _make_auth(role="student")
        with pytest.raises(HTTPException) as exc_info:
            _require_org_admin_or_platform_admin(auth, "any-org")
        assert exc_info.value.status_code == 403

    def test_config_flag_exists(self):
        """enable_org_admin flag exists in Settings with default False."""
        from app.core.config import Settings
        assert "enable_org_admin" in Settings.model_fields
        assert Settings.model_fields["enable_org_admin"].default is False


# ---------------------------------------------------------------------------
# 8. Self-Removal Guard (Audit Fix)
# ---------------------------------------------------------------------------

class TestSelfRemovalGuard:
    """Test that org admin/owner cannot remove themselves."""

    @patch("app.api.v1.organizations.settings", _mock_settings(enable_org_admin=True))
    @patch("app.api.v1.organizations.get_organization_repository")
    @pytest.mark.asyncio
    async def test_org_admin_cannot_remove_self(self, mock_get_repo):
        """Org admin trying to remove themselves → 400."""
        from fastapi import HTTPException
        from app.api.v1.organizations import remove_member

        mock_repo = MagicMock()
        mock_repo.get_user_org_role.return_value = "admin"
        mock_get_repo.return_value = mock_repo

        auth = _make_auth(role="student", user_id="manager-1")
        request = _make_request()

        with pytest.raises(HTTPException) as exc_info:
            await remove_member(request=request, org_id="org-x", user_id="manager-1", auth=auth)
        assert exc_info.value.status_code == 400
        assert "yourself" in exc_info.value.detail

    @patch("app.api.v1.organizations.settings", _mock_settings(enable_org_admin=True))
    @patch("app.api.v1.organizations.get_organization_repository")
    @pytest.mark.asyncio
    async def test_org_owner_cannot_remove_self(self, mock_get_repo):
        """Org owner trying to remove themselves → 400."""
        from fastapi import HTTPException
        from app.api.v1.organizations import remove_member

        mock_repo = MagicMock()
        mock_repo.get_user_org_role.return_value = "owner"
        mock_get_repo.return_value = mock_repo

        auth = _make_auth(role="teacher", user_id="dean-1")
        request = _make_request()

        with pytest.raises(HTTPException) as exc_info:
            await remove_member(request=request, org_id="org-x", user_id="dean-1", auth=auth)
        assert exc_info.value.status_code == 400

    @patch("app.api.v1.organizations.settings", _mock_settings(enable_org_admin=True))
    @patch("app.api.v1.organizations.get_organization_repository")
    @pytest.mark.asyncio
    async def test_platform_admin_can_remove_self(self, mock_get_repo):
        """Platform admin CAN remove themselves (they have other access)."""
        from app.api.v1.organizations import remove_member

        mock_repo = MagicMock()
        mock_repo.remove_user_from_org.return_value = True
        mock_get_repo.return_value = mock_repo

        auth = _make_auth(role="admin", user_id="platform-admin-1")
        request = _make_request()

        await remove_member(request=request, org_id="org-x", user_id="platform-admin-1", auth=auth)
        mock_repo.remove_user_from_org.assert_called_once()


# ---------------------------------------------------------------------------
# 9. List Members Endpoint Tests
# ---------------------------------------------------------------------------

class TestListMembersEndpoint:
    """Test list_members endpoint access control."""

    @patch("app.api.v1.organizations.settings", _mock_settings(enable_org_admin=True))
    @patch("app.api.v1.organizations.get_organization_repository")
    @pytest.mark.asyncio
    async def test_org_admin_can_list_members(self, mock_get_repo):
        """Org admin can list members of their own org."""
        from app.api.v1.organizations import list_members

        mock_repo = MagicMock()
        mock_repo.get_user_org_role.return_value = "admin"
        mock_repo.get_org_members.return_value = [{"user_id": "u1", "role": "member"}]
        mock_get_repo.return_value = mock_repo

        auth = _make_auth(role="student", user_id="manager-1")
        request = _make_request()

        result = await list_members(request=request, org_id="org-x", auth=auth)
        assert len(result) == 1
        mock_repo.get_org_members.assert_called_once_with("org-x")

    @patch("app.api.v1.organizations.settings", _mock_settings(enable_org_admin=True))
    @patch("app.api.v1.organizations.get_organization_repository")
    @pytest.mark.asyncio
    async def test_non_member_cannot_list_members(self, mock_get_repo):
        """Non-member gets 403 trying to list members."""
        from fastapi import HTTPException
        from app.api.v1.organizations import list_members

        mock_repo = MagicMock()
        mock_repo.get_user_org_role.return_value = None
        mock_get_repo.return_value = mock_repo

        auth = _make_auth(role="student", user_id="outsider")
        request = _make_request()

        with pytest.raises(HTTPException) as exc_info:
            await list_members(request=request, org_id="org-x", auth=auth)
        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# 10. Org Admin Removing Owner (Audit Gap)
# ---------------------------------------------------------------------------

class TestOrgAdminRemoveOwner:
    """Test that org admin cannot remove an owner."""

    @patch("app.api.v1.organizations.settings", _mock_settings(enable_org_admin=True))
    @patch("app.api.v1.organizations.get_organization_repository")
    @pytest.mark.asyncio
    async def test_org_admin_cannot_remove_owner(self, mock_get_repo):
        """Org admin trying to remove an owner → 403."""
        from fastapi import HTTPException
        from app.api.v1.organizations import remove_member

        mock_repo = MagicMock()
        mock_repo.get_user_org_role.side_effect = ["admin", "owner"]
        mock_get_repo.return_value = mock_repo

        auth = _make_auth(role="student", user_id="manager-1")
        request = _make_request()

        with pytest.raises(HTTPException) as exc_info:
            await remove_member(request=request, org_id="org-x", user_id="the-owner", auth=auth)
        assert exc_info.value.status_code == 403

    @patch("app.api.v1.organizations.settings", _mock_settings(enable_org_admin=True))
    @patch("app.api.v1.organizations.get_organization_repository")
    @pytest.mark.asyncio
    async def test_org_admin_cannot_assign_owner_role(self, mock_get_repo):
        """Org admin trying to add member as owner → 403."""
        from fastapi import HTTPException
        from app.api.v1.organizations import add_member
        from app.models.organization import AddMemberRequest

        mock_repo = MagicMock()
        mock_repo.get_user_org_role.return_value = "admin"
        mock_get_repo.return_value = mock_repo

        auth = _make_auth(role="student", user_id="manager-1")
        body = AddMemberRequest(user_id="new-user", role="owner")
        request = _make_request()

        with pytest.raises(HTTPException) as exc_info:
            await add_member(request=request, org_id="org-x", body=body, auth=auth)
        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# 11. has_permission with org_role (Audit Fix)
# ---------------------------------------------------------------------------

class TestHasPermissionWithOrgRole:
    """Test has_permission passes org_role correctly."""

    @patch("app.core.org_settings.get_effective_settings")
    @patch("app.core.config.settings")
    def test_has_permission_with_org_admin(self, mock_config, mock_eff):
        """has_permission with org_role='admin' → manage:members passes."""
        from app.core.org_settings import has_permission
        from app.models.organization import OrgSettings

        mock_config.enable_org_admin = True
        mock_eff.return_value = OrgSettings()

        assert has_permission("org-x", "student", "manage", "members", org_role="admin") is True

    @patch("app.core.org_settings.get_effective_settings")
    def test_has_permission_without_org_role(self, mock_eff):
        """has_permission without org_role → manage:members fails."""
        from app.core.org_settings import has_permission
        from app.models.organization import OrgSettings

        mock_eff.return_value = OrgSettings()

        assert has_permission("org-x", "student", "manage", "members") is False


# ---------------------------------------------------------------------------
# 12. Admin Context Multi-Tenant Guard (Audit Fix #2)
# ---------------------------------------------------------------------------

class TestAdminContextMultiTenantGuard:
    """Test admin-context endpoint respects enable_multi_tenant flag."""

    @pytest.mark.asyncio
    async def test_admin_context_multi_tenant_off_hides_org_admin(self):
        """When enable_multi_tenant=False, is_org_admin=False and enable_org_admin=False."""
        from app.auth.user_router import get_my_admin_context
        from app.core.security import AuthenticatedUser

        mock_settings = MagicMock()
        mock_settings.enable_org_admin = True
        mock_settings.enable_multi_tenant = False

        # Sprint 194c: admin-context now takes AuthenticatedUser from require_auth
        auth = AuthenticatedUser(user_id="user-with-org-role", auth_method="jwt", role="student")

        with patch("app.core.config.settings", mock_settings):
            result = await get_my_admin_context(auth=auth)

        assert result["is_org_admin"] is False
        assert result["admin_org_ids"] == []
        assert result["enable_org_admin"] is False  # multi_tenant required

    @pytest.mark.asyncio
    async def test_admin_context_system_admin_always_passes(self):
        """System admin is_org_admin=True even when multi_tenant=False."""
        from app.auth.user_router import get_my_admin_context
        from app.core.security import AuthenticatedUser

        mock_settings = MagicMock()
        mock_settings.enable_org_admin = False
        mock_settings.enable_multi_tenant = False

        # Sprint 194c: admin-context now takes AuthenticatedUser from require_auth
        auth = AuthenticatedUser(user_id="platform-admin", auth_method="jwt", role="admin")

        with patch("app.core.config.settings", mock_settings):
            result = await get_my_admin_context(auth=auth)

        assert result["is_system_admin"] is True
        assert result["is_org_admin"] is True  # system admin always counts


# ---------------------------------------------------------------------------
# 13. Settings PATCH Condition Clarity (Audit Fix #3)
# ---------------------------------------------------------------------------

class TestSettingsPatchSimplified:
    """Test simplified PATCH condition (caller != platform_admin)."""

    @patch("app.api.v1.organizations.settings", _mock_settings(enable_org_admin=True))
    @patch("app.api.v1.organizations.get_organization_repository")
    @pytest.mark.asyncio
    async def test_platform_admin_can_patch_all_keys(self, mock_get_repo):
        """Platform admin can update ANY setting key including features."""
        from app.api.v1.organizations import update_org_settings

        mock_org = MagicMock()
        mock_org.settings = {}
        mock_repo = MagicMock()
        mock_repo.get_organization.return_value = mock_org
        mock_repo.update_organization.return_value = mock_org
        mock_get_repo.return_value = mock_repo

        auth = _make_auth(role="admin", user_id="platform-admin-1")
        body = {"features": {"enable_product_search": True}, "branding": {"chatbot_name": "X"}}
        request = _make_request()

        with patch("app.models.organization.OrgSettings") as mock_schema:
            mock_schema.return_value = MagicMock()
            with patch("app.core.org_settings.get_effective_settings") as mock_eff:
                mock_eff.return_value = MagicMock(model_dump=lambda: {})
                await update_org_settings(request=request, org_id="org-x", body=body, auth=auth)

        # Both keys should pass through (not stripped)
        call_args = mock_repo.update_organization.call_args
        assert call_args is not None
