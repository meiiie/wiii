"""
Generic Webhook Receiver — Multi-channel webhook endpoint for Wiii.

Receives webhook POST requests from external services (Telegram, custom bots)
and routes them through the appropriate channel adapter.

Sprint 12: Multi-Channel Gateway.
"""

import logging

from fastapi import APIRouter, Request, HTTPException

from app.channels.registry import ChannelRegistry
from app.channels.base import to_chat_request
from app.core.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhook"])


@router.post("/webhook/{channel_id}")
@limiter.limit("30/minute")
async def webhook_receiver(channel_id: str, request: Request):
    """
    Generic webhook endpoint for all channel types.

    Routes incoming webhooks to the appropriate channel adapter based
    on channel_id, processes through ChatOrchestrator, and returns
    the channel-specific response format.

    Args:
        channel_id: Channel type identifier (e.g., 'telegram', 'custom')
        request: FastAPI Request object

    Returns:
        Channel-specific response format
    """
    registry = ChannelRegistry()

    # Look up adapter
    adapter = registry.get(channel_id)
    if adapter is None:
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy channel adapter: '{channel_id}'. "
                   f"Các channel khả dụng: {registry.list_all()}"
        )

    # Parse request body
    try:
        body = await request.json()
    except Exception as e:
        logger.warning("Webhook invalid JSON: %s", e)
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # Parse incoming message
    try:
        channel_msg = adapter.parse_incoming(body)
    except ValueError as e:
        logger.warning("Webhook parse error for %s: %s", channel_id, e)
        raise HTTPException(status_code=400, detail="Cannot parse incoming message")

    # Convert to ChatRequest
    chat_request = to_chat_request(channel_msg)

    # Process via ChatOrchestrator
    try:
        from app.services.chat_orchestrator import ChatOrchestrator
        orchestrator = ChatOrchestrator()
        result = await orchestrator.process(chat_request)
    except Exception as e:
        logger.error("[WEBHOOK] Error processing %s message: %s", channel_id, e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal processing error"
        )

    # Format outgoing response
    response_data = {
        "answer": result.get("answer", result.get("response", "")),
        "sources": result.get("sources", []),
        "metadata": result.get("metadata", {}),
    }

    # Add channel-specific fields (e.g., chat_id for Telegram)
    if channel_id == "telegram":
        response_data["chat_id"] = channel_msg.metadata.get("telegram_chat_id", "")

    return adapter.format_outgoing(response_data)
