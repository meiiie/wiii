"""
Organization Management API — Multi-Tenant (Sprint 24).

REST endpoints for organization CRUD and membership management.
Feature-gated: only active when enable_multi_tenant=True.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.security import AuthenticatedUser, require_auth
from app.models.organization import (
    AddMemberRequest,
    OrganizationCreate,
    OrganizationResponse,
    OrganizationUpdate,
    UserOrganizationResponse,
)
from app.repositories.organization_repository import get_organization_repository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/organizations", tags=["Organizations"])


def _require_multi_tenant() -> None:
    """Raise 404 if multi-tenant is disabled."""
    if not settings.enable_multi_tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Multi-tenant is not enabled",
        )


def _require_admin(auth: AuthenticatedUser) -> None:
    """Raise 403 if the user is not admin."""
    if auth.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )


# =============================================================================
# Organization CRUD
# =============================================================================


@router.get("", response_model=list[OrganizationResponse])
@limiter.limit("30/minute")
async def list_organizations(
    request: Request,
    auth: AuthenticatedUser = Depends(require_auth),
):
    """List organizations. Admin sees all; regular users see only their orgs."""
    _require_multi_tenant()
    repo = get_organization_repository()

    if auth.role == "admin":
        return repo.list_organizations(active_only=False)
    else:
        user_orgs = repo.get_user_organizations(auth.user_id)
        return [uo.organization for uo in user_orgs if uo.organization]


@router.get("/{org_id}", response_model=OrganizationResponse)
@limiter.limit("30/minute")
async def get_organization(
    request: Request,
    org_id: str,
    auth: AuthenticatedUser = Depends(require_auth),
):
    """Get organization details."""
    _require_multi_tenant()
    repo = get_organization_repository()
    org = repo.get_organization(org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization '{org_id}' not found",
        )

    # Non-admin users can only view their own organizations
    if auth.role != "admin" and not repo.is_user_in_org(auth.user_id, org_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization",
        )

    return org


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_organization(
    request: Request,
    body: OrganizationCreate,
    auth: AuthenticatedUser = Depends(require_auth),
):
    """Create a new organization (admin only)."""
    _require_multi_tenant()
    _require_admin(auth)

    repo = get_organization_repository()

    # Check for duplicate
    existing = repo.get_organization(body.id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Organization '{body.id}' already exists",
        )

    result = repo.create_organization(body)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create organization",
        )

    return result


@router.patch("/{org_id}", response_model=OrganizationResponse)
@limiter.limit("10/minute")
async def update_organization(
    request: Request,
    org_id: str,
    body: OrganizationUpdate,
    auth: AuthenticatedUser = Depends(require_auth),
):
    """Update an organization (admin only)."""
    _require_multi_tenant()
    _require_admin(auth)

    repo = get_organization_repository()

    existing = repo.get_organization(org_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization '{org_id}' not found",
        )

    result = repo.update_organization(org_id, body)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update organization",
        )

    return result


@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def delete_organization(
    request: Request,
    org_id: str,
    auth: AuthenticatedUser = Depends(require_auth),
):
    """Soft-delete an organization (admin only)."""
    _require_multi_tenant()
    _require_admin(auth)

    if org_id == "default":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the default organization",
        )

    repo = get_organization_repository()
    deleted = repo.delete_organization(org_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization '{org_id}' not found or already inactive",
        )


# =============================================================================
# Membership
# =============================================================================


@router.post("/{org_id}/members", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def add_member(
    request: Request,
    org_id: str,
    body: AddMemberRequest,
    auth: AuthenticatedUser = Depends(require_auth),
):
    """Add a user to an organization (admin only)."""
    _require_multi_tenant()
    _require_admin(auth)

    repo = get_organization_repository()

    org = repo.get_organization(org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization '{org_id}' not found",
        )

    success = repo.add_user_to_org(body.user_id, org_id, body.role)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add member",
        )

    return {"user_id": body.user_id, "organization_id": org_id, "role": body.role}


@router.delete("/{org_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def remove_member(
    request: Request,
    org_id: str,
    user_id: str,
    auth: AuthenticatedUser = Depends(require_auth),
):
    """Remove a user from an organization (admin only)."""
    _require_multi_tenant()
    _require_admin(auth)

    repo = get_organization_repository()
    removed = repo.remove_user_from_org(user_id, org_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found in organization",
        )


@router.get("/{org_id}/members")
@limiter.limit("30/minute")
async def list_members(
    request: Request,
    org_id: str,
    auth: AuthenticatedUser = Depends(require_auth),
):
    """List members of an organization (admin only)."""
    _require_multi_tenant()
    _require_admin(auth)

    repo = get_organization_repository()
    return repo.get_org_members(org_id)


# =============================================================================
# User Self-Service
# =============================================================================


@router.get("/users/me/organizations", response_model=list[UserOrganizationResponse])
@limiter.limit("30/minute")
async def my_organizations(
    request: Request,
    auth: AuthenticatedUser = Depends(require_auth),
):
    """List current user's organizations."""
    _require_multi_tenant()
    repo = get_organization_repository()
    return repo.get_user_organizations(auth.user_id)
