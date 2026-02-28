"""
Sprint 178: Admin Analytics API — Phase 2

Endpoints:
  GET /admin/analytics/overview    — DAU, chat volume, error rate
  GET /admin/analytics/llm-usage   — Token/cost breakdown
  GET /admin/analytics/users       — User growth, engagement
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.admin_security import check_admin_module as _check_admin_module
from app.api.deps import RequireAdmin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/analytics", tags=["admin-analytics"])


async def _get_pool():
    from app.core.database import get_asyncpg_pool
    return await get_asyncpg_pool()


# =============================================================================
# GET /admin/analytics/overview
# =============================================================================

@router.get("/overview", dependencies=[Depends(_check_admin_module)])
async def analytics_overview(
    auth: RequireAdmin,
    from_date: Optional[str] = Query(None, alias="from", description="ISO date YYYY-MM-DD"),
    to_date: Optional[str] = Query(None, alias="to", description="ISO date YYYY-MM-DD"),
    org_id: Optional[str] = Query(None),
):
    """Overview analytics: daily active users, chat volume, error rate."""
    pool = await _get_pool()

    # Build safe date boundaries
    conditions_base = []
    params = []
    idx = 1

    if from_date:
        conditions_base.append(f"created_at >= ${idx}::timestamptz")
        params.append(from_date)
        idx += 1
    else:
        conditions_base.append("created_at >= NOW() - INTERVAL '30 days'")

    if to_date:
        conditions_base.append(f"created_at <= ${idx}::timestamptz")
        params.append(to_date)
        idx += 1

    org_cond = ""
    if org_id:
        org_cond = f" AND organization_id = ${idx}"
        params.append(org_id)
        idx += 1

    where = "WHERE " + " AND ".join(conditions_base)

    async with pool.acquire() as conn:
        # Daily active users (from chat_sessions)
        dau_rows = []
        try:
            dau_rows = await conn.fetch(
                f"""
                SELECT DATE(created_at) AS date, COUNT(DISTINCT user_id) AS count
                FROM chat_sessions
                {where} {org_cond}
                GROUP BY DATE(created_at)
                ORDER BY date
                """,
                *params,
            )
        except Exception as e:
            logger.debug("[ADMIN] DAU query failed: %s", e)

        # Chat volume
        chat_rows = []
        try:
            chat_rows = await conn.fetch(
                f"""
                SELECT DATE(created_at) AS date,
                       COUNT(*) AS messages,
                       COUNT(DISTINCT session_id) AS sessions
                FROM chat_sessions
                {where} {org_cond}
                GROUP BY DATE(created_at)
                ORDER BY date
                """,
                *params,
            )
        except Exception as e:
            logger.debug("[ADMIN] Chat volume query failed: %s", e)

        # Error rate from llm_usage_log
        error_rows = []
        try:
            error_rows = await conn.fetch(
                f"""
                SELECT DATE(created_at) AS date,
                       COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE duration_ms = 0 AND input_tokens = 0) AS errors
                FROM llm_usage_log
                {where} {org_cond}
                GROUP BY DATE(created_at)
                ORDER BY date
                """,
                *params,
            )
        except Exception as e:
            logger.debug("[ADMIN] Error rate query failed: %s", e)

    return {
        "period_start": from_date or "30 days ago",
        "period_end": to_date or "now",
        "daily_active_users": [
            {"date": str(r["date"]), "count": r["count"]} for r in dau_rows
        ],
        "chat_volume": [
            {"date": str(r["date"]), "messages": r["messages"], "sessions": r["sessions"]}
            for r in chat_rows
        ],
        "error_rate": [
            {
                "date": str(r["date"]),
                "total": r["total"],
                "errors": r["errors"],
                "rate": round(r["errors"] / max(r["total"], 1), 4),
            }
            for r in error_rows
        ],
    }


# =============================================================================
# GET /admin/analytics/llm-usage
# =============================================================================

@router.get("/llm-usage", dependencies=[Depends(_check_admin_module)])
async def analytics_llm_usage(
    auth: RequireAdmin,
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    org_id: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    group_by: str = Query("day", description="day, model, or org"),
):
    """LLM usage analytics: tokens, cost, breakdown."""
    pool = await _get_pool()

    conditions = ["created_at >= NOW() - INTERVAL '30 days'"]
    params = []
    idx = 1

    if from_date:
        conditions[0] = f"created_at >= ${idx}::timestamptz"
        params.append(from_date)
        idx += 1
    if to_date:
        conditions.append(f"created_at <= ${idx}::timestamptz")
        params.append(to_date)
        idx += 1
    if org_id:
        conditions.append(f"organization_id = ${idx}")
        params.append(org_id)
        idx += 1
    if model:
        conditions.append(f"model = ${idx}")
        params.append(model)
        idx += 1

    where = "WHERE " + " AND ".join(conditions)

    async with pool.acquire() as conn:
        # Totals
        try:
            totals = await conn.fetchrow(
                f"""
                SELECT COALESCE(SUM(input_tokens + output_tokens), 0) AS total_tokens,
                       COALESCE(SUM(estimated_cost_usd), 0) AS total_cost,
                       COUNT(*) AS total_requests
                FROM llm_usage_log {where}
                """,
                *params,
            )
        except Exception as e:
            logger.debug("[ADMIN] LLM totals query failed: %s", e)
            totals = {"total_tokens": 0, "total_cost": 0, "total_requests": 0}

        # Breakdown
        group_col_map = {
            "day": "DATE(created_at)",
            "model": "model",
            "org": "organization_id",
        }
        group_col = group_col_map.get(group_by, "DATE(created_at)")

        breakdown = []
        try:
            breakdown_rows = await conn.fetch(
                f"""
                SELECT {group_col} AS group_key,
                       SUM(input_tokens + output_tokens) AS tokens,
                       SUM(estimated_cost_usd) AS cost,
                       COUNT(*) AS requests
                FROM llm_usage_log {where}
                GROUP BY {group_col}
                ORDER BY {group_col}
                """,
                *params,
            )
            breakdown = [
                {
                    "group": str(r["group_key"]),
                    "tokens": r["tokens"] or 0,
                    "cost": float(r["cost"] or 0),
                    "requests": r["requests"],
                }
                for r in breakdown_rows
            ]
        except Exception as e:
            logger.debug("[ADMIN] LLM breakdown query failed: %s", e)

        # Top models
        top_models = []
        try:
            model_rows = await conn.fetch(
                f"""
                SELECT model, SUM(input_tokens + output_tokens) AS tokens, COUNT(*) AS requests
                FROM llm_usage_log {where}
                GROUP BY model ORDER BY tokens DESC LIMIT 10
                """,
                *params,
            )
            top_models = [
                {"model": r["model"], "tokens": r["tokens"] or 0, "requests": r["requests"]}
                for r in model_rows
            ]
        except Exception as e:
            logger.debug("[ADMIN] Top models query failed: %s", e)

        # Top users
        top_users = []
        try:
            user_rows = await conn.fetch(
                f"""
                SELECT user_id, SUM(input_tokens + output_tokens) AS tokens, COUNT(*) AS requests
                FROM llm_usage_log {where}
                GROUP BY user_id ORDER BY tokens DESC LIMIT 10
                """,
                *params,
            )
            top_users = [
                {"user_id": r["user_id"], "tokens": r["tokens"] or 0, "requests": r["requests"]}
                for r in user_rows
            ]
        except Exception as e:
            logger.debug("[ADMIN] Top users query failed: %s", e)

    return {
        "total_tokens": totals["total_tokens"],
        "total_cost_usd": float(totals["total_cost"]),
        "total_requests": totals["total_requests"],
        "breakdown": breakdown,
        "top_models": top_models,
        "top_users": top_users,
    }


# =============================================================================
# GET /admin/analytics/users
# =============================================================================

@router.get("/users", dependencies=[Depends(_check_admin_module)])
async def analytics_users(
    auth: RequireAdmin,
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    org_id: Optional[str] = Query(None),
):
    """User analytics: growth, engagement, role distribution."""
    pool = await _get_pool()

    conditions = []
    params = []
    idx = 1

    if from_date:
        conditions.append(f"created_at >= ${idx}::timestamptz")
        params.append(from_date)
        idx += 1
    else:
        conditions.append("created_at >= NOW() - INTERVAL '30 days'")

    if to_date:
        conditions.append(f"created_at <= ${idx}::timestamptz")
        params.append(to_date)
        idx += 1

    where = "WHERE " + " AND ".join(conditions)

    org_cond = ""
    if org_id:
        org_cond = f" AND organization_id = ${idx}"
        params.append(org_id)
        idx += 1

    async with pool.acquire() as conn:
        total_users = await conn.fetchval("SELECT COUNT(*) FROM users") or 0

        new_users = await conn.fetchval(
            f"SELECT COUNT(*) FROM users {where}",
            *params[:len(conditions)],
        ) or 0

        # Active users in period (from chat_sessions)
        active_users = 0
        try:
            active_users = await conn.fetchval(
                f"""
                SELECT COUNT(DISTINCT user_id) FROM chat_sessions
                {where} {org_cond}
                """,
                *params,
            ) or 0
        except Exception as e:
            logger.debug("[ADMIN] Active users query failed: %s", e)

        # User growth curve
        growth = []
        try:
            growth_rows = await conn.fetch(
                f"""
                SELECT DATE(created_at) AS date, COUNT(*) AS new_users
                FROM users
                {where}
                GROUP BY DATE(created_at)
                ORDER BY date
                """,
                *params[:len(conditions)],
            )
            growth = [{"date": str(r["date"]), "new_users": r["new_users"]} for r in growth_rows]
        except Exception as e:
            logger.debug("[ADMIN] User growth query failed: %s", e)

        # Role distribution
        role_dist = {}
        try:
            role_rows = await conn.fetch(
                "SELECT role, COUNT(*) AS count FROM users GROUP BY role"
            )
            role_dist = {r["role"]: r["count"] for r in role_rows}
        except Exception as e:
            logger.debug("[ADMIN] Role distribution query failed: %s", e)

        # Top active users
        top_active = []
        try:
            active_rows = await conn.fetch(
                f"""
                SELECT user_id, COUNT(*) AS sessions
                FROM chat_sessions
                {where} {org_cond}
                GROUP BY user_id
                ORDER BY sessions DESC
                LIMIT 10
                """,
                *params,
            )
            top_active = [
                {"user_id": r["user_id"], "sessions": r["sessions"]}
                for r in active_rows
            ]
        except Exception as e:
            logger.debug("[ADMIN] Top active users query failed: %s", e)

    return {
        "total_users": total_users,
        "new_users_period": new_users,
        "active_users_period": active_users,
        "user_growth": growth,
        "role_distribution": role_dist,
        "top_active_users": top_active,
    }
