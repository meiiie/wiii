"""
Facebook Messenger Platform Webhook — Sprint 173
Sprint 188: Deduplication, async processing, channel_sender DRY.
Sprint 192: X-Hub-Signature-256 verification for security.

Handles:
- GET  /messenger/webhook  → Verification handshake (hub.challenge)
- POST /messenger/webhook  → Incoming messages from Messenger

Facebook sends a GET request with hub.mode, hub.verify_token, hub.challenge
to verify the webhook. Then sends POST requests with incoming messages.

Sprint 188 improvements:
- Message deduplication (LRU of last 200 message IDs per sender)
- Async processing: immediate 200 ACK, background task for AI reply
- Uses channel_sender.py for send (DRY)
- Configurable Graph API version via settings.facebook_graph_api_version

Sprint 192:
- X-Hub-Signature-256 verification on POST requests
"""

import asyncio
import hashlib
import hmac
import json
import logging
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Query

from app.core.config import settings

logger = logging.getLogger(__name__)

# File-based debug log for webhook events
_WEBHOOK_LOG = Path(__file__).resolve().parent.parent.parent.parent / "webhook_debug.log"

# Sprint 188: Message deduplication — LRU cache of recent message IDs
_MAX_DEDUP_SIZE = 200
_seen_message_ids: OrderedDict = OrderedDict()


def _is_duplicate(message_id: str) -> bool:
    """Check if message was already processed. Thread-safe via GIL."""
    if not message_id:
        return False
    if message_id in _seen_message_ids:
        return True
    _seen_message_ids[message_id] = True
    if len(_seen_message_ids) > _MAX_DEDUP_SIZE:
        _seen_message_ids.popitem(last=False)
    return False


def _log_to_file(msg: str):
    """Append a timestamped line to webhook_debug.log."""
    try:
        with open(_WEBHOOK_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass

router = APIRouter(prefix="/messenger", tags=["messenger"])


@router.get("/webhook")
async def messenger_verify(
    request: Request,
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
):
    """
    Facebook webhook verification endpoint.

    Facebook sends: GET /messenger/webhook?hub.mode=subscribe&hub.verify_token=TOKEN&hub.challenge=CHALLENGE
    We must return hub.challenge as plain text if verify_token matches.
    """
    _log_to_file(f"GET verify: mode={hub_mode}, challenge={hub_challenge}")
    if hub_mode == "subscribe" and hmac.compare_digest(
        hub_verify_token or "", settings.facebook_verify_token or ""
    ):
        logger.info("[MESSENGER] Webhook verified successfully")
        _log_to_file(f"Verified OK, returning challenge: {hub_challenge}")
        return int(hub_challenge) if hub_challenge else ""

    logger.warning("[MESSENGER] Webhook verification failed: mode=%s", hub_mode)
    _log_to_file(f"Verification FAILED: mode={hub_mode}")
    raise HTTPException(status_code=403, detail="Verification failed")


def _verify_signature(raw_body: bytes, signature_header: str) -> bool:
    """Verify X-Hub-Signature-256 from Facebook.

    Facebook signs every POST with HMAC-SHA256 using the App Secret.
    Header format: sha256=<hex_digest>

    Returns True if signature matches or if app_secret is not configured
    (development mode). Returns False if verification fails.
    """
    app_secret = settings.facebook_app_secret
    if not app_secret:
        logger.warning("[MESSENGER] facebook_app_secret not set — skipping signature check")
        return True  # Allow in dev mode

    if not signature_header:
        logger.warning("[MESSENGER] Missing X-Hub-Signature-256 header")
        return False

    expected = "sha256=" + hmac.new(
        app_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(signature_header, expected)


@router.post("/webhook")
async def messenger_incoming(request: Request):
    """
    Receive incoming messages from Facebook Messenger.

    Sprint 188: Immediate 200 ACK + background processing.
    Sprint 192: X-Hub-Signature-256 verification.
    Facebook expects response within 20 seconds — we ACK immediately
    and process the AI query asynchronously.
    """
    # Sprint 192: Verify Facebook signature before parsing
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not _verify_signature(raw_body, signature):
        _log_to_file("Signature verification FAILED")
        raise HTTPException(status_code=403, detail="Invalid signature")

    body = json.loads(raw_body)
    _log_to_file(f"POST received: {json.dumps(body, ensure_ascii=False)[:500]}")

    if body.get("object") != "page":
        _log_to_file("Rejected: not a page event")
        raise HTTPException(status_code=400, detail="Not a page event")

    for entry in body.get("entry", []):
        for event in entry.get("messaging", []):
            sender_id = event.get("sender", {}).get("id")
            message = event.get("message", {})
            text = message.get("text", "")
            message_id = message.get("mid", "")

            if not sender_id or not text:
                continue

            # Don't reply to page's own messages
            if sender_id == settings.facebook_page_id:
                continue

            # Sprint 188: Deduplication
            if _is_duplicate(message_id):
                logger.debug("[MESSENGER] Duplicate message skipped: %s", message_id)
                continue

            logger.info(
                "[MESSENGER] Message from %s: %s",
                sender_id,
                text[:100],
            )

            # Sprint 188: Async processing — fire-and-forget background task
            asyncio.create_task(
                _process_and_reply_background(sender_id, text)
            )

    # Immediate ACK — Facebook won't retry
    return {"status": "ok"}


async def _process_and_reply_background(sender_id: str, text: str) -> None:
    """Background task: process message through Wiii and send reply.

    Sprint 188: Separated from webhook handler for async ACK pattern.
    """
    from app.engine.living_agent.channel_sender import send_messenger_message

    try:
        answer = await _process_and_reply(sender_id, text)
        result = await send_messenger_message(sender_id, answer)
        if not result.success:
            logger.error("[MESSENGER] Send failed: %s", result.error)
    except Exception as e:
        logger.error("[MESSENGER] Background processing failed: %s", e)
        try:
            await send_messenger_message(
                sender_id,
                "Xin lỗi, mình gặp lỗi khi xử lý tin nhắn. Bạn thử lại nhé!",
            )
        except Exception:
            pass


async def _check_otp_linking(text: str, channel_type: str, sender_id: str) -> str | None:
    """Check if message is a 6-digit OTP code for identity linking.

    Sprint 174b: Intercepts before multi-agent to prevent AI interpreting codes.
    Returns response message if OTP matched, None to continue normal flow.
    """
    if not text.isdigit() or len(text) != 6:
        return None
    from app.auth.otp_linking import verify_and_link
    success, msg = await verify_and_link(text, channel_type, sender_id)
    if success:
        return "Lien ket thanh cong! Tu gio Wiii se nho ban tren moi nen tang."
    if msg == "expired":
        return "Ma da het han. Vui long tao ma moi tren ung dung."
    return None  # Not an OTP code, proceed normally


async def _process_and_reply(sender_id: str, text: str) -> str:
    """Process user message through the multi-agent runtime and return answer.

    Sprint 174: Uses IdentityResolver for canonical user ID and
    PersonalityMode for soul/professional switching.
    Sprint 174b: Checks OTP linking before multi-agent processing.
    """
    # Sprint 174b: OTP identity linking interception
    otp_result = await _check_otp_linking(text.strip(), "messenger", sender_id)
    if otp_result:
        return otp_result

    from app.auth.identity_resolver import resolve_user_id
    from app.engine.personality_mode import resolve_personality_mode
    from app.engine.multi_agent.runtime import run_wiii_turn
    from app.engine.multi_agent.runtime_contracts import WiiiRunContext, WiiiTurnRequest

    canonical_user_id = await resolve_user_id("messenger", sender_id)
    personality_mode = resolve_personality_mode("messenger")

    turn_result = await run_wiii_turn(
        WiiiTurnRequest(
            query=text,
            run_context=WiiiRunContext(
                user_id=canonical_user_id,
                session_id=f"messenger_{sender_id}",
                context={
                    "user_role": "student",
                    "conversation_history": "",
                    "semantic_context": "",
                    "personality_mode": personality_mode,
                    "channel_type": "messenger",
                },
            ),
        )
    )
    result = turn_result.payload
    return result.get("response", result.get("final_response", "Mình không hiểu câu hỏi."))


async def _send_messenger_reply(recipient_id: str, text: str):
    """Send a text message back via Messenger (legacy wrapper).

    Sprint 188: Delegates to channel_sender for DRY.
    """
    from app.engine.living_agent.channel_sender import send_messenger_message

    result = await send_messenger_message(recipient_id, text)
    if not result.success:
        logger.error("[MESSENGER] Send failed: %s", result.error)
