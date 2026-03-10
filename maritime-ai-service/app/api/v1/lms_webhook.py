"""
LMS Webhook API — Sprint 155: "Cầu Nối"

POST /api/v1/lms/webhook/{connector_id} — Receives webhook events from registered LMS.
POST /api/v1/lms/webhook                — Global fallback (flat config compat).
GET  /api/v1/lms/health                 — Health check for LMS integration status.

Sprint 155b: Per-connector signature verification via registry.
Sprint 155c: Security fixes — connector_id from URL path (not body),
             verify signature BEFORE parsing body, sanitized error messages.
"""

import json
import logging

from fastapi import APIRouter, HTTPException, Request

from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.integrations.lms.base import verify_hmac_sha256
from app.integrations.lms.models import LMSWebhookEvent, LMSWebhookResponse
from app.integrations.lms.webhook_handler import LMSWebhookHandler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/lms", tags=["lms"])

_handler = LMSWebhookHandler()


def _get_registry():
    """Lazy-load registry to avoid import issues at module level."""
    from app.integrations.lms.registry import get_lms_connector_registry
    return get_lms_connector_registry()


@router.post("/webhook/{connector_id}")
@limiter.limit("60/minute")
async def lms_webhook_with_connector(request: Request, connector_id: str):
    """Receive webhook from a specific registered LMS connector.

    The connector_id comes from the URL path (trusted routing),
    NOT from the request body (untrusted).

    Flow:
    1. Feature gate check
    2. Look up connector by ID from URL path
    3. Read raw body + verify signature BEFORE parsing
    4. Parse JSON into LMSWebhookEvent
    5. Override event.source with connector_id (provenance)
    6. Dispatch to handler
    7. Return LMSWebhookResponse
    """
    settings = get_settings()

    # 1. Feature gate
    if not settings.enable_lms_integration:
        raise HTTPException(status_code=404, detail="LMS integration not enabled")

    # 2. Look up connector from URL path (not body)
    registry = _get_registry()
    connector = registry.get(connector_id)
    if connector is None:
        raise HTTPException(status_code=404, detail="Unknown LMS connector")

    # 3. Read raw body + verify signature BEFORE parsing
    body_bytes = await request.body()
    headers_dict = dict(request.headers)

    if not connector.verify_signature(body_bytes, headers_dict):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # 4. Parse JSON into event
    try:
        data = json.loads(body_bytes)
        event = LMSWebhookEvent(**data)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid webhook event format")

    # 5. Override source with trusted connector_id
    event.source = connector_id

    # 6. Handle event
    response = await _handler.handle_event(event)

    # 7. Return with appropriate HTTP status
    status_code = 200 if response.status != "error" else 500
    return _sanitized_response(response, status_code)


@router.post("/webhook")
@limiter.limit("60/minute")
async def lms_webhook_global(request: Request):
    """Global webhook endpoint — backward compat with Sprint 155 flat config.

    Uses global lms_webhook_secret for signature verification.
    For multi-LMS, prefer /webhook/{connector_id} instead.
    """
    settings = get_settings()

    # 1. Feature gate
    if not settings.enable_lms_integration:
        raise HTTPException(status_code=404, detail="LMS integration not enabled")

    # 2. Read raw body
    body_bytes = await request.body()

    # 3. Verify signature BEFORE parsing body
    if settings.lms_webhook_secret:
        signature = request.headers.get("x-lms-signature", "")
        if not signature:
            raise HTTPException(status_code=401, detail="Missing X-LMS-Signature header")
        if not verify_hmac_sha256(body_bytes, signature, settings.lms_webhook_secret):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
    else:
        # No secret configured — reject unsigned webhooks
        logger.warning("Webhook received but no lms_webhook_secret configured — rejecting")
        raise HTTPException(status_code=401, detail="Webhook secret not configured")

    # 4. Parse event
    try:
        data = json.loads(body_bytes)
        event = LMSWebhookEvent(**data)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid webhook event format")

    # 5. Handle event
    response = await _handler.handle_event(event)

    # 6. Return with appropriate HTTP status
    status_code = 200 if response.status != "error" else 500
    return _sanitized_response(response, status_code)


def _sanitized_response(response: LMSWebhookResponse, status_code: int = 200) -> dict:
    """Return response with sanitized error messages (no internal details)."""
    result = response.model_dump()
    if response.status == "error":
        # Don't leak internal exception details to caller
        result["message"] = "Internal processing error"
    from fastapi.responses import JSONResponse
    return JSONResponse(content=result, status_code=status_code)


@router.get("/health")
@limiter.limit("30/minute")
async def lms_integration_health(request: Request):
    """Health check for LMS integration — shows all registered connectors."""
    settings = get_settings()
    registry = _get_registry()
    connectors = registry.get_all_enabled()

    return {
        "enabled": settings.enable_lms_integration,
        "connector_count": len(connectors),
        "connectors": [
            {
                "id": c.get_config().id,
                "display_name": c.get_config().display_name,
                "backend_type": c.get_config().backend_type.value,
                "base_url_configured": bool(c.get_config().base_url),
                "webhook_secret_configured": c.get_config().webhook_secret is not None,
            }
            for c in connectors
        ],
        # Backward compat fields
        "base_url_configured": settings.lms_base_url is not None,
        "webhook_secret_configured": settings.lms_webhook_secret is not None,
        "service_token_configured": settings.lms_service_token is not None,
    }
