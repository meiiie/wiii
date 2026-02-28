"""
API Version 1 Router
Aggregates all v1 endpoints (REST, WebSocket, Webhook)
"""
import logging

from fastapi import APIRouter

from app.api.v1.chat import router as chat_router
from app.api.v1.chat_stream import router as chat_stream_router  # Streaming API
from app.api.v1.health import router as health_router
from app.api.v1.insights import router as insights_router  # Insights API
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.memories import router as memories_router
from app.api.v1.sources import router as sources_router
from app.api.v1.admin import router as admin_router  # Admin Document API
from app.api.v1.webhook import router as webhook_router  # Sprint 12: Webhook
from app.api.v1.threads import router as threads_router  # Sprint 16: Thread Management
from app.api.v1.organizations import router as org_router  # Sprint 24: Multi-Tenant
from app.api.v1.feedback import router as feedback_router  # Sprint 107: Feedback
from app.api.v1.character import router as character_router  # Sprint 120: Character State
from app.api.v1.mood import router as mood_router  # Sprint 120: Mood/Emotional State

logger = logging.getLogger(__name__)

router = APIRouter(tags=["v1"])

# Include sub-routers
router.include_router(chat_router)
router.include_router(chat_stream_router)  # POST /chat/stream
router.include_router(health_router)
router.include_router(insights_router)  # GET /insights/{user_id}
router.include_router(knowledge_router)
router.include_router(memories_router)
router.include_router(sources_router)
router.include_router(admin_router)  # POST/GET/DELETE /admin/documents
router.include_router(webhook_router)  # POST /webhook/{channel_id}
router.include_router(threads_router)  # GET/DELETE/PATCH /threads
router.include_router(org_router)  # Sprint 24: Organizations
router.include_router(feedback_router)  # Sprint 107: Feedback
router.include_router(character_router)  # Sprint 120: Character State
router.include_router(mood_router)  # Sprint 120: Mood/Emotional State

# Sprint 158: User profile + admin endpoints (always included, JWT-enforced)
from app.auth.user_router import router as user_router
router.include_router(user_router)


# ---------------------------------------------------------------------------
# Config-gated routers — log success/failure for debuggability
# ---------------------------------------------------------------------------

def _register_optional_router(
    flag_name: str, import_path: str, label: str,
) -> None:
    """Register an optional router, logging success or failure."""
    from app.core.config import settings
    if not getattr(settings, flag_name, False):
        return
    try:
        import importlib
        parts = import_path.rsplit(".", 1)
        mod = importlib.import_module(parts[0])
        sub_router = getattr(mod, parts[1])
        router.include_router(sub_router)
        logger.info("[OK] %s router registered", label)
    except Exception as e:
        logger.error("[FAIL] %s router registration failed: %s", label, e)


_register_optional_router("enable_websocket", "app.api.v1.websocket.router", "WebSocket")
_register_optional_router("enable_google_oauth", "app.auth.google_oauth.router", "Google OAuth")
_register_optional_router("enable_lms_token_exchange", "app.auth.lms_auth_router.router", "LMS Token Exchange")
_register_optional_router("enable_living_agent", "app.api.v1.living_agent.router", "Living Agent")
_register_optional_router("enable_messenger_webhook", "app.api.v1.messenger_webhook.router", "Messenger Webhook")
_register_optional_router("enable_zalo_webhook", "app.api.v1.zalo_webhook.router", "Zalo Webhook")
_register_optional_router("enable_org_knowledge", "app.api.v1.org_knowledge.router", "Org Knowledge")
_register_optional_router("enable_soul_bridge", "app.api.v1.soul_bridge.router", "Soul Bridge")
_register_optional_router("enable_knowledge_visualization", "app.api.v1.knowledge_visualization.router", "Knowledge Visualization")

# Sprint 155: LMS Integration (multiple routers)
try:
    from app.core.config import settings as _settings
    if getattr(_settings, "enable_lms_integration", False):
        from app.api.v1.lms_webhook import router as lms_router
        router.include_router(lms_router)
        from app.api.v1.lms_data import router as lms_data_router
        router.include_router(lms_data_router)
        from app.api.v1.lms_dashboard import router as lms_dashboard_router
        router.include_router(lms_dashboard_router)
        logger.info("[OK] LMS Integration routers registered (3 routers)")
except Exception as e:
    logger.error("[FAIL] LMS Integration router registration failed: %s", e)

# Sprint 178: Admin Module (multiple routers)
try:
    if getattr(_settings, "enable_admin_module", False):
        from app.api.v1.admin_dashboard import router as admin_dashboard_router
        router.include_router(admin_dashboard_router)
        from app.api.v1.admin_feature_flags import router as admin_ff_router
        router.include_router(admin_ff_router)
        from app.api.v1.admin_analytics import router as admin_analytics_router
        router.include_router(admin_analytics_router)
        from app.api.v1.admin_audit import router as admin_audit_router
        router.include_router(admin_audit_router)
        from app.api.v1.admin_gdpr import router as admin_gdpr_router
        router.include_router(admin_gdpr_router)
        logger.info("[OK] Admin Module routers registered (5 routers)")
except Exception as e:
    logger.error("[FAIL] Admin Module router registration failed: %s", e)


@router.get("/")
async def api_v1_root():
    """API v1 root endpoint"""
    return {"api": "v1", "status": "active"}
