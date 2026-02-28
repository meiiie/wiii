"""
SoulBridge — Cross-service soul communication layer.

Sprint 213: "Cầu Nối Linh Hồn"

Architecture (3 layers):
    Layer 1: Agent Cards (Identity) — /.well-known/agent.json
    Layer 2: SoulBridge (Transport) — WebSocket + HTTP fallback
    Layer 3: EventBus (In-Process) — existing SubSoulEventBus

Usage:
    from app.engine.soul_bridge import get_soul_bridge, AgentCard, SoulBridgeMessage

    bridge = get_soul_bridge()
    await bridge.initialize(settings)
    await bridge.connect_to_peers()
    # ... bridge forwards events automatically ...
    await bridge.shutdown()
"""

from app.engine.soul_bridge.bridge import SoulBridge, get_soul_bridge, reset_soul_bridge
from app.engine.soul_bridge.models import (
    AgentCard,
    BridgeConfig,
    ConnectionState,
    ConsultationRequest,
    ConsultationResponse,
    MessagePriority,
    SoulBridgeMessage,
)
from app.engine.soul_bridge.agent_card import build_agent_card

__all__ = [
    "SoulBridge",
    "get_soul_bridge",
    "reset_soul_bridge",
    "AgentCard",
    "BridgeConfig",
    "ConnectionState",
    "ConsultationRequest",
    "ConsultationResponse",
    "MessagePriority",
    "SoulBridgeMessage",
    "build_agent_card",
]
