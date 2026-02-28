"""
Sprint 178: Admin Dashboard API — Phase 1

Endpoints:
  GET /admin/dashboard  — System overview counts
  GET /admin/users      — User search with filters
  GET /admin/feature-flags — Read all feature flags
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.config import settings
from app.core.admin_security import check_admin_module as _check_admin_module
from app.api.deps import RequireAdmin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


# =============================================================================
# GET /admin/dashboard
# =============================================================================

@router.get("/dashboard", dependencies=[Depends(_check_admin_module)])
async def admin_dashboard(auth: RequireAdmin):
    """System overview: user counts, sessions, token usage, active flags."""
    try:
        from app.core.database import get_asyncpg_pool
        pool = await get_asyncpg_pool()
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable")

    async with pool.acquire() as conn:
        total_users = await conn.fetchval("SELECT COUNT(*) FROM users") or 0
        active_users = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE is_active = true"
        ) or 0

        # Organizations
        total_orgs = 0
        org_list = []
        try:
            total_orgs = await conn.fetchval("SELECT COUNT(*) FROM organizations") or 0
            org_rows = await conn.fetch(
                "SELECT o.id, o.name, o.display_name, o.is_active, "
                "(SELECT COUNT(*) FROM user_organizations uo WHERE uo.organization_id = o.id) AS member_count, "
                "(SELECT COUNT(*) FROM organization_documents od WHERE od.organization_id = o.id AND od.status = 'ready') AS document_count "
                "FROM organizations o ORDER BY o.name"
            )
            org_list = [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "display_name": r["display_name"],
                    "member_count": r["member_count"],
                    "document_count": r["document_count"],
                    "is_active": r["is_active"],
                }
                for r in org_rows
            ]
        except Exception as e:
            logger.debug("[ADMIN] Dashboard org query failed: %s", e)

        # Chat sessions 24h
        try:
            total_sessions_24h = await conn.fetchval(
                "SELECT COUNT(DISTINCT session_id) FROM chat_sessions "
                "WHERE created_at >= NOW() - INTERVAL '24 hours'"
            ) or 0
        except Exception as e:
            logger.debug("[ADMIN] Dashboard sessions query failed: %s", e)
            total_sessions_24h = 0

        # LLM usage 24h
        total_tokens_24h = 0
        estimated_cost_24h = 0.0
        try:
            row = await conn.fetchrow(
                "SELECT COALESCE(SUM(input_tokens + output_tokens), 0) AS tokens, "
                "COALESCE(SUM(estimated_cost_usd), 0) AS cost "
                "FROM llm_usage_log WHERE created_at >= NOW() - INTERVAL '24 hours'"
            )
            if row:
                total_tokens_24h = row["tokens"]
                estimated_cost_24h = float(row["cost"])
        except Exception as e:
            logger.debug("[ADMIN] Dashboard LLM usage query failed: %s", e)

        # Active feature flags
        flags_active = sum(
            1
            for name in dir(settings)
            if name.startswith("enable_") and getattr(settings, name, False) is True
        )

    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_organizations": total_orgs,
        "total_chat_sessions_24h": total_sessions_24h,
        "total_llm_tokens_24h": total_tokens_24h,
        "estimated_cost_24h_usd": estimated_cost_24h,
        "feature_flags_active": flags_active,
        "organizations": org_list,
    }


# =============================================================================
# GET /admin/users
# =============================================================================

@router.get("/users", dependencies=[Depends(_check_admin_module)])
async def admin_user_search(
    auth: RequireAdmin,
    email: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    org_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None, description="active or inactive"),
    q: Optional[str] = Query(None, description="Free-text search on name/email"),
    sort: str = Query("created_at_desc"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Search users with filters, pagination, sorting."""
    try:
        from app.core.database import get_asyncpg_pool
        pool = await get_asyncpg_pool()
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable")

    conditions = []
    params = []
    idx = 1

    if email:
        conditions.append(f"u.email ILIKE ${idx}")
        params.append(f"%{email}%")
        idx += 1

    if role:
        conditions.append(f"u.role = ${idx}")
        params.append(role)
        idx += 1

    if status == "active":
        conditions.append("u.is_active = true")
    elif status == "inactive":
        conditions.append("u.is_active = false")

    if q:
        conditions.append(f"(u.name ILIKE ${idx} OR u.email ILIKE ${idx})")
        params.append(f"%{q}%")
        idx += 1

    if org_id:
        conditions.append(f"EXISTS (SELECT 1 FROM user_organizations uo WHERE uo.user_id = u.id AND uo.organization_id = ${idx})")
        params.append(org_id)
        idx += 1

    where_clause = " AND ".join(conditions)
    if where_clause:
        where_clause = "WHERE " + where_clause

    # Sort
    sort_map = {
        "created_at_desc": "u.created_at DESC",
        "created_at_asc": "u.created_at ASC",
        "name_asc": "u.name ASC",
        "name_desc": "u.name DESC",
        "email_asc": "u.email ASC",
    }
    order = sort_map.get(sort, "u.created_at DESC")

    async with pool.acquire() as conn:
        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM users u {where_clause}", *params
        )

        rows = await conn.fetch(
            f"""
            SELECT u.id, u.email, u.name, u.role, u.is_active, u.created_at,
                   (SELECT COUNT(*) FROM user_organizations uo WHERE uo.user_id = u.id) AS organization_count
            FROM users u
            {where_clause}
            ORDER BY {order}
            LIMIT ${idx} OFFSET ${idx + 1}
            """,
            *params,
            limit,
            offset,
        )

    users = [
        {
            "id": str(r["id"]),
            "email": r["email"],
            "name": r["name"],
            "role": r["role"],
            "is_active": r["is_active"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "organization_count": r["organization_count"],
        }
        for r in rows
    ]

    return {"users": users, "total": total or 0, "limit": limit, "offset": offset}


# =============================================================================
# GET /admin/feature-flags
# =============================================================================

@router.get("/feature-flags", dependencies=[Depends(_check_admin_module)])
async def admin_feature_flags_read(
    auth: RequireAdmin,
    org_id: Optional[str] = Query(None, description="Filter flags for a specific organization"),
):
    """Read all feature flags: config.py defaults merged with DB overrides.

    When org_id is provided, returns 3-layer cascade:
    config → global DB override → org-specific override.
    """
    try:
        from app.services.feature_flag_service import list_all_flags
        return await list_all_flags(org_id=org_id)
    except Exception as e:
        logger.debug("[ADMIN] Feature flag service unavailable, config-only fallback: %s", e)
        # Fallback: config-only flags if feature_flag_service unavailable
        flags = []
        for name in sorted(dir(settings)):
            if not name.startswith("enable_"):
                continue
            val = getattr(settings, name, None)
            if not isinstance(val, bool):
                continue
            flags.append({
                "key": name,
                "value": val,
                "source": "config",
                "flag_type": "release",
                "description": None,
                "owner": None,
                "expires_at": None,
            })
        return flags
