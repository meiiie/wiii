"""
Sprint 178: Admin security utilities.

IP allowlist enforcement for admin routes.
"""
import logging

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


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
    if client_ip not in allowed_ips:
        logger.warning("Admin IP blocked: %s (allowed: %s)", client_ip, allowed_ips)
        raise HTTPException(status_code=403, detail="IP not allowed for admin access")
