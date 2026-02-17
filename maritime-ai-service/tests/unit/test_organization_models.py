"""
Tests for Organization Pydantic models.

Sprint 24: Multi-Organization Architecture.

Verifies:
- OrganizationCreate validation (required fields, allowed_domains)
- OrganizationUpdate partial update
- OrganizationResponse serialization
- UserOrganizationResponse nested org
- AddMemberRequest validation
"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from app.models.organization import (
    AddMemberRequest,
    OrganizationCreate,
    OrganizationResponse,
    OrganizationUpdate,
    UserOrganizationResponse,
)


# =============================================================================
# OrganizationCreate
# =============================================================================


class TestOrganizationCreate:
    def test_create_minimal(self):
        org = OrganizationCreate(id="test-org", name="Test")
        assert org.id == "test-org"
        assert org.name == "Test"
        assert org.allowed_domains == []
        assert org.settings == {}
        assert org.display_name is None

    def test_create_full(self):
        org = OrganizationCreate(
            id="lms-hang-hai",
            name="LMS Hang Hai",
            display_name="LMS Hang Hai Viet Nam",
            description="Maritime education org",
            allowed_domains=["maritime"],
            default_domain="maritime",
            settings={"theme": "blue"},
        )
        assert org.allowed_domains == ["maritime"]
        assert org.default_domain == "maritime"
        assert org.settings["theme"] == "blue"

    def test_create_empty_id_rejected(self):
        with pytest.raises(ValidationError):
            OrganizationCreate(id="", name="Test")

    def test_create_empty_name_rejected(self):
        with pytest.raises(ValidationError):
            OrganizationCreate(id="test", name="")

    def test_create_id_max_length(self):
        long_id = "a" * 101
        with pytest.raises(ValidationError):
            OrganizationCreate(id=long_id, name="Test")


# =============================================================================
# OrganizationUpdate
# =============================================================================


class TestOrganizationUpdate:
    def test_update_all_none(self):
        update = OrganizationUpdate()
        dumped = update.model_dump(exclude_none=True)
        assert dumped == {}

    def test_update_partial(self):
        update = OrganizationUpdate(name="New Name", is_active=False)
        dumped = update.model_dump(exclude_none=True)
        assert dumped == {"name": "New Name", "is_active": False}

    def test_update_allowed_domains(self):
        update = OrganizationUpdate(allowed_domains=["maritime", "traffic_law"])
        assert update.allowed_domains == ["maritime", "traffic_law"]


# =============================================================================
# OrganizationResponse
# =============================================================================


class TestOrganizationResponse:
    def test_response_defaults(self):
        resp = OrganizationResponse(id="test", name="Test")
        assert resp.is_active is True
        assert resp.allowed_domains == []
        assert resp.settings == {}

    def test_response_serialization(self):
        now = datetime.now(timezone.utc)
        resp = OrganizationResponse(
            id="org-1",
            name="Org One",
            display_name="Organization One",
            allowed_domains=["maritime"],
            is_active=True,
            created_at=now,
        )
        data = resp.model_dump()
        assert data["id"] == "org-1"
        assert data["allowed_domains"] == ["maritime"]
        assert data["created_at"] == now


# =============================================================================
# UserOrganizationResponse
# =============================================================================


class TestUserOrganizationResponse:
    def test_membership_without_org(self):
        uo = UserOrganizationResponse(
            user_id="user-1",
            organization_id="org-1",
            role="member",
        )
        assert uo.organization is None

    def test_membership_with_org(self):
        org = OrganizationResponse(id="org-1", name="Org")
        uo = UserOrganizationResponse(
            user_id="user-1",
            organization_id="org-1",
            role="admin",
            organization=org,
        )
        assert uo.organization.name == "Org"
        assert uo.role == "admin"


# =============================================================================
# AddMemberRequest
# =============================================================================


class TestAddMemberRequest:
    def test_add_member_defaults(self):
        req = AddMemberRequest(user_id="user-1")
        assert req.role == "member"

    def test_add_member_custom_role(self):
        req = AddMemberRequest(user_id="user-1", role="owner")
        assert req.role == "owner"

    def test_add_member_empty_user_rejected(self):
        with pytest.raises(ValidationError):
            AddMemberRequest(user_id="")
