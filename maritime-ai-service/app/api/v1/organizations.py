"""
Organization Management API — Multi-Tenant (Sprint 24).

REST endpoints for organization CRUD and membership management.
Feature-gated: only active when enable_multi_tenant=True.

Sprint 161: Added settings GET/PATCH + permissions endpoint.
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
    OrgSettings,
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


def _require_org_admin_or_platform_admin(auth: AuthenticatedUser, org_id: str) -> str:
    """
    Raise 403 if user is neither platform admin nor org admin/owner for this org.

    Sprint 181: Two-tier admin — system admin always passes, org admin passes
    only for their own org(s) when enable_org_admin=True.

    Returns the org-level role ('admin'/'owner') or 'platform_admin' for downstream checks.
    """
    if auth.role == "admin":
        return "platform_admin"

    if not settings.enable_org_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )

    repo = get_organization_repository()
    org_role = repo.get_user_org_role(auth.user_id, org_id)
    if org_role not in ("admin", "owner"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization admin role required",
        )
    return org_role


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

    # Sprint 194b (M4): Non-admin users can only view their own organizations.
    # Platform admins always pass; org members can view their org.
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
    """Add a user to an organization (platform admin or org admin/owner)."""
    _require_multi_tenant()
    caller_level = _require_org_admin_or_platform_admin(auth, org_id)

    # Sprint 181: Org admin cannot assign admin/owner roles (escalation prevention)
    if caller_level not in ("platform_admin", "owner") and body.role in ("admin", "owner"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only platform admin or org owner can assign admin/owner roles",
        )

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
    """Remove a user from an organization (platform admin or org admin/owner)."""
    _require_multi_tenant()
    caller_level = _require_org_admin_or_platform_admin(auth, org_id)

    # Sprint 181: Prevent self-removal (could leave org with no admin/owner)
    if user_id == auth.user_id and caller_level != "platform_admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove yourself from the organization",
        )

    # Sprint 181: Org admin cannot remove admin/owner members (only owner/platform admin can)
    repo = get_organization_repository()
    if caller_level not in ("platform_admin", "owner"):
        target_role = repo.get_user_org_role(user_id, org_id)
        if target_role in ("admin", "owner"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only platform admin or org owner can remove admin/owner members",
            )
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
    """List members of an organization (platform admin or org admin/owner)."""
    _require_multi_tenant()
    _require_org_admin_or_platform_admin(auth, org_id)

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


# =============================================================================
# Sprint 161: Org Settings + Permissions
# =============================================================================


@router.get("/{org_id}/settings")
@limiter.limit("30/minute")
async def get_org_settings(
    request: Request,
    org_id: str,
    auth: AuthenticatedUser = Depends(require_auth),
):
    """Get effective org settings (merged with platform defaults)."""
    _require_multi_tenant()

    repo = get_organization_repository()
    org = repo.get_organization(org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization '{org_id}' not found",
        )

    # Members can read settings (needed for branding); only admin/org admin can modify
    # Sprint 194b (M4): Consistent with two-tier admin model — platform admin
    # always passes, org members can read their org settings
    if auth.role != "admin" and not repo.is_user_in_org(auth.user_id, org_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization",
        )

    from app.core.org_settings import get_effective_settings

    effective = get_effective_settings(org_id)
    return effective.model_dump()


@router.patch("/{org_id}/settings")
@limiter.limit("10/minute")
async def update_org_settings(
    request: Request,
    org_id: str,
    body: dict,
    auth: AuthenticatedUser = Depends(require_auth),
):
    """Partial-update org settings (deep merge with existing). Admin or org admin."""
    _require_multi_tenant()
    caller_level = _require_org_admin_or_platform_admin(auth, org_id)

    # Sprint 181: Org admin can only change branding + onboarding (not features/ai_config/permissions)
    # Org owner gets same restriction — full settings requires platform admin
    _ORG_ADMIN_ALLOWED_KEYS = {"branding", "onboarding", "schema_version"}
    if caller_level != "platform_admin":
        restricted_keys = set(body.keys()) - _ORG_ADMIN_ALLOWED_KEYS
        if restricted_keys:
            # Silently strip restricted keys instead of 403 (graceful degradation)
            body = {k: v for k, v in body.items() if k in _ORG_ADMIN_ALLOWED_KEYS}
            if not body:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Org admin can only update branding and onboarding settings",
                )

    repo = get_organization_repository()
    org = repo.get_organization(org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization '{org_id}' not found",
        )

    # Deep merge existing settings with new values
    from app.core.org_settings import deep_merge

    current_settings = org.settings or {}
    merged = deep_merge(current_settings, body)

    # Validate merged result against schema
    try:
        OrgSettings(**merged)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid settings: {str(e)[:200]}",
        )

    # Persist
    result = repo.update_organization(
        org_id,
        OrganizationUpdate(settings=merged),
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update settings",
        )

    # Return effective (merged with platform defaults)
    from app.core.org_settings import get_effective_settings

    return get_effective_settings(org_id).model_dump()


@router.get("/{org_id}/permissions")
@limiter.limit("30/minute")
async def get_org_permissions_endpoint(
    request: Request,
    org_id: str,
    auth: AuthenticatedUser = Depends(require_auth),
):
    """Get current user's permissions within this organization."""
    _require_multi_tenant()

    repo = get_organization_repository()
    if not repo.is_user_in_org(auth.user_id, org_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization",
        )

    from app.core.org_settings import get_org_permissions

    # Sprint 181: Pass org-level role for additional management permissions
    org_role = None
    if settings.enable_org_admin:
        org_role = repo.get_user_org_role(auth.user_id, org_id)

    perms = get_org_permissions(org_id, auth.role, org_role=org_role)
    return {"permissions": perms, "role": auth.role, "organization_id": org_id, "org_role": org_role}
