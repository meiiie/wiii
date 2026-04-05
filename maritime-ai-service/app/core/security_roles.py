"""
Role normalization and authority helpers for auth/security.

Extracted from app.core.security so the main module can focus on validation and
dependency wiring while this module owns the pure role-mapping logic.
"""

from typing import Optional


DEFAULT_LEGACY_ROLE = "student"
DEFAULT_PLATFORM_ROLE = "user"
PLATFORM_ADMIN_ROLE = "platform_admin"

_HOST_ROLE_ALIASES = {
    "student": "student",
    "learner": "student",
    "pupil": "student",
    "teacher": "teacher",
    "instructor": "teacher",
    "professor": "teacher",
    "lecturer": "teacher",
    "ta": "teacher",
    "teaching_assistant": "teacher",
    "admin": "admin",
    "administrator": "admin",
    "manager": "admin",
    "org_admin": "org_admin",
    "organization_admin": "org_admin",
    "owner": "org_admin",
}

_PLATFORM_ROLE_ALIASES = {
    "admin": PLATFORM_ADMIN_ROLE,
    "platform_admin": PLATFORM_ADMIN_ROLE,
    "system_admin": PLATFORM_ADMIN_ROLE,
    "user": DEFAULT_PLATFORM_ROLE,
    "member": DEFAULT_PLATFORM_ROLE,
}


def normalize_role_source(value: object) -> Optional[str]:
    """Normalize role-source labels used in additive Identity V2 claims."""
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized or None


def normalize_platform_role(value: object) -> str:
    """Normalize a platform-scoped role claim."""
    if not isinstance(value, str):
        return DEFAULT_PLATFORM_ROLE
    normalized = value.strip().lower()
    return _PLATFORM_ROLE_ALIASES.get(normalized, DEFAULT_PLATFORM_ROLE)


def normalize_host_role(value: object) -> Optional[str]:
    """Normalize a host-local role without treating it as platform authority."""
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    return _HOST_ROLE_ALIASES.get(normalized)


def normalize_legacy_role(value: object) -> Optional[str]:
    """Normalize legacy compatibility roles without granting platform authority."""
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized in {"student", "teacher", "admin"}:
        return normalized
    return None


def map_host_role_to_legacy_role(host_role: object) -> str:
    """Map host-local roles onto legacy compatibility roles."""
    normalized = normalize_host_role(host_role)
    if normalized in {"teacher", "admin", "org_admin"}:
        return "teacher"
    return DEFAULT_LEGACY_ROLE


def resolve_interaction_role(auth: object, default: str = DEFAULT_LEGACY_ROLE) -> str:
    """Resolve the compatibility role for a conversational turn."""
    if auth is None:
        return default

    if isinstance(auth, dict):
        host_role = auth.get("host_role")
        role = auth.get("role")
        auth_method = auth.get("auth_method")
        role_source = auth.get("role_source")
    else:
        host_role = getattr(auth, "host_role", None)
        role = getattr(auth, "role", None)
        auth_method = getattr(auth, "auth_method", None)
        role_source = getattr(auth, "role_source", None)

    normalized_host_role = normalize_host_role(host_role)
    if normalized_host_role:
        return map_host_role_to_legacy_role(normalized_host_role)

    normalized_role = normalize_legacy_role(role)
    normalized_source = normalize_role_source(role_source)
    if normalized_role and (
        auth_method in {"api_key", "lms", "lms_service"}
        or normalized_source in {"api_key", "lms_host", "host", "workspace"}
    ):
        return normalized_role

    return default


def derive_platform_role_from_legacy_role(
    legacy_role: object,
    *,
    auth_method: Optional[str] = None,
    role_source: Optional[str] = None,
) -> str:
    """Derive a safe platform role from legacy role data."""
    normalized_source = normalize_role_source(role_source)
    if normalized_source == "lms_host" or auth_method in {"lms", "lms_service"}:
        return DEFAULT_PLATFORM_ROLE
    if isinstance(legacy_role, str) and legacy_role.strip().lower() == "admin":
        return PLATFORM_ADMIN_ROLE
    return DEFAULT_PLATFORM_ROLE


def is_platform_admin(auth: object) -> bool:
    """Return True only for real Wiii platform admins."""
    if auth is None:
        return False
    if isinstance(auth, dict):
        platform_role = auth.get("platform_role")
        legacy_role = auth.get("role")
        auth_method = auth.get("auth_method")
        role_source = auth.get("role_source")
    else:
        platform_role = getattr(auth, "platform_role", None)
        legacy_role = getattr(auth, "role", None)
        auth_method = getattr(auth, "auth_method", None)
        role_source = getattr(auth, "role_source", None)

    if normalize_platform_role(platform_role) == PLATFORM_ADMIN_ROLE:
        return True
    return (
        derive_platform_role_from_legacy_role(
            legacy_role,
            auth_method=auth_method,
            role_source=role_source,
        )
        == PLATFORM_ADMIN_ROLE
    )


__all__ = [
    "DEFAULT_LEGACY_ROLE",
    "DEFAULT_PLATFORM_ROLE",
    "PLATFORM_ADMIN_ROLE",
    "derive_platform_role_from_legacy_role",
    "is_platform_admin",
    "map_host_role_to_legacy_role",
    "normalize_host_role",
    "normalize_legacy_role",
    "normalize_platform_role",
    "normalize_role_source",
    "resolve_interaction_role",
]
