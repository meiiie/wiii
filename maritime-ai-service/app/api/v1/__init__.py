"""
API Version 1 Router
Aggregates all v1 endpoints (REST, WebSocket, Webhook)
"""
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
from app.api.v1.preferences import router as preferences_router  # Sprint 120: User Preferences

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
router.include_router(preferences_router)  # Sprint 120: User Preferences

# Sprint 158: User profile + admin endpoints (always included, JWT-enforced)
from app.auth.user_router import router as user_router
router.include_router(user_router)

# Sprint 12: WebSocket endpoint (config-gated)
try:
    from app.core.config import settings
    if settings.enable_websocket:
        from app.api.v1.websocket import router as ws_router
        router.include_router(ws_router)  # WS /ws/{session_id}
except Exception:
    pass  # Fail gracefully if WebSocket setup fails

# Sprint 155: LMS Integration webhook (config-gated)
try:
    if getattr(settings, "enable_lms_integration", False):
        from app.api.v1.lms_webhook import router as lms_router
        router.include_router(lms_router)
except Exception:
    pass

# Sprint 157: Google OAuth routes (config-gated)
try:
    if getattr(settings, "enable_google_oauth", False):
        from app.auth.google_oauth import router as auth_router
        router.include_router(auth_router)
except Exception:
    pass

# Sprint 159: LMS Token Exchange (config-gated)
try:
    if getattr(settings, "enable_lms_token_exchange", False):
        from app.auth.lms_auth_router import router as lms_auth_router
        router.include_router(lms_auth_router)
except Exception:
    pass


@router.get("/")
async def api_v1_root():
    """API v1 root endpoint"""
    return {"api": "v1", "status": "active"}
