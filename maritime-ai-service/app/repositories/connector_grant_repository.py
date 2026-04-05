"""Connector grant repository for durable host/workspace connections.

Connector grants represent a durable relationship between a canonical Wiii
user and an external host/workspace such as LMS. They are intentionally
separate from live page/runtime host session state.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import asyncpg

logger = logging.getLogger(__name__)


def _normalize_json(value: Optional[dict[str, Any]]) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def build_connector_grant_key(
    connector_id: str,
    *,
    host_user_id: Optional[str] = None,
    host_workspace_id: Optional[str] = None,
) -> str:
    """Build a stable grant key scoped to connector + external account/workspace."""
    normalized_connector = str(connector_id or "").strip() or "unknown-connector"
    normalized_user = str(host_user_id or "").strip() or "*"
    normalized_workspace = str(host_workspace_id or "").strip() or "*"
    return f"{normalized_connector}:{normalized_user}:{normalized_workspace}"


def _is_missing_table_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "connector_grants" in message and (
        "does not exist" in message or "undefinedtable" in message
    )


async def _get_pool() -> asyncpg.Pool:
    from app.core.database import get_asyncpg_pool

    return await get_asyncpg_pool()


def _format_grant_row(row: dict[str, Any]) -> dict[str, Any]:
    result = dict(row)
    for key in (
        "created_at",
        "updated_at",
        "last_connected_at",
        "last_used_at",
    ):
        value = result.get(key)
        if value is not None and hasattr(value, "isoformat"):
            result[key] = value.isoformat()
    if not isinstance(result.get("granted_capabilities"), dict):
        result["granted_capabilities"] = {}
    if not isinstance(result.get("auth_metadata"), dict):
        result["auth_metadata"] = {}
    return result


async def upsert_connector_grant(
    *,
    user_id: str,
    connector_id: str,
    host_type: str,
    host_name: Optional[str] = None,
    host_user_id: Optional[str] = None,
    host_workspace_id: Optional[str] = None,
    host_organization_id: Optional[str] = None,
    organization_id: Optional[str] = None,
    granted_capabilities: Optional[dict[str, Any]] = None,
    auth_metadata: Optional[dict[str, Any]] = None,
    status: str = "active",
) -> Optional[dict[str, Any]]:
    """Create or refresh a durable connector grant.

    Best-effort by design: if the migration has not landed yet, return None and
    let authentication continue.
    """

    grant_key = build_connector_grant_key(
        connector_id,
        host_user_id=host_user_id,
        host_workspace_id=host_workspace_id,
    )
    capabilities = _normalize_json(granted_capabilities)
    metadata = _normalize_json(auth_metadata)

    pool = await _get_pool()
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO connector_grants (
                    user_id,
                    connector_id,
                    grant_key,
                    host_type,
                    host_name,
                    host_user_id,
                    host_workspace_id,
                    host_organization_id,
                    organization_id,
                    granted_capabilities,
                    auth_metadata,
                    status,
                    last_connected_at,
                    last_used_at,
                    created_at,
                    updated_at
                )
                VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9,
                    $10::jsonb, $11::jsonb, $12,
                    NOW(), NOW(), NOW(), NOW()
                )
                ON CONFLICT (user_id, grant_key) DO UPDATE
                SET
                    connector_id = EXCLUDED.connector_id,
                    host_type = EXCLUDED.host_type,
                    host_name = EXCLUDED.host_name,
                    host_user_id = EXCLUDED.host_user_id,
                    host_workspace_id = EXCLUDED.host_workspace_id,
                    host_organization_id = EXCLUDED.host_organization_id,
                    organization_id = EXCLUDED.organization_id,
                    granted_capabilities = EXCLUDED.granted_capabilities,
                    auth_metadata = EXCLUDED.auth_metadata,
                    status = EXCLUDED.status,
                    last_connected_at = NOW(),
                    last_used_at = NOW(),
                    updated_at = NOW()
                RETURNING
                    id,
                    user_id,
                    connector_id,
                    grant_key,
                    host_type,
                    host_name,
                    host_user_id,
                    host_workspace_id,
                    host_organization_id,
                    organization_id,
                    granted_capabilities,
                    auth_metadata,
                    status,
                    created_at,
                    updated_at,
                    last_connected_at,
                    last_used_at
                """,
                user_id,
                connector_id,
                grant_key,
                host_type,
                host_name,
                host_user_id,
                host_workspace_id,
                host_organization_id,
                organization_id,
                capabilities,
                metadata,
                status,
            )
        except Exception as exc:
            if _is_missing_table_error(exc):
                logger.info(
                    "connector_grants table unavailable; skipping grant upsert for %s/%s",
                    user_id,
                    connector_id,
                )
                return None
            raise
    return _format_grant_row(dict(row)) if row else None


async def list_connector_grants_for_user(user_id: str) -> list[dict[str, Any]]:
    """List durable connector grants for a canonical Wiii user."""
    pool = await _get_pool()
    async with pool.acquire() as conn:
        try:
            rows = await conn.fetch(
                """
                SELECT
                    id,
                    user_id,
                    connector_id,
                    grant_key,
                    host_type,
                    host_name,
                    host_user_id,
                    host_workspace_id,
                    host_organization_id,
                    organization_id,
                    granted_capabilities,
                    auth_metadata,
                    status,
                    created_at,
                    updated_at,
                    last_connected_at,
                    last_used_at
                FROM connector_grants
                WHERE user_id = $1
                ORDER BY last_used_at DESC NULLS LAST, created_at DESC
                """,
                user_id,
            )
        except Exception as exc:
            if _is_missing_table_error(exc):
                return []
            raise
    return [_format_grant_row(dict(row)) for row in rows]


async def count_connector_grants_for_user(user_id: str) -> int:
    """Count connector grants for profile summaries."""
    pool = await _get_pool()
    async with pool.acquire() as conn:
        try:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM connector_grants WHERE user_id = $1",
                user_id,
            )
        except Exception as exc:
            if _is_missing_table_error(exc):
                return 0
            raise
    return int(count or 0)
