"""
SoulBridge Core — Singleton bridge connecting Wiii's EventBus to remote peer souls.

Sprint 213: "Cầu Nối Linh Hồn"

Architecture:
    Local EventBus → SoulBridge intercepts bridge-worthy events
        → PeerConnection sends via WebSocket/HTTP
            → Remote SoulBridge receives
                → Remote EventBus re-emits (tagged source:bridge:<peer>)

Anti-Echo:
    Events with source starting with "bridge:" are never re-forwarded.
    Dedup cache (UUID, 5-min TTL) prevents duplicate processing.

Design:
    - Singleton pattern (get_soul_bridge())
    - Feature-gated: enable_soul_bridge=False
    - Non-blocking: all errors caught, never affects chat pipeline
    - Subscribes to existing EventBus — zero changes to event producers
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set
from uuid import uuid4

from app.engine.soul_bridge.models import (
    AgentCard,
    BridgeConfig,
    ConnectionState,
    MessagePriority,
    SoulBridgeMessage,
)
from app.engine.soul_bridge.response_tracker import ResponseTracker
from app.engine.soul_bridge.transport import PeerConnection

logger = logging.getLogger(__name__)

# Dedup cache TTL (seconds)
_DEDUP_TTL = 300  # 5 minutes


class SoulBridge:
    """Singleton bridge for cross-service soul communication.

    Subscribes to the local SubSoulEventBus and forwards bridge-worthy events
    to connected peer souls via WebSocket/HTTP. Receives remote events and
    re-emits them on the local EventBus.

    Usage:
        bridge = get_soul_bridge()
        await bridge.initialize(settings)
        # ... runs in background ...
        await bridge.shutdown()
    """

    def __init__(self) -> None:
        self._peers: Dict[str, PeerConnection] = {}
        self._peer_cards: Dict[str, AgentCard] = {}
        self._bridge_events: Set[str] = set()
        self._dedup_cache: Dict[str, float] = {}  # message_id → timestamp
        self._initialized = False
        self._soul_id = "wiii"
        self._cleanup_task: Optional[asyncio.Task] = None
        # Sprint 215: Request-response support
        self._response_tracker = ResponseTracker()
        self._consultation_handler: Optional[Callable[..., Coroutine]] = None
        # Sprint 216: Per-peer event ring buffer for SoulBridgePanel
        self._peer_events: Dict[str, List[Dict[str, Any]]] = {}
        self._max_events_per_peer = 200

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def soul_id(self) -> str:
        return self._soul_id

    async def initialize(self, settings: Any = None) -> None:
        """Initialize the bridge from settings.

        Reads peer URLs, bridge event types, and subscribes to local EventBus.
        Does NOT auto-connect — call connect_to_peers() separately.

        Args:
            settings: App settings object with soul_bridge_* fields.
        """
        if self._initialized:
            return

        if settings is None:
            from app.core.config import settings as app_settings
            settings = app_settings

        # Parse bridge-worthy event types
        events_str = getattr(settings, "soul_bridge_bridge_events", "ESCALATION,STATUS_UPDATE,MOOD_CHANGE,DISCOVERY,DAILY_REPORT")
        self._bridge_events = {e.strip() for e in events_str.split(",") if e.strip()}

        # Parse peer URLs
        peers_str = getattr(settings, "soul_bridge_peers", "")
        heartbeat_interval = getattr(settings, "soul_bridge_heartbeat_interval", 30)
        reconnect_max = getattr(settings, "soul_bridge_reconnect_max", 60)
        ws_path = getattr(settings, "soul_bridge_ws_path", "/api/v1/soul-bridge/ws")

        for peer_entry in peers_str.split(","):
            peer_entry = peer_entry.strip()
            if not peer_entry:
                continue

            # Format: "peer_id=url" or just "url" (peer_id derived from URL)
            if "=" in peer_entry:
                peer_id, peer_url = peer_entry.split("=", 1)
            else:
                peer_url = peer_entry
                # Derive peer_id from URL
                peer_id = peer_url.rstrip("/").rsplit("/", 1)[-1].rsplit(":", 1)[0]
                if not peer_id or peer_id in ("localhost", "127.0.0.1"):
                    peer_id = f"peer_{len(self._peers)}"

            config = BridgeConfig(
                peer_id=peer_id.strip(),
                peer_url=peer_url.strip(),
                ws_path=ws_path,
                heartbeat_interval=heartbeat_interval,
                reconnect_max=reconnect_max,
            )

            conn = PeerConnection(config)
            conn.on_message(self._on_remote_event)
            self._peers[peer_id.strip()] = conn

        # Subscribe to local EventBus
        self._subscribe_local_events()

        # Start dedup cache cleanup
        self._cleanup_task = asyncio.create_task(self._cleanup_dedup_loop())

        self._initialized = True
        logger.info(
            "[SOUL_BRIDGE] Initialized: %d peers, bridge_events=%s",
            len(self._peers),
            self._bridge_events,
        )

    async def connect_to_peers(self) -> Dict[str, bool]:
        """Connect to all configured peers.

        Returns:
            Dict mapping peer_id to connection success.
        """
        results = {}
        for peer_id, conn in self._peers.items():
            try:
                success = await conn.connect()
                results[peer_id] = success
                if success:
                    # Fetch peer's agent card
                    card = await self._fetch_peer_card(peer_id)
                    if card:
                        self._peer_cards[peer_id] = card
            except Exception as e:
                logger.warning("[SOUL_BRIDGE] Failed to connect to '%s': %s", peer_id, e)
                results[peer_id] = False
        return results

    async def connect_to_peer(self, peer_id: str) -> bool:
        """Connect to a specific peer by ID."""
        conn = self._peers.get(peer_id)
        if not conn:
            logger.warning("[SOUL_BRIDGE] Unknown peer: %s", peer_id)
            return False
        return await conn.connect()

    async def disconnect_from_peer(self, peer_id: str) -> bool:
        """Disconnect from a specific peer."""
        conn = self._peers.get(peer_id)
        if not conn:
            return False
        await conn.disconnect()
        return True

    async def shutdown(self) -> None:
        """Gracefully close all connections and clean up."""
        # Sprint 215: Cancel pending request-response futures
        cancelled = self._response_tracker.cleanup()
        if cancelled:
            logger.info("[SOUL_BRIDGE] Cancelled %d pending request futures", cancelled)

        # Unsubscribe from EventBus
        self._unsubscribe_local_events()

        # Cancel cleanup task
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await asyncio.wait_for(self._cleanup_task, timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

        # Disconnect all peers
        for peer_id, conn in self._peers.items():
            try:
                await conn.disconnect()
            except Exception as e:
                logger.warning("[SOUL_BRIDGE] Error disconnecting '%s': %s", peer_id, e)

        self._initialized = False
        logger.info("[SOUL_BRIDGE] Shutdown complete")

    # =========================================================================
    # Event Forwarding: Local → Remote
    # =========================================================================

    def _subscribe_local_events(self) -> None:
        """Subscribe to local EventBus for bridge-worthy events."""
        try:
            from app.engine.subsoul.protocol import get_event_bus
            bus = get_event_bus()
            bus.subscribe(
                subscriber_id="soul_bridge",
                handler=self._on_local_event,
                event_types=None,  # All types — we filter in handler
                # min_priority defaults to EventPriority.LOW (all events)
            )
            logger.info("[SOUL_BRIDGE] Subscribed to local EventBus")
        except Exception as e:
            logger.warning("[SOUL_BRIDGE] Failed to subscribe to EventBus: %s", e)

    def _unsubscribe_local_events(self) -> None:
        """Unsubscribe from local EventBus."""
        try:
            from app.engine.subsoul.protocol import get_event_bus
            bus = get_event_bus()
            bus.unsubscribe("soul_bridge")
        except Exception:
            pass

    async def _on_local_event(self, event: Any) -> None:
        """Handle local EventBus event — forward to remote peers if bridge-worthy.

        Anti-echo: Skip events that originated from a bridge (source starts with "bridge:").
        """
        # Anti-echo: don't re-forward bridge-originated events
        source = getattr(event, "source", "")
        if source.startswith("bridge:"):
            return

        # Check if event type is bridge-worthy
        event_type = getattr(event, "event_type", None)
        if event_type is None:
            return

        event_type_str = event_type.value if hasattr(event_type, "value") else str(event_type)
        if event_type_str not in self._bridge_events:
            return

        # Map priority
        priority_str = getattr(event, "priority", "NORMAL")
        if hasattr(priority_str, "value"):
            priority_str = priority_str.value
        try:
            priority = MessagePriority(priority_str)
        except ValueError:
            priority = MessagePriority.NORMAL

        # Build bridge message
        message = SoulBridgeMessage(
            source_soul=self._soul_id,
            event_type=event_type_str,
            payload=getattr(event, "payload", {}) or {},
            priority=priority,
        )

        # Send to all connected peers
        for peer_id, conn in self._peers.items():
            if conn.is_connected:
                try:
                    await conn.send(message)
                    logger.debug(
                        "[SOUL_BRIDGE] Forwarded %s to '%s'",
                        event_type_str, peer_id,
                    )
                except Exception as e:
                    logger.warning("[SOUL_BRIDGE] Forward to '%s' failed: %s", peer_id, e)

    # =========================================================================
    # Event Receiving: Remote → Local
    # =========================================================================

    async def _on_remote_event(self, message: SoulBridgeMessage) -> None:
        """Handle incoming message from a remote peer.

        Sprint 215: Intercept replies and consultation requests before EventBus re-emit.
        Dedup check → reply resolution → consultation handling → re-emit on local EventBus.
        """
        # Dedup check
        if self._is_duplicate(message.id):
            logger.debug("[SOUL_BRIDGE] Duplicate message %s, skipping", message.id)
            return

        # Anti-echo: don't process our own messages
        if message.source_soul == self._soul_id:
            return

        logger.info(
            "[SOUL_BRIDGE] Received %s from '%s' (priority=%s)",
            message.event_type,
            message.source_soul,
            message.priority.value,
        )

        # Sprint 215: If this is a reply to a pending request, resolve the future
        if message.reply_to_id:
            resolved = self._response_tracker.resolve(message.reply_to_id, message)
            if resolved:
                logger.info("[SOUL_BRIDGE] Resolved reply for request %s", message.reply_to_id)
                return  # Don't re-emit replies on EventBus

        # Sprint 215: If this is a CONSULTATION request, handle it
        if message.event_type == "CONSULTATION" and message.request_id:
            asyncio.ensure_future(self._handle_consultation(message))
            return  # Don't re-emit consultation requests on EventBus

        # Sprint 216: Store in per-peer ring buffer before re-emit
        self._store_event(message.source_soul, message)

        # Re-emit on local EventBus with bridge source tag
        try:
            from app.engine.subsoul.protocol import get_event_bus, SubSoulEvent, EventType, EventPriority

            # Map event type
            try:
                event_type = EventType(message.event_type)
            except ValueError:
                logger.warning("[SOUL_BRIDGE] Unknown event type: %s", message.event_type)
                return

            # Map priority
            try:
                priority = EventPriority(message.priority.value)
            except ValueError:
                priority = EventPriority.NORMAL

            local_event = SubSoulEvent(
                event_type=event_type,
                priority=priority,
                subsoul_id=message.source_soul,
                source=f"bridge:{message.source_soul}",
                payload=message.payload,
                timestamp=message.timestamp,
            )

            bus = get_event_bus()
            await bus.emit(local_event)

        except Exception as e:
            logger.warning("[SOUL_BRIDGE] Failed to re-emit remote event: %s", e)

    # =========================================================================
    # Broadcast (for heartbeat integration)
    # =========================================================================

    async def broadcast_status(self, payload: Dict[str, Any]) -> None:
        """Broadcast a STATUS_UPDATE to all connected peers.

        Called by HeartbeatScheduler after each cycle.
        """
        message = SoulBridgeMessage(
            source_soul=self._soul_id,
            event_type="STATUS_UPDATE",
            payload=payload,
            priority=MessagePriority.LOW,
        )

        for peer_id, conn in self._peers.items():
            if conn.is_connected:
                try:
                    await conn.send(message)
                except Exception as e:
                    logger.debug("[SOUL_BRIDGE] Broadcast to '%s' failed: %s", peer_id, e)

    # =========================================================================
    # Sprint 215: Request-Response (ask_peer / consultation)
    # =========================================================================

    def register_consultation_handler(
        self, handler: Callable[..., Coroutine],
    ) -> None:
        """Register handler for incoming CONSULTATION requests.

        The handler receives the payload dict and must return a response dict.
        """
        self._consultation_handler = handler
        logger.info("[SOUL_BRIDGE] Consultation handler registered")

    async def ask_peer(
        self,
        peer_id: str,
        event_type: str,
        payload: Dict[str, Any],
        timeout: float = 15.0,
    ) -> Optional[SoulBridgeMessage]:
        """Send a request to a peer and wait for the reply.

        Args:
            peer_id: Target peer ID (e.g., "bro").
            event_type: Event type for the request (e.g., "CONSULTATION").
            payload: Request payload dict.
            timeout: Max seconds to wait for reply.

        Returns:
            The reply SoulBridgeMessage, or None on timeout/error.
        """
        if not self._initialized:
            logger.warning("[SOUL_BRIDGE] ask_peer called before initialization")
            return None

        conn = self._peers.get(peer_id)
        if not conn or not conn.is_connected:
            logger.warning("[SOUL_BRIDGE] ask_peer: peer '%s' not connected", peer_id)
            return None

        request_id = str(uuid4())
        future = self._response_tracker.create_future(request_id)

        message = SoulBridgeMessage(
            source_soul=self._soul_id,
            target_soul=peer_id,
            event_type=event_type,
            payload=payload,
            priority=MessagePriority.HIGH,
            request_id=request_id,
        )

        try:
            await conn.send(message)
        except Exception as e:
            logger.warning("[SOUL_BRIDGE] ask_peer send failed: %s", e)
            self._response_tracker.cancel(request_id)
            return None

        try:
            reply = await asyncio.wait_for(future, timeout=timeout)
            return reply
        except asyncio.TimeoutError:
            logger.warning("[SOUL_BRIDGE] ask_peer timeout after %.1fs (peer=%s)", timeout, peer_id)
            self._response_tracker.cancel(request_id)
            return None
        except asyncio.CancelledError:
            self._response_tracker.cancel(request_id)
            return None

    async def _handle_consultation(self, message: SoulBridgeMessage) -> None:
        """Handle incoming CONSULTATION request — call handler and send reply."""
        if not self._consultation_handler:
            logger.debug("[SOUL_BRIDGE] No consultation handler registered, ignoring")
            return

        try:
            response_payload = await self._consultation_handler(message.payload)
        except Exception as e:
            logger.warning("[SOUL_BRIDGE] Consultation handler error: %s", e)
            response_payload = {"error": str(e), "response": ""}

        # Build reply with reply_to_id pointing to the request
        reply = SoulBridgeMessage(
            source_soul=self._soul_id,
            target_soul=message.source_soul,
            event_type="CONSULTATION_REPLY",
            payload=response_payload,
            priority=MessagePriority.HIGH,
            reply_to_id=message.request_id,
        )

        # Send back to the requesting peer
        conn = self._peers.get(message.source_soul)
        if conn and conn.is_connected:
            try:
                await conn.send(reply)
            except Exception as e:
                logger.warning("[SOUL_BRIDGE] Failed to send consultation reply: %s", e)

    # =========================================================================
    # Per-Peer Event Ring Buffer (Sprint 216)
    # =========================================================================

    def _store_event(self, peer_id: str, msg: SoulBridgeMessage) -> None:
        """Store event in per-peer ring buffer."""
        import uuid as _uuid
        from datetime import datetime

        if peer_id not in self._peer_events:
            self._peer_events[peer_id] = []

        event = {
            "id": str(getattr(msg, "id", None) or _uuid.uuid4()),
            "event_type": msg.event_type,
            "payload": msg.payload or {},
            "priority": msg.priority.value if hasattr(msg.priority, "value") else str(msg.priority),
            "timestamp": msg.timestamp.isoformat() if hasattr(msg, "timestamp") and msg.timestamp else datetime.utcnow().isoformat(),
            "source_soul": msg.source_soul,
        }
        self._peer_events[peer_id].append(event)

        # FIFO eviction
        if len(self._peer_events[peer_id]) > self._max_events_per_peer:
            self._peer_events[peer_id] = self._peer_events[peer_id][-self._max_events_per_peer:]

    def get_peer_events(
        self, peer_id: str, event_type: Optional[str] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get recent events for a peer, optionally filtered by type."""
        events = self._peer_events.get(peer_id, [])
        if event_type:
            events = [e for e in events if e["event_type"] == event_type]
        return events[-limit:]

    # =========================================================================
    # Peer Management
    # =========================================================================

    def get_peer_status(self, peer_id: str) -> Optional[ConnectionState]:
        """Get connection state for a specific peer."""
        conn = self._peers.get(peer_id)
        return conn.state if conn else None

    def get_all_peer_status(self) -> Dict[str, str]:
        """Get connection state for all peers."""
        return {
            peer_id: conn.state.value
            for peer_id, conn in self._peers.items()
        }

    def get_peer_card(self, peer_id: str) -> Optional[AgentCard]:
        """Get cached agent card for a peer."""
        return self._peer_cards.get(peer_id)

    async def _fetch_peer_card(self, peer_id: str) -> Optional[AgentCard]:
        """Fetch agent card from peer's /.well-known/agent.json."""
        conn = self._peers.get(peer_id)
        if not conn:
            return None

        url = f"{conn.config.peer_url.rstrip('/')}/.well-known/agent.json"
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    return AgentCard(**data)
        except ImportError:
            logger.debug("[SOUL_BRIDGE] httpx not available for agent card fetch")
        except Exception as e:
            logger.debug("[SOUL_BRIDGE] Failed to fetch agent card from '%s': %s", peer_id, e)
        return None

    def get_bridge_status(self) -> Dict[str, Any]:
        """Get full bridge status for API response."""
        return {
            "initialized": self._initialized,
            "soul_id": self._soul_id,
            "bridge_events": sorted(self._bridge_events),
            "peer_count": len(self._peers),
            "peers": {
                peer_id: {
                    "state": conn.state.value,
                    "url": conn.config.peer_url,
                    "has_card": peer_id in self._peer_cards,
                }
                for peer_id, conn in self._peers.items()
            },
            "dedup_cache_size": len(self._dedup_cache),
        }

    # =========================================================================
    # Dedup Cache
    # =========================================================================

    def _is_duplicate(self, message_id: str) -> bool:
        """Check if a message has already been processed.

        Uses a TTL cache (5 minutes) to prevent reprocessing.
        """
        now = time.monotonic()

        if message_id in self._dedup_cache:
            return True

        self._dedup_cache[message_id] = now
        return False

    async def _cleanup_dedup_loop(self) -> None:
        """Background task: periodically clean expired dedup cache entries."""
        while True:
            try:
                await asyncio.sleep(60)  # Cleanup every minute
                now = time.monotonic()
                expired = [
                    msg_id for msg_id, ts in self._dedup_cache.items()
                    if now - ts > _DEDUP_TTL
                ]
                for msg_id in expired:
                    del self._dedup_cache[msg_id]

                if expired:
                    logger.debug("[SOUL_BRIDGE] Cleaned %d expired dedup entries", len(expired))
            except asyncio.CancelledError:
                break
            except Exception:
                pass


# =============================================================================
# Singleton
# =============================================================================

_bridge_instance: Optional[SoulBridge] = None


def get_soul_bridge() -> SoulBridge:
    """Get the singleton SoulBridge instance."""
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = SoulBridge()
    return _bridge_instance


def reset_soul_bridge() -> None:
    """Reset the singleton (for testing)."""
    global _bridge_instance
    _bridge_instance = None
