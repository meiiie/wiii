"""
Sprint 157: Token service — create, refresh, revoke JWT tokens.

Access tokens: short-lived (configurable, default 30 min)
Refresh tokens: long-lived (configurable, default 30 days), stored hashed in DB
"""
import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)


class TokenPair(BaseModel):
    """Access + refresh token pair returned after authentication."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until access token expires


class AccessTokenPayload(BaseModel):
    """Decoded access token claims."""
    sub: str  # Wiii user ID
    email: Optional[str] = None
    name: Optional[str] = None
    role: str = "student"
    auth_method: str = "google"  # google, lti, api_key
    type: str = "access"
    exp: datetime
    iat: datetime
    iss: str = "wiii"


def _hash_token(token: str) -> str:
    """SHA-256 hash a token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(
    user_id: str,
    email: Optional[str] = None,
    name: Optional[str] = None,
    role: str = "student",
    auth_method: str = "google",
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a short-lived JWT access token."""
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.jwt_expire_minutes))

    payload = {
        "sub": user_id,
        "email": email,
        "name": name,
        "role": role,
        "auth_method": auth_method,
        "type": "access",
        "iss": "wiii",
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token() -> str:
    """Create a cryptographically random refresh token."""
    return secrets.token_urlsafe(64)


def verify_access_token(token: str) -> AccessTokenPayload:
    """Verify and decode an access token. Raises JWTError on failure."""
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    return AccessTokenPayload(**payload)


async def create_token_pair(
    user_id: str,
    email: Optional[str] = None,
    name: Optional[str] = None,
    role: str = "student",
    auth_method: str = "google",
) -> TokenPair:
    """Create access + refresh token pair and store refresh token hash in DB."""
    access_token = create_access_token(
        user_id=user_id,
        email=email,
        name=name,
        role=role,
        auth_method=auth_method,
    )
    refresh_token = create_refresh_token()

    # Store refresh token hash in DB
    token_id = str(uuid.uuid4())
    token_hash = _hash_token(refresh_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_expire_days)

    try:
        from app.core.database import get_asyncpg_pool
        pool = await get_asyncpg_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO refresh_tokens (id, user_id, token_hash, auth_method, expires_at, created_at)
                VALUES ($1, $2, $3, $4, $5, NOW())
                """,
                token_id, user_id, token_hash, auth_method, expires_at,
            )
    except Exception:
        logger.warning("Failed to store refresh token — token will be stateless only")

    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_expire_minutes * 60,
    )


async def refresh_access_token(refresh_token: str) -> Optional[TokenPair]:
    """
    Validate a refresh token and issue a new token pair.

    Returns new TokenPair or None if refresh token is invalid/expired/revoked.
    Implements refresh token rotation (old token revoked, new one issued).
    """
    token_hash = _hash_token(refresh_token)

    try:
        from app.core.database import get_asyncpg_pool
        pool = await get_asyncpg_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT rt.id, rt.user_id, rt.expires_at, rt.revoked_at, rt.auth_method,
                       u.email, u.name, u.role
                FROM refresh_tokens rt
                JOIN users u ON u.id = rt.user_id
                WHERE rt.token_hash = $1
                """,
                token_hash,
            )

            if not row:
                logger.warning("Refresh token not found")
                return None

            if row["revoked_at"] is not None:
                logger.warning("Refresh token already revoked (user %s)", row["user_id"])
                return None

            if row["expires_at"].replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
                logger.warning("Refresh token expired (user %s)", row["user_id"])
                return None

            # Revoke the old refresh token (rotation)
            await conn.execute(
                "UPDATE refresh_tokens SET revoked_at = NOW() WHERE id = $1",
                row["id"],
            )

            # Issue new pair
            return await create_token_pair(
                user_id=row["user_id"],
                email=row["email"],
                name=row["name"],
                role=row["role"],
                auth_method=row.get("auth_method") or "google",  # Refresh inherits original method
            )
    except Exception:
        logger.exception("Error during token refresh")
        return None


async def revoke_user_tokens(user_id: str) -> int:
    """Revoke all refresh tokens for a user (logout everywhere). Returns count revoked."""
    try:
        from app.core.database import get_asyncpg_pool
        pool = await get_asyncpg_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE refresh_tokens SET revoked_at = NOW() WHERE user_id = $1 AND revoked_at IS NULL",
                user_id,
            )
            count = int(result.split()[-1])
            logger.info("Revoked %d refresh tokens for user %s", count, user_id)
            return count
    except Exception:
        logger.exception("Error revoking tokens for user %s", user_id)
        return 0
