"""
Sprint 178: LLM usage persistence.

Fire-and-forget INSERT into llm_usage_log table.
No-op when enable_admin_module=False. Never raises.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def log_llm_usage(
    request_id: str,
    user_id: str,
    session_id: str,
    model: str,
    provider: str,
    tier: str,
    input_tokens: int,
    output_tokens: int,
    duration_ms: float = 0,
    estimated_cost_usd: float = 0,
    component: str = "",
    organization_id: Optional[str] = None,
) -> None:
    """Fire-and-forget single LLM usage insert. Never raises."""
    try:
        from app.core.config import settings
        if not getattr(settings, "enable_admin_module", False):
            return

        from app.core.database import get_asyncpg_pool
        pool = await get_asyncpg_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO llm_usage_log
                    (request_id, user_id, session_id, organization_id,
                     model, provider, tier, component,
                     input_tokens, output_tokens, duration_ms, estimated_cost_usd)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                """,
                request_id,
                user_id,
                session_id,
                organization_id,
                model,
                provider or "",
                tier or "",
                component,
                input_tokens,
                output_tokens,
                duration_ms,
                estimated_cost_usd,
            )
    except Exception as e:
        logger.warning("Failed to log LLM usage: %s", e)


async def log_llm_usage_batch(
    request_id: str,
    user_id: str,
    session_id: str,
    calls: list,
    organization_id: Optional[str] = None,
) -> None:
    """Batch insert from TokenTracker.calls list. Never raises."""
    try:
        from app.core.config import settings
        if not getattr(settings, "enable_admin_module", False):
            return

        if not calls:
            return

        from app.core.database import get_asyncpg_pool
        pool = await get_asyncpg_pool()
        async with pool.acquire() as conn:
            records = []
            for call in calls:
                records.append((
                    request_id,
                    user_id,
                    session_id,
                    organization_id,
                    call.get("model", "unknown"),
                    call.get("provider", ""),
                    call.get("tier", ""),
                    call.get("component", ""),
                    call.get("input_tokens", 0),
                    call.get("output_tokens", 0),
                    call.get("duration_ms", 0),
                    call.get("estimated_cost_usd", 0),
                ))
            await conn.executemany(
                """
                INSERT INTO llm_usage_log
                    (request_id, user_id, session_id, organization_id,
                     model, provider, tier, component,
                     input_tokens, output_tokens, duration_ms, estimated_cost_usd)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                """,
                records,
            )
    except Exception as e:
        logger.warning("Failed to log LLM usage batch: %s", e)
