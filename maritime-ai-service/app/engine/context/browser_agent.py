"""Sprint 222b Phase 7: Standalone Browser Agent — Playwright MCP integration.

Provides MCP server configuration for Playwright when Wiii runs as a
standalone desktop app. Includes SSRF prevention and rate limiting.
"""
import logging
import time
from collections import defaultdict
from typing import Any, Optional
from urllib.parse import urlparse
import ipaddress

logger = logging.getLogger(__name__)

EXPECTED_BROWSER_TOOLS = [
    "browser_navigate",
    "browser_snapshot",
    "browser_click",
    "browser_type",
    "browser_fill_form",
    "browser_press_key",
    "browser_select_option",
    "browser_take_screenshot",
    "browser_wait_for",
    "browser_tabs",
]


def get_browser_mcp_config() -> Optional[dict[str, Any]]:
    """Return MCP server config for Playwright, or None if disabled."""
    from app.core.config import get_settings
    settings = get_settings()
    if not settings.enable_browser_agent:
        return None
    return {
        "name": "playwright",
        "command": settings.browser_agent_mcp_command,
        "args": list(settings.browser_agent_mcp_args),
        "transport": "stdio",
    }


def validate_browser_url(url: str) -> bool:
    """Validate URL for SSRF prevention — block private/reserved/local addresses."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    hostname = parsed.hostname
    if not hostname:
        return False
    if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        return False
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_reserved or ip.is_loopback or ip.is_link_local:
            return False
    except ValueError:
        lower = hostname.lower()
        if lower.endswith(".local") or lower.endswith(".internal"):
            return False
    return True


class BrowserSessionLimiter:
    """Per-user rate limiter for browser sessions (sliding window, 1 hour)."""

    def __init__(self, max_per_hour: int = 10):
        self._max = max_per_hour
        self._sessions: dict[str, list[float]] = defaultdict(list)

    def check_and_increment(self, user_id: str) -> bool:
        """Check if user can start a new browser session. Returns True if allowed."""
        now = time.time()
        cutoff = now - 3600
        self._sessions[user_id] = [t for t in self._sessions[user_id] if t > cutoff]
        if len(self._sessions[user_id]) >= self._max:
            return False
        self._sessions[user_id].append(now)
        return True


_limiter: Optional[BrowserSessionLimiter] = None


def get_browser_limiter() -> BrowserSessionLimiter:
    """Get or create the singleton BrowserSessionLimiter."""
    global _limiter
    if _limiter is None:
        from app.core.config import get_settings
        settings = get_settings()
        _limiter = BrowserSessionLimiter(
            max_per_hour=settings.browser_agent_max_sessions_per_hour
        )
    return _limiter
