"""
Sprint 224: Magic Link Service — token generation, verification, WebSocket session management.
"""
import asyncio
import hashlib
import logging
import re
import secrets
from datetime import datetime, timezone
from typing import Optional, Tuple


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
# WebSocket session manager
#
# The store implementation is selected at startup via
# ``initialize_session_store`` in ``magic_link_session_store.py``. The default
# is a single-process in-memory dict; with
# ``enable_distributed_magic_link_sessions=True`` and a reachable Valkey, it
# becomes a Valkey-backed store that survives FastAPI restarts and works
# across multiple workers. Call sites use this thin alias so they remain
# decoupled from the choice.
# ---------------------------------------------------------------------------

# Backward-compat re-exports — older code may still import these names from here.
from app.auth.magic_link_session_store import (  # noqa: E402 (intentional late re-export)
    InMemorySessionStore as MagicLinkSessionManager,
    _SessionEntry,
    get_session_store,
)


def get_session_manager():
    """Return the active session store (in-memory or Valkey, picked at startup)."""
    return get_session_store()


# ---------------------------------------------------------------------------
# DB cleanup — runs periodically from the FastAPI lifespan
# ---------------------------------------------------------------------------

async def cleanup_expired_tokens(grace_period_hours: int = 24) -> int:
    """Delete ``magic_link_tokens`` rows whose ``expires_at`` is past plus a grace period.

    The verify endpoint already rejects expired tokens, so deleting them is purely
    operational hygiene: it caps table size, keeps the per-email rate-limit COUNT
    fast, and avoids unbounded growth in production.

    Returns the number of rows deleted (0 on any error — never raises).
    """
    if grace_period_hours < 0:
        grace_period_hours = 0
    try:
        from app.core.database import get_asyncpg_pool

        pool = await get_asyncpg_pool()
        async with pool.acquire() as conn:
            # asyncpg treats parameterised intervals oddly; use a make_interval-style cast
            # to keep the query injection-safe while supporting any positive grace value.
            result = await conn.execute(
                """
                DELETE FROM magic_link_tokens
                WHERE expires_at < NOW() - ($1::int * INTERVAL '1 hour')
                """,
                int(grace_period_hours),
            )
        # asyncpg execute() returns "DELETE <n>" — parse the trailing count
        try:
            deleted = int(result.split()[-1])
        except (ValueError, AttributeError, IndexError):
            deleted = 0
        if deleted:
            logger.info(
                "Magic link cleanup deleted %d expired token row(s) (grace=%dh)",
                deleted,
                grace_period_hours,
            )
        return deleted
    except Exception as exc:
        logger.warning("Magic link cleanup failed: %s", exc)
        return 0


async def magic_link_cleanup_loop(
    interval_seconds: float,
    grace_period_hours: int = 24,
) -> None:
    """Background loop: run ``cleanup_expired_tokens`` every ``interval_seconds``.

    Intended to be wrapped in ``asyncio.create_task`` from the FastAPI lifespan
    and cancelled on shutdown.
    """
    interval = max(60.0, float(interval_seconds))
    while True:
        try:
            await asyncio.sleep(interval)
            await cleanup_expired_tokens(grace_period_hours)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Magic link cleanup loop iteration failed: %s", exc)


async def magic_link_session_reaper_loop(
    interval_seconds: float,
    max_age_seconds: float,
) -> None:
    """Background loop: drop stale in-memory WS sessions every ``interval_seconds``.

    Intended to be wrapped in ``asyncio.create_task`` from the FastAPI lifespan
    and cancelled on shutdown.
    """
    interval = max(15.0, float(interval_seconds))
    while True:
        try:
            await asyncio.sleep(interval)
            mgr = get_session_manager()
            mgr.reap_stale(max_age_seconds)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Magic link session reaper loop iteration failed: %s", exc)
