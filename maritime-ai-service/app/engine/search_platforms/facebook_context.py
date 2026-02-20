"""Per-request Facebook cookie context.

Sprint 154: "Dang Nhap Facebook"

Follows org_context.py pattern — set in API layer, read in adapter.
ContextVar is request-scoped in asyncio: each request gets its own value.
"""
from contextvars import ContextVar

current_facebook_cookie: ContextVar[str] = ContextVar(
    "current_facebook_cookie", default=""
)


def set_facebook_cookie(cookie: str) -> None:
    """Set Facebook cookie for the current request."""
    current_facebook_cookie.set(cookie)


def get_facebook_cookie() -> str:
    """Get Facebook cookie for the current request (empty string if not set)."""
    return current_facebook_cookie.get()
