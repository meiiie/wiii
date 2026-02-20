"""
Sprint 157: User service — find-or-create users, link identities.

Operates on the `users` and `user_identities` tables.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import asyncpg

from app.core.config import settings

logger = logging.getLogger(__name__)


async def _get_pool() -> asyncpg.Pool:
    """Get the shared asyncpg connection pool."""
    from app.core.database import get_asyncpg_pool
    return await get_asyncpg_pool()


async def find_user_by_provider(
    provider: str,
    provider_sub: str,
    provider_issuer: Optional[str] = None,
) -> Optional[dict]:
    """
    Find a Wiii user by provider identity.

    Returns dict with user fields or None.
    """
    pool = await _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT u.id, u.email, u.name, u.avatar_url, u.role, u.is_active
            FROM user_identities ui
            JOIN users u ON u.id = ui.user_id
            WHERE ui.provider = $1
              AND ui.provider_sub = $2
              AND (ui.provider_issuer = $3 OR ($3 IS NULL AND ui.provider_issuer IS NULL))
            """,
            provider, provider_sub, provider_issuer,
        )
        if row:
            # Update last_used_at
            await conn.execute(
                """
                UPDATE user_identities SET last_used_at = NOW()
                WHERE provider = $1 AND provider_sub = $2
                  AND (provider_issuer = $3 OR ($3 IS NULL AND provider_issuer IS NULL))
                """,
                provider, provider_sub, provider_issuer,
            )
            return dict(row)
    return None


async def find_user_by_email(email: str) -> Optional[dict]:
    """Find a user by email (case-insensitive)."""
    pool = await _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, email, name, avatar_url, role, is_active FROM users WHERE LOWER(email) = LOWER($1)",
            email,
        )
        return dict(row) if row else None


async def create_user(
    email: Optional[str],
    name: Optional[str],
    avatar_url: Optional[str] = None,
    role: str = "student",
) -> dict:
    """Create a new Wiii user. Returns user dict with id."""
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    pool = await _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (id, email, name, avatar_url, role, is_active, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, true, $6, $6)
            """,
            user_id, email, name, avatar_url, role, now,
        )
    logger.info("Created user %s (email=%s)", user_id, email)
    return {"id": user_id, "email": email, "name": name, "avatar_url": avatar_url, "role": role, "is_active": True}


async def link_identity(
    user_id: str,
    provider: str,
    provider_sub: str,
    provider_issuer: Optional[str] = None,
    email: Optional[str] = None,
    display_name: Optional[str] = None,
    avatar_url: Optional[str] = None,
) -> str:
    """Link an external identity to a Wiii user. Returns identity ID."""
    identity_id = str(uuid.uuid4())
    pool = await _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO user_identities (id, user_id, provider, provider_sub, provider_issuer, email, display_name, avatar_url, linked_at, last_used_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW(), NOW())
            ON CONFLICT (provider, provider_sub, provider_issuer) DO UPDATE
              SET last_used_at = NOW(), email = EXCLUDED.email, display_name = EXCLUDED.display_name, avatar_url = EXCLUDED.avatar_url
            """,
            identity_id, user_id, provider, provider_sub, provider_issuer, email, display_name, avatar_url,
        )
    logger.info("Linked identity %s/%s to user %s", provider, provider_sub, user_id)
    return identity_id


async def find_or_create_by_google(
    google_sub: str,
    email: str,
    name: Optional[str] = None,
    avatar_url: Optional[str] = None,
) -> dict:
    """
    Find existing user by Google identity or create a new one.

    Strategy:
    1. Look up by (google, google_sub) → exact match
    2. Look up by email → auto-link Google identity
    3. Create new user + link Google identity
    """
    # 1. Exact provider match
    user = await find_user_by_provider("google", google_sub)
    if user:
        logger.debug("Google login: existing user %s", user["id"])
        return user

    # 2. Email match → auto-link
    user = await find_user_by_email(email)
    if user:
        await link_identity(
            user_id=user["id"],
            provider="google",
            provider_sub=google_sub,
            email=email,
            display_name=name,
            avatar_url=avatar_url,
        )
        logger.info("Google login: auto-linked to existing user %s via email %s", user["id"], email)
        return user

    # 3. New user
    user = await create_user(email=email, name=name, avatar_url=avatar_url)
    await link_identity(
        user_id=user["id"],
        provider="google",
        provider_sub=google_sub,
        email=email,
        display_name=name,
        avatar_url=avatar_url,
    )
    logger.info("Google login: created new user %s for email %s", user["id"], email)
    return user
