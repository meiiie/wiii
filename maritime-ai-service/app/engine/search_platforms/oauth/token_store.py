"""
OAuth Token Store — Sprint 149 Skeleton

Encrypted token storage for platform OAuth credentials.
Uses Fernet symmetric encryption for tokens at rest (Vietnam PDPL 01/2026 compliance).

Future implementation will store tokens in PostgreSQL:
    CREATE TABLE oauth_tokens (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id VARCHAR(255) NOT NULL,
        platform_id VARCHAR(100) NOT NULL,
        access_token_encrypted BYTEA NOT NULL,
        refresh_token_encrypted BYTEA,
        expires_at TIMESTAMPTZ,
        scopes TEXT[],
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE (user_id, platform_id)
    );

This is a skeleton — no runtime behavior until enable_oauth_token_store=True.
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class OAuthToken:
    """Represents a stored OAuth token for a user+platform pair."""
    user_id: str
    platform_id: str
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[float] = None
    scopes: Optional[list] = None


class OAuthTokenStore:
    """
    Encrypted OAuth token storage (skeleton).

    Future: Fernet encryption + PostgreSQL persistence.
    Current: In-memory only, for development/testing.
    """

    def __init__(self, encryption_key: Optional[str] = None):
        self._encryption_key = encryption_key
        self._tokens: dict = {}  # (user_id, platform_id) → OAuthToken
        if encryption_key:
            logger.info("OAuthTokenStore initialized with encryption")
        else:
            logger.debug("OAuthTokenStore initialized (no encryption, dev mode)")

    async def store_token(self, token: OAuthToken) -> None:
        """Store an OAuth token (encrypted at rest in production)."""
        key = (token.user_id, token.platform_id)
        self._tokens[key] = token
        logger.debug("Stored OAuth token for user=%s platform=%s", token.user_id, token.platform_id)

    async def get_token(self, user_id: str, platform_id: str) -> Optional[OAuthToken]:
        """Retrieve an OAuth token."""
        return self._tokens.get((user_id, platform_id))

    async def delete_token(self, user_id: str, platform_id: str) -> bool:
        """Delete an OAuth token."""
        key = (user_id, platform_id)
        if key in self._tokens:
            del self._tokens[key]
            return True
        return False

    async def has_valid_token(self, user_id: str, platform_id: str) -> bool:
        """Check if a valid (non-expired) token exists."""
        import time
        token = self._tokens.get((user_id, platform_id))
        if token is None:
            return False
        if token.expires_at and time.time() > token.expires_at:
            return False
        return True
