"""
Wiii Middleware — Request-ID Correlation & Organization Context

Generates a unique request ID for every inbound request when the caller
does not supply one via X-Request-ID.  The ID is:
  1. Bound to structlog context vars (auto-attached to every log line).
  2. Returned in the response X-Request-ID header.

Sprint 24: OrgContextMiddleware propagates X-Organization-ID into ContextVar.

SOTA 2026: Every production service must propagate correlation IDs.
"""

import logging
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


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
    Propagate X-Organization-ID into ContextVar for multi-tenant isolation.

    Sprint 24: Feature-gated by settings.enable_multi_tenant.
    When disabled, this middleware is a no-op pass-through.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        from app.core.config import settings

        if not settings.enable_multi_tenant:
            return await call_next(request)

        from app.core.org_context import current_org_id, current_org_allowed_domains

        org_id = request.headers.get("X-Organization-ID")
        token_org = None
        token_domains = None

        if org_id:
            token_org = current_org_id.set(org_id)
            structlog.contextvars.bind_contextvars(organization_id=org_id)

            # Optionally load allowed_domains from repository
            try:
                from app.repositories.organization_repository import get_organization_repository
                repo = get_organization_repository()
                org = repo.get_organization(org_id)
                if org and org.allowed_domains:
                    token_domains = current_org_allowed_domains.set(org.allowed_domains)
            except Exception as e:
                # Sprint 28: Log instead of silent pass — helps debug multi-tenant issues
                logger.warning("[MIDDLEWARE] Failed to load org domains for %s: %s", org_id, e)

        try:
            response: Response = await call_next(request)
        finally:
            if token_org is not None:
                current_org_id.reset(token_org)
            if token_domains is not None:
                current_org_allowed_domains.reset(token_domains)

        return response
