"""
Telegram Channel Adapter — Telegram Bot messaging for Wiii.

Converts Telegram webhook updates to/from ChannelMessage format.
Uses the Telegram Bot API JSON structure (no aiogram dependency required
for basic adapter functionality — aiogram used only for bot lifecycle).

Sprint 12: Multi-Channel Gateway.
"""

import logging
from typing import Any, Dict

from app.channels.base import ChannelAdapter, ChannelMessage

logger = logging.getLogger(__name__)


class TelegramAdapter(ChannelAdapter):
    """
    Telegram channel adapter.

    Incoming: Telegram Update JSON → ChannelMessage
    Outgoing: Response dict → Telegram sendMessage format
    """

    @property
    def channel_type(self) -> str:
        return "telegram"

    def parse_incoming(self, raw: Any) -> ChannelMessage:
        """
        Parse a Telegram webhook Update into ChannelMessage.

        Expected: Telegram Update JSON with 'message' field containing
        'text', 'from', 'chat' objects.

        Args:
            raw: Telegram Update dict (from webhook POST body)

        Returns:
            ChannelMessage

        Raises:
            ValueError: If the update doesn't contain a processable message
        """
        if not isinstance(raw, dict):
            raise ValueError(f"Expected dict, got {type(raw)}")

        # Extract message from update (could be message, edited_message, etc.)
        message = raw.get("message") or raw.get("edited_message")
        if not message:
            raise ValueError("No message in Telegram update")

        text = message.get("text", "")
        if not text:
            raise ValueError("No text content in Telegram message")

        # Extract sender info
        sender = message.get("from", {})
        sender_id = str(sender.get("id", "unknown"))
        sender_name = (
            sender.get("first_name", "")
            + (" " + sender.get("last_name", "") if sender.get("last_name") else "")
        ).strip()

        # Extract chat info
        chat = message.get("chat", {})
        chat_id = str(chat.get("id", ""))
        chat_type = chat.get("type", "private")

        metadata = {
            "sender_name": sender_name,
            "sender_username": sender.get("username", ""),
            "chat_type": chat_type,
            "message_id": message.get("message_id"),
            "update_id": raw.get("update_id"),
            "telegram_chat_id": chat_id,
        }

        return ChannelMessage(
            text=text,
            sender_id=sender_id,
            channel_id=f"tg:{chat_id}",
            channel_type="telegram",
            metadata=metadata,
        )

    def format_outgoing(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format a response for Telegram sendMessage API.

        Output format (Telegram Bot API sendMessage):
        {
            "chat_id": "...",
            "text": "...",
            "parse_mode": "Markdown"
        }
        """
        answer = response.get("answer", response.get("content", ""))
        chat_id = response.get("chat_id", "")

        result = {
            "chat_id": chat_id,
            "text": answer,
            "parse_mode": "Markdown",
        }

        # Add source references as inline keyboard if available
        sources = response.get("sources", [])
        if sources:
            source_text = "\n\n📚 *Nguồn tham khảo:*"
            for i, src in enumerate(sources[:3], 1):
                if isinstance(src, dict):
                    source_text += f"\n{i}. {src.get('title', src.get('source', 'N/A'))}"
                else:
                    source_text += f"\n{i}. {src}"
            result["text"] += source_text

        return result

    def format_typing_action(self, chat_id: str) -> Dict[str, Any]:
        """Format a typing action for Telegram (sendChatAction)."""
        return {
            "chat_id": chat_id,
            "action": "typing",
        }
