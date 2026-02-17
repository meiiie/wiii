"""
Tests for ConnectionManager user_id tracking — Sprint 20.

Verifies:
- register_user creates user→session mapping
- send_to_user broadcasts to all user sessions
- disconnect cleans up user mapping
- is_user_online returns correct status
- Multiple sessions per user
- Backward compatibility (session_id-only methods still work)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.api.v1.websocket import ConnectionManager


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def manager():
    """Fresh ConnectionManager instance."""
    return ConnectionManager()


def _make_ws(accepted: bool = True) -> AsyncMock:
    """Create a mock WebSocket."""
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    return ws


# =============================================================================
# register_user
# =============================================================================

class TestRegisterUser:

    def test_register_creates_mapping(self, manager):
        """register_user links session to user."""
        manager._connections["session-1"] = _make_ws()
        manager.register_user("session-1", "user-A")

        assert "user-A" in manager._user_sessions
        assert "session-1" in manager._user_sessions["user-A"]
        assert manager._session_users["session-1"] == "user-A"

    def test_register_multiple_sessions(self, manager):
        """Same user can have multiple sessions."""
        manager._connections["s1"] = _make_ws()
        manager._connections["s2"] = _make_ws()

        manager.register_user("s1", "user-A")
        manager.register_user("s2", "user-A")

        assert len(manager._user_sessions["user-A"]) == 2
        assert "s1" in manager._user_sessions["user-A"]
        assert "s2" in manager._user_sessions["user-A"]

    def test_register_different_users(self, manager):
        """Different users get separate mappings."""
        manager._connections["s1"] = _make_ws()
        manager._connections["s2"] = _make_ws()

        manager.register_user("s1", "user-A")
        manager.register_user("s2", "user-B")

        assert len(manager._user_sessions) == 2
        assert "s1" in manager._user_sessions["user-A"]
        assert "s2" in manager._user_sessions["user-B"]

    def test_register_idempotent(self, manager):
        """Registering same session+user again doesn't duplicate."""
        manager._connections["s1"] = _make_ws()
        manager.register_user("s1", "user-A")
        manager.register_user("s1", "user-A")

        assert len(manager._user_sessions["user-A"]) == 1


# =============================================================================
# disconnect
# =============================================================================

class TestDisconnect:

    def test_disconnect_cleans_user_mapping(self, manager):
        """Disconnect removes session from user mapping."""
        ws = _make_ws()
        manager._connections["s1"] = ws
        manager.register_user("s1", "user-A")

        manager.disconnect("s1")

        assert "s1" not in manager._connections
        assert "s1" not in manager._session_users
        assert "user-A" not in manager._user_sessions  # no sessions left → removed

    def test_disconnect_partial_user_sessions(self, manager):
        """Disconnect one session; user still has another."""
        manager._connections["s1"] = _make_ws()
        manager._connections["s2"] = _make_ws()
        manager.register_user("s1", "user-A")
        manager.register_user("s2", "user-A")

        manager.disconnect("s1")

        assert "user-A" in manager._user_sessions
        assert "s2" in manager._user_sessions["user-A"]
        assert "s1" not in manager._user_sessions["user-A"]

    def test_disconnect_without_user(self, manager):
        """Disconnect a session that was never registered to a user."""
        manager._connections["s1"] = _make_ws()
        manager.disconnect("s1")

        assert "s1" not in manager._connections


# =============================================================================
# is_user_online
# =============================================================================

class TestIsUserOnline:

    def test_online_when_connected(self, manager):
        """User is online when they have an active connection."""
        manager._connections["s1"] = _make_ws()
        manager.register_user("s1", "user-A")

        assert manager.is_user_online("user-A") is True

    def test_offline_when_disconnected(self, manager):
        """User is offline after all sessions disconnected."""
        manager._connections["s1"] = _make_ws()
        manager.register_user("s1", "user-A")
        manager.disconnect("s1")

        assert manager.is_user_online("user-A") is False

    def test_offline_unknown_user(self, manager):
        """Unknown user is reported as offline."""
        assert manager.is_user_online("ghost") is False


# =============================================================================
# send_to_user
# =============================================================================

class TestSendToUser:

    @pytest.mark.asyncio
    async def test_send_to_single_session(self, manager):
        """Send to user with one session."""
        ws = _make_ws()
        manager._connections["s1"] = ws
        manager.register_user("s1", "user-A")

        sent = await manager.send_to_user("user-A", '{"msg": "hi"}')

        assert sent == 1
        ws.send_text.assert_called_once_with('{"msg": "hi"}')

    @pytest.mark.asyncio
    async def test_send_to_multiple_sessions(self, manager):
        """Send to user with multiple sessions."""
        ws1 = _make_ws()
        ws2 = _make_ws()
        manager._connections["s1"] = ws1
        manager._connections["s2"] = ws2
        manager.register_user("s1", "user-A")
        manager.register_user("s2", "user-A")

        sent = await manager.send_to_user("user-A", "hello")

        assert sent == 2
        ws1.send_text.assert_called_once_with("hello")
        ws2.send_text.assert_called_once_with("hello")

    @pytest.mark.asyncio
    async def test_send_to_offline_user(self, manager):
        """Sending to offline user returns 0 sent."""
        sent = await manager.send_to_user("ghost", "hello")
        assert sent == 0

    @pytest.mark.asyncio
    async def test_send_handles_broken_connection(self, manager):
        """Broken connection doesn't crash, just skips."""
        ws = _make_ws()
        ws.send_text.side_effect = RuntimeError("Connection closed")
        manager._connections["s1"] = ws
        manager.register_user("s1", "user-A")

        sent = await manager.send_to_user("user-A", "test")

        assert sent == 0  # Failed, but didn't crash


# =============================================================================
# get_user_sessions
# =============================================================================

class TestGetUserSessions:

    def test_get_sessions_for_user(self, manager):
        """Returns copy of user's session set."""
        manager._connections["s1"] = _make_ws()
        manager._connections["s2"] = _make_ws()
        manager.register_user("s1", "user-A")
        manager.register_user("s2", "user-A")

        sessions = manager.get_user_sessions("user-A")
        assert sessions == {"s1", "s2"}

        # Verify it's a copy (modifying doesn't affect internal state)
        sessions.add("s3")
        assert "s3" not in manager._user_sessions["user-A"]

    def test_get_sessions_unknown_user(self, manager):
        """Unknown user returns empty set."""
        assert manager.get_user_sessions("ghost") == set()


# =============================================================================
# Backward compatibility
# =============================================================================

class TestBackwardCompatibility:

    @pytest.mark.asyncio
    async def test_connect_still_works(self, manager):
        """Original connect() method still works."""
        ws = _make_ws()
        await manager.connect(ws, "session-abc")

        assert manager.active_connections == 1
        assert "session-abc" in manager.get_sessions()
        ws.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_json_still_works(self, manager):
        """Original send_json() method still works."""
        ws = _make_ws()
        manager._connections["s1"] = ws

        await manager.send_json("s1", '{"data": 1}')
        ws.send_text.assert_called_once_with('{"data": 1}')
