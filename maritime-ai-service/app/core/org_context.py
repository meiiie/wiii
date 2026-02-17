"""
Organization Context — Per-Request ContextVar for Multi-Tenant Isolation.

Sprint 24: Multi-Organization Architecture.
Same pattern as token_tracker.py — ContextVar for request-scoped isolation.
"""

from contextvars import ContextVar
from typing import Optional

current_org_id: ContextVar[Optional[str]] = ContextVar(
    "current_org_id", default=None
)
current_org_allowed_domains: ContextVar[Optional[list[str]]] = ContextVar(
    "current_org_allowed_domains", default=None
)


def get_current_org_id() -> Optional[str]:
    """Get the current request's organization ID."""
    return current_org_id.get()


def get_current_org_allowed_domains() -> Optional[list[str]]:
    """Get the current request's org-scoped allowed domain list."""
    return current_org_allowed_domains.get()
