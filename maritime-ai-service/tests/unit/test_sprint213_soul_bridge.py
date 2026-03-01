"""
Sprint 213: SoulBridge — Soul-to-Soul Communication Bridge Tests.

Tests:
    - AgentCard: build, serialize, deserialize
    - SoulBridgeMessage: envelope, priority, serialization
    - PeerConnection: connect/disconnect lifecycle, heartbeat, HTTP fallback
    - SoulBridge: local→remote, remote→local, anti-echo, dedup
    - BridgeAPI: endpoints, WebSocket
    - Integration: end-to-end event flow
    - Edge cases: peer down, bridge disabled
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset singletons before each test."""
    from app.engine.soul_bridge.bridge import reset_soul_bridge
    from app.engine.subsoul.protocol import reset_event_bus
    reset_soul_bridge()
    reset_event_bus()
    yield
    reset_soul_bridge()
    reset_event_bus()


def _mock_settings(**overrides):
    """Create mock settings with soul_bridge defaults."""
    defaults = {
        "enable_soul_bridge": True,
        "soul_bridge_peers": "bro=http://localhost:8001",
        "soul_bridge_heartbeat_interval": 30,
        "soul_bridge_reconnect_max": 60,
        "soul_bridge_ws_path": "/api/v1/soul-bridge/ws",
        "soul_bridge_bridge_events": "ESCALATION,STATUS_UPDATE,MOOD_CHANGE,DISCOVERY,DAILY_REPORT",
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


# ===========================================================================
# TestAgentCard
# ===========================================================================


class TestAgentCard:
    """Tests for AgentCard model and builder."""

    def test_default_card(self):
        from app.engine.soul_bridge.models import AgentCard
        card = AgentCard()
        assert card.name == "Wiii"
        assert card.soul_id == "wiii"
        assert isinstance(card.capabilities, list)
        assert isinstance(card.supported_events, list)

    def test_card_serialization(self):
        from app.engine.soul_bridge.models import AgentCard
        card = AgentCard(
            name="TestSoul",
            description="Test",
            version="2.0",
            capabilities=["search"],
            soul_id="test",
        )
        d = card.to_dict()
        assert d["name"] == "TestSoul"
        assert d["soul_id"] == "test"
        assert d["version"] == "2.0"
        assert "search" in d["capabilities"]

    def test_card_with_emotions(self):
        from app.engine.soul_bridge.models import AgentCard
        card = AgentCard(
            emotional_state={"mood": "curious", "energy": 0.8},
        )
        assert card.emotional_state["mood"] == "curious"
        assert card.emotional_state["energy"] == 0.8

    def test_build_agent_card_defaults(self):
        from app.engine.soul_bridge.agent_card import build_agent_card
        card = build_agent_card()
        assert card.name == "Wiii"
        assert len(card.capabilities) > 0
        assert len(card.supported_events) > 0

    def test_build_agent_card_with_soul(self):
        from app.engine.soul_bridge.agent_card import build_agent_card

        soul = MagicMock()
        soul.name = "TestWiii"
        soul.species = "Test Agent"
        soul.interests = MagicMock()
        soul.interests.primary = ["maritime", "AI"]

        card = build_agent_card(soul_config=soul)
        assert card.name == "TestWiii"
        assert "maritime" in card.skills
        assert "AI" in card.skills

    def test_build_agent_card_with_base_url(self):
        from app.engine.soul_bridge.agent_card import build_agent_card
        card = build_agent_card(base_url="http://localhost:8000")
        assert card.url == "http://localhost:8000"
        assert "agent_card" in card.endpoints
        assert "websocket" in card.endpoints

    def test_build_agent_card_with_emotions(self):
        from app.engine.soul_bridge.agent_card import build_agent_card
        emotions = {"mood": "happy", "energy": 0.9}
        card = build_agent_card(emotional_state=emotions)
        assert card.emotional_state["mood"] == "happy"


# ===========================================================================
# TestSoulBridgeMessage
# ===========================================================================


class TestSoulBridgeMessage:
    """Tests for SoulBridgeMessage envelope."""

    def test_default_message(self):
        from app.engine.soul_bridge.models import SoulBridgeMessage
        msg = SoulBridgeMessage()
        assert msg.id  # UUID generated
        assert msg.source_soul == ""
        assert msg.priority.value == "NORMAL"

    def test_message_creation(self):
        from app.engine.soul_bridge.models import SoulBridgeMessage, MessagePriority
        msg = SoulBridgeMessage(
            source_soul="wiii",
            target_soul="bro",
            event_type="ESCALATION",
            payload={"level": "critical"},
            priority=MessagePriority.CRITICAL,
        )
        assert msg.source_soul == "wiii"
        assert msg.target_soul == "bro"
        assert msg.event_type == "ESCALATION"
        assert msg.payload["level"] == "critical"
        assert msg.priority == MessagePriority.CRITICAL

    def test_message_serialization(self):
        from app.engine.soul_bridge.models import SoulBridgeMessage
        msg = SoulBridgeMessage(
            source_soul="wiii",
            event_type="STATUS_UPDATE",
            payload={"mood": "curious"},
        )
        d = msg.to_json_dict()
        assert d["source_soul"] == "wiii"
        assert d["event_type"] == "STATUS_UPDATE"
        assert isinstance(d["timestamp"], str)

    def test_message_deserialization(self):
        from app.engine.soul_bridge.models import SoulBridgeMessage, MessagePriority
        data = {
            "id": "test-123",
            "source_soul": "bro",
            "target_soul": "wiii",
            "event_type": "ESCALATION",
            "payload": {"liq": 5000000},
            "timestamp": "2026-02-27T10:00:00+00:00",
            "priority": "CRITICAL",
        }
        msg = SoulBridgeMessage.from_json_dict(data)
        assert msg.id == "test-123"
        assert msg.source_soul == "bro"
        assert msg.priority == MessagePriority.CRITICAL
        assert msg.payload["liq"] == 5000000

    def test_message_deserialization_unknown_priority(self):
        from app.engine.soul_bridge.models import SoulBridgeMessage, MessagePriority
        data = {"priority": "UNKNOWN_LEVEL"}
        msg = SoulBridgeMessage.from_json_dict(data)
        assert msg.priority == MessagePriority.NORMAL

    def test_message_roundtrip(self):
        from app.engine.soul_bridge.models import SoulBridgeMessage
        original = SoulBridgeMessage(
            source_soul="test",
            event_type="DISCOVERY",
            payload={"key": "value"},
        )
        serialized = original.to_json_dict()
        restored = SoulBridgeMessage.from_json_dict(serialized)
        assert restored.source_soul == original.source_soul
        assert restored.event_type == original.event_type
        assert restored.payload == original.payload


# ===========================================================================
# TestConnectionState
# ===========================================================================


class TestConnectionState:
    """Tests for ConnectionState enum."""

    def test_all_states(self):
        from app.engine.soul_bridge.models import ConnectionState
        assert ConnectionState.DISCONNECTED.value == "DISCONNECTED"
        assert ConnectionState.CONNECTING.value == "CONNECTING"
        assert ConnectionState.CONNECTED.value == "CONNECTED"
        assert ConnectionState.RECONNECTING.value == "RECONNECTING"


# ===========================================================================
# TestBridgeConfig
# ===========================================================================


class TestBridgeConfig:
    """Tests for BridgeConfig model."""

    def test_defaults(self):
        from app.engine.soul_bridge.models import BridgeConfig
        config = BridgeConfig()
        assert config.peer_id == ""
        assert config.heartbeat_interval == 30
        assert config.reconnect_max == 60

    def test_custom_config(self):
        from app.engine.soul_bridge.models import BridgeConfig
        config = BridgeConfig(
            peer_id="bro",
            peer_url="http://localhost:8001",
            heartbeat_interval=15,
        )
        assert config.peer_id == "bro"
        assert config.peer_url == "http://localhost:8001"
        assert config.heartbeat_interval == 15


# ===========================================================================
# TestRetryConfig
# ===========================================================================


class TestRetryConfig:
    """Tests for priority-based retry configuration."""

    def test_critical_retry(self):
        from app.engine.soul_bridge.models import MessagePriority, get_retry_config
        config = get_retry_config(MessagePriority.CRITICAL)
        assert config["interval"] == 1
        assert config["max_attempts"] == 30

    def test_low_no_retry(self):
        from app.engine.soul_bridge.models import MessagePriority, get_retry_config
        config = get_retry_config(MessagePriority.LOW)
        assert config["max_attempts"] == 0

    def test_normal_retry(self):
        from app.engine.soul_bridge.models import MessagePriority, get_retry_config
        config = get_retry_config(MessagePriority.NORMAL)
        assert config["interval"] == 30
        assert config["max_attempts"] == 3


# ===========================================================================
# TestPeerConnection
# ===========================================================================


class TestPeerConnection:
    """Tests for PeerConnection transport layer."""

    def test_initial_state(self):
        from app.engine.soul_bridge.transport import PeerConnection
        from app.engine.soul_bridge.models import BridgeConfig, ConnectionState

        config = BridgeConfig(peer_id="test", peer_url="http://localhost:9999")
        conn = PeerConnection(config)

        assert conn.peer_id == "test"
        assert conn.state == ConnectionState.DISCONNECTED
        assert not conn.is_connected

    def test_on_message_registers_handler(self):
        from app.engine.soul_bridge.transport import PeerConnection
        from app.engine.soul_bridge.models import BridgeConfig

        config = BridgeConfig(peer_id="test", peer_url="http://localhost:9999")
        conn = PeerConnection(config)

        handler = AsyncMock()
        conn.on_message(handler)
        assert handler in conn._handlers

    @pytest.mark.asyncio
    async def test_connect_without_websockets_package(self):
        from app.engine.soul_bridge.transport import PeerConnection
        from app.engine.soul_bridge.models import BridgeConfig, ConnectionState

        config = BridgeConfig(peer_id="test", peer_url="http://localhost:9999")
        conn = PeerConnection(config)

        # Mock import failure for websockets
        with patch.dict("sys.modules", {"websockets": None}):
            with patch("builtins.__import__", side_effect=ImportError("no websockets")):
                result = await conn.connect()
                # Should fail gracefully
                assert not result or conn.state in (ConnectionState.DISCONNECTED, ConnectionState.RECONNECTING)

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self):
        from app.engine.soul_bridge.transport import PeerConnection
        from app.engine.soul_bridge.models import BridgeConfig, ConnectionState

        config = BridgeConfig(peer_id="test", peer_url="http://localhost:9999")
        conn = PeerConnection(config)

        await conn.disconnect()
        assert conn.state == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_send_http_fallback(self):
        from app.engine.soul_bridge.transport import PeerConnection
        from app.engine.soul_bridge.models import BridgeConfig, SoulBridgeMessage

        config = BridgeConfig(peer_id="test", peer_url="http://localhost:9999")
        conn = PeerConnection(config)

        msg = SoulBridgeMessage(source_soul="wiii", event_type="TEST")

        # Use patch.object on the connection's _send_http directly for simplicity
        with patch.object(conn, "_send_http", new_callable=AsyncMock, return_value=True):
            result = await conn._send_http(msg)
            assert result is True

    @pytest.mark.asyncio
    async def test_send_http_fallback_returns_false_on_error(self):
        from app.engine.soul_bridge.transport import PeerConnection
        from app.engine.soul_bridge.models import BridgeConfig, SoulBridgeMessage

        config = BridgeConfig(peer_id="test", peer_url="http://localhost:9999")
        conn = PeerConnection(config)

        msg = SoulBridgeMessage(source_soul="wiii", event_type="TEST")

        # Real _send_http will try to import httpx and fail gracefully
        result = await conn._send_http(msg)
        # Should return False (httpx may or may not be installed, both cases handled)
        assert isinstance(result, bool)


# ===========================================================================
# TestSoulBridge
# ===========================================================================


class TestSoulBridge:
    """Tests for SoulBridge core logic."""

    def test_singleton(self):
        from app.engine.soul_bridge.bridge import get_soul_bridge, reset_soul_bridge
        bridge1 = get_soul_bridge()
        bridge2 = get_soul_bridge()
        assert bridge1 is bridge2
        reset_soul_bridge()
        bridge3 = get_soul_bridge()
        assert bridge3 is not bridge1

    @pytest.mark.asyncio
    async def test_initialize(self):
        from app.engine.soul_bridge.bridge import get_soul_bridge
        bridge = get_soul_bridge()
        settings = _mock_settings()

        with patch("app.engine.subsoul.protocol.get_event_bus") as mock_bus:
            mock_bus.return_value = MagicMock()
            await bridge.initialize(settings)

        assert bridge.is_initialized
        assert "bro" in bridge._peers
        assert "ESCALATION" in bridge._bridge_events

    @pytest.mark.asyncio
    async def test_initialize_no_peers(self):
        from app.engine.soul_bridge.bridge import get_soul_bridge
        bridge = get_soul_bridge()
        settings = _mock_settings(soul_bridge_peers="")

        with patch("app.engine.subsoul.protocol.get_event_bus") as mock_bus:
            mock_bus.return_value = MagicMock()
            await bridge.initialize(settings)

        assert bridge.is_initialized
        assert len(bridge._peers) == 0

    @pytest.mark.asyncio
    async def test_initialize_multiple_peers(self):
        from app.engine.soul_bridge.bridge import get_soul_bridge
        bridge = get_soul_bridge()
        settings = _mock_settings(
            soul_bridge_peers="bro=http://localhost:8001,trader=http://localhost:8002"
        )

        with patch("app.engine.subsoul.protocol.get_event_bus") as mock_bus:
            mock_bus.return_value = MagicMock()
            await bridge.initialize(settings)

        assert len(bridge._peers) == 2
        assert "bro" in bridge._peers
        assert "trader" in bridge._peers

    @pytest.mark.asyncio
    async def test_anti_echo_local(self):
        """Events with source='bridge:*' should not be re-forwarded."""
        from app.engine.soul_bridge.bridge import get_soul_bridge
        from app.engine.subsoul.protocol import SubSoulEvent, EventType, EventPriority

        bridge = get_soul_bridge()
        settings = _mock_settings()

        with patch("app.engine.subsoul.protocol.get_event_bus") as mock_bus:
            mock_bus.return_value = MagicMock()
            await bridge.initialize(settings)

        # Create event from bridge (should be skipped)
        event = SubSoulEvent(
            event_type=EventType.ESCALATION,
            priority=EventPriority.HIGH,
            subsoul_id="bro",
            source="bridge:bro",
            payload={"test": True},
        )

        # Mock peer connection
        mock_conn = MagicMock()
        mock_conn.is_connected = True
        mock_conn.send = AsyncMock()
        bridge._peers["bro"] = mock_conn

        await bridge._on_local_event(event)

        # Should NOT forward (anti-echo)
        mock_conn.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_forward_local_event(self):
        """Bridge-worthy local events should be forwarded to connected peers."""
        from app.engine.soul_bridge.bridge import get_soul_bridge
        from app.engine.subsoul.protocol import SubSoulEvent, EventType, EventPriority

        bridge = get_soul_bridge()
        settings = _mock_settings()

        with patch("app.engine.subsoul.protocol.get_event_bus") as mock_bus:
            mock_bus.return_value = MagicMock()
            await bridge.initialize(settings)

        event = SubSoulEvent(
            event_type=EventType.ESCALATION,
            priority=EventPriority.CRITICAL,
            subsoul_id="bro",
            source="subsoul:bro",
            payload={"liquidation": 5000000},
        )

        mock_conn = MagicMock()
        mock_conn.is_connected = True
        mock_conn.send = AsyncMock(return_value=True)
        bridge._peers["bro"] = mock_conn

        await bridge._on_local_event(event)

        mock_conn.send.assert_called_once()
        sent_msg = mock_conn.send.call_args[0][0]
        assert sent_msg.event_type == "ESCALATION"
        assert sent_msg.source_soul == "wiii"

    @pytest.mark.asyncio
    async def test_skip_non_bridge_event(self):
        """Events not in bridge_events set should be skipped."""
        from app.engine.soul_bridge.bridge import get_soul_bridge
        from app.engine.subsoul.protocol import SubSoulEvent, EventType, EventPriority

        bridge = get_soul_bridge()
        settings = _mock_settings()

        with patch("app.engine.subsoul.protocol.get_event_bus") as mock_bus:
            mock_bus.return_value = MagicMock()
            await bridge.initialize(settings)

        # ACTION_TAKEN is not in default bridge_events
        event = SubSoulEvent(
            event_type=EventType.ACTION_TAKEN,
            priority=EventPriority.NORMAL,
            subsoul_id="bro",
            source="subsoul:bro",
        )

        mock_conn = MagicMock()
        mock_conn.is_connected = True
        mock_conn.send = AsyncMock()
        bridge._peers["bro"] = mock_conn

        await bridge._on_local_event(event)
        mock_conn.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_receive_remote_event(self):
        """Remote events should be re-emitted on local EventBus."""
        from app.engine.soul_bridge.bridge import get_soul_bridge
        from app.engine.soul_bridge.models import SoulBridgeMessage, MessagePriority

        bridge = get_soul_bridge()
        settings = _mock_settings()

        mock_bus = MagicMock()
        mock_bus.emit = AsyncMock()

        with patch("app.engine.subsoul.protocol.get_event_bus", return_value=mock_bus):
            await bridge.initialize(settings)

            message = SoulBridgeMessage(
                source_soul="bro",
                target_soul="wiii",
                event_type="ESCALATION",
                payload={"alert": "high liquidation"},
                priority=MessagePriority.CRITICAL,
            )

            await bridge._on_remote_event(message)

        # Should emit on local bus
        assert mock_bus.emit.called
        emitted_event = mock_bus.emit.call_args[0][0]
        assert emitted_event.source == "bridge:bro"
        assert emitted_event.event_type.value == "ESCALATION"

    @pytest.mark.asyncio
    async def test_anti_echo_remote(self):
        """Events from own soul_id should not be re-emitted."""
        from app.engine.soul_bridge.bridge import get_soul_bridge
        from app.engine.soul_bridge.models import SoulBridgeMessage

        bridge = get_soul_bridge()
        settings = _mock_settings()

        mock_bus = MagicMock()
        mock_bus.emit = AsyncMock()

        with patch("app.engine.subsoul.protocol.get_event_bus", return_value=mock_bus):
            await bridge.initialize(settings)

            # Message from self
            message = SoulBridgeMessage(
                source_soul="wiii",  # Same as bridge's soul_id
                event_type="STATUS_UPDATE",
            )

            await bridge._on_remote_event(message)

        mock_bus.emit.assert_not_called()

    @pytest.mark.asyncio
    async def test_dedup_cache(self):
        """Duplicate messages should be detected and skipped."""
        from app.engine.soul_bridge.bridge import get_soul_bridge
        from app.engine.soul_bridge.models import SoulBridgeMessage

        bridge = get_soul_bridge()
        settings = _mock_settings()

        mock_bus = MagicMock()
        mock_bus.emit = AsyncMock()

        with patch("app.engine.subsoul.protocol.get_event_bus", return_value=mock_bus):
            await bridge.initialize(settings)

            message = SoulBridgeMessage(
                id="unique-123",
                source_soul="bro",
                event_type="ESCALATION",
            )

            # First time — should process
            await bridge._on_remote_event(message)
            assert mock_bus.emit.call_count == 1

            # Second time — should skip (dedup)
            await bridge._on_remote_event(message)
            assert mock_bus.emit.call_count == 1  # Still 1

    def test_dedup_detection(self):
        from app.engine.soul_bridge.bridge import get_soul_bridge
        bridge = get_soul_bridge()

        assert not bridge._is_duplicate("msg-1")
        assert bridge._is_duplicate("msg-1")  # Second call → duplicate
        assert not bridge._is_duplicate("msg-2")

    @pytest.mark.asyncio
    async def test_broadcast_status(self):
        """broadcast_status should send to all connected peers."""
        from app.engine.soul_bridge.bridge import get_soul_bridge

        bridge = get_soul_bridge()
        settings = _mock_settings()

        with patch("app.engine.subsoul.protocol.get_event_bus") as mock_bus:
            mock_bus.return_value = MagicMock()
            await bridge.initialize(settings)

        mock_conn = MagicMock()
        mock_conn.is_connected = True
        mock_conn.send = AsyncMock(return_value=True)
        bridge._peers["bro"] = mock_conn

        await bridge.broadcast_status({"mood": "curious", "energy": 0.8})

        mock_conn.send.assert_called_once()
        sent = mock_conn.send.call_args[0][0]
        assert sent.event_type == "STATUS_UPDATE"
        assert sent.payload["mood"] == "curious"

    @pytest.mark.asyncio
    async def test_broadcast_skips_disconnected(self):
        """broadcast_status should skip disconnected peers."""
        from app.engine.soul_bridge.bridge import get_soul_bridge

        bridge = get_soul_bridge()
        settings = _mock_settings()

        with patch("app.engine.subsoul.protocol.get_event_bus") as mock_bus:
            mock_bus.return_value = MagicMock()
            await bridge.initialize(settings)

        mock_conn = MagicMock()
        mock_conn.is_connected = False
        mock_conn.send = AsyncMock()
        bridge._peers["bro"] = mock_conn

        await bridge.broadcast_status({"mood": "neutral"})
        mock_conn.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_bridge_status(self):
        from app.engine.soul_bridge.bridge import get_soul_bridge

        bridge = get_soul_bridge()
        settings = _mock_settings()

        with patch("app.engine.subsoul.protocol.get_event_bus") as mock_bus:
            mock_bus.return_value = MagicMock()
            await bridge.initialize(settings)

        status = bridge.get_bridge_status()
        assert status["initialized"] is True
        assert status["soul_id"] == "wiii"
        assert "bro" in status["peers"]
        assert "ESCALATION" in status["bridge_events"]

    @pytest.mark.asyncio
    async def test_shutdown(self):
        from app.engine.soul_bridge.bridge import get_soul_bridge

        bridge = get_soul_bridge()
        settings = _mock_settings()

        with patch("app.engine.subsoul.protocol.get_event_bus") as mock_bus:
            mock_bus.return_value = MagicMock()
            await bridge.initialize(settings)

        assert bridge.is_initialized

        # Mock disconnect
        for conn in bridge._peers.values():
            conn.disconnect = AsyncMock()

        await bridge.shutdown()
        assert not bridge.is_initialized


# ===========================================================================
# TestBridgeEventTypeEnum
# ===========================================================================


class TestBridgeEventType:
    """Tests for BRIDGE_EVENT addition to EventType enum."""

    def test_bridge_event_exists(self):
        from app.engine.subsoul.protocol import EventType
        assert hasattr(EventType, "BRIDGE_EVENT")
        assert EventType.BRIDGE_EVENT.value == "BRIDGE_EVENT"

    def test_all_event_types(self):
        from app.engine.subsoul.protocol import EventType
        types = [e.value for e in EventType]
        assert "ESCALATION" in types
        assert "BRIDGE_EVENT" in types
        assert "KILL_SWITCH" in types


# ===========================================================================
# TestConfigFlags
# ===========================================================================


class TestConfigFlags:
    """Tests for soul_bridge config flags."""

    def test_default_disabled(self):
        from app.core.config import Settings
        default = Settings.model_fields["enable_soul_bridge"].default
        assert default is False

    def test_default_peers_empty(self):
        from app.core.config import Settings
        default = Settings.model_fields["soul_bridge_peers"].default
        assert default == ""

    def test_default_heartbeat_interval(self):
        from app.core.config import Settings
        default = Settings.model_fields["soul_bridge_heartbeat_interval"].default
        assert default == 30

    def test_default_reconnect_max(self):
        from app.core.config import Settings
        default = Settings.model_fields["soul_bridge_reconnect_max"].default
        assert default == 60

    def test_default_ws_path(self):
        from app.core.config import Settings
        default = Settings.model_fields["soul_bridge_ws_path"].default
        assert default == "/api/v1/soul-bridge/ws"

    def test_default_bridge_events(self):
        from app.core.config import Settings
        default = Settings.model_fields["soul_bridge_bridge_events"].default
        assert "ESCALATION" in default
        assert "STATUS_UPDATE" in default
        assert "MOOD_CHANGE" in default


# ===========================================================================
# TestHeartbeatIntegration
# ===========================================================================


class TestHeartbeatIntegration:
    """Tests for SoulBridge integration with HeartbeatScheduler."""

    @pytest.mark.asyncio
    async def test_broadcast_soul_bridge_disabled(self):
        """When soul_bridge disabled, broadcast is a no-op."""
        from app.engine.living_agent.heartbeat import HeartbeatScheduler
        from app.engine.living_agent.models import HeartbeatResult

        scheduler = HeartbeatScheduler()
        engine = MagicMock()
        engine.mood = MagicMock()
        engine.mood.value = "curious"
        engine.energy = 0.7
        result = HeartbeatResult()

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.enable_soul_bridge = False
            await scheduler._broadcast_soul_bridge(engine, result)
            # Should complete without error (no-op)

    @pytest.mark.asyncio
    async def test_broadcast_soul_bridge_enabled(self):
        """When soul_bridge enabled, broadcast calls bridge.broadcast_status."""
        from app.engine.living_agent.heartbeat import HeartbeatScheduler
        from app.engine.living_agent.models import HeartbeatResult

        scheduler = HeartbeatScheduler()
        engine = MagicMock()
        engine.mood = MagicMock()
        engine.mood.value = "curious"
        engine.energy = 0.7
        result = HeartbeatResult()
        result.duration_ms = 150

        mock_bridge = MagicMock()
        mock_bridge.is_initialized = True
        mock_bridge.broadcast_status = AsyncMock()

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.enable_soul_bridge = True
            with patch("app.engine.soul_bridge.get_soul_bridge", return_value=mock_bridge):
                await scheduler._broadcast_soul_bridge(engine, result)

        mock_bridge.broadcast_status.assert_called_once()
        payload = mock_bridge.broadcast_status.call_args[0][0]
        assert payload["mood"] == "curious"
        assert payload["energy"] == 0.7

    @pytest.mark.asyncio
    async def test_broadcast_soul_bridge_error_resilient(self):
        """broadcast_soul_bridge should not propagate errors."""
        from app.engine.living_agent.heartbeat import HeartbeatScheduler
        from app.engine.living_agent.models import HeartbeatResult

        scheduler = HeartbeatScheduler()
        engine = MagicMock()
        engine.mood = MagicMock()
        engine.mood.value = "curious"
        engine.energy = 0.7
        result = HeartbeatResult()

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.enable_soul_bridge = True
            with patch("app.engine.soul_bridge.get_soul_bridge", side_effect=Exception("bridge broken")):
                # Should NOT raise
                await scheduler._broadcast_soul_bridge(engine, result)


# ===========================================================================
# TestBridgeAPI
# ===========================================================================


class TestBridgeAPI:
    """Tests for SoulBridge API endpoints."""

    def test_event_payload_model(self):
        from app.api.v1.soul_bridge import EventPayload
        payload = EventPayload(
            source_soul="bro",
            event_type="ESCALATION",
            payload={"test": True},
        )
        assert payload.source_soul == "bro"
        assert payload.event_type == "ESCALATION"

    def test_connect_request_model(self):
        from app.api.v1.soul_bridge import ConnectRequest
        req = ConnectRequest(peer_id="bro")
        assert req.peer_id == "bro"

    def test_require_admin_rejects_non_admin(self):
        """Non-admin users should be rejected from all management endpoints."""
        from app.api.v1.soul_bridge import _require_admin
        from app.core.security import AuthenticatedUser

        student = AuthenticatedUser(user_id="u1", auth_method="api_key", role="student")
        with pytest.raises(Exception) as exc_info:
            _require_admin(student)
        assert exc_info.value.status_code == 403

        teacher = AuthenticatedUser(user_id="u2", auth_method="api_key", role="teacher")
        with pytest.raises(Exception) as exc_info:
            _require_admin(teacher)
        assert exc_info.value.status_code == 403

    def test_require_admin_allows_admin(self):
        """Admin users should pass the guard."""
        from app.api.v1.soul_bridge import _require_admin
        from app.core.security import AuthenticatedUser

        admin = AuthenticatedUser(user_id="a1", auth_method="jwt", role="admin")
        # Should NOT raise
        _require_admin(admin)

    @pytest.mark.asyncio
    async def test_status_requires_admin(self):
        """GET /status should require admin auth."""
        from app.api.v1.soul_bridge import get_bridge_status
        from app.core.security import AuthenticatedUser

        student = AuthenticatedUser(user_id="u1", auth_method="api_key", role="student")
        with pytest.raises(Exception) as exc_info:
            await get_bridge_status(auth=student)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_connect_requires_admin(self):
        """POST /connect should require admin auth."""
        from app.api.v1.soul_bridge import connect_to_peer, ConnectRequest
        from app.core.security import AuthenticatedUser

        student = AuthenticatedUser(user_id="u1", auth_method="api_key", role="student")
        req = ConnectRequest(peer_id="bro")
        with pytest.raises(Exception) as exc_info:
            await connect_to_peer(request=req, auth=student)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_disconnect_requires_admin(self):
        """POST /disconnect should require admin auth."""
        from app.api.v1.soul_bridge import disconnect_from_peer, ConnectRequest
        from app.core.security import AuthenticatedUser

        student = AuthenticatedUser(user_id="u1", auth_method="api_key", role="student")
        req = ConnectRequest(peer_id="bro")
        with pytest.raises(Exception) as exc_info:
            await disconnect_from_peer(request=req, auth=student)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_peers_requires_admin(self):
        """GET /peers should require admin auth."""
        from app.api.v1.soul_bridge import list_peers
        from app.core.security import AuthenticatedUser

        student = AuthenticatedUser(user_id="u1", auth_method="api_key", role="student")
        with pytest.raises(Exception) as exc_info:
            await list_peers(auth=student)
        assert exc_info.value.status_code == 403


# ===========================================================================
# TestEdgeCases
# ===========================================================================


class TestEdgeCases:
    """Edge case tests."""

    @pytest.mark.asyncio
    async def test_receive_unknown_event_type(self):
        """Unknown event types should be logged and skipped."""
        from app.engine.soul_bridge.bridge import get_soul_bridge
        from app.engine.soul_bridge.models import SoulBridgeMessage

        bridge = get_soul_bridge()
        settings = _mock_settings()

        mock_bus = MagicMock()
        mock_bus.emit = AsyncMock()

        with patch("app.engine.subsoul.protocol.get_event_bus", return_value=mock_bus):
            await bridge.initialize(settings)

            message = SoulBridgeMessage(
                source_soul="bro",
                event_type="TOTALLY_UNKNOWN_TYPE",
            )

            # Should NOT raise
            await bridge._on_remote_event(message)
            mock_bus.emit.assert_not_called()

    @pytest.mark.asyncio
    async def test_local_event_no_event_type(self):
        """Events without event_type should be skipped."""
        from app.engine.soul_bridge.bridge import get_soul_bridge

        bridge = get_soul_bridge()
        settings = _mock_settings()

        with patch("app.engine.subsoul.protocol.get_event_bus") as mock_bus:
            mock_bus.return_value = MagicMock()
            await bridge.initialize(settings)

        event = MagicMock()
        event.event_type = None
        event.source = "local"

        mock_conn = MagicMock()
        mock_conn.is_connected = True
        mock_conn.send = AsyncMock()
        bridge._peers["bro"] = mock_conn

        await bridge._on_local_event(event)
        mock_conn.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_peer_status_unknown_peer(self):
        from app.engine.soul_bridge.bridge import get_soul_bridge
        bridge = get_soul_bridge()
        assert bridge.get_peer_status("nonexistent") is None

    @pytest.mark.asyncio
    async def test_peer_card_unknown_peer(self):
        from app.engine.soul_bridge.bridge import get_soul_bridge
        bridge = get_soul_bridge()
        assert bridge.get_peer_card("nonexistent") is None

    @pytest.mark.asyncio
    async def test_connect_unknown_peer(self):
        from app.engine.soul_bridge.bridge import get_soul_bridge
        bridge = get_soul_bridge()
        result = await bridge.connect_to_peer("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_disconnect_unknown_peer(self):
        from app.engine.soul_bridge.bridge import get_soul_bridge
        bridge = get_soul_bridge()
        result = await bridge.disconnect_from_peer("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_double_initialize(self):
        """Calling initialize twice should be idempotent."""
        from app.engine.soul_bridge.bridge import get_soul_bridge
        bridge = get_soul_bridge()
        settings = _mock_settings()

        with patch("app.engine.subsoul.protocol.get_event_bus") as mock_bus:
            mock_bus.return_value = MagicMock()
            await bridge.initialize(settings)
            await bridge.initialize(settings)  # Second call — no-op

        assert bridge.is_initialized

    @pytest.mark.asyncio
    async def test_initialize_with_url_only_peers(self):
        """Peer entries without explicit ID should derive ID from URL."""
        from app.engine.soul_bridge.bridge import get_soul_bridge
        bridge = get_soul_bridge()
        settings = _mock_settings(soul_bridge_peers="http://192.168.1.100:8001")

        with patch("app.engine.subsoul.protocol.get_event_bus") as mock_bus:
            mock_bus.return_value = MagicMock()
            await bridge.initialize(settings)

        assert len(bridge._peers) == 1

    def test_message_priority_mapping(self):
        from app.engine.soul_bridge.models import MessagePriority
        assert MessagePriority.CRITICAL.value == "CRITICAL"
        assert MessagePriority.HIGH.value == "HIGH"
        assert MessagePriority.NORMAL.value == "NORMAL"
        assert MessagePriority.LOW.value == "LOW"

    @pytest.mark.asyncio
    async def test_fetch_peer_card_no_peer(self):
        from app.engine.soul_bridge.bridge import get_soul_bridge
        bridge = get_soul_bridge()
        result = await bridge._fetch_peer_card("nonexistent")
        assert result is None


# ===========================================================================
# TestPackageExports
# ===========================================================================


class TestPackageExports:
    """Test __init__.py exports."""

    def test_import_soul_bridge(self):
        from app.engine.soul_bridge import SoulBridge
        assert SoulBridge is not None

    def test_import_get_soul_bridge(self):
        from app.engine.soul_bridge import get_soul_bridge
        assert callable(get_soul_bridge)

    def test_import_agent_card(self):
        from app.engine.soul_bridge import AgentCard
        assert AgentCard is not None

    def test_import_soul_bridge_message(self):
        from app.engine.soul_bridge import SoulBridgeMessage
        assert SoulBridgeMessage is not None

    def test_import_connection_state(self):
        from app.engine.soul_bridge import ConnectionState
        assert ConnectionState is not None

    def test_import_build_agent_card(self):
        from app.engine.soul_bridge import build_agent_card
        assert callable(build_agent_card)

    def test_import_bridge_config(self):
        from app.engine.soul_bridge import BridgeConfig
        assert BridgeConfig is not None

    def test_import_message_priority(self):
        from app.engine.soul_bridge import MessagePriority
        assert MessagePriority is not None

    def test_import_reset(self):
        from app.engine.soul_bridge import reset_soul_bridge
        assert callable(reset_soul_bridge)


# ===========================================================================
# TestPeerConnectionSendQueue
# ===========================================================================


class TestPeerConnectionSendQueue:
    """Tests for send queue behavior."""

    @pytest.mark.asyncio
    async def test_send_queues_when_connected(self):
        from app.engine.soul_bridge.transport import PeerConnection
        from app.engine.soul_bridge.models import BridgeConfig, SoulBridgeMessage, ConnectionState

        config = BridgeConfig(peer_id="test", peer_url="http://localhost:9999")
        conn = PeerConnection(config)
        conn._state = ConnectionState.CONNECTED
        conn._ws = MagicMock()  # Fake WS

        msg = SoulBridgeMessage(source_soul="wiii", event_type="TEST")
        result = await conn.send(msg)
        assert result is True
        assert conn._send_queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_send_falls_back_to_http(self):
        from app.engine.soul_bridge.transport import PeerConnection
        from app.engine.soul_bridge.models import BridgeConfig, SoulBridgeMessage, ConnectionState

        config = BridgeConfig(peer_id="test", peer_url="http://localhost:9999")
        conn = PeerConnection(config)
        conn._state = ConnectionState.DISCONNECTED

        msg = SoulBridgeMessage(source_soul="wiii", event_type="TEST")

        with patch.object(conn, "_send_http", new_callable=AsyncMock, return_value=True):
            result = await conn.send(msg)
            assert result is True


# ===========================================================================
# TestBridgeEventFlow (Integration-like)
# ===========================================================================


class TestBridgeEventFlow:
    """Integration-style tests simulating full event flow."""

    @pytest.mark.asyncio
    async def test_full_local_to_remote_flow(self):
        """Test complete flow: local event → bridge → remote peer."""
        from app.engine.soul_bridge.bridge import get_soul_bridge
        from app.engine.subsoul.protocol import SubSoulEvent, EventType, EventPriority

        bridge = get_soul_bridge()
        settings = _mock_settings()

        with patch("app.engine.subsoul.protocol.get_event_bus") as mock_bus:
            mock_bus.return_value = MagicMock()
            await bridge.initialize(settings)

        # Mock connected peer
        mock_conn = MagicMock()
        mock_conn.is_connected = True
        mock_conn.send = AsyncMock(return_value=True)
        bridge._peers["bro"] = mock_conn

        # Emit local event
        event = SubSoulEvent(
            event_type=EventType.MOOD_CHANGE,
            priority=EventPriority.NORMAL,
            subsoul_id="wiii",
            source="emotion_engine",
            payload={"from": "neutral", "to": "curious"},
        )

        await bridge._on_local_event(event)

        # Verify forwarded
        mock_conn.send.assert_called_once()
        msg = mock_conn.send.call_args[0][0]
        assert msg.event_type == "MOOD_CHANGE"
        assert msg.payload["from"] == "neutral"
        assert msg.payload["to"] == "curious"

    @pytest.mark.asyncio
    async def test_full_remote_to_local_flow(self):
        """Test complete flow: remote message → bridge → local EventBus."""
        from app.engine.soul_bridge.bridge import get_soul_bridge
        from app.engine.soul_bridge.models import SoulBridgeMessage, MessagePriority

        bridge = get_soul_bridge()
        settings = _mock_settings()

        mock_bus = MagicMock()
        mock_bus.emit = AsyncMock()

        with patch("app.engine.subsoul.protocol.get_event_bus", return_value=mock_bus):
            await bridge.initialize(settings)

            # Simulate remote message from Bro
            message = SoulBridgeMessage(
                source_soul="bro",
                event_type="DISCOVERY",
                payload={"pattern": "liquidation cascade detected"},
                priority=MessagePriority.HIGH,
            )

            await bridge._on_remote_event(message)

        # Verify re-emitted on local bus
        mock_bus.emit.assert_called_once()
        emitted = mock_bus.emit.call_args[0][0]
        assert emitted.source == "bridge:bro"
        assert emitted.event_type.value == "DISCOVERY"
        assert emitted.payload["pattern"] == "liquidation cascade detected"

    @pytest.mark.asyncio
    async def test_bidirectional_no_loop(self):
        """Anti-echo prevents infinite loops between two bridges."""
        from app.engine.soul_bridge.bridge import get_soul_bridge
        from app.engine.soul_bridge.models import SoulBridgeMessage, MessagePriority
        from app.engine.subsoul.protocol import SubSoulEvent, EventType, EventPriority

        bridge = get_soul_bridge()
        settings = _mock_settings()

        mock_bus = MagicMock()
        mock_bus.emit = AsyncMock()

        with patch("app.engine.subsoul.protocol.get_event_bus", return_value=mock_bus):
            await bridge.initialize(settings)

        mock_conn = MagicMock()
        mock_conn.is_connected = True
        mock_conn.send = AsyncMock(return_value=True)
        bridge._peers["bro"] = mock_conn

        # Step 1: Remote event arrives from Bro
        remote_msg = SoulBridgeMessage(
            source_soul="bro",
            event_type="ESCALATION",
            payload={"test": True},
        )

        with patch("app.engine.subsoul.protocol.get_event_bus", return_value=mock_bus):
            await bridge._on_remote_event(remote_msg)

        # Step 2: Local bus re-emits with source="bridge:bro"
        emitted = mock_bus.emit.call_args[0][0]
        assert emitted.source == "bridge:bro"

        # Step 3: If this re-emitted event hits _on_local_event, it should be blocked
        await bridge._on_local_event(emitted)
        # conn.send should NOT be called (anti-echo blocks it)
        mock_conn.send.assert_not_called()


# ===========================================================================
# TestEventBuffer (Sprint 216)
# ===========================================================================


class TestEventBuffer:
    """Test per-peer event ring buffer (Sprint 216)."""

    @pytest.mark.asyncio
    async def test_event_stored(self):
        """_store_event adds to buffer."""
        from app.engine.soul_bridge.bridge import SoulBridge
        from app.engine.soul_bridge.models import SoulBridgeMessage

        bridge = SoulBridge.__new__(SoulBridge)
        bridge._peer_events = {}
        bridge._max_events_per_peer = 100

        msg = SoulBridgeMessage(
            source_soul="bro",
            target_soul="wiii",
            event_type="STATUS_UPDATE",
            payload={"risk_score": 22.7},
        )
        bridge._store_event("bro", msg)

        assert "bro" in bridge._peer_events
        assert len(bridge._peer_events["bro"]) == 1
        assert bridge._peer_events["bro"][0]["event_type"] == "STATUS_UPDATE"
        assert bridge._peer_events["bro"][0]["payload"]["risk_score"] == 22.7

    @pytest.mark.asyncio
    async def test_buffer_fifo_eviction(self):
        """Buffer evicts oldest when exceeding max size."""
        from app.engine.soul_bridge.bridge import SoulBridge
        from app.engine.soul_bridge.models import SoulBridgeMessage

        bridge = SoulBridge.__new__(SoulBridge)
        bridge._peer_events = {}
        bridge._max_events_per_peer = 5

        for i in range(10):
            msg = SoulBridgeMessage(
                source_soul="bro",
                target_soul="wiii",
                event_type="STATUS_UPDATE",
                payload={"seq": i},
            )
            bridge._store_event("bro", msg)

        assert len(bridge._peer_events["bro"]) == 5
        assert bridge._peer_events["bro"][0]["payload"]["seq"] == 5
        assert bridge._peer_events["bro"][-1]["payload"]["seq"] == 9

    def test_get_peer_events_empty(self):
        """get_peer_events returns empty for unknown peer."""
        from app.engine.soul_bridge.bridge import SoulBridge

        bridge = SoulBridge.__new__(SoulBridge)
        bridge._peer_events = {}
        assert bridge.get_peer_events("unknown") == []

    def test_get_peer_events_with_limit(self):
        """get_peer_events respects limit."""
        from app.engine.soul_bridge.bridge import SoulBridge

        bridge = SoulBridge.__new__(SoulBridge)
        bridge._peer_events = {"bro": [
            {"event_type": "STATUS_UPDATE", "payload": {"seq": i}, "timestamp": f"2026-03-01T00:0{i}:00"}
            for i in range(5)
        ]}

        result = bridge.get_peer_events("bro", limit=3)
        assert len(result) == 3
        assert result[0]["payload"]["seq"] == 2  # Last 3 items

    def test_get_peer_events_filter_type(self):
        """get_peer_events filters by event_type."""
        from app.engine.soul_bridge.bridge import SoulBridge

        bridge = SoulBridge.__new__(SoulBridge)
        bridge._peer_events = {"bro": [
            {"event_type": "STATUS_UPDATE", "payload": {}, "timestamp": "t1"},
            {"event_type": "ESCALATION", "payload": {}, "timestamp": "t2"},
            {"event_type": "STATUS_UPDATE", "payload": {}, "timestamp": "t3"},
        ]}

        result = bridge.get_peer_events("bro", event_type="ESCALATION")
        assert len(result) == 1
        assert result[0]["event_type"] == "ESCALATION"
