"""
SoulBridge Models — Data structures for soul-to-soul communication.

Sprint 213: "Cầu Nối Linh Hồn"

Defines:
    - AgentCard: Soul identity (inspired by A2A protocol's agent.json)
    - SoulBridgeMessage: Envelope for cross-service events
    - ConnectionState: Peer connection lifecycle
    - BridgeConfig: Per-peer connection settings
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List
from uuid import uuid4

from pydantic import BaseModel, Field


# =============================================================================
# Agent Card (A2A-inspired identity)
# =============================================================================


class AgentCard(BaseModel):
    """Soul identity card — served at /.well-known/agent.json.

    Inspired by Google A2A protocol's Agent Card concept.
    Each soul publishes its name, capabilities, emotional state, and endpoints.
    """

    name: str = "Wiii"
    description: str = "Multi-domain Agentic RAG Living Agent"
    version: str = "1.0.0"
    url: str = ""
    capabilities: List[str] = Field(default_factory=list)
    supported_events: List[str] = Field(default_factory=list)
    emotional_state: Dict[str, Any] = Field(default_factory=dict)
    skills: List[str] = Field(default_factory=list)
    soul_id: str = "wiii"
    endpoints: Dict[str, str] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for JSON response."""
        return self.model_dump(mode="json")


# =============================================================================
# Connection State
# =============================================================================


class ConnectionState(str, Enum):
    """Peer connection lifecycle states."""

    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"


# =============================================================================
# Message Priority (maps to EventPriority retry behavior)
# =============================================================================


class MessagePriority(str, Enum):
    """Priority levels for bridge messages — controls retry behavior."""

    CRITICAL = "CRITICAL"   # 1s retry, 30 attempts
    HIGH = "HIGH"           # 5s retry, 10 attempts
    NORMAL = "NORMAL"       # 30s retry, 3 attempts
    LOW = "LOW"             # No retry


# =============================================================================
# SoulBridge Message (envelope)
# =============================================================================


class SoulBridgeMessage(BaseModel):
    """Envelope for cross-service soul events.

    Wraps a SubSoulEvent (or any payload) for transport over WebSocket/HTTP.
    Includes source tracking for anti-echo and dedup via message ID.

    Sprint 215: Added request_id/reply_to_id for request-response correlation.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    source_soul: str = ""           # e.g., "wiii", "bro"
    target_soul: str = ""           # e.g., "bro", "wiii" ("" = broadcast)
    event_type: str = ""            # Maps to EventType value
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    priority: MessagePriority = MessagePriority.NORMAL
    request_id: str = ""            # Sprint 215: Correlation ID for request-response
    reply_to_id: str = ""           # Sprint 215: References the request_id being replied to

    def to_json_dict(self) -> Dict[str, Any]:
        """Serialize for WebSocket/HTTP transport."""
        data = {
            "id": self.id,
            "source_soul": self.source_soul,
            "target_soul": self.target_soul,
            "event_type": self.event_type,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "priority": self.priority.value,
        }
        if self.request_id:
            data["request_id"] = self.request_id
        if self.reply_to_id:
            data["reply_to_id"] = self.reply_to_id
        return data

    @classmethod
    def from_json_dict(cls, data: Dict[str, Any]) -> SoulBridgeMessage:
        """Deserialize from WebSocket/HTTP transport."""
        priority = data.get("priority", "NORMAL")
        if isinstance(priority, str):
            try:
                priority = MessagePriority(priority)
            except ValueError:
                priority = MessagePriority.NORMAL

        return cls(
            id=data.get("id", str(uuid4())),
            source_soul=data.get("source_soul", ""),
            target_soul=data.get("target_soul", ""),
            event_type=data.get("event_type", ""),
            payload=data.get("payload", {}),
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.now(timezone.utc),
            priority=priority,
            request_id=data.get("request_id", ""),
            reply_to_id=data.get("reply_to_id", ""),
        )


# =============================================================================
# Bridge Config (per-peer)
# =============================================================================


class BridgeConfig(BaseModel):
    """Configuration for connecting to a peer soul service."""

    peer_id: str = ""               # e.g., "bro"
    peer_url: str = ""              # e.g., "http://localhost:8001"
    ws_path: str = "/api/v1/soul-bridge/ws"
    reconnect_interval: int = 5     # Initial reconnect delay (seconds)
    reconnect_max: int = 60         # Max reconnect delay (seconds)
    heartbeat_interval: int = 30    # Ping interval (seconds)
    max_retry: int = 10             # Max reconnect attempts before giving up


# =============================================================================
# Retry Config (per priority)
# =============================================================================


_RETRY_CONFIG: Dict[MessagePriority, Dict[str, int]] = {
    MessagePriority.CRITICAL: {"interval": 1, "max_attempts": 30},
    MessagePriority.HIGH: {"interval": 5, "max_attempts": 10},
    MessagePriority.NORMAL: {"interval": 30, "max_attempts": 3},
    MessagePriority.LOW: {"interval": 0, "max_attempts": 0},
}


def get_retry_config(priority: MessagePriority) -> Dict[str, int]:
    """Get retry configuration for a given priority level."""
    return _RETRY_CONFIG.get(priority, _RETRY_CONFIG[MessagePriority.NORMAL])


# =============================================================================
# Consultation Models (Sprint 215: Cross-Soul Query Routing)
# =============================================================================


class ConsultationRequest(BaseModel):
    """Payload for asking a peer soul a question."""

    query: str = ""
    user_id: str = ""
    context: Dict[str, Any] = Field(default_factory=dict)
    domain_hint: str = ""           # e.g., "trading", "crypto", "risk"
    timeout_seconds: float = 15.0


class ConsultationResponse(BaseModel):
    """Payload returned by a peer soul answering a consultation."""

    response: str = ""
    confidence: float = 0.0
    sources: List[str] = Field(default_factory=list)
    mood: str = ""
    error: str = ""
