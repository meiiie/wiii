"""
Auth/security Pydantic models.

Extracted from app.core.security to keep request dependency code focused on
verification flow while this module owns the data contracts.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.core.security_roles import DEFAULT_LEGACY_ROLE, DEFAULT_PLATFORM_ROLE


class TokenPayload(BaseModel):
    """JWT token payload structure."""

    sub: str
    exp: datetime
    iat: datetime
    type: str = "access"
    role: Optional[str] = None
    platform_role: Optional[str] = None
    organization_role: Optional[str] = None
    host_role: Optional[str] = None
    role_source: Optional[str] = None
    active_organization_id: Optional[str] = None
    connector_id: Optional[str] = None
    identity_version: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    auth_method: Optional[str] = None
    iss: Optional[str] = None
    jti: Optional[str] = None


class AuthenticatedUser(BaseModel):
    """Authenticated user information."""

    user_id: str
    auth_method: str
    role: str = DEFAULT_LEGACY_ROLE
    platform_role: str = DEFAULT_PLATFORM_ROLE
    organization_role: Optional[str] = None
    host_role: Optional[str] = None
    role_source: Optional[str] = None
    session_id: Optional[str] = None
    organization_id: Optional[str] = None
    connector_id: Optional[str] = None
    identity_version: Optional[str] = None


__all__ = [
    "AuthenticatedUser",
    "TokenPayload",
]
