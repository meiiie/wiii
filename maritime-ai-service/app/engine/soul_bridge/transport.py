"""
SoulBridge Transport Layer — WebSocket + HTTP fallback for cross-service communication.

Sprint 213: "Cầu Nối Linh Hồn"

Handles:
    - WebSocket connection with exponential backoff reconnect
    - HTTP POST fallback when WebSocket unavailable
    - Heartbeat ping to detect dead peers
    - Priority-based retry for failed sends

Design:
    - Non-blocking: all errors caught, never propagates to caller
    - Exponential backoff: 1s→2s→4s→...→max_delay
    - Heartbeat: periodic ping, marks peer dead on 3 missed pongs
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from urllib.parse import urlparse
from typing import Any, Callable, Coroutine, Dict, List, Optional

from app.core.config import settings
from app.engine.soul_bridge.models import (
    BridgeConfig,
    ConnectionState,
    MessagePriority,
    SoulBridgeMessage,
    get_retry_config,
)

logger = logging.getLogger(__name__)

# Type alias for message handler
MessageHandler = Callable[[SoulBridgeMessage], Coroutine[Any, Any, None]]


class PeerConnection:
    """Manages WebSocket connection to a single peer soul service.

    Lifecycle:
        1. connect() — establish WebSocket, start heartbeat loop
        2. send() — send message via WebSocket (HTTP fallback)
        3. disconnect() — graceful close

    Auto-reconnect on disconnect with exponential backoff.
    """

    def __init__(self, config: BridgeConfig) -> None:
        self.config = config
        self.peer_id = config.peer_id
        self._state = ConnectionState.DISCONNECTED
        self._ws = None  # WebSocket connection (aiohttp or websockets)
        self._handlers: List[MessageHandler] = []
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._receive_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        self._reconnect_count = 0
        self._last_pong: float = 0.0
        self._missed_pongs = 0
        self._send_queue: asyncio.Queue[SoulBridgeMessage] = asyncio.Queue(maxsize=1000)
        self._send_task: Optional[asyncio.Task] = None

    @property
    def state(self) -> ConnectionState:
        return self._state

    @property
    def is_connected(self) -> bool:
        return self._state == ConnectionState.CONNECTED

    def on_message(self, handler: MessageHandler) -> None:
        """Register a handler for incoming messages."""
        self._handlers.append(handler)

    def _ensure_reconnect_loop(self) -> None:
        """Start a single reconnect loop if one is not already running."""
        if self._shutdown_event.is_set():
            return
        if self._reconnect_task and not self._reconnect_task.done():
            return
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    def _should_soften_connect_warning(self) -> bool:
        """Reduce noise for expected local-dev peer failures."""
        if settings.environment != "development":
            return False

        hostname = (urlparse(self.config.peer_url).hostname or "").lower()
        return hostname in {"localhost", "127.0.0.1", "host.docker.internal"}

    async def connect(self, schedule_reconnect: bool = True) -> bool:
        """Establish WebSocket connection to peer.

        Returns:
            True if connection established, False otherwise.
        """
        if self._state in (ConnectionState.CONNECTED, ConnectionState.CONNECTING):
            return self._state == ConnectionState.CONNECTED

        self._state = ConnectionState.CONNECTING
        self._shutdown_event.clear()
        base = self.config.peer_url.rstrip("/")
        # Convert http(s):// → ws(s):// for WebSocket connection
        if base.startswith("https://"):
            base = "wss://" + base[len("https://"):]
        elif base.startswith("http://"):
            base = "ws://" + base[len("http://"):]
        ws_url = f"{base}{self.config.ws_path}"

        try:
            import websockets
            self._ws = await asyncio.wait_for(
                websockets.connect(ws_url),
                timeout=10.0,
            )
            self._state = ConnectionState.CONNECTED
            self._reconnect_count = 0
            self._last_pong = time.monotonic()
            self._missed_pongs = 0

            # Start background tasks
            self._receive_task = asyncio.create_task(self._receive_loop())
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            self._send_task = asyncio.create_task(self._send_loop())

            logger.info("[SOUL_BRIDGE] Connected to peer '%s' at %s", self.peer_id, ws_url)
            return True

        except ImportError:
            logger.warning("[SOUL_BRIDGE] websockets package not installed — using HTTP-only mode for peer '%s'", self.peer_id)
            self._state = ConnectionState.DISCONNECTED
            return False
        except Exception as e:
            if schedule_reconnect:
                log_method = logger.info if self._should_soften_connect_warning() else logger.warning
                log_method("[SOUL_BRIDGE] Connect to peer '%s' failed: %s", self.peer_id, e)
            else:
                logger.debug("[SOUL_BRIDGE] Reconnect to peer '%s' failed: %s", self.peer_id, e)
            self._state = ConnectionState.DISCONNECTED
            if schedule_reconnect:
                self._ensure_reconnect_loop()
            return False

    async def disconnect(self) -> None:
        """Gracefully close the connection."""
        self._shutdown_event.set()

        # Cancel background tasks
        for task in [self._receive_task, self._heartbeat_task, self._send_task, self._reconnect_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await asyncio.wait_for(task, timeout=5.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass

        # Close WebSocket
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

        self._state = ConnectionState.DISCONNECTED
        logger.info("[SOUL_BRIDGE] Disconnected from peer '%s'", self.peer_id)

    async def send(self, message: SoulBridgeMessage) -> bool:
        """Send a message to the peer.

        Tries WebSocket first, falls back to HTTP POST.

        Returns:
            True if message queued/sent, False on failure.
        """
        if self._state == ConnectionState.CONNECTED and self._ws:
            try:
                self._send_queue.put_nowait(message)
                return True
            except asyncio.QueueFull:
                logger.warning("[SOUL_BRIDGE] Send queue full for peer '%s'", self.peer_id)

        # HTTP fallback
        return await self._send_http(message)

    async def _send_ws(self, message: SoulBridgeMessage) -> bool:
        """Send via WebSocket."""
        if not self._ws:
            return False
        try:
            data = json.dumps(message.to_json_dict(), ensure_ascii=False)
            await self._ws.send(data)
            return True
        except Exception as e:
            logger.warning("[SOUL_BRIDGE] WS send to '%s' failed: %s", self.peer_id, e)
            return False

    async def _send_http(self, message: SoulBridgeMessage) -> bool:
        """Send via HTTP POST fallback."""
        url = f"{self.config.peer_url.rstrip('/')}/api/v1/soul-bridge/events"
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=message.to_json_dict())
                if resp.status_code < 300:
                    return True
                logger.warning("[SOUL_BRIDGE] HTTP fallback to '%s' returned %d", self.peer_id, resp.status_code)
        except ImportError:
            logger.debug("[SOUL_BRIDGE] httpx not available for HTTP fallback")
        except Exception as e:
            logger.warning("[SOUL_BRIDGE] HTTP fallback to '%s' failed: %s", self.peer_id, e)
        return False

    async def _send_loop(self) -> None:
        """Background task: drain send queue via WebSocket."""
        while not self._shutdown_event.is_set():
            try:
                message = await asyncio.wait_for(self._send_queue.get(), timeout=1.0)
                success = await self._send_ws(message)
                if not success:
                    # Try HTTP fallback
                    await self._send_http(message)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug("[SOUL_BRIDGE] Send loop error: %s", e)

    async def _receive_loop(self) -> None:
        """Background task: receive messages from WebSocket."""
        while not self._shutdown_event.is_set() and self._ws:
            try:
                raw = await asyncio.wait_for(self._ws.recv(), timeout=self.config.heartbeat_interval * 2)

                # Handle pong
                if raw == "pong":
                    self._last_pong = time.monotonic()
                    self._missed_pongs = 0
                    continue

                # Parse message
                data = json.loads(raw)
                message = SoulBridgeMessage.from_json_dict(data)

                # Dispatch to handlers
                for handler in self._handlers:
                    try:
                        await handler(message)
                    except Exception as e:
                        logger.error("[SOUL_BRIDGE] Handler error for peer '%s': %s", self.peer_id, e)

            except asyncio.TimeoutError:
                logger.debug("[SOUL_BRIDGE] No message from '%s' (timeout)", self.peer_id)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("[SOUL_BRIDGE] Receive error from '%s': %s", self.peer_id, e)
                break

        # Connection lost — trigger reconnect
        if not self._shutdown_event.is_set():
            self._state = ConnectionState.RECONNECTING
            self._ensure_reconnect_loop()

    async def _heartbeat_loop(self) -> None:
        """Background task: periodic ping to detect dead peers."""
        interval = self.config.heartbeat_interval
        while not self._shutdown_event.is_set():
            try:
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=interval)
                break
            except asyncio.TimeoutError:
                pass

            if self._ws and self._state == ConnectionState.CONNECTED:
                try:
                    await self._ws.send("ping")
                except Exception:
                    self._missed_pongs += 1

                # Check for dead peer (3 missed pongs)
                elapsed = time.monotonic() - self._last_pong
                if elapsed > interval * 3:
                    logger.warning("[SOUL_BRIDGE] Peer '%s' appears dead (no pong for %.0fs)", self.peer_id, elapsed)
                    self._state = ConnectionState.RECONNECTING
                    self._ensure_reconnect_loop()
                    break

    async def _reconnect_loop(self) -> None:
        """Background task: reconnect with exponential backoff."""
        self._state = ConnectionState.RECONNECTING
        max_delay = self.config.reconnect_max
        max_attempts = self.config.max_retry

        while not self._shutdown_event.is_set() and self._reconnect_count < max_attempts:
            delay = min(2 ** self._reconnect_count * self.config.reconnect_interval, max_delay)
            self._reconnect_count += 1

            logger.info(
                "[SOUL_BRIDGE] Reconnecting to '%s' in %ds (attempt %d/%d)",
                self.peer_id, delay, self._reconnect_count, max_attempts,
            )

            try:
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=delay)
                break  # Shutdown
            except asyncio.TimeoutError:
                pass

            # Clean up old connection
            if self._ws:
                try:
                    await self._ws.close()
                except Exception:
                    pass
                self._ws = None

            # Attempt reconnect
            connected = await self.connect(schedule_reconnect=False)
            if connected:
                return

        if self._reconnect_count >= max_attempts:
            logger.warning("[SOUL_BRIDGE] Max reconnect attempts reached for '%s'", self.peer_id)
            self._state = ConnectionState.DISCONNECTED
