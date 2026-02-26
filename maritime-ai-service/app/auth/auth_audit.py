"""
Sprint 176: Auth audit event logging.

Fire-and-forget INSERT into auth_events table.
No-op when enable_auth_audit=False. Never raises.
"""
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def log_auth_event(
    event_type: str,
    user_id: Optional[str] = None,
    provider: Optional[str] = None,
    result: str = "success",
    reason: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    organization_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> None:
    """Fire-and-forget auth event logging. No-op when enable_auth_audit=False."""
    try:
        from app.core.config import settings
        if not settings.enable_auth_audit:
            return

        from app.core.database import get_asyncpg_pool
        pool = await get_asyncpg_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO auth_events (event_type, user_id, provider, result, reason,
                                         ip_address, user_agent, organization_id, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb)
                """,
                event_type,
                user_id,
                provider,
                result,
                reason,
                ip_address,
                user_agent,
                organization_id,
                json.dumps(metadata, ensure_ascii=False) if metadata else None,
            )
    except Exception as e:
        logger.warning("Failed to log auth event %s: %s", event_type, e)
