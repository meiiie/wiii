"""
Organization Filter — Centralized Org-Scoped Query Helpers.

Sprint 160: "Hàng Rào" — Multi-Tenant Data Isolation.

Provides DRY helpers for adding org_id WHERE clauses to repository queries.
Feature-gated: when enable_multi_tenant=False, all helpers return empty/None
so existing behavior is completely unchanged.

Pattern: Defense-in-depth — app-level filtering (Phase 1).
RLS policies (Phase 2) will be added in a follow-up sprint.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_effective_org_id() -> Optional[str]:
    """Get the effective organization ID for the current request.

    When multi-tenant disabled: returns default_organization_id ("default")
    so INSERTs always have a valid org_id (Sprint 175b: NOT NULL support).

    When enabled: falls back through ContextVar → config default.

    Note: org_where_clause() / org_where_positional() still return ""
    when multi-tenant is disabled — query filtering is unchanged.
    """
    from app.core.config import settings

    if not settings.enable_multi_tenant:
        # Sprint 175b: Return default instead of None so INSERTs always
        # have a valid org_id (prerequisite for NOT NULL constraints).
        return settings.default_organization_id

    from app.core.org_context import get_current_org_id

    return get_current_org_id() or settings.default_organization_id


def org_where_clause(
    org_id: Optional[str],
    *,
    column: str = "organization_id",
    param: str = "org_id",
    allow_null: bool = False,
) -> str:
    """Return a SQL AND fragment for org-scoped filtering (named params).

    For use with SQLAlchemy ``text()`` queries that use ``:param`` style.

    Args:
        org_id: Organization ID. When None, returns empty string (no filter).
        column: DB column name (default ``organization_id``).
        param: Bind-parameter name (default ``org_id``).
        allow_null: If True, also matches rows where column IS NULL.
            Use for shared resources like knowledge_embeddings.

    Returns:
        SQL fragment like ``" AND organization_id = :org_id"`` or ``""``.
    """
    from app.core.config import settings

    if not settings.enable_multi_tenant or org_id is None:
        return ""

    if allow_null:
        return f" AND ({column} = :{param} OR {column} IS NULL)"

    return f" AND {column} = :{param}"


def org_where_positional(
    org_id: Optional[str],
    params: list,
    *,
    column: str = "organization_id",
    allow_null: bool = False,
) -> str:
    """Return a SQL AND fragment for org-scoped filtering (positional params).

    For use with asyncpg queries that use ``$1, $2, ...`` style.

    Args:
        org_id: Organization ID. When None, returns empty string.
        params: Mutable list of query parameters — appends org_id if needed.
        column: DB column name.
        allow_null: If True, also matches rows where column IS NULL.

    Returns:
        SQL fragment like ``" AND organization_id = $N"`` or ``""``.
    """
    from app.core.config import settings

    if not settings.enable_multi_tenant or org_id is None:
        return ""

    params.append(org_id)
    idx = len(params)

    if allow_null:
        return f" AND ({column} = ${idx} OR {column} IS NULL)"

    return f" AND {column} = ${idx}"
