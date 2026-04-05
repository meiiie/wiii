"""
Organization Settings — runtime merge utility.

Sprint 161: "Không Gian Riêng" — org-level customization.

Pattern: 4-layer cascade (Salesforce/Slack/Google Workspace industry standard)
  Platform Defaults  <-  Org Settings  <-  Role Overrides  <-  User Preferences

The org settings JSONB is validated against OrgSettings Pydantic schema,
merged with PLATFORM_DEFAULTS using deep_merge(), and cached per-request.
"""

import copy
import logging
from typing import Optional

from app.models.organization import OrgSettings

logger = logging.getLogger(__name__)

# =============================================================================
# Platform Defaults — Wiii brand baseline (single source of truth)
# =============================================================================

PLATFORM_DEFAULTS = OrgSettings()


# =============================================================================
# Deep Merge Utility
# =============================================================================


def deep_merge(base: dict, overlay: dict) -> dict:
    """
    Recursively merge overlay into base. Overlay values win.

    Used for: platformDefaults <- orgSettings <- userPrefs
    Pattern: Salesforce metadata-driven, Google OU inheritance.
    """
    result = copy.deepcopy(base)
    for key, value in overlay.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


# =============================================================================
# Settings Resolution
# =============================================================================


def get_effective_settings(org_id: Optional[str] = None) -> OrgSettings:
    """
    Resolve effective org settings: merge DB settings with platform defaults.

    When enable_multi_tenant=False or org_id is None, returns PLATFORM_DEFAULTS.
    Feature-gated: zero behavior change for single-tenant deployments.

    Args:
        org_id: Organization ID to resolve settings for (None = platform defaults).

    Returns:
        Merged OrgSettings with platform defaults as base.
    """
    from app.core.config import settings as app_settings

    if not org_id or not app_settings.enable_multi_tenant:
        return PLATFORM_DEFAULTS

    try:
        from app.repositories.organization_repository import (
            get_organization_repository,
        )

        repo = get_organization_repository()
        org = repo.get_organization(org_id)
        if not org or not org.settings:
            return PLATFORM_DEFAULTS

        # Deep merge: platform defaults <- org DB settings
        merged_dict = deep_merge(
            PLATFORM_DEFAULTS.model_dump(),
            org.settings,
        )

        return OrgSettings(**merged_dict)

    except Exception as e:
        logger.warning("Failed to resolve org settings for '%s': %s", org_id, e)
        return PLATFORM_DEFAULTS


def get_org_permissions(org_id: Optional[str], role: str, org_role: Optional[str] = None) -> list[str]:
    """
    Get permissions list for a role within an organization.

    Resolves org-level permission overrides, falling back to platform defaults.

    Sprint 181: When org_role is 'admin' or 'owner' and enable_org_admin is True,
    additional management permissions are granted.

    Args:
        org_id: Organization ID (None = platform defaults).
        role: Compatibility permission tier used for org settings resolution.
            In Identity V2, Wiii web normally uses only:
            - "student" for regular users
            - "admin" for platform admins
        org_role: User's role within the org (member, admin, owner). Optional.

    Returns:
        List of permission strings like ["read:chat", "use:tools"].
    """
    effective = get_effective_settings(org_id)
    perms = effective.permissions

    role_map = {
        "student": perms.student,
        "teacher": perms.teacher,
        "admin": perms.admin,
    }

    base_perms = role_map.get(role, perms.student)

    # Sprint 181: Org admin/owner gets additional management permissions
    if org_role in ("admin", "owner"):
        from app.core.config import settings as app_settings
        if app_settings.enable_org_admin:
            extra = ["manage:members", "read:org_analytics", "read:org_dashboard", "manage:knowledge"]
            if org_role == "owner":
                extra.append("manage:org_settings")
            return list(set(base_perms + extra))

    return base_perms


def has_permission(
    org_id: Optional[str], role: str, action: str, resource: str,
    org_role: Optional[str] = None,
) -> bool:
    """
    Check if a role has a specific permission within an organization.

    Args:
        org_id: Organization ID.
        role: User platform role.
        action: Permission action (e.g., "read", "manage").
        resource: Permission resource (e.g., "chat", "settings").
        org_role: User's org-level role (member/admin/owner). Sprint 181.

    Returns:
        True if the role has the permission.
    """
    perms = get_org_permissions(org_id, role, org_role=org_role)
    return f"{action}:{resource}" in perms


def is_agent_visible(org_id: Optional[str], agent_name: str) -> bool:
    """
    Check if an agent/node is visible for this organization.

    Used by supervisor routing to skip agents not enabled for the org.
    Pattern: LaunchDarkly per-org feature flags.

    Args:
        org_id: Organization ID (None = all agents visible).
        agent_name: Agent node name (e.g., "product_search_agent").

    Returns:
        True if the agent should be available.
    """
    settings = get_effective_settings(org_id)
    return agent_name in settings.features.visible_agents


def is_feature_enabled(org_id: Optional[str], feature_name: str) -> bool:
    """
    Check if a feature flag is enabled for this organization.

    Args:
        org_id: Organization ID.
        feature_name: Feature flag name (e.g., "enable_product_search").

    Returns:
        True if enabled.
    """
    settings = get_effective_settings(org_id)
    return getattr(settings.features, feature_name, False)
