"""
Wiii Multi-Channel Gateway — Channel Adapter Abstraction Layer (Sprint 12).

Normalizes messages from multiple channels (WebSocket, Telegram, Webhook)
into the existing ChatRequest pipeline via ChatOrchestrator.

Inspired by OpenClaw's 10+ channel support.
"""

from app.channels.base import ChannelMessage, ChannelAdapter, to_chat_request
from app.channels.registry import ChannelRegistry

__all__ = ["ChannelMessage", "ChannelAdapter", "to_chat_request", "ChannelRegistry"]
