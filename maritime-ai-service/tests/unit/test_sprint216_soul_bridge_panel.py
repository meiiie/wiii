"""Sprint 216 — SoulBridgePanel backend API tests."""
import pytest
from unittest.mock import MagicMock, patch


def _mock_bridge_with_events():
    """Create a mock SoulBridge with events."""
    bridge = MagicMock()
    bridge.get_peer_events.return_value = [
        {
            "id": "evt-1",
            "event_type": "STATUS_UPDATE",
            "payload": {"risk_score": 22.7, "mood": "ALERT"},
            "priority": "NORMAL",
            "timestamp": "2026-03-01T10:00:00",
            "source_soul": "bro",
        },
        {
            "id": "evt-2",
            "event_type": "ESCALATION",
            "payload": {"type": "LIQUIDATION_WARNING", "severity": "CRITICAL"},
            "priority": "CRITICAL",
            "timestamp": "2026-03-01T10:01:00",
            "source_soul": "bro",
        },
    ]
    return bridge


def _mock_bridge_with_peer():
    """Create a mock SoulBridge with a connected peer."""
    bridge = _mock_bridge_with_events()

    mock_card = MagicMock()
    mock_card.name = "Bro"
    mock_card.description = "SubSoul — Trading Risk Guardian"
    mock_card.capabilities = ["risk_assessment", "news_intelligence"]
    mock_card.supported_events = ["STATUS_UPDATE", "ESCALATION", "MOOD_CHANGE"]
    mock_card.soul_id = "bro"

    mock_conn = MagicMock()
    mock_conn.state.value = "CONNECTED"

    bridge._peers = {"bro": mock_conn}
    bridge.get_peer_card.return_value = mock_card
    return bridge


class TestGetPeerEvents:
    """GET /api/v1/soul-bridge/peers/{peer_id}/events"""

    @pytest.mark.asyncio
    async def test_returns_events(self):
        from app.api.v1.soul_bridge import get_peer_events

        bridge = _mock_bridge_with_events()
        with patch("app.api.v1.soul_bridge._get_bridge", return_value=bridge):
            result = await get_peer_events("bro", limit=50, event_type=None)

        assert result["peer_id"] == "bro"
        assert result["count"] == 2
        assert len(result["events"]) == 2
        bridge.get_peer_events.assert_called_once_with("bro", event_type=None, limit=50)

    @pytest.mark.asyncio
    async def test_filters_by_event_type(self):
        from app.api.v1.soul_bridge import get_peer_events

        bridge = MagicMock()
        bridge.get_peer_events.return_value = []
        with patch("app.api.v1.soul_bridge._get_bridge", return_value=bridge):
            result = await get_peer_events("bro", limit=10, event_type="ESCALATION")

        bridge.get_peer_events.assert_called_once_with("bro", event_type="ESCALATION", limit=10)
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_empty_events(self):
        from app.api.v1.soul_bridge import get_peer_events

        bridge = MagicMock()
        bridge.get_peer_events.return_value = []
        with patch("app.api.v1.soul_bridge._get_bridge", return_value=bridge):
            result = await get_peer_events("unknown_peer", limit=50, event_type=None)

        assert result["events"] == []
        assert result["count"] == 0


class TestGetPeerDetail:
    """GET /api/v1/soul-bridge/peers/{peer_id}/detail"""

    @pytest.mark.asyncio
    async def test_returns_full_detail(self):
        from app.api.v1.soul_bridge import get_peer_detail

        bridge = _mock_bridge_with_peer()
        with patch("app.api.v1.soul_bridge._get_bridge", return_value=bridge):
            result = await get_peer_detail("bro")

        assert result["peer_id"] == "bro"
        assert result["state"] == "CONNECTED"
        assert result["card"]["name"] == "Bro"
        assert result["card"]["description"] == "SubSoul — Trading Risk Guardian"
        assert "risk_assessment" in result["card"]["capabilities"]
        assert len(result["recent_events"]) == 2
        # latest_status should be the STATUS_UPDATE payload
        assert result["latest_status"]["risk_score"] == 22.7

    @pytest.mark.asyncio
    async def test_unknown_peer_404(self):
        from app.api.v1.soul_bridge import get_peer_detail
        from fastapi import HTTPException

        bridge = MagicMock()
        bridge._peers = {}
        with patch("app.api.v1.soul_bridge._get_bridge", return_value=bridge):
            with pytest.raises(HTTPException) as exc_info:
                await get_peer_detail("nonexistent")
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_peer_without_card(self):
        from app.api.v1.soul_bridge import get_peer_detail

        bridge = MagicMock()
        mock_conn = MagicMock()
        mock_conn.state.value = "CONNECTING"
        bridge._peers = {"bro": mock_conn}
        bridge.get_peer_card.return_value = None
        bridge.get_peer_events.return_value = []

        with patch("app.api.v1.soul_bridge._get_bridge", return_value=bridge):
            result = await get_peer_detail("bro")

        assert result["card"] is None
        assert result["state"] == "CONNECTING"
        assert result["latest_status"] is None

    @pytest.mark.asyncio
    async def test_latest_status_from_events(self):
        """latest_status extracts from the most recent STATUS_UPDATE event."""
        from app.api.v1.soul_bridge import get_peer_detail

        bridge = MagicMock()
        mock_conn = MagicMock()
        mock_conn.state.value = "CONNECTED"
        bridge._peers = {"bro": mock_conn}
        bridge.get_peer_card.return_value = None
        bridge.get_peer_events.return_value = [
            {"event_type": "ESCALATION", "payload": {"alert": True}, "timestamp": "t1"},
            {"event_type": "STATUS_UPDATE", "payload": {"mood": "CALM", "risk_score": 5}, "timestamp": "t2"},
            {"event_type": "MOOD_CHANGE", "payload": {"from": "CALM", "to": "ALERT"}, "timestamp": "t3"},
        ]

        with patch("app.api.v1.soul_bridge._get_bridge", return_value=bridge):
            result = await get_peer_detail("bro")

        # Should pick the STATUS_UPDATE (t2), not ESCALATION or MOOD_CHANGE
        assert result["latest_status"]["mood"] == "CALM"
        assert result["latest_status"]["risk_score"] == 5
