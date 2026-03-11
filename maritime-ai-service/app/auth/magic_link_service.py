"""
Sprint 224: Magic Link Service — token generation, verification, WebSocket session management.
"""
import hashlib
import logging
import re
import secrets
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from fastapi import WebSocket


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Token generation + hashing
# ---------------------------------------------------------------------------

def generate_magic_token() -> Tuple[str, str]:
    """Generate a magic link token and its SHA256 hash.

    Returns:
        (raw_token, token_hash) — raw goes in the email link, hash goes in DB.
    """
    raw_token = secrets.token_urlsafe(48)
    token_hash = hash_token(raw_token)
    return raw_token, token_hash


def hash_token(raw_token: str) -> str:
    """SHA256 hash a raw token for DB storage."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Verification helpers (pure functions, no DB)
# ---------------------------------------------------------------------------

def is_token_expired(expires_at: datetime) -> bool:
    """Check if a token has expired."""
    return datetime.now(timezone.utc) >= expires_at


def is_token_used(used_at: Optional[datetime]) -> bool:
    """Check if a token has already been used."""
    return used_at is not None


def validate_email(email: str) -> bool:
    """Basic email format validation."""
    if not email or not email.strip():
        return False
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email.strip()))


# ---------------------------------------------------------------------------
# WebSocket session manager (in-memory, single-instance)
# ---------------------------------------------------------------------------

class MagicLinkSessionManager:
    """Manages WebSocket connections waiting for magic link verification."""

    def __init__(self):
        self._sessions: Dict[str, WebSocket] = {}

    async def register(self, session_id: str, websocket: WebSocket) -> None:
        """Register a WebSocket connection for a session."""
        await websocket.accept()
        self._sessions[session_id] = websocket
        logger.info("Magic link WS session registered: %s", session_id)

    async def push_tokens(self, session_id: str, payload: dict) -> bool:
        """Push auth tokens to a waiting WebSocket session.

        Returns True if delivered, False if session not found.
        """
        ws = self._sessions.pop(session_id, None)
        if ws is None:
            logger.warning("Magic link WS session not found: %s", session_id)
            return False
        try:
            await ws.send_json(payload)
            await ws.close()
            logger.info("Magic link tokens pushed to session: %s", session_id)
            return True
        except Exception as e:
            logger.error("Failed to push tokens to WS session %s: %s", session_id, e)
            return False

    def remove(self, session_id: str) -> None:
        """Remove a session (on disconnect or timeout)."""
        self._sessions.pop(session_id, None)

    @property
    def active_count(self) -> int:
        return len(self._sessions)


# Singleton
_session_manager: Optional[MagicLinkSessionManager] = None


def get_session_manager() -> MagicLinkSessionManager:
    """Get the singleton session manager."""
    global _session_manager
    if _session_manager is None:
        _session_manager = MagicLinkSessionManager()
    return _session_manager
