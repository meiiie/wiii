"""
WebSocket Channel Adapter — Real-time bidirectional messaging.

Converts WebSocket JSON messages to/from ChannelMessage format.
Protocol: {"type": "message"|"typing"|"ping", "content": "..."}
"""

import json
import logging
from typing import Any, Dict

from app.channels.base import ChannelAdapter, ChannelMessage

logger = logging.getLogger(__name__)


class WebSocketAdapter(ChannelAdapter):
    """
    WebSocket channel adapter.

    Incoming: JSON string → ChannelMessage
    Outgoing: Response dict → JSON string
    """

    @property
    def channel_type(self) -> str:
        return "websocket"

    def parse_incoming(self, raw: Any) -> ChannelMessage:
        """
        Parse a WebSocket JSON message into ChannelMessage.

        Expected format:
        {
            "type": "message",
            "content": "user's question here",
            "sender_id": "user-123",        # optional
            "session_id": "session-abc",     # optional
            "metadata": {...}               # optional
        }

        Args:
            raw: JSON string or dict from WebSocket

        Returns:
            ChannelMessage

        Raises:
            ValueError: If message cannot be parsed
        """
        if isinstance(raw, str):
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON: {e}")
        elif isinstance(raw, dict):
            data = raw
        else:
            raise ValueError(f"Unexpected message type: {type(raw)}")

        msg_type = data.get("type", "message")
        if msg_type not in ("message", "typing", "ping"):
            raise ValueError(f"Unknown message type: {msg_type}")

        content = data.get("content", "")
        if msg_type == "ping":
            content = content or "__ping__"

        sender_id = data.get("sender_id", "anonymous")
        session_id = data.get("session_id", "")

        metadata = data.get("metadata", {})
        metadata["ws_message_type"] = msg_type
        if session_id:
            metadata["session_id"] = session_id

        return ChannelMessage(
            text=content,
            sender_id=sender_id,
            channel_id=f"ws:{session_id or sender_id}",
            channel_type="websocket",
            metadata=metadata,
        )

    def format_outgoing(self, response: Dict[str, Any]) -> str:
        """
        Format a response dict as a WebSocket JSON message.

        Output format:
        {
            "type": "response",
            "content": "...",
            "sources": [...],
            "metadata": {...}
        }
        """
        return json.dumps({
            "type": "response",
            "content": response.get("answer", response.get("content", "")),
            "sources": response.get("sources", []),
            "metadata": {
                k: v for k, v in response.items()
                if k not in ("answer", "content", "sources")
            },
        }, ensure_ascii=False)

    def format_error(self, error: str) -> str:
        """Format an error message for WebSocket."""
        return json.dumps({
            "type": "error",
            "content": error,
        }, ensure_ascii=False)

    def format_pong(self) -> str:
        """Format a pong response for WebSocket heartbeat."""
        return json.dumps({"type": "pong"})

    def format_typing(self, is_typing: bool = True) -> str:
        """Format a typing indicator for WebSocket."""
        return json.dumps({
            "type": "typing",
            "content": is_typing,
        })
