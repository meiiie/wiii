"""
Tests for SupervisorAgent - Query Router & Response Synthesizer.

Tests LLM routing, rule-based fallback, response synthesis,
skill activation, and state wiring.
"""

import sys
import types
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

# Break circular import: multi_agent.__init__ → graph → agents → tutor_node
# → services.__init__ → chat_service → multi_agent.graph
_cs_key = "app.services.chat_service"
_svc_key = "app.services"
_had_cs = _cs_key in sys.modules
_had_svc = _svc_key in sys.modules
_orig_cs = sys.modules.get(_cs_key)
if not _had_cs:
    _mock_cs = types.ModuleType(_cs_key)
    _mock_cs.ChatService = type("ChatService", (), {})
    _mock_cs.get_chat_service = lambda: None
    sys.modules[_cs_key] = _mock_cs

from app.engine.multi_agent.agent_config import AgentConfigRegistry

if not _had_cs:
    sys.modules.pop(_cs_key, None)
    if not _had_svc:
        sys.modules.pop(_svc_key, None)
elif _orig_cs is not None:
    sys.modules[_cs_key] = _orig_cs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_supervisor(llm=None):
    """Create SupervisorAgent with optional mocked LLM."""
    with patch.object(
        AgentConfigRegistry, "get_llm", return_value=llm,
    ):
        from app.engine.multi_agent.supervisor import SupervisorAgent
        return SupervisorAgent()


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.ainvoke = AsyncMock()
    return llm


@pytest.fixture
def base_state():
    return {
        "query": "COLREGs Rule 13",
        "context": {},
        "domain_id": "maritime",
        "domain_config": {},
    }


# Lazy imports inside route()/synthesize() do:
#   from app.services.output_processor import extract_thinking_from_response
#   from app.domains.registry import get_domain_registry
# Patch at SOURCE module because they're resolved at call time.
EXTRACT_THINKING_PATCH = "app.services.output_processor.extract_thinking_from_response"
DOMAIN_REGISTRY_PATCH = "app.domains.registry.get_domain_registry"


# ---------------------------------------------------------------------------
# route() — LLM routing
# ---------------------------------------------------------------------------

class TestSupervisorRoute:
    """Sprint 103: route() always uses structured output (_route_structured)."""

    @pytest.mark.asyncio
    async def test_route_to_rag(self, mock_llm, base_state):
        from app.engine.structured_schemas import RoutingDecision
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(return_value=RoutingDecision(agent="RAG_AGENT"))
        mock_llm.with_structured_output.return_value = mock_structured
        sup = _make_supervisor(mock_llm)

        result = await sup.route(base_state)
        assert result == "rag_agent"

    @pytest.mark.asyncio
    async def test_route_to_tutor(self, mock_llm, base_state):
        from app.engine.structured_schemas import RoutingDecision
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(return_value=RoutingDecision(agent="TUTOR_AGENT"))
        mock_llm.with_structured_output.return_value = mock_structured
        sup = _make_supervisor(mock_llm)

        result = await sup.route(base_state)
        assert result == "tutor_agent"

    @pytest.mark.asyncio
    async def test_route_to_memory(self, mock_llm, base_state):
        from app.engine.structured_schemas import RoutingDecision
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(return_value=RoutingDecision(agent="MEMORY_AGENT"))
        mock_llm.with_structured_output.return_value = mock_structured
        sup = _make_supervisor(mock_llm)

        result = await sup.route(base_state)
        assert result == "memory_agent"

    @pytest.mark.asyncio
    async def test_route_to_direct(self, mock_llm, base_state):
        from app.engine.structured_schemas import RoutingDecision
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(return_value=RoutingDecision(agent="DIRECT"))
        mock_llm.with_structured_output.return_value = mock_structured
        sup = _make_supervisor(mock_llm)

        result = await sup.route(base_state)
        assert result == "direct"

    def test_code_studio_keywords_route_to_code_studio(self):
        sup = _make_supervisor(None)
        result = sup._rule_based_route("ve bieu do bang python va luu PNG")
        assert result == "code_studio_agent"

    @pytest.mark.asyncio
    async def test_route_to_code_studio(self, mock_llm, base_state):
        from app.engine.structured_schemas import RoutingDecision
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(
            return_value=RoutingDecision(agent="CODE_STUDIO_AGENT", intent="code_execution")
        )
        mock_llm.with_structured_output.return_value = mock_structured
        sup = _make_supervisor(mock_llm)
        base_state["query"] = "Ve bieu do bang python va tao file PNG"

        result = await sup.route(base_state)
        assert result == "code_studio_agent"

    @pytest.mark.asyncio
    async def test_route_llm_unavailable_falls_back(self, base_state):
        sup = _make_supervisor(None)
        # No LLM → rule-based
        base_state["query"] = "COLREGs Rule 13 là gì và áp dụng như thế nào?"
        result = await sup.route(base_state)
        assert result in ("rag_agent", "tutor_agent", "memory_agent", "direct")

    @pytest.mark.asyncio
    async def test_route_llm_error_falls_back(self, mock_llm, base_state):
        mock_llm.with_structured_output.side_effect = Exception("API error")
        sup = _make_supervisor(mock_llm)
        base_state["query"] = "COLREGs Rule 13 là gì?"
        result = await sup.route(base_state)
        # Should fall back to rule-based without crashing
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# _rule_based_route() tests
# ---------------------------------------------------------------------------

class TestRuleBasedRoute:
    def test_no_domain_config_defaults_to_direct(self):
        """Sprint 103: Without domain_config, non-social/personal → DIRECT."""
        sup = _make_supervisor(None)
        assert sup._rule_based_route("giải thích COLREGs") == "direct"
        assert sup._rule_based_route("cho tôi ví dụ") == "direct"
        assert sup._rule_based_route("tìm trên mạng về tàu") == "direct"
        assert sup._rule_based_route("tin tức hàng hải mới nhất") == "direct"

    def test_personal_keywords_route_to_memory(self):
        sup = _make_supervisor(None)
        assert sup._rule_based_route("tên tôi là gì nhỉ") == "memory_agent"
        assert sup._rule_based_route("nhớ lần trước không") == "memory_agent"

    def test_long_query_without_domain_defaults_to_direct(self):
        sup = _make_supervisor(None)
        # Sprint 80: No domain signal → DIRECT (off-topic protection)
        result = sup._rule_based_route("quy định nào áp dụng cho tàu máy lớn hơn 50m")
        assert result == "direct"

    def test_short_query_defaults_to_direct(self):
        sup = _make_supervisor(None)
        result = sup._rule_based_route("hi")
        assert result == "direct"

    def test_custom_domain_keywords_route_to_rag(self):
        sup = _make_supervisor(None)
        domain_config = {"routing_keywords": ["luật giao thông, biển báo"]}
        result = sup._rule_based_route("luật giao thông đường bộ", domain_config)
        assert result == "rag_agent"

    def test_domain_keywords_from_registry_fallback(self):
        sup = _make_supervisor(None)
        mock_domain = MagicMock()
        mock_config = MagicMock()
        mock_config.routing_keywords = ["colregs", "solas"]
        mock_domain.get_config.return_value = mock_config

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_domain

        with patch(DOMAIN_REGISTRY_PATCH, return_value=mock_registry):
            result = sup._rule_based_route("colregs rule 13")

        assert result == "rag_agent"

    def test_domain_registry_error_doesnt_crash(self):
        sup = _make_supervisor(None)
        with patch(DOMAIN_REGISTRY_PATCH, side_effect=Exception("No registry")):
            # Sprint 80: Should still work without crashing; no domain signal → DIRECT
            result = sup._rule_based_route("quy định nào áp dụng cho tàu máy lớn")
        assert result == "direct"


# ---------------------------------------------------------------------------
# synthesize() tests
# ---------------------------------------------------------------------------

class TestSupervisorSynthesize:
    @pytest.mark.asyncio
    async def test_single_output_passthrough(self, mock_llm):
        sup = _make_supervisor(mock_llm)
        state = {"agent_outputs": {"rag": "Rule 13 answer"}}
        result = await sup.synthesize(state)
        assert result == "Rule 13 answer"

    @pytest.mark.asyncio
    async def test_no_outputs_returns_apology(self, mock_llm):
        sup = _make_supervisor(mock_llm)
        state = {"agent_outputs": {}}
        result = await sup.synthesize(state)
        assert "Xin lỗi" in result

    @pytest.mark.asyncio
    async def test_multiple_outputs_with_llm(self, mock_llm):
        mock_llm.ainvoke.return_value = MagicMock(content="Synthesized answer")
        sup = _make_supervisor(mock_llm)
        state = {
            "query": "test",
            "agent_outputs": {"rag": "RAG output", "memory": "Memory output"},
        }

        with patch(EXTRACT_THINKING_PATCH, return_value=("Synthesized answer", None)):
            result = await sup.synthesize(state)

        assert result == "Synthesized answer"

    @pytest.mark.asyncio
    async def test_multiple_outputs_no_llm_concatenates(self):
        sup = _make_supervisor(None)
        state = {
            "query": "test",
            "agent_outputs": {"rag": "RAG output", "memory": "Memory output"},
        }
        result = await sup.synthesize(state)
        assert "RAG output" in result
        assert "Memory output" in result

    @pytest.mark.asyncio
    async def test_synthesis_llm_error_returns_first_output(self, mock_llm):
        mock_llm.ainvoke.side_effect = Exception("API error")
        sup = _make_supervisor(mock_llm)
        state = {
            "query": "test",
            "agent_outputs": {"rag": "RAG output", "tutor": "Tutor output"},
        }
        result = await sup.synthesize(state)
        # Returns first output on error
        assert result in ("RAG output", "Tutor output")


# ---------------------------------------------------------------------------
# process() tests
# ---------------------------------------------------------------------------

class TestSupervisorProcess:
    """Sprint 103: process() uses structured routing (RoutingDecision)."""

    def _setup_structured_mock(self, mock_llm, agent_name):
        """Helper to set up structured output mock for route()."""
        from app.engine.structured_schemas import RoutingDecision
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(return_value=RoutingDecision(agent=agent_name))
        mock_llm.with_structured_output.return_value = mock_structured

    @pytest.mark.asyncio
    async def test_process_sets_next_agent(self, mock_llm, base_state):
        self._setup_structured_mock(mock_llm, "RAG_AGENT")
        sup = _make_supervisor(mock_llm)

        with patch(DOMAIN_REGISTRY_PATCH, side_effect=Exception("skip")):
            result = await sup.process(base_state)

        assert result["next_agent"] == "rag_agent"
        assert result["current_agent"] == "supervisor"

    @pytest.mark.asyncio
    async def test_process_skill_activation(self, mock_llm, base_state):
        self._setup_structured_mock(mock_llm, "TUTOR_AGENT")
        sup = _make_supervisor(mock_llm)

        mock_domain = MagicMock()
        mock_skill = MagicMock()
        mock_skill.id = "colregs_overview"
        mock_domain.match_skills.return_value = [mock_skill]
        mock_domain.activate_skill.return_value = "## COLREGs Overview\nContent here..."

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_domain

        with patch(DOMAIN_REGISTRY_PATCH, return_value=mock_registry):
            result = await sup.process(base_state)

        assert result["skill_context"] == "## COLREGs Overview\nContent here..."

    @pytest.mark.asyncio
    async def test_process_keeps_capability_context_separate(self, mock_llm, base_state):
        self._setup_structured_mock(mock_llm, "TUTOR_AGENT")
        sup = _make_supervisor(mock_llm)

        mock_domain = MagicMock()
        mock_skill = MagicMock()
        mock_skill.id = "colregs_overview"
        mock_domain.match_skills.return_value = [mock_skill]
        mock_domain.activate_skill.return_value = "## COLREGs Overview\nContent here..."

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_domain

        with patch(DOMAIN_REGISTRY_PATCH, return_value=mock_registry):
            with patch(
                "app.engine.skills.skill_handbook.get_skill_handbook",
                return_value=MagicMock(
                    summarize_for_query=MagicMock(return_value="Capability handbook phù hợp lúc này:\n- tool_knowledge_search")
                ),
            ):
                result = await sup.process(base_state)

        assert result["skill_context"] == "## COLREGs Overview\nContent here..."
        assert result["capability_context"].startswith("Capability handbook phù hợp")

    @pytest.mark.asyncio
    async def test_process_skill_activation_error_doesnt_crash(self, mock_llm, base_state):
        self._setup_structured_mock(mock_llm, "RAG_AGENT")
        sup = _make_supervisor(mock_llm)

        with patch(DOMAIN_REGISTRY_PATCH, side_effect=Exception("Registry error")):
            result = await sup.process(base_state)

        # Should still route successfully despite skill error
        assert result["next_agent"] == "rag_agent"

    @pytest.mark.asyncio
    async def test_process_no_domain_id_skips_skills(self, mock_llm):
        state = {"query": "hello there test", "context": {}, "domain_id": "", "domain_config": {}}
        self._setup_structured_mock(mock_llm, "DIRECT")
        sup = _make_supervisor(mock_llm)

        result = await sup.process(state)

        assert "skill_context" not in result

    @pytest.mark.asyncio
    async def test_process_uses_parallel_dispatch_for_complex_learning_query(self, mock_llm, base_state):
        self._setup_structured_mock(mock_llm, "TUTOR_AGENT")
        sup = _make_supervisor(mock_llm)
        base_state["query"] = (
            "Giải thích thật chi tiết quy tắc 13 COLREG, "
            "đưa ví dụ thực tế và đối chiếu với tài liệu gốc giúp tôi nhé."
        )

        with patch("app.core.config.settings.enable_subagent_architecture", True):
            with patch.object(sup, "_is_complex_query", return_value=True):
                with patch(
                    "app.engine.multi_agent.orchestration_planner.plan_parallel_targets",
                    return_value=["tutor", "rag"],
                ):
                    result = await sup.process(base_state)

        assert result["next_agent"] == "parallel_dispatch"
        assert result["_parallel_targets"] == ["tutor", "rag"]

    @pytest.mark.asyncio
    async def test_process_uses_parallel_dispatch_for_complex_product_query(self, mock_llm, base_state):
        self._setup_structured_mock(mock_llm, "PRODUCT_SEARCH_AGENT")
        sup = _make_supervisor(mock_llm)
        base_state["query"] = (
            "Tìm iPhone 17 Pro Max rẻ nhất, so giá trên nhiều nguồn "
            "và phân tích giúp tôi nguồn nào đáng tin nhất."
        )

        with patch("app.core.config.settings.enable_product_search", True):
            with patch("app.core.config.settings.enable_subagent_architecture", True):
                with patch.object(sup, "_is_complex_query", return_value=True):
                    with patch(
                        "app.engine.multi_agent.orchestration_planner.plan_parallel_targets",
                        return_value=["search", "rag"],
                    ):
                        result = await sup.process(base_state)

        assert result["next_agent"] == "parallel_dispatch"
        assert result["_parallel_targets"] == ["search", "rag"]


# ---------------------------------------------------------------------------
# is_available() tests
# ---------------------------------------------------------------------------

class TestSupervisorIsAvailable:
    def test_available_with_llm(self, mock_llm):
        sup = _make_supervisor(mock_llm)
        assert sup.is_available() is True

    def test_not_available_without_llm(self):
        sup = _make_supervisor(None)
        assert sup.is_available() is False


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestSupervisorSingleton:
    def test_get_supervisor_agent_returns_instance(self):
        import app.engine.multi_agent.supervisor as mod
        mod._supervisor = None
        try:
            with patch.object(AgentConfigRegistry, "get_llm", return_value=MagicMock()):
                sup = mod.get_supervisor_agent()
                assert isinstance(sup, mod.SupervisorAgent)
                sup2 = mod.get_supervisor_agent()
                assert sup is sup2
        finally:
            mod._supervisor = None
