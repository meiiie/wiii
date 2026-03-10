"""
Security Module - Authentication and Authorization
Requirements: 1.3

Supports both API Key and JWT Token authentication.
Sprint 192: Org membership validation, API key role restriction, JWT audience.
"""
import hmac
import logging
from datetime import datetime
from typing import Optional

from fastapi import Header, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)

# Security schemes
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


class TokenPayload(BaseModel):
    """JWT Token payload structure"""
    sub: str  # Subject (user_id)
    exp: datetime  # Expiration time
    iat: datetime  # Issued at
    type: str = "access"  # Token type
    role: Optional[str] = None  # Sprint 28: role from JWT (prevents X-Role override)
    # Sprint 157: OAuth-issued tokens include extra claims
    email: Optional[str] = None
    name: Optional[str] = None
    auth_method: Optional[str] = None  # "google", "lti", "api_key"
    iss: Optional[str] = None  # "wiii" for OAuth-issued tokens
    jti: Optional[str] = None  # Sprint 176: unique token ID for revocation tracking


class AuthenticatedUser(BaseModel):
    """
    Authenticated user information.
    
    LMS Integration: Now includes role and session tracking.
    """
    user_id: str
    auth_method: str  # "api_key", "lms_service", or "jwt"
    role: str = "student"  # student / teacher / admin
    session_id: Optional[str] = None  # For LMS session tracking
    organization_id: Optional[str] = None  # For multi-tenant support


# =============================================================================
# JWT Token Functions
# =============================================================================
# NOTE: Token creation is handled by app.auth.token_service.create_access_token()
# which includes aud, jti, iss, email, name, role claims.
# This module only provides verify_jwt_token() used by require_auth().

def verify_jwt_token(token: str) -> TokenPayload:
    """
    Verify and decode a JWT token.

    Uses token_service.decode_jwt_payload() for single-source decode logic
    (aud validation, JTI denylist). Builds TokenPayload from raw claims
    (preserving None defaults for missing fields like auth_method).

    Raises:
        HTTPException: If token is invalid, expired, or revoked
    """
    try:
        from app.auth.token_service import decode_jwt_payload
        payload = decode_jwt_payload(token)
        return TokenPayload(**payload)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("JWT verification failed: %s", e)
        # Preserve specific revocation detail for JTI denylist
        detail = "Token has been revoked" if "revoked" in str(e).lower() else "Invalid or expired token"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


# =============================================================================
# API Key Validation
# =============================================================================


def _get_configured_secret(value: object) -> str | None:
    """Normalize configured shared secrets before constant-time comparison."""
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def verify_api_key(api_key: str) -> bool:
    """
    Verify an API key.

    Args:
        api_key: The API key to verify

    Returns:
        True if valid, False otherwise
    """
    if not isinstance(api_key, str) or not api_key:
        return False

    configured_api_key = _get_configured_secret(
        getattr(settings, "api_key", None)
    )
    if not configured_api_key:
        if settings.environment == "production":
            logger.error(
                "SECURITY: No API key configured in production "
                "— rejecting request"
            )
            return False
        logger.warning(
            "No API key configured — allowing all requests "
            "(development mode)"
        )
        return True

    return hmac.compare_digest(api_key, configured_api_key)


def verify_lms_service_token(service_token: str) -> bool:
    """Verify the dedicated LMS service token for proxied backend requests."""
    if not isinstance(service_token, str) or not service_token:
        return False

    configured_service_token = _get_configured_secret(
        getattr(settings, "lms_service_token", None)
    )
    if not configured_service_token:
        return False

    return hmac.compare_digest(service_token, configured_service_token)


# =============================================================================
# Sprint 192: Org Membership Validation
# =============================================================================

async def _validate_org_membership(
    user_id: str,
    org_id: str,
    role: str,
) -> bool:
    """Check if user is a member of the specified organization.

    Platform admins (role=admin) bypass the check.
    Fail-open on DB error (log warning, don't reject).
    """
    if role == "admin":
        return True

    try:
        from app.core.database import get_asyncpg_pool
        pool = await get_asyncpg_pool(create=True)
        async with pool.acquire() as conn:
            row = await conn.fetchval(
                (
                    "SELECT 1 FROM user_organizations "
                    "WHERE user_id = $1 AND organization_id = $2"
                ),
                user_id,
                org_id,
            )
            return row is not None
    except Exception as e:
        logger.warning("Org membership check failed (fail-closed): %s", e)
        return False


# =============================================================================
# Authentication Dependencies
# =============================================================================

async def require_auth(
    api_key: Optional[str] = Security(api_key_header),
    credentials: Optional[HTTPAuthorizationCredentials] = Security(
        bearer_scheme
    ),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    x_role: Optional[str] = Header(None, alias="X-Role"),
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    x_org_id: Optional[str] = Header(None, alias="X-Organization-ID"),
) -> AuthenticatedUser:
    """
    Require authentication via API Key, LMS service token, or JWT Token.

    Auth modes:
    - API key: server-to-server client identity only
    - LMS service token: trusted proxied LMS request carrying end-user context
    - JWT: end-user identity

    LMS Integration: Accepts additional headers for proxied user context.
    - X-User-ID: Real user ID from LMS (required for LMS service auth)
    - X-Role: User role (student/teacher/admin)
    - X-Session-ID: Session tracking for analytics
    - X-Organization-ID: Multi-tenant support

    Requirements: 1.3

    Args:
        api_key: API key from X-API-Key header
        credentials: JWT token from Authorization header
        x_user_id: User ID from LMS
        x_role: User role from LMS
        x_session_id: Session ID for tracking
        x_org_id: Organization ID for multi-tenant

    Returns:
        AuthenticatedUser with user information

    Raises:
        HTTPException 401: If no valid authentication provided
        HTTPException 403: If user is not a member of the specified org
    """
    # Try API Key or LMS service token first
    if api_key:
        if verify_api_key(api_key):
            effective_role = x_role or "student"

            # Sprint 192: Restrict role escalation via API key in production
            if (
                settings.enforce_api_key_role_restriction
                and settings.environment == "production"
                and effective_role not in ("student", "teacher")
            ):
                logger.warning(
                    "SECURITY: API key auth attempted role=%s for "
                    "user=%s — downgraded to student",
                    effective_role,
                    x_user_id or "anonymous",
                )
                # Audit event (fire-and-forget)
                try:
                    import asyncio
                    from app.auth.auth_audit import log_auth_event
                    asyncio.ensure_future(log_auth_event(
                        "role_downgrade",
                        provider="api_key",
                        user_id=x_user_id or "anonymous",
                        reason=(
                            f"Attempted role={effective_role} "
                            "via API key in production"
                        ),
                    ))
                except Exception:
                    pass
                effective_role = "student"

            # Sprint 194b (C2): In production, general API key auth does NOT
            # trust X-User-ID. End-user identity must come from JWT or the
            # dedicated LMS service token path below.
            if settings.environment == "production":
                effective_user_id = "api-client"
                if x_user_id and x_user_id != "api-client":
                    logger.warning(
                        "SECURITY: Ignoring X-User-ID=%s for API key auth in production — "
                        "use JWT or LMS service token for end-user identity",
                        x_user_id,
                    )
            else:
                effective_user_id = x_user_id or "anonymous"

            user = AuthenticatedUser(
                user_id=effective_user_id,
                auth_method="api_key",
                role=effective_role,
                session_id=x_session_id,
                organization_id=x_org_id,
            )

            # Sprint 192: Validate org membership
            if x_org_id and settings.enable_org_membership_check:
                is_member = await _validate_org_membership(
                    user.user_id,
                    x_org_id,
                    user.role,
                )
                if not is_member:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"User is not a member of organization '{x_org_id}'",
                    )

            return user
        elif verify_lms_service_token(api_key):
            if not x_user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="LMS service authentication requires X-User-ID header.",
                )

            effective_role = x_role or "student"
            if (
                settings.enforce_api_key_role_restriction
                and settings.environment == "production"
                and effective_role not in ("student", "teacher")
            ):
                logger.warning(
                    "SECURITY: LMS service auth attempted role=%s for "
                    "user=%s — downgraded to student",
                    effective_role,
                    x_user_id,
                )
                effective_role = "student"

            user = AuthenticatedUser(
                user_id=x_user_id,
                auth_method="lms_service",
                role=effective_role,
                session_id=x_session_id,
                organization_id=x_org_id,
            )

            if x_org_id and settings.enable_org_membership_check:
                is_member = await _validate_org_membership(
                    user.user_id,
                    x_org_id,
                    user.role,
                )
                if not is_member:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"User is not a member of organization '{x_org_id}'",
                    )

            return user
        else:
            logger.warning("Invalid API key provided")
            # Sprint 176: Audit event (fire-and-forget, non-blocking)
            try:
                import asyncio
                from app.auth.auth_audit import log_auth_event
                asyncio.ensure_future(log_auth_event(
                    "auth_failed", provider="api_key", result="failed",
                    reason="Invalid API key",
                ))
            except Exception:
                pass
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )

    # Try JWT Token
    if credentials:
        token_payload = verify_jwt_token(credentials.credentials)
        # Sprint 28 SECURITY: JWT role from token payload, NOT from X-Role header
        # X-Role override is only allowed for API key auth (trusted LMS backend)
        jwt_role = token_payload.role or "student"
        # Sprint 157: OAuth tokens carry auth_method; legacy tokens default to "jwt"
        auth_method = token_payload.auth_method or "jwt"

        user = AuthenticatedUser(
            user_id=token_payload.sub,
            auth_method=auth_method,
            role=jwt_role,
            session_id=x_session_id,
            organization_id=x_org_id,
        )

        # Sprint 192: Validate org membership
        if x_org_id and settings.enable_org_membership_check:
            is_member = await _validate_org_membership(user.user_id, x_org_id, user.role)
            if not is_member:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"User is not a member of organization '{x_org_id}'",
                )

        return user

    # No authentication provided
    logger.warning("No authentication credentials provided")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Provide X-API-Key header or Bearer token.",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def optional_auth(
    api_key: Optional[str] = Security(api_key_header),
    credentials: Optional[HTTPAuthorizationCredentials] = Security(
        bearer_scheme
    ),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    x_role: Optional[str] = Header(None, alias="X-Role"),
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    x_org_id: Optional[str] = Header(None, alias="X-Organization-ID"),
) -> Optional[AuthenticatedUser]:
    """
    Optional authentication - returns None if not authenticated.
    Useful for endpoints that work with or without auth.

    LMS Integration: Passes all headers to require_auth.
    """
    try:
        return await require_auth(
            api_key,
            credentials,
            x_user_id, x_role, x_session_id, x_org_id
        )
    except HTTPException:
        return None

