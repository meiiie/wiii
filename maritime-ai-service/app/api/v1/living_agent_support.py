"""Support helpers for living_agent API routes."""

from __future__ import annotations

import json

from sqlalchemy import text

from app.core.database import get_shared_session_factory
from app.core.org_filter import get_effective_org_id, org_where_clause


def fetch_browsing_log_entries(*, days: int, limit: int, response_cls):
    org_id = get_effective_org_id()
    org_clause = org_where_clause(org_id)

    session_factory = get_shared_session_factory()
    with session_factory() as session:
        params = {"days": days, "limit": limit}
        if org_id:
            params["org_id"] = org_id

        rows = session.execute(
            text(
                f"""
                SELECT id, platform, COALESCE(url, '') as url, title,
                       COALESCE(summary, '') as summary, relevance_score, browsed_at
                FROM wiii_browsing_log
                WHERE browsed_at >= NOW() - INTERVAL '1 day' * :days
                {org_clause}
                ORDER BY browsed_at DESC
                LIMIT :limit
                """
            ),
            params,
        ).fetchall()

        return [
            response_cls(
                id=str(row[0]),
                platform=row[1],
                url=row[2],
                title=row[3],
                summary=row[4],
                relevance_score=float(row[5]) if row[5] else 0.0,
                browsed_at=row[6].isoformat() if row[6] else "",
            )
            for row in rows
        ]


def fetch_pending_action_entries(*, status_filter: str | None, response_cls):
    org_id = get_effective_org_id()
    org_clause = org_where_clause(org_id)

    session_factory = get_shared_session_factory()
    with session_factory() as session:
        query = """
            SELECT id, action_type, COALESCE(target, '') as target,
                   priority, status, created_at, resolved_at, approved_by
            FROM wiii_pending_actions
            WHERE 1=1
        """
        params = {}
        if status_filter:
            query += " AND status = :status"
            params["status"] = status_filter
        query += org_clause
        if org_id:
            params["org_id"] = org_id
        query += " ORDER BY created_at DESC LIMIT 100"

        rows = session.execute(text(query), params).fetchall()

        return [
            response_cls(
                id=str(row[0]),
                action_type=row[1],
                target=row[2],
                priority=float(row[3]) if row[3] else 0.5,
                status=row[4],
                created_at=row[5].isoformat() if row[5] else "",
                resolved_at=row[6].isoformat() if row[6] else None,
                approved_by=row[7],
            )
            for row in rows
        ]


def resolve_pending_action_record(
    *,
    action_id: str,
    decision: str,
    approved_by: str,
    http_exception_cls,
):
    org_id = get_effective_org_id()
    org_clause = org_where_clause(org_id)

    session_factory = get_shared_session_factory()
    with session_factory() as session:
        select_params = {"id": action_id}
        if org_id:
            select_params["org_id"] = org_id
        row = session.execute(
            text(f"SELECT status FROM wiii_pending_actions WHERE id = :id{org_clause}"),
            select_params,
        ).fetchone()

        if not row:
            raise http_exception_cls(status_code=404, detail="Action not found")
        if row[0] != "pending":
            raise http_exception_cls(
                status_code=400,
                detail=f"Action is already {row[0]}",
            )

        new_status = "approved" if decision == "approve" else "rejected"
        update_params = {
            "status": new_status,
            "approved_by": approved_by,
            "id": action_id,
        }
        if org_id:
            update_params["org_id"] = org_id
        session.execute(
            text(
                f"""
                UPDATE wiii_pending_actions
                SET status = :status, approved_by = :approved_by, resolved_at = NOW()
                WHERE id = :id{org_clause}
                """
            ),
            update_params,
        )
        session.commit()


def fetch_heartbeat_audit_entries(*, limit: int, response_cls):
    org_id = get_effective_org_id()
    org_clause = org_where_clause(org_id)

    session_factory = get_shared_session_factory()
    with session_factory() as session:
        params = {"limit": limit}
        if org_id:
            params["org_id"] = org_id

        rows = session.execute(
            text(
                f"""
                SELECT id, cycle_number, actions_taken, insights_gained,
                       duration_ms, error, created_at
                FROM wiii_heartbeat_audit
                WHERE 1=1{org_clause}
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            params,
        ).fetchall()

        results = []
        for row in rows:
            try:
                actions = json.loads(row[2]) if row[2] else []
            except (json.JSONDecodeError, TypeError):
                actions = []

            results.append(
                response_cls(
                    id=str(row[0]),
                    cycle_number=row[1],
                    actions_taken=actions,
                    insights_gained=row[3] or 0,
                    duration_ms=row[4] or 0,
                    error=row[5],
                    created_at=row[6].isoformat() if row[6] else "",
                )
            )
        return results
