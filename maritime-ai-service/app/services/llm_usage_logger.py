"""
Sprint 178: LLM usage persistence.

Fire-and-forget INSERT into llm_usage_log table.
No-op when enable_admin_module=False. Never raises.
"""
import logging
from typing import Any, Mapping, Optional

from app.core.token_tracker import split_tracking_tier

logger = logging.getLogger(__name__)


def _get_call_field(call: Any, field_name: str, default: Any = None) -> Any:
    """Read a field from either dict-like or object-like call records."""
    if isinstance(call, Mapping):
        return call.get(field_name, default)
    return getattr(call, field_name, default)


def _normalize_call_record(call: Any) -> tuple[str, str, str, str, int, int, float, float]:
    """Normalize tracked call records into DB-ready columns."""
    model = str(_get_call_field(call, "model", "unknown") or "unknown")
    provider = str(_get_call_field(call, "provider", "") or "")
    raw_tier = str(_get_call_field(call, "tier", "") or "")
    inferred_provider, normalized_tier = split_tracking_tier(raw_tier)
    provider = provider or inferred_provider
    tier = normalized_tier or raw_tier
    component = str(_get_call_field(call, "component", "") or "")
    input_tokens = int(_get_call_field(call, "input_tokens", 0) or 0)
    output_tokens = int(_get_call_field(call, "output_tokens", 0) or 0)
    duration_ms = float(_get_call_field(call, "duration_ms", 0) or 0)
    estimated_cost_usd = float(_get_call_field(call, "estimated_cost_usd", 0) or 0)
    return (
        model,
        provider,
        tier,
        component,
        input_tokens,
        output_tokens,
        duration_ms,
        estimated_cost_usd,
    )


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
                (
                    model,
                    provider,
                    tier,
                    component,
                    input_tokens,
                    output_tokens,
                    duration_ms,
                    estimated_cost_usd,
                ) = _normalize_call_record(call)
                records.append((
                    request_id,
                    user_id,
                    session_id,
                    organization_id,
                    model,
                    provider,
                    tier,
                    component,
                    input_tokens,
                    output_tokens,
                    duration_ms,
                    estimated_cost_usd,
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
