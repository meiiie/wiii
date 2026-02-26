"""
Zalo OA Incoming Webhook — Sprint 174: Cross-Platform Identity
Sprint 188: Deduplication, async processing, channel_sender DRY.

Handles:
- POST /zalo/webhook  → Incoming messages from Zalo Official Account

Zalo OA sends events as POST with JSON body containing event_name,
sender, and message fields. Supported events: user_send_text.

MAC verification is optional (permissive when zalo_oa_secret_key is unset).

Sprint 188 improvements:
- Message deduplication (LRU of last 200 message IDs)
- Async processing: immediate 200 ACK, background task for AI reply
- Uses channel_sender.py for send (DRY)
"""

import asyncio
import hashlib
import hmac
import json
import logging
from collections import OrderedDict
from typing import Optional

from fastapi import APIRouter, Request, HTTPException

from app.core.config import settings

logger = logging.getLogger(__name__)

# Sprint 188: Message deduplication — LRU cache of recent message IDs
_MAX_DEDUP_SIZE = 200
_seen_message_ids: OrderedDict = OrderedDict()


def _is_duplicate(message_id: str) -> bool:
    """Check if message was already processed."""
    if not message_id:
        return False
    if message_id in _seen_message_ids:
        return True
    _seen_message_ids[message_id] = True
    if len(_seen_message_ids) > _MAX_DEDUP_SIZE:
        _seen_message_ids.popitem(last=False)
    return False

router = APIRouter(prefix="/zalo", tags=["zalo"])


def _verify_zalo_mac(body_bytes: bytes, mac_header: Optional[str]) -> bool:
    """Verify Zalo OA webhook MAC signature.

    When zalo_oa_secret_key is not configured, verification is skipped
    (permissive mode for development/testing).

    Args:
        body_bytes: Raw request body bytes
        mac_header: MAC header value from Zalo

    Returns:
        True if verified or verification skipped, False if mismatch.
    """
    secret = settings.zalo_oa_secret_key
    if not secret:
        return True  # Permissive when unconfigured

    if not mac_header:
        logger.warning("[ZALO] Missing MAC header — rejecting request")
        return False

    expected = hmac.new(
        secret.encode("utf-8"),
        body_bytes,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, mac_header)


@router.post("/webhook")
async def zalo_incoming(request: Request):
    """Receive incoming messages from Zalo Official Account.

    Zalo OA sends message events as POST with JSON body:
    {
      "event_name": "user_send_text",
      "sender": {"id": "..."},
      "message": {"text": "..."}
    }
    """
    body_bytes = await request.body()

    # MAC verification (optional, permissive when unconfigured)
    mac_header = request.headers.get("X-ZaloOA-Signature")
    if not _verify_zalo_mac(body_bytes, mac_header):
        raise HTTPException(status_code=403, detail="Invalid MAC signature")

    try:
        body = json.loads(body_bytes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    event_name = body.get("event_name", "")

    # Only handle text messages
    if event_name != "user_send_text":
        logger.debug("[ZALO] Ignoring event: %s", event_name)
        return {"status": "ignored", "event": event_name}

    sender_id = body.get("sender", {}).get("id")
    message = body.get("message", {})
    text = message.get("text", "")
    message_id = message.get("msg_id", body.get("msg_id", ""))

    if not sender_id or not text:
        return {"status": "ignored", "reason": "missing sender or text"}

    # Sprint 188: Deduplication
    if _is_duplicate(message_id):
        logger.debug("[ZALO] Duplicate message skipped: %s", message_id)
        return {"status": "ok", "note": "duplicate"}

    logger.info("[ZALO] Message from %s: %s", sender_id, text[:100])

    # Sprint 188: Async processing — fire-and-forget background task
    asyncio.create_task(
        _process_and_reply_background(sender_id, text)
    )

    # Immediate ACK
    return {"status": "ok"}


async def _process_and_reply_background(sender_id: str, text: str) -> None:
    """Background task: process message through Wiii and send reply.

    Sprint 188: Separated from webhook handler for async ACK pattern.
    """
    from app.engine.living_agent.channel_sender import send_zalo_message

    try:
        answer = await _process_and_reply(sender_id, text)
        result = await send_zalo_message(sender_id, answer)
        if not result.success:
            logger.error("[ZALO] Send failed: %s", result.error)
    except Exception as e:
        logger.error("[ZALO] Background processing failed: %s", e)
        try:
            await send_zalo_message(
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
    """Process user message through multi-agent graph and return answer.

    Sprint 174b: Checks OTP linking before multi-agent processing.
    """
    # Sprint 174b: OTP identity linking interception
    otp_result = await _check_otp_linking(text.strip(), "zalo", sender_id)
    if otp_result:
        return otp_result

    from app.auth.identity_resolver import resolve_user_id
    from app.engine.personality_mode import resolve_personality_mode
    from app.engine.multi_agent.graph import process_with_multi_agent

    canonical_user_id = await resolve_user_id("zalo", sender_id)
    personality_mode = resolve_personality_mode("zalo")

    result = await process_with_multi_agent(
        query=text,
        user_id=canonical_user_id,
        session_id=f"zalo_{sender_id}",
        context={
            "user_role": "student",
            "conversation_history": "",
            "semantic_context": "",
            "personality_mode": personality_mode,
            "channel_type": "zalo",
        },
    )
    return result.get("response", result.get("final_response", "Mình không hiểu câu hỏi."))


async def _send_zalo_reply(recipient_id: str, text: str):
    """Send a text message back via Zalo OA (legacy wrapper).

    Sprint 188: Delegates to channel_sender for DRY.
    """
    from app.engine.living_agent.channel_sender import send_zalo_message

    result = await send_zalo_message(recipient_id, text)
    if not result.success:
        logger.error("[ZALO] Send failed: %s", result.error)
