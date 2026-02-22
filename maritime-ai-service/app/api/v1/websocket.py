"""
WebSocket Chat Endpoint — Real-time bidirectional messaging for Wiii.

Provides WebSocket connections at /api/v1/ws/{session_id} for real-time
chat. Supports JSON message protocol with typing indicators and heartbeat.

Sprint 12: Multi-Channel Gateway.
"""

import logging
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.channels.base import to_chat_request
from app.channels.websocket_adapter import WebSocketAdapter

logger = logging.getLogger(__name__)

router = APIRouter()

# WebSocket adapter singleton
_ws_adapter = WebSocketAdapter()


class ConnectionManager:
    """
    Manages active WebSocket connections.

    Tracks connections by session_id and user_id for targeted messaging
    and ensures clean disconnect handling.

    Sprint 20: Added user_id tracking for proactive notifications.
    Sprint 171b: Added organization_id tracking for multi-tenant isolation.
    """

    def __init__(self):
        self._connections: Dict[str, WebSocket] = {}       # session_id → ws
        self._user_sessions: Dict[str, Set[str]] = {}      # user_id → {session_ids}
        self._session_users: Dict[str, str] = {}            # session_id → user_id
        self._session_orgs: Dict[str, str] = {}             # session_id → org_id

    async def connect(self, websocket: WebSocket, session_id: str) -> None:
        """Accept a WebSocket connection and register it."""
        await websocket.accept()
        self._connections[session_id] = websocket
        logger.info("[WS] Connected: session=%s", session_id)

    def register_user(
        self, session_id: str, user_id: str, organization_id: str = ""
    ) -> None:
        """Link a session to a user_id and optional org_id."""
        self._session_users[session_id] = user_id
        if organization_id:
            self._session_orgs[session_id] = organization_id
        if user_id not in self._user_sessions:
            self._user_sessions[user_id] = set()
        self._user_sessions[user_id].add(session_id)
        logger.debug(
            "[WS] Registered user=%s org=%s on session=%s",
            user_id, organization_id or "(none)", session_id,
        )

    def disconnect(self, session_id: str) -> None:
        """Remove a WebSocket connection and clean up user/org mapping."""
        self._connections.pop(session_id, None)
        self._session_orgs.pop(session_id, None)
        user_id = self._session_users.pop(session_id, None)
        if user_id and user_id in self._user_sessions:
            self._user_sessions[user_id].discard(session_id)
            if not self._user_sessions[user_id]:
                del self._user_sessions[user_id]
        logger.info("[WS] Disconnected: session=%s", session_id)

    async def send_json(self, session_id: str, data: str) -> None:
        """Send a JSON string to a specific session."""
        ws = self._connections.get(session_id)
        if ws:
            await ws.send_text(data)

    async def send_to_user(
        self, user_id: str, data: str, organization_id: str = ""
    ) -> int:
        """
        Send a message to sessions belonging to a user.

        When organization_id is provided, only sends to sessions in that org
        (prevents cross-org message leakage in multi-tenant mode).

        Returns the number of sessions the message was sent to.
        """
        session_ids = self._user_sessions.get(user_id, set())
        sent = 0
        for sid in list(session_ids):
            # Filter by org if specified
            if organization_id and self._session_orgs.get(sid) != organization_id:
                continue
            ws = self._connections.get(sid)
            if ws:
                try:
                    await ws.send_text(data)
                    sent += 1
                except Exception as e:
                    logger.warning("[WS] Failed to send to session=%s: %s", sid, e)
        return sent

    def is_user_online(self, user_id: str) -> bool:
        """Check if a user has any active WebSocket connections."""
        session_ids = self._user_sessions.get(user_id, set())
        return any(sid in self._connections for sid in session_ids)

    @property
    def active_connections(self) -> int:
        return len(self._connections)

    def get_sessions(self) -> list:
        return list(self._connections.keys())

    def get_user_sessions(self, user_id: str) -> Set[str]:
        """Get all session_ids for a user."""
        return self._user_sessions.get(user_id, set()).copy()

    def get_session_org(self, session_id: str) -> str:
        """Get organization_id for a session."""
        return self._session_orgs.get(session_id, "")


# Global connection manager
manager = ConnectionManager()


@router.websocket("/ws/{session_id}")
async def websocket_chat(
    websocket: WebSocket,
    session_id: str,
    api_key: str = Query(default=None, alias="api_key"),
    organization_id: str = Query(default="", alias="org_id"),
):
    """
    WebSocket endpoint for real-time chat.

    Protocol:
    - Client sends: {"type": "message", "content": "question", "sender_id": "user-123"}
    - Server responds: {"type": "response", "content": "answer", "sources": [...]}
    - Heartbeat: Client sends {"type": "ping"}, server responds {"type": "pong"}
    - Typing: Server sends {"type": "typing", "content": true/false}

    Auth: Pass api_key as query parameter: /ws/{session_id}?api_key=xxx
    """
    # Authenticate — reject invalid API keys (fail-closed)
    if api_key:
        try:
            from app.core.config import settings
            import hmac
            if settings.api_key and not hmac.compare_digest(api_key, settings.api_key):
                await websocket.close(code=4001, reason="Invalid API key")
                return
        except Exception as e:
            logger.error("[WS] Auth module error: %s", e)
            await websocket.close(code=4003, reason="Authentication error")
            return
    elif not api_key:
        # No API key provided — check if auth is required in production
        try:
            from app.core.config import settings
            if settings.api_key and not settings.debug:
                await websocket.close(code=4001, reason="API key required")
                return
        except Exception:
            pass  # Allow connection if config unavailable (dev mode)

    await manager.connect(websocket, session_id)

    try:
        while True:
            # Receive message
            raw_data = await websocket.receive_text()

            try:
                channel_msg = _ws_adapter.parse_incoming(raw_data)
            except ValueError as e:
                await websocket.send_text(
                    _ws_adapter.format_error(f"Invalid message: {e}")
                )
                continue

            # Register user_id from sender_id (first message auto-links)
            # Also pick up org_id from message metadata (overrides query param)
            msg_org_id = channel_msg.metadata.get("organization_id", "") or organization_id
            if channel_msg.sender_id:
                manager.register_user(session_id, channel_msg.sender_id, msg_org_id)

            # Handle ping/pong heartbeat
            if channel_msg.metadata.get("ws_message_type") == "ping":
                await websocket.send_text(_ws_adapter.format_pong())
                continue

            # Handle typing indicator (client-side, just acknowledge)
            if channel_msg.metadata.get("ws_message_type") == "typing":
                continue

            # Process message through the pipeline
            try:
                # Send typing indicator
                await websocket.send_text(_ws_adapter.format_typing(True))

                # Set org context ContextVar for downstream filtering
                if msg_org_id:
                    try:
                        from app.core.org_context import current_org_id
                        current_org_id.set(msg_org_id)
                    except Exception:
                        pass  # org_context not available

                # Convert to ChatRequest
                chat_request = to_chat_request(channel_msg)
                # Override session_id from URL
                chat_request.session_id = session_id
                # Pass organization_id if available
                if msg_org_id:
                    chat_request.organization_id = msg_org_id

                # Process via ChatOrchestrator
                from app.services.chat_orchestrator import ChatOrchestrator
                orchestrator = ChatOrchestrator()
                result = await orchestrator.process(chat_request)

                # Format and send response
                response_data = {
                    "answer": result.get("answer", result.get("response", "")),
                    "sources": result.get("sources", []),
                    "metadata": result.get("metadata", {}),
                }
                await websocket.send_text(_ws_adapter.format_outgoing(response_data))

            except Exception as e:
                logger.error("[WS] Error processing message: %s", e, exc_info=True)
                await websocket.send_text(
                    _ws_adapter.format_error("Internal processing error")
                )
            finally:
                # Stop typing indicator
                await websocket.send_text(_ws_adapter.format_typing(False))

    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        logger.error("[WS] Unexpected error: %s", e, exc_info=True)
        manager.disconnect(session_id)
