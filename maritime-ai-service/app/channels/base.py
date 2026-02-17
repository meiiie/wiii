"""
Channel Adapter Abstraction — Base classes for multi-channel messaging.

All channels normalize their messages into ChannelMessage, which is then
converted to ChatRequest for processing through the existing pipeline.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class ChannelMessage:
    """
    Normalized message from any channel.

    Every channel adapter converts its native message format into this
    universal representation, which can then be mapped to ChatRequest.
    """

    text: str
    sender_id: str
    channel_id: str
    channel_type: str  # "websocket", "telegram", "webhook"
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)


class ChannelAdapter(ABC):
    """
    Abstract base class for channel adapters.

    Each adapter knows how to:
    1. Parse incoming messages from its channel into ChannelMessage
    2. Format outgoing responses back to the channel's native format
    """

    @property
    @abstractmethod
    def channel_type(self) -> str:
        """Unique identifier for this channel type (e.g., 'websocket', 'telegram')."""
        ...

    @abstractmethod
    def parse_incoming(self, raw: Any) -> ChannelMessage:
        """
        Parse raw channel-specific data into a normalized ChannelMessage.

        Args:
            raw: Channel-specific incoming data (dict, bytes, object, etc.)

        Returns:
            ChannelMessage with normalized fields

        Raises:
            ValueError: If the raw data cannot be parsed
        """
        ...

    @abstractmethod
    def format_outgoing(self, response: Dict[str, Any]) -> Any:
        """
        Format a response dict back to the channel's native format.

        Args:
            response: Response data from ChatOrchestrator (typically contains
                     'answer', 'sources', 'metadata', etc.)

        Returns:
            Channel-specific response format (dict, string, etc.)
        """
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} channel_type={self.channel_type}>"


def to_chat_request(msg: ChannelMessage, default_role: str = "student") -> "ChatRequest":
    """
    Convert a ChannelMessage to a ChatRequest for the existing pipeline.

    This is the key bridge between the channel layer and the core
    ChatOrchestrator. All channels ultimately feed into ChatRequest.

    Args:
        msg: Normalized channel message
        default_role: Default user role if not specified in metadata

    Returns:
        ChatRequest instance ready for ChatOrchestrator.process()
    """
    from app.models.schemas import ChatRequest, UserRole

    role_str = msg.metadata.get("role", default_role)
    try:
        role = UserRole(role_str)
    except ValueError:
        role = UserRole.STUDENT

    return ChatRequest(
        user_id=msg.sender_id,
        message=msg.text,
        role=role,
        session_id=msg.metadata.get("session_id", msg.channel_id),
        thread_id=msg.metadata.get("thread_id"),
        domain_id=msg.metadata.get("domain_id"),
    )
