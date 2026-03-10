"""
Wiii Middleware — Request-ID Correlation & Organization Context

Generates a unique request ID for every inbound request when the caller
does not supply one via X-Request-ID.  The ID is:
  1. Bound to structlog context vars (auto-attached to every log line).
  2. Returned in the response X-Request-ID header.

Sprint 24: OrgContextMiddleware propagates X-Organization-ID into ContextVar.
Sprint 175: Subdomain → org_id extraction (fallback when no header).

SOTA 2026: Every production service must propagate correlation IDs.
"""

import logging
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# Subdomains that should NOT be treated as org slugs
_RESERVED_SUBDOMAINS = frozenset({"www", "api", "admin", "app", "mail", "static", "cdn"})


def extract_org_from_subdomain(host: str, base_domain: str) -> str | None:
    """
    Extract org slug from Host header using the configured base domain.

    Example: 'phuong-luu-kiem.holilihu.online' with base_domain='holilihu.online' → 'phuong-luu-kiem'

    Returns None if:
    - base_domain is empty/not configured
    - Host doesn't end with base_domain
    - Extracted subdomain is reserved (www, api, admin, etc.)
    - No subdomain present (bare domain)
    """
    if not base_domain or not host:
        return None

    # Strip port (e.g. 'org.holilihu.online:8080' → 'org.holilihu.online')
    hostname = host.split(":")[0].lower()
    base = base_domain.lower()

    # Host must end with '.{base_domain}' — not just equal to base_domain
    suffix = f".{base}"
    if not hostname.endswith(suffix):
        return None

    subdomain = hostname[: -len(suffix)]
    if not subdomain or subdomain in _RESERVED_SUBDOMAINS:
        return None

    return subdomain


class EmbedCSPMiddleware(BaseHTTPMiddleware):
    """
    Sprint 220b: Set CSP frame-ancestors on /embed routes to allow iframe embedding.

    Without this, browsers block iframing due to X-Frame-Options: DENY (default).
    Only applies to /embed paths — other routes remain unaffected.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response: Response = await call_next(request)

        if request.url.path.startswith("/embed"):
            from app.core.config import settings

            origins = settings.embed_allowed_origins.strip()
            if origins:
                # Space-separated origins → CSP frame-ancestors directive
                frame_ancestors = f"frame-ancestors 'self' {origins}"
            else:
                frame_ancestors = "frame-ancestors 'self'"

            response.headers["Content-Security-Policy"] = frame_ancestors
            # Remove X-Frame-Options — it conflicts with CSP frame-ancestors
            # and older browsers use it to block iframes
            if "X-Frame-Options" in response.headers:
                del response.headers["X-Frame-Options"]

        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Inject / propagate X-Request-ID for every request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex

        # Bind to structlog context so all log lines include request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        # Store on request state for access in route handlers
        request.state.request_id = request_id

        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class OrgContextMiddleware(BaseHTTPMiddleware):
    """
    Propagate organization context into ContextVar for multi-tenant isolation.

    Resolution priority (Sprint 175):
      1. X-Organization-ID header (explicit — from client or Nginx proxy)
      2. Subdomain extraction from Host header (when subdomain_base_domain configured)
      3. None (no org context — personal workspace)

    Sprint 24: Feature-gated by settings.enable_multi_tenant.
    When disabled, this middleware is a no-op pass-through.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        from app.core.config import settings

        if not settings.enable_multi_tenant:
            return await call_next(request)

        from app.core.org_context import current_org_id, current_org_allowed_domains

        # Sprint 175: Priority — header first, then subdomain fallback
        org_id = request.headers.get("X-Organization-ID")
        if not org_id and settings.subdomain_base_domain:
            host = request.headers.get("host", "")
            org_id = extract_org_from_subdomain(host, settings.subdomain_base_domain)

        token_org = None
        token_domains = None

        if org_id:
            token_org = current_org_id.set(org_id)
            structlog.contextvars.bind_contextvars(organization_id=org_id)

            # Load allowed_domains from repository
            # Sprint 194c (B6): Fail-closed — if DB lookup fails, clear org context
            # entirely rather than proceeding with org_id set but no domain restrictions.
            try:
                from app.repositories.organization_repository import get_organization_repository
                repo = get_organization_repository()
                org = repo.get_organization(org_id)
                if org and org.allowed_domains:
                    token_domains = current_org_allowed_domains.set(org.allowed_domains)
            except Exception as e:
                logger.warning(
                    "[MIDDLEWARE] Failed to load org for %s: %s — rejecting request (fail-closed)",
                    org_id, e,
                )
                # Fail-closed: reject request since we can't verify org permissions
                if token_org is not None:
                    current_org_id.reset(token_org)
                    token_org = None
                return JSONResponse(
                    status_code=503,
                    content={"detail": "Không thể xác minh tổ chức. Vui lòng thử lại sau."},
                )

        try:
            response: Response = await call_next(request)
        finally:
            if token_org is not None:
                current_org_id.reset(token_org)
            if token_domains is not None:
                current_org_allowed_domains.reset(token_domains)

        return response
