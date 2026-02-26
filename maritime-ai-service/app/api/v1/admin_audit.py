"""
Sprint 178: Admin Audit Trail Viewer — Phase 3

Endpoints:
  GET /admin/audit-logs   — Query admin audit log
  GET /admin/auth-events  — Query auth events (Sprint 176 table)
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.config import settings
from app.api.deps import RequireAdmin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin-audit"])


def _check_admin_module(request: Request):
    if not getattr(settings, "enable_admin_module", False):
        raise HTTPException(status_code=404, detail="Admin module not enabled")
    from app.core.admin_security import check_admin_ip_allowlist
    check_admin_ip_allowlist(request)


async def _get_pool():
    from app.core.database import get_asyncpg_pool
    return await get_asyncpg_pool()


# =============================================================================
# GET /admin/audit-logs
# =============================================================================

@router.get("/audit-logs", dependencies=[Depends(_check_admin_module)])
async def admin_audit_logs(
    auth: RequireAdmin,
    actor_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    target_type: Optional[str] = Query(None),
    target_id: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    org_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Query admin audit log with filters."""
    pool = await _get_pool()

    conditions = []
    params = []
    idx = 1

    if actor_id:
        conditions.append(f"actor_id = ${idx}")
        params.append(actor_id)
        idx += 1
    if action:
        conditions.append(f"action = ${idx}")
        params.append(action)
        idx += 1
    if target_type:
        conditions.append(f"target_type = ${idx}")
        params.append(target_type)
        idx += 1
    if target_id:
        conditions.append(f"target_id = ${idx}")
        params.append(target_id)
        idx += 1
    if from_date:
        conditions.append(f"occurred_at >= ${idx}::timestamptz")
        params.append(from_date)
        idx += 1
    if to_date:
        conditions.append(f"occurred_at <= ${idx}::timestamptz")
        params.append(to_date)
        idx += 1
    if org_id:
        conditions.append(f"organization_id = ${idx}")
        params.append(org_id)
        idx += 1

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    async with pool.acquire() as conn:
        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM admin_audit_log {where}", *params
        ) or 0

        rows = await conn.fetch(
            f"""
            SELECT id, actor_id, actor_role, actor_name, action,
                   http_method, http_path, http_status,
                   target_type, target_id, target_name,
                   old_value, new_value,
                   ip_address, user_agent, request_id, organization_id,
                   occurred_at
            FROM admin_audit_log {where}
            ORDER BY occurred_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
            """,
            *params,
            limit,
            offset,
        )

    entries = [
        {
            "id": r["id"],
            "actor_id": r["actor_id"],
            "actor_role": r["actor_role"],
            "actor_name": r["actor_name"],
            "action": r["action"],
            "http_method": r["http_method"],
            "http_path": r["http_path"],
            "http_status": r["http_status"],
            "target_type": r["target_type"],
            "target_id": r["target_id"],
            "target_name": r["target_name"],
            "old_value": r["old_value"],
            "new_value": r["new_value"],
            "ip_address": r["ip_address"],
            "request_id": r["request_id"],
            "organization_id": r["organization_id"],
            "occurred_at": r["occurred_at"].isoformat() if r["occurred_at"] else None,
        }
        for r in rows
    ]

    return {"entries": entries, "total": total, "limit": limit, "offset": offset}


# =============================================================================
# GET /admin/auth-events
# =============================================================================

@router.get("/auth-events", dependencies=[Depends(_check_admin_module)])
async def admin_auth_events(
    auth: RequireAdmin,
    user_id: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Query auth events (Sprint 176 auth_events table)."""
    pool = await _get_pool()

    conditions = []
    params = []
    idx = 1

    if user_id:
        conditions.append(f"user_id = ${idx}")
        params.append(user_id)
        idx += 1
    if event_type:
        conditions.append(f"event_type = ${idx}")
        params.append(event_type)
        idx += 1
    if from_date:
        conditions.append(f"created_at >= ${idx}::timestamptz")
        params.append(from_date)
        idx += 1
    if to_date:
        conditions.append(f"created_at <= ${idx}::timestamptz")
        params.append(to_date)
        idx += 1

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    async with pool.acquire() as conn:
        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM auth_events {where}", *params
        ) or 0

        rows = await conn.fetch(
            f"""
            SELECT id, event_type, user_id, provider, result, reason,
                   ip_address, user_agent, organization_id, metadata, created_at
            FROM auth_events {where}
            ORDER BY created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
            """,
            *params,
            limit,
            offset,
        )

    entries = [
        {
            "id": r["id"],
            "event_type": r["event_type"],
            "user_id": r["user_id"],
            "provider": r["provider"],
            "result": r["result"],
            "reason": r["reason"],
            "ip_address": r["ip_address"],
            "organization_id": r["organization_id"],
            "metadata": r["metadata"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]

    return {"entries": entries, "total": total, "limit": limit, "offset": offset}
