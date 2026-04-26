"""
Sprint 215: "Hỏi Bro" — Cross-Soul Query Routing Tests

Tests:
    - ResponseTracker: create_future, resolve, cancel, timeout, cleanup
    - ask_peer: happy_path, timeout, peer_disconnected, send_fails, not_initialized
    - Consultation reply: reply_routes_to_tracker, consultation_invokes_handler, reply_no_pending
    - ColleagueNode: happy_path, bro_offline, timeout_fallback, non_admin_denied, feature_disabled
    - Supervisor routing: colleague_admin_ok, non_admin_fallback, feature_disabled, bridge_disabled,
                          prompt_includes_role, rule_based_no_colleague
    - Graph wiring: node_exists_when_enabled, node_absent_when_disabled, route_decision_accepts,
                    edge_to_synthesizer
    - Consultation models: request_model, response_model, message_correlation_fields
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

# =====================================================================
# Test Consultation Models
# =====================================================================


class TestConsultationModels:
    """Test ConsultationRequest, ConsultationResponse, and message correlation fields."""

    def test_consultation_request_model(self):
        from app.engine.soul_bridge.models import ConsultationRequest

        req = ConsultationRequest(
            query="BTC situation?",
            user_id="admin-1",
            domain_hint="trading",
            timeout_seconds=10.0,
        )
        assert req.query == "BTC situation?"
        assert req.user_id == "admin-1"
        assert req.domain_hint == "trading"
        assert req.timeout_seconds == 10.0

    def test_consultation_response_model(self):
        from app.engine.soul_bridge.models import ConsultationResponse

        resp = ConsultationResponse(
            response="Market is volatile",
            confidence=0.85,
            sources=["Binance WS"],
            mood="cautious",
        )
        assert resp.response == "Market is volatile"
        assert resp.confidence == 0.85
        assert resp.mood == "cautious"
        assert resp.error == ""

    def test_message_correlation_fields(self):
        from app.engine.soul_bridge.models import SoulBridgeMessage

        msg = SoulBridgeMessage(
            source_soul="wiii",
            target_soul="bro",
            event_type="CONSULTATION",
            request_id="req-123",
        )
        assert msg.request_id == "req-123"
        assert msg.reply_to_id == ""

        # Serialization roundtrip
        data = msg.to_json_dict()
        assert data["request_id"] == "req-123"
        assert "reply_to_id" not in data  # Empty string omitted

        # With reply_to_id
        reply = SoulBridgeMessage(
            source_soul="bro",
            target_soul="wiii",
            event_type="CONSULTATION_REPLY",
            reply_to_id="req-123",
        )
        data2 = reply.to_json_dict()
        assert data2["reply_to_id"] == "req-123"
        assert "request_id" not in data2

        # Deserialize
        parsed = SoulBridgeMessage.from_json_dict(data2)
        assert parsed.reply_to_id == "req-123"
        assert parsed.request_id == ""

    def test_message_correlation_roundtrip(self):
        from app.engine.soul_bridge.models import SoulBridgeMessage

        msg = SoulBridgeMessage(
            source_soul="wiii",
            event_type="CONSULTATION",
            request_id="abc-123",
            reply_to_id="xyz-456",
        )
        data = msg.to_json_dict()
        parsed = SoulBridgeMessage.from_json_dict(data)
        assert parsed.request_id == "abc-123"
        assert parsed.reply_to_id == "xyz-456"


# =====================================================================
# Test ResponseTracker
# =====================================================================


class TestResponseTracker:
    """Test the ResponseTracker class for pending request-response management."""

    @pytest.mark.asyncio
    async def test_create_future(self):
        from app.engine.soul_bridge.response_tracker import ResponseTracker

        tracker = ResponseTracker()
        future = tracker.create_future("req-1")
        assert not future.done()
        assert tracker.pending_count == 1

    @pytest.mark.asyncio
    async def test_resolve(self):
        from app.engine.soul_bridge.response_tracker import ResponseTracker

        tracker = ResponseTracker()
        future = tracker.create_future("req-1")

        resolved = tracker.resolve("req-1", "hello")
        assert resolved is True
        assert future.done()
        assert future.result() == "hello"
        assert tracker.pending_count == 0

    def test_resolve_unknown_returns_false(self):
        from app.engine.soul_bridge.response_tracker import ResponseTracker

        tracker = ResponseTracker()
        resolved = tracker.resolve("nonexistent", "data")
        assert resolved is False

    @pytest.mark.asyncio
    async def test_cancel(self):
        from app.engine.soul_bridge.response_tracker import ResponseTracker

        tracker = ResponseTracker()
        future = tracker.create_future("req-1")

        cancelled = tracker.cancel("req-1")
        assert cancelled is True
        assert future.cancelled()
        assert tracker.pending_count == 0

    def test_cancel_unknown_returns_false(self):
        from app.engine.soul_bridge.response_tracker import ResponseTracker

        tracker = ResponseTracker()
        assert tracker.cancel("nonexistent") is False

    @pytest.mark.asyncio
    async def test_cleanup(self):
        from app.engine.soul_bridge.response_tracker import ResponseTracker

        tracker = ResponseTracker()
        f1 = tracker.create_future("req-1")
        f2 = tracker.create_future("req-2")

        count = tracker.cleanup()
        assert count == 2
        assert f1.cancelled()
        assert f2.cancelled()
        assert tracker.pending_count == 0


# =====================================================================
# Test ask_peer
# =====================================================================


class TestAskPeer:
    """Test SoulBridge.ask_peer() method."""

    @pytest.fixture
    def bridge(self):
        from app.engine.soul_bridge.bridge import SoulBridge
        b = SoulBridge()
        b._initialized = True
        b._soul_id = "wiii"
        return b

    @pytest.mark.asyncio
    async def test_happy_path(self, bridge):
        """ask_peer sends message and resolves when reply arrives."""
        from app.engine.soul_bridge.models import SoulBridgeMessage

        # Mock peer connection
        mock_conn = MagicMock()
        mock_conn.is_connected = True
        mock_conn.send = AsyncMock()
        bridge._peers["bro"] = mock_conn

        # Simulate reply arriving after send
        async def simulate_reply():
            await asyncio.sleep(0.05)
            reply = SoulBridgeMessage(
                source_soul="bro",
                event_type="CONSULTATION_REPLY",
                payload={"response": "Market ok"},
            )
            bridge._response_tracker.resolve(
                list(bridge._response_tracker._pending.keys())[0],
                reply,
            )

        asyncio.ensure_future(simulate_reply())
        result = await bridge.ask_peer("bro", "CONSULTATION", {"query": "BTC?"}, timeout=5.0)

        assert result is not None
        assert result.payload["response"] == "Market ok"
        mock_conn.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_timeout(self, bridge):
        """ask_peer returns None on timeout."""
        mock_conn = MagicMock()
        mock_conn.is_connected = True
        mock_conn.send = AsyncMock()
        bridge._peers["bro"] = mock_conn

        result = await bridge.ask_peer("bro", "CONSULTATION", {"query": "BTC?"}, timeout=0.1)
        assert result is None
        assert bridge._response_tracker.pending_count == 0

    @pytest.mark.asyncio
    async def test_peer_disconnected(self, bridge):
        """ask_peer returns None when peer is not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected = False
        bridge._peers["bro"] = mock_conn

        result = await bridge.ask_peer("bro", "CONSULTATION", {"query": "test"})
        assert result is None

    @pytest.mark.asyncio
    async def test_peer_not_found(self, bridge):
        """ask_peer returns None when peer doesn't exist."""
        result = await bridge.ask_peer("unknown", "CONSULTATION", {"query": "test"})
        assert result is None

    @pytest.mark.asyncio
    async def test_send_fails(self, bridge):
        """ask_peer returns None when send raises."""
        mock_conn = MagicMock()
        mock_conn.is_connected = True
        mock_conn.send = AsyncMock(side_effect=ConnectionError("broken"))
        bridge._peers["bro"] = mock_conn

        result = await bridge.ask_peer("bro", "CONSULTATION", {"query": "test"}, timeout=1.0)
        assert result is None
        assert bridge._response_tracker.pending_count == 0

    @pytest.mark.asyncio
    async def test_not_initialized(self, bridge):
        """ask_peer returns None when bridge not initialized."""
        bridge._initialized = False
        result = await bridge.ask_peer("bro", "CONSULTATION", {"query": "test"})
        assert result is None


# =====================================================================
# Test Consultation Reply Routing
# =====================================================================


class TestConsultationReply:
    """Test that replies route to ResponseTracker and consultations invoke handler."""

    @pytest.fixture
    def bridge(self):
        from app.engine.soul_bridge.bridge import SoulBridge
        b = SoulBridge()
        b._initialized = True
        b._soul_id = "wiii"
        return b

    @pytest.mark.asyncio
    async def test_reply_routes_to_tracker(self, bridge):
        """Incoming message with reply_to_id resolves the pending future."""
        from app.engine.soul_bridge.models import SoulBridgeMessage

        future = bridge._response_tracker.create_future("req-abc")

        reply = SoulBridgeMessage(
            source_soul="bro",
            event_type="CONSULTATION_REPLY",
            payload={"response": "all good"},
            reply_to_id="req-abc",
        )

        await bridge._on_remote_event(reply)

        assert future.done()
        assert future.result().payload["response"] == "all good"

    @pytest.mark.asyncio
    async def test_consultation_invokes_handler(self, bridge):
        """Incoming CONSULTATION triggers the registered handler."""
        from app.engine.soul_bridge.models import SoulBridgeMessage

        handler = AsyncMock(return_value={"response": "handled"})
        bridge.register_consultation_handler(handler)

        # Mock peer for reply
        mock_conn = MagicMock()
        mock_conn.is_connected = True
        mock_conn.send = AsyncMock()
        bridge._peers["bro"] = mock_conn

        msg = SoulBridgeMessage(
            source_soul="bro",
            event_type="CONSULTATION",
            payload={"query": "risk?"},
            request_id="req-xyz",
        )

        await bridge._on_remote_event(msg)
        # Give the ensure_future task a chance to run
        await asyncio.sleep(0.1)

        handler.assert_called_once_with({"query": "risk?"})

    @pytest.mark.asyncio
    async def test_reply_no_pending(self, bridge):
        """Reply with no matching pending future is silently ignored."""
        from app.engine.soul_bridge.models import SoulBridgeMessage

        reply = SoulBridgeMessage(
            source_soul="bro",
            event_type="CONSULTATION_REPLY",
            payload={"response": "orphan"},
            reply_to_id="nonexistent-req",
        )

        # Should not raise
        await bridge._on_remote_event(reply)


# =====================================================================
# Test ColleagueNode
# =====================================================================


class TestColleagueNode:
    """Test the colleague_agent_process function."""

    def _mock_settings(self, **overrides):
        s = MagicMock()
        s.enable_cross_soul_query = overrides.get("enable_cross_soul_query", True)
        s.enable_soul_bridge = overrides.get("enable_soul_bridge", True)
        s.cross_soul_query_peer_id = overrides.get("cross_soul_query_peer_id", "bro")
        s.cross_soul_query_timeout = overrides.get("cross_soul_query_timeout", 5.0)
        return s

    @pytest.mark.asyncio
    async def test_happy_path(self):
        from app.engine.multi_agent.agents.colleague_node import colleague_agent_process
        from app.engine.soul_bridge.models import SoulBridgeMessage

        state = {
            "query": "BTC tình hình sao?",
            "context": {"user_role": "admin"},
            "user_id": "admin-1",
        }

        reply = SoulBridgeMessage(
            source_soul="bro",
            event_type="CONSULTATION_REPLY",
            payload={
                "response": "Thị trường ổn",
                "confidence": 0.8,
                "mood": "calm",
                "sources": ["Binance WS"],
                "error": "",
            },
        )

        mock_bridge = MagicMock()
        mock_bridge.is_initialized = True
        mock_bridge.ask_peer = AsyncMock(return_value=reply)

        with patch("app.core.config.get_settings", return_value=self._mock_settings()):
            with patch("app.engine.soul_bridge.bridge.get_soul_bridge", return_value=mock_bridge):
                result = await colleague_agent_process(state)

        assert "Thị trường ổn" in result["agent_outputs"]["colleague"]
        assert result["current_agent"] == "colleague_agent"
        mock_bridge.ask_peer.assert_called_once()

    @pytest.mark.asyncio
    async def test_bro_offline(self):
        from app.engine.multi_agent.agents.colleague_node import colleague_agent_process

        state = {
            "query": "BTC?",
            "context": {"user_role": "admin"},
            "user_id": "admin-1",
        }

        mock_bridge = MagicMock()
        mock_bridge.is_initialized = True
        mock_bridge.ask_peer = AsyncMock(return_value=None)

        with patch("app.core.config.get_settings", return_value=self._mock_settings()):
            with patch("app.engine.soul_bridge.bridge.get_soul_bridge", return_value=mock_bridge):
                result = await colleague_agent_process(state)

        assert "không thể kết nối" in result["final_response"]

    @pytest.mark.asyncio
    async def test_timeout_fallback(self):
        from app.engine.multi_agent.agents.colleague_node import colleague_agent_process

        state = {
            "query": "Crypto risk?",
            "context": {"user_role": "admin"},
            "user_id": "admin-1",
        }

        mock_bridge = MagicMock()
        mock_bridge.is_initialized = True
        mock_bridge.ask_peer = AsyncMock(return_value=None)

        with patch("app.core.config.get_settings", return_value=self._mock_settings()):
            with patch("app.engine.soul_bridge.bridge.get_soul_bridge", return_value=mock_bridge):
                result = await colleague_agent_process(state)

        assert "colleague" in result["agent_outputs"]
        assert "kết nối" in result["final_response"]

    @pytest.mark.asyncio
    async def test_non_admin_denied(self):
        from app.engine.multi_agent.agents.colleague_node import colleague_agent_process

        state = {
            "query": "BTC?",
            "context": {"user_role": "student"},
            "user_id": "student-1",
        }

        result = await colleague_agent_process(state)
        assert "quản trị viên" in result["final_response"]

    @pytest.mark.asyncio
    async def test_feature_disabled(self):
        from app.engine.multi_agent.agents.colleague_node import colleague_agent_process

        state = {
            "query": "BTC?",
            "context": {"user_role": "admin"},
            "user_id": "admin-1",
        }

        with patch("app.core.config.get_settings",
                    return_value=self._mock_settings(enable_cross_soul_query=False)):
            result = await colleague_agent_process(state)

        assert "chưa được bật" in result["final_response"]


# =====================================================================
# Test Supervisor Routing
# =====================================================================


class TestSupervisorRouting:
    """Test that supervisor correctly routes colleague_consult intent."""

    def _mock_settings(self, **overrides):
        s = MagicMock()
        s.enable_product_search = False
        s.enable_cross_soul_query = overrides.get("enable_cross_soul_query", True)
        s.enable_soul_bridge = overrides.get("enable_soul_bridge", True)
        s.enable_subagent_architecture = False
        s.enable_org_knowledge = False
        s.default_domain = "maritime"
        return s

    @pytest.mark.asyncio
    async def test_colleague_admin_ok(self):
        """Admin user with colleague_consult intent routes to colleague_agent."""
        from app.engine.multi_agent.supervisor import SupervisorAgent, AgentType
        from app.engine.structured_schemas import RoutingDecision

        supervisor = SupervisorAgent.__new__(SupervisorAgent)
        supervisor._llm = MagicMock()

        mock_result = RoutingDecision(
            reasoning="User asks Bro about crypto",
            intent="colleague_consult",
            agent="COLLEAGUE_AGENT",
            confidence=0.95,
        )

        structured_llm = MagicMock()
        structured_llm.ainvoke = AsyncMock(return_value=mock_result)
        supervisor._llm.with_structured_output = MagicMock(return_value=structured_llm)

        state = {
            "query": "Hỏi Bro về BTC",
            "context": {"user_role": "admin"},
            "domain_config": {"domain_name": "AI", "routing_keywords": []},
            "routing_metadata": None,
        }

        with patch("app.engine.multi_agent.supervisor.settings", self._mock_settings()), \
             patch(
                 "app.engine.multi_agent.supervisor.StructuredInvokeService.ainvoke",
                 new=AsyncMock(return_value=mock_result),
             ):
            result = await supervisor._route_structured(
                "Hỏi Bro về BTC", {"user_role": "admin"}, "AI", "", "", {}, state,
            )

        assert result == AgentType.COLLEAGUE.value

    @pytest.mark.asyncio
    async def test_non_admin_fallback(self):
        """Non-admin user with colleague intent falls back to DIRECT."""
        from app.engine.multi_agent.supervisor import SupervisorAgent, AgentType
        from app.engine.structured_schemas import RoutingDecision

        supervisor = SupervisorAgent.__new__(SupervisorAgent)
        supervisor._llm = MagicMock()

        mock_result = RoutingDecision(
            reasoning="User asks Bro",
            intent="colleague_consult",
            agent="COLLEAGUE_AGENT",
            confidence=0.95,
        )

        structured_llm = MagicMock()
        structured_llm.ainvoke = AsyncMock(return_value=mock_result)
        supervisor._llm.with_structured_output = MagicMock(return_value=structured_llm)

        state = {"routing_metadata": None}

        with patch("app.engine.multi_agent.supervisor.settings", self._mock_settings()), \
             patch(
                 "app.engine.multi_agent.supervisor.StructuredInvokeService.ainvoke",
                 new=AsyncMock(return_value=mock_result),
             ):
            result = await supervisor._route_structured(
                "Hỏi Bro về BTC", {"user_role": "student"}, "AI", "", "", {}, state,
            )

        assert result == AgentType.DIRECT.value

    @pytest.mark.asyncio
    async def test_feature_disabled(self):
        """Colleague routing falls back when enable_cross_soul_query=False."""
        from app.engine.multi_agent.supervisor import SupervisorAgent, AgentType
        from app.engine.structured_schemas import RoutingDecision

        supervisor = SupervisorAgent.__new__(SupervisorAgent)
        supervisor._llm = MagicMock()

        mock_result = RoutingDecision(
            reasoning="User asks Bro",
            intent="colleague_consult",
            agent="COLLEAGUE_AGENT",
            confidence=0.95,
        )

        structured_llm = MagicMock()
        structured_llm.ainvoke = AsyncMock(return_value=mock_result)
        supervisor._llm.with_structured_output = MagicMock(return_value=structured_llm)

        state = {"routing_metadata": None}

        with patch("app.engine.multi_agent.supervisor.settings",
                    self._mock_settings(enable_cross_soul_query=False)), \
             patch(
                 "app.engine.multi_agent.supervisor.StructuredInvokeService.ainvoke",
                 new=AsyncMock(return_value=mock_result),
             ):
            result = await supervisor._route_structured(
                "Hỏi Bro về BTC", {"user_role": "admin"}, "AI", "", "", {}, state,
            )

        assert result == AgentType.DIRECT.value

    @pytest.mark.asyncio
    async def test_bridge_disabled(self):
        """Colleague routing falls back when enable_soul_bridge=False."""
        from app.engine.multi_agent.supervisor import SupervisorAgent, AgentType
        from app.engine.structured_schemas import RoutingDecision

        supervisor = SupervisorAgent.__new__(SupervisorAgent)
        supervisor._llm = MagicMock()

        mock_result = RoutingDecision(
            reasoning="User asks Bro",
            intent="colleague_consult",
            agent="COLLEAGUE_AGENT",
            confidence=0.95,
        )

        structured_llm = MagicMock()
        structured_llm.ainvoke = AsyncMock(return_value=mock_result)
        supervisor._llm.with_structured_output = MagicMock(return_value=structured_llm)

        state = {"routing_metadata": None}

        with patch("app.engine.multi_agent.supervisor.settings",
                    self._mock_settings(enable_soul_bridge=False)), \
             patch(
                 "app.engine.multi_agent.supervisor.StructuredInvokeService.ainvoke",
                 new=AsyncMock(return_value=mock_result),
             ):
            result = await supervisor._route_structured(
                "Hỏi Bro", {"user_role": "admin"}, "AI", "", "", {}, state,
            )

        assert result == AgentType.DIRECT.value

    def test_prompt_includes_role(self):
        """Routing prompt template includes {user_role} placeholder."""
        from app.engine.multi_agent.supervisor import ROUTING_PROMPT_TEMPLATE
        assert "{user_role}" in ROUTING_PROMPT_TEMPLATE
        assert "colleague_consult" in ROUTING_PROMPT_TEMPLATE

    def test_rule_based_no_colleague(self):
        """Rule-based fallback never routes to colleague_agent."""
        from app.engine.multi_agent.supervisor import SupervisorAgent, AgentType

        supervisor = SupervisorAgent.__new__(SupervisorAgent)
        supervisor._llm = None

        # Even with "Bro" in query, rule-based should NOT produce colleague
        result = supervisor._rule_based_route("Hỏi Bro về crypto", {})
        assert result != AgentType.COLLEAGUE.value


# =====================================================================
# Test Graph Wiring
# =====================================================================


class TestRunnerWiring:
    """Test that colleague_agent is wired into WiiiRunner."""

    def _mock_settings(self, **overrides):
        """Create mock settings for graph building."""
        s = MagicMock()
        s.enable_product_search = overrides.get("enable_product_search", False)
        s.enable_subagent_architecture = overrides.get("enable_subagent_architecture", False)
        s.enable_cross_soul_query = overrides.get("enable_cross_soul_query", True)
        s.enable_soul_bridge = overrides.get("enable_soul_bridge", True)
        s.quality_skip_threshold = 0.85
        return s

    def test_route_decision_accepts_colleague(self):
        """route_decision accepts colleague_agent as valid route."""
        from app.engine.multi_agent.graph import route_decision

        state = {"next_agent": "colleague_agent"}
        assert route_decision(state) == "colleague_agent"

    def test_route_decision_unknown_defaults_to_direct(self):
        """Unknown route defaults to direct."""
        from app.engine.multi_agent.graph import route_decision

        state = {"next_agent": "alien_agent"}
        assert route_decision(state) == "direct"

    def test_node_exists_when_enabled(self):
        """Colleague agent node is registered when both flags are enabled."""
        import app.engine.multi_agent.runner as runner_mod
        from app.engine.multi_agent.runner import get_wiii_runner

        runner_mod._RUNNER = None
        with patch("app.engine.multi_agent.runner.settings", self._mock_settings()):
            runner = get_wiii_runner()
            assert "colleague_agent" in runner._feature_nodes
            assert runner._get_node("colleague_agent") is not None
        runner_mod._RUNNER = None

    def test_node_absent_when_disabled(self):
        """Colleague agent node is gated off when cross-soul is disabled."""
        import app.engine.multi_agent.runner as runner_mod
        from app.engine.multi_agent.runner import get_wiii_runner

        runner_mod._RUNNER = None
        with patch(
            "app.engine.multi_agent.runner.settings",
            self._mock_settings(enable_cross_soul_query=False),
        ):
            runner = get_wiii_runner()
            assert "colleague_agent" in runner._feature_nodes
            assert runner._get_node("colleague_agent") is None
        runner_mod._RUNNER = None


# =====================================================================
# Test EventType additions
# =====================================================================


class TestEventTypes:
    """Verify CONSULTATION and CONSULTATION_REPLY event types exist."""

    def test_consultation_event_type(self):
        from app.engine.subsoul.protocol import EventType
        assert EventType.CONSULTATION.value == "CONSULTATION"

    def test_consultation_reply_event_type(self):
        from app.engine.subsoul.protocol import EventType
        assert EventType.CONSULTATION_REPLY.value == "CONSULTATION_REPLY"


# =====================================================================
# Test Config Flags
# =====================================================================


class TestConfigFlags:
    """Verify Sprint 215 config flags exist with correct defaults."""

    def test_enable_cross_soul_query_default(self):
        from app.core.config import Settings
        default = Settings.model_fields["enable_cross_soul_query"].default
        assert default is False

    def test_cross_soul_query_timeout_default(self):
        from app.core.config import Settings
        default = Settings.model_fields["cross_soul_query_timeout"].default
        assert default == 15.0

    def test_cross_soul_query_peer_id_default(self):
        from app.core.config import Settings
        default = Settings.model_fields["cross_soul_query_peer_id"].default
        assert default == "bro"

    def test_bridge_events_include_consultation(self):
        from app.core.config import Settings
        default = Settings.model_fields["soul_bridge_bridge_events"].default
        assert "CONSULTATION" in default
        assert "CONSULTATION_REPLY" in default
