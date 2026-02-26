"""
Sprint 178: Admin audit event logging.

Fire-and-forget INSERT into admin_audit_log table.
No-op when enable_admin_module=False. Never raises.
"""
import json
import logging
from typing import Optional

from fastapi import Request

logger = logging.getLogger(__name__)


async def log_admin_action(
    actor_id: str,
    action: str,
    *,
    actor_role: str = "admin",
    actor_name: Optional[str] = None,
    http_method: Optional[str] = None,
    http_path: Optional[str] = None,
    http_status: Optional[int] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    target_name: Optional[str] = None,
    old_value: Optional[dict] = None,
    new_value: Optional[dict] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    request_id: Optional[str] = None,
    organization_id: Optional[str] = None,
) -> None:
    """Fire-and-forget admin audit. No-op when enable_admin_module=False. Never raises."""
    try:
        from app.core.config import settings
        if not getattr(settings, "enable_admin_module", False):
            return

        from app.core.database import get_asyncpg_pool
        pool = await get_asyncpg_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO admin_audit_log
                    (actor_id, actor_role, actor_name, action,
                     http_method, http_path, http_status,
                     target_type, target_id, target_name,
                     old_value, new_value,
                     ip_address, user_agent, request_id, organization_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                        $11::jsonb, $12::jsonb, $13, $14, $15, $16)
                """,
                actor_id,
                actor_role,
                actor_name,
                action,
                http_method,
                http_path,
                http_status,
                target_type,
                target_id,
                target_name,
                json.dumps(old_value, ensure_ascii=False) if old_value else None,
                json.dumps(new_value, ensure_ascii=False) if new_value else None,
                ip_address,
                user_agent,
                request_id,
                organization_id,
            )
    except Exception as e:
        logger.warning("Failed to log admin action %s: %s", action, e)


def extract_audit_context(request: Request) -> dict:
    """Extract audit context from a FastAPI Request object."""
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
        "request_id": request.headers.get("x-request-id"),
        "organization_id": request.headers.get("x-organization-id"),
        "http_method": request.method,
        "http_path": str(request.url.path),
    }
