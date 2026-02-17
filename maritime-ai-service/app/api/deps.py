"""
API Dependencies - Dependency Injection for FastAPI
Requirements: 1.3

Provides reusable dependencies for authentication, database sessions, etc.
LMS Integration: Added RequireAdmin for admin-only endpoints.
"""
from typing import Annotated, Optional

from fastapi import Depends, HTTPException

from app.core.security import (
    AuthenticatedUser,
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
    Require admin role for endpoint access.
    
    LMS Integration: Only users with role='admin' can access.
    
    Raises:
        HTTPException 403: If user is not admin
    """
    if auth.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required."
        )
    return auth

# Require admin role
RequireAdmin = Annotated[AuthenticatedUser, Depends(_require_admin)]



