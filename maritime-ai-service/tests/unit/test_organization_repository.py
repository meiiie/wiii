"""
Tests for OrganizationRepository — Organization and membership CRUD.

Sprint 24: Multi-Organization Architecture.

Verifies:
- Organization CRUD: create, get, list, update, soft-delete
- User-org membership: add, remove, list, is_member, default org
- Edge cases: duplicate, nonexistent, active filtering
- Error handling (DB failures)
- Singleton
"""

import json
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.models.organization import (
    OrganizationCreate,
    OrganizationUpdate,
)
from app.repositories.organization_repository import (
    OrganizationRepository,
    get_organization_repository,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def repo():
    """Fresh OrganizationRepository with mocked DB session."""
    r = OrganizationRepository()
    r._initialized = True
    r._engine = MagicMock()

    mock_session = MagicMock()
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_session_factory.return_value.__exit__ = MagicMock(return_value=False)
    r._session_factory = mock_session_factory
    r._mock_session = mock_session
    return r


@pytest.fixture
def sample_org_row():
    """Sample org DB row (10 columns)."""
    return (
        "lms-hang-hai",                     # 0: id
        "LMS Hang Hai",                     # 1: name
        "LMS Hang Hai Viet Nam",            # 2: display_name
        "Maritime education",               # 3: description
        ["maritime"],                       # 4: allowed_domains
        "maritime",                         # 5: default_domain
        {"theme": "blue"},                  # 6: settings (dict)
        True,                               # 7: is_active
        datetime(2026, 2, 9, tzinfo=timezone.utc),  # 8: created_at
        datetime(2026, 2, 9, tzinfo=timezone.utc),  # 9: updated_at
    )


@pytest.fixture
def sample_membership_row(sample_org_row):
    """Sample membership join row (14 columns = 4 membership + 10 org)."""
    return (
        "user-1",           # 0: user_id
        "lms-hang-hai",     # 1: organization_id
        "member",           # 2: role
        datetime(2026, 2, 9, tzinfo=timezone.utc),  # 3: joined_at
    ) + sample_org_row


# =============================================================================
# Organization CRUD
# =============================================================================


class TestCreateOrganization:
    def test_create_success(self, repo):
        org = OrganizationCreate(
            id="test-org", name="Test", allowed_domains=["maritime"]
        )
        result = repo.create_organization(org)
        assert result is not None
        assert result.id == "test-org"
        assert result.name == "Test"
        assert result.is_active is True
        repo._mock_session.execute.assert_called_once()
        repo._mock_session.commit.assert_called_once()

    def test_create_db_failure(self, repo):
        repo._mock_session.execute.side_effect = Exception("DB error")
        org = OrganizationCreate(id="test-org", name="Test")
        result = repo.create_organization(org)
        assert result is None

    def test_create_no_session_factory(self):
        r = OrganizationRepository()
        r._initialized = True
        r._session_factory = None
        org = OrganizationCreate(id="x", name="Y")
        assert r.create_organization(org) is None


class TestGetOrganization:
    def test_get_found(self, repo, sample_org_row):
        repo._mock_session.execute.return_value.fetchone.return_value = sample_org_row
        result = repo.get_organization("lms-hang-hai")
        assert result is not None
        assert result.id == "lms-hang-hai"
        assert result.allowed_domains == ["maritime"]

    def test_get_not_found(self, repo):
        repo._mock_session.execute.return_value.fetchone.return_value = None
        result = repo.get_organization("nonexistent")
        assert result is None

    def test_get_db_failure(self, repo):
        repo._mock_session.execute.side_effect = Exception("DB error")
        assert repo.get_organization("x") is None


class TestListOrganizations:
    def test_list_active_only(self, repo, sample_org_row):
        repo._mock_session.execute.return_value.fetchall.return_value = [sample_org_row]
        result = repo.list_organizations(active_only=True)
        assert len(result) == 1
        assert result[0].id == "lms-hang-hai"

    def test_list_empty(self, repo):
        repo._mock_session.execute.return_value.fetchall.return_value = []
        result = repo.list_organizations()
        assert result == []

    def test_list_db_failure(self, repo):
        repo._mock_session.execute.side_effect = Exception("DB error")
        assert repo.list_organizations() == []


class TestUpdateOrganization:
    def test_update_success(self, repo, sample_org_row):
        # First call: UPDATE, second call (from get_organization): SELECT
        repo._mock_session.execute.return_value.fetchone.return_value = sample_org_row
        data = OrganizationUpdate(name="New Name")
        result = repo.update_organization("lms-hang-hai", data)
        assert result is not None

    def test_update_no_fields(self, repo, sample_org_row):
        repo._mock_session.execute.return_value.fetchone.return_value = sample_org_row
        data = OrganizationUpdate()
        result = repo.update_organization("lms-hang-hai", data)
        # Should call get_organization directly
        assert result is not None

    def test_update_db_failure(self, repo):
        repo._mock_session.execute.side_effect = Exception("DB error")
        data = OrganizationUpdate(name="X")
        assert repo.update_organization("x", data) is None


class TestDeleteOrganization:
    def test_delete_success(self, repo):
        repo._mock_session.execute.return_value.rowcount = 1
        assert repo.delete_organization("test-org") is True

    def test_delete_not_found(self, repo):
        repo._mock_session.execute.return_value.rowcount = 0
        assert repo.delete_organization("nonexistent") is False

    def test_delete_db_failure(self, repo):
        repo._mock_session.execute.side_effect = Exception("DB error")
        assert repo.delete_organization("x") is False


# =============================================================================
# Membership
# =============================================================================


class TestAddUserToOrg:
    def test_add_success(self, repo):
        result = repo.add_user_to_org("user-1", "org-1")
        assert result is True
        repo._mock_session.execute.assert_called_once()
        repo._mock_session.commit.assert_called_once()

    def test_add_with_role(self, repo):
        result = repo.add_user_to_org("user-1", "org-1", role="admin")
        assert result is True

    def test_add_db_failure(self, repo):
        repo._mock_session.execute.side_effect = Exception("DB error")
        assert repo.add_user_to_org("u", "o") is False


class TestRemoveUserFromOrg:
    def test_remove_success(self, repo):
        repo._mock_session.execute.return_value.rowcount = 1
        assert repo.remove_user_from_org("user-1", "org-1") is True

    def test_remove_not_found(self, repo):
        repo._mock_session.execute.return_value.rowcount = 0
        assert repo.remove_user_from_org("user-1", "org-1") is False


class TestGetUserOrganizations:
    def test_get_user_orgs(self, repo, sample_membership_row):
        repo._mock_session.execute.return_value.fetchall.return_value = [
            sample_membership_row
        ]
        result = repo.get_user_organizations("user-1")
        assert len(result) == 1
        assert result[0].user_id == "user-1"
        assert result[0].organization.id == "lms-hang-hai"

    def test_get_user_orgs_empty(self, repo):
        repo._mock_session.execute.return_value.fetchall.return_value = []
        assert repo.get_user_organizations("user-x") == []


class TestGetOrgMembers:
    def test_get_members(self, repo):
        repo._mock_session.execute.return_value.fetchall.return_value = [
            ("user-1", "org-1", "member", datetime(2026, 2, 9, tzinfo=timezone.utc)),
        ]
        result = repo.get_org_members("org-1")
        assert len(result) == 1
        assert result[0]["user_id"] == "user-1"


class TestGetUserDefaultOrg:
    def test_default_found(self, repo):
        repo._mock_session.execute.return_value.fetchone.return_value = ("org-1",)
        assert repo.get_user_default_org("user-1") == "org-1"

    def test_default_none(self, repo):
        repo._mock_session.execute.return_value.fetchone.return_value = None
        assert repo.get_user_default_org("user-1") is None


class TestIsUserInOrg:
    def test_is_member(self, repo):
        repo._mock_session.execute.return_value.fetchone.return_value = (1,)
        assert repo.is_user_in_org("user-1", "org-1") is True

    def test_is_not_member(self, repo):
        repo._mock_session.execute.return_value.fetchone.return_value = None
        assert repo.is_user_in_org("user-1", "org-1") is False


# =============================================================================
# Helpers
# =============================================================================


class TestOrgRowToResponse:
    def test_parse_dict_settings(self, sample_org_row):
        resp = OrganizationRepository._org_row_to_response(sample_org_row)
        assert resp.settings == {"theme": "blue"}

    def test_parse_string_settings(self):
        row = (
            "id", "name", None, None,
            ["maritime"], None,
            '{"key": "val"}',  # JSON string
            True, None, None,
        )
        resp = OrganizationRepository._org_row_to_response(row)
        assert resp.settings == {"key": "val"}

    def test_parse_null_settings(self):
        row = ("id", "name", None, None, None, None, None, True, None, None)
        resp = OrganizationRepository._org_row_to_response(row)
        assert resp.settings == {}
        assert resp.allowed_domains == []


# =============================================================================
# Singleton
# =============================================================================


class TestSingleton:
    def test_get_returns_instance(self):
        import app.repositories.organization_repository as mod
        mod._org_repo = None
        repo = get_organization_repository()
        assert isinstance(repo, OrganizationRepository)
        mod._org_repo = None  # cleanup
