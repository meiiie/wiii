"""
API Dependencies - Dependency Injection for FastAPI
Requirements: 1.3

Provides reusable dependencies for authentication, database sessions, etc.
Wiii platform semantics: admin-only endpoints use canonical platform admin,
not host-local LMS roles.
"""
from typing import Annotated, Optional

from fastapi import Depends, HTTPException

from app.core.security import (
    AuthenticatedUser,
    is_platform_admin,
    optional_auth,
    require_auth,
)


# =============================================================================
# Authentication Dependencies
# =============================================================================

# Require authentication (API Key or JWT)
RequireAuth = Annotated[AuthenticatedUser, Depends(require_auth)]

# Optional authentication
OptionalAuth = Annotated[Optional[AuthenticatedUser], Depends(optional_auth)]


# =============================================================================
# Role-Based Access Control
# =============================================================================

async def _require_admin(auth: AuthenticatedUser = Depends(require_auth)) -> AuthenticatedUser:
    """
    Require canonical Wiii platform admin access for endpoint access.

    Host-local roles such as LMS teacher/student/admin are not sufficient.

    Raises:
        HTTPException 403: If user is not a platform admin
    """
    if not is_platform_admin(auth):
        raise HTTPException(
            status_code=403,
            detail="Admin access required."
        )
    return auth

# Require admin role
RequireAdmin = Annotated[AuthenticatedUser, Depends(_require_admin)]



