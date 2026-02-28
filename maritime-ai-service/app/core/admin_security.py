"""
Sprint 178: Admin security utilities.

IP allowlist enforcement and module gate for admin routes.
"""
import logging

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


def check_admin_module(request: Request) -> None:
    """Dependency: verify admin module is enabled + IP allowlist.

    Shared by all Sprint 178 admin routers to avoid DRY violation.
    """
    from app.core.config import settings

    if not getattr(settings, "enable_admin_module", False):
        raise HTTPException(status_code=404, detail="Admin module not enabled")
    check_admin_ip_allowlist(request)


def check_admin_ip_allowlist(request: Request) -> None:
    """Check request IP against admin allowlist.

    No-op if admin_ip_allowlist is empty (allow all).
    Raises 403 if IP is not in the allowlist.
    """
    from app.core.config import settings

    allowlist_str = getattr(settings, "admin_ip_allowlist", "")
    if not allowlist_str or not allowlist_str.strip():
        return

    allowed_ips = {ip.strip() for ip in allowlist_str.split(",") if ip.strip()}
    if not allowed_ips:
        return

    client_ip = request.client.host if request.client else None
    if not client_ip:
        logger.warning("Admin access denied: client IP unavailable (behind proxy?)")
        raise HTTPException(status_code=403, detail="Client IP not available")
    if client_ip not in allowed_ips:
        logger.warning("Admin IP blocked: %s (allowed: %s)", client_ip, allowed_ips)
        raise HTTPException(status_code=403, detail="IP not allowed for admin access")
