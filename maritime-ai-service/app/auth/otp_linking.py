"""
Sprint 176: Database-backed OTP service for cross-platform identity linking.

Replaces Sprint 174b in-memory _otp_store with persistent DB table.
Cluster-safe, survives restarts.

Flow:
  1. User (logged in via JWT) calls POST /users/me/identities/link -> gets 6-digit code
  2. User sends code on Messenger/Zalo
  3. Webhook intercepts 6-digit message -> verify_and_link() -> links identity
  4. Code marked used_at after use; expired codes cleaned up on generate
"""
import logging
import random
import secrets
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


def _get_expiry_seconds() -> int:
    """Get OTP expiry from settings (lazy to avoid import-time config load)."""
    from app.core.config import settings
    return settings.otp_link_expiry_seconds


async def generate_link_code(user_id: str, channel_type: str) -> str:
    """Generate 6-digit OTP for identity linking.

    - Cleans up expired codes
    - Sprint 192: Rate limit — max N codes per user per window
    - Invalidates any existing code for same user+channel
    - Returns 6-digit string (100000-999999)
    - Stored in otp_link_codes table (Sprint 176: DB-backed)

    Raises:
        ValueError: If rate limit exceeded
    """
    from app.core.config import settings
    from app.core.database import get_asyncpg_pool

    code = f"{secrets.randbelow(900000) + 100000}"
    expiry = _get_expiry_seconds()
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expiry)

    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        # Sprint 194c (B8): Probabilistic cleanup — run 10% of the time
        # to reduce DB load at scale (was: every generate call)
        if random.random() < 0.1:
            await conn.execute(
                "DELETE FROM otp_link_codes WHERE expires_at < NOW()"
            )

        # Sprint 192: Rate limit — count recent codes for this user
        window_start = datetime.now(timezone.utc) - timedelta(minutes=settings.otp_generate_window_minutes)
        recent_count = await conn.fetchval(
            "SELECT COUNT(*) FROM otp_link_codes WHERE user_id = $1 AND created_at >= $2",
            user_id, window_start,
        )
        if recent_count is not None and recent_count >= settings.otp_max_generate_per_window:
            logger.warning(
                "OTP rate limit exceeded for user %s: %d codes in %d min",
                user_id, recent_count, settings.otp_generate_window_minutes,
            )
            raise ValueError(
                f"Rate limit exceeded: max {settings.otp_max_generate_per_window} "
                f"codes per {settings.otp_generate_window_minutes} minutes"
            )

        # Revoke existing codes for same user+channel
        await conn.execute(
            "DELETE FROM otp_link_codes WHERE user_id = $1 AND channel_type = $2 AND used_at IS NULL",
            user_id, channel_type,
        )
        # Insert new code
        await conn.execute(
            """
            INSERT INTO otp_link_codes (code, user_id, channel_type, expires_at, created_at)
            VALUES ($1, $2, $3, $4, NOW())
            """,
            code, user_id, channel_type, expires_at,
        )

    logger.info("Generated OTP for user %s on %s", user_id, channel_type)
    return code


async def verify_and_link(
    code: str, channel_type: str, platform_sender_id: str
) -> tuple[bool, str]:
    """Verify OTP and link identity.

    Sprint 192: Lockout after N failed attempts — burns the code.
    Sprint 194c: Exponential backoff between failed attempts.

    Returns:
        (success, message) where message is:
        - user_id on success
        - "expired" if code was valid but expired
        - "locked" if code was burned due to too many failed attempts
        - "rate_limited" if exponential cooldown period not elapsed
        - "" if code not found or channel mismatch
    """
    from app.core.config import settings
    from app.core.database import get_asyncpg_pool

    pool = await get_asyncpg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT user_id, channel_type, expires_at, used_at, "
            "COALESCE(failed_attempts, 0) as failed_attempts, "
            "updated_at "
            "FROM otp_link_codes WHERE code = $1",
            code,
        )

        if not row:
            return False, ""

        if row["channel_type"] != channel_type:
            # Sprint 192: Increment failed attempts even for wrong channel
            await conn.execute(
                "UPDATE otp_link_codes SET failed_attempts = COALESCE(failed_attempts, 0) + 1, "
                "updated_at = NOW() WHERE code = $1",
                code,
            )
            return False, ""

        if row["used_at"] is not None:
            return False, ""

        # Sprint 192: Check lockout (burned code)
        if row["failed_attempts"] >= settings.otp_max_verify_attempts:
            # Burn the code
            await conn.execute(
                "UPDATE otp_link_codes SET used_at = NOW() WHERE code = $1",
                code,
            )
            logger.warning(
                "OTP code burned after %d failed attempts for user %s",
                row["failed_attempts"], row["user_id"],
            )
            return False, "locked"

        # Sprint 194c (B3): Exponential cooldown after failed attempts
        # Delay = 2^(attempts-1) seconds, capped at 60s
        if row["failed_attempts"] > 0 and row["updated_at"] is not None:
            cooldown_seconds = min(2 ** (row["failed_attempts"] - 1), 60)
            last_attempt = row["updated_at"]
            if last_attempt.tzinfo is None:
                last_attempt = last_attempt.replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - last_attempt).total_seconds()
            if elapsed < cooldown_seconds:
                return False, "rate_limited"

        if row["expires_at"].replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            # Mark expired code as used to prevent retry
            await conn.execute(
                "UPDATE otp_link_codes SET used_at = NOW() WHERE code = $1",
                code,
            )
            return False, "expired"

        # Mark code as used
        await conn.execute(
            "UPDATE otp_link_codes SET used_at = NOW(), linked_platform_sender_id = $2 WHERE code = $1",
            code, platform_sender_id,
        )

    # Link identity via user_service
    from app.auth.user_service import link_identity
    await link_identity(
        user_id=row["user_id"],
        provider=channel_type,
        provider_sub=platform_sender_id,
    )

    logger.info(
        "OTP verified: linked %s/%s to user %s",
        channel_type, platform_sender_id, row["user_id"],
    )

    # Sprint 177: Trigger cross-platform memory merge (non-blocking)
    try:
        from app.core.config import settings
        if settings.enable_cross_platform_memory:
            from app.engine.semantic_memory.cross_platform import get_cross_platform_memory
            merger = get_cross_platform_memory()
            legacy_id = f"{channel_type}_{platform_sender_id}"
            await merger.merge_memories(
                canonical_user_id=row["user_id"],
                legacy_user_id=legacy_id,
                channel_type=channel_type,
            )
    except Exception as e:
        logger.warning("Cross-platform memory merge failed (non-blocking): %s", e)

    return True, row["user_id"]
