"""
Sprint 72→73: SOTA Memory Agent — Retrieve-Extract-Decide-Respond

Tests for the rewritten MemoryAgentNode and related changes:
1. TestMemoryAgentRetrieve — Phase 1: existing fact retrieval
2. TestMemoryAgentExtract — Phase 2: fact extraction + storage
3. TestMemoryAgentRespond — Phase 4: LLM response generation
4. TestMemoryAgentProcess — Full pipeline integration
5. TestMemoryAgentEdge — Graph edge: skip grader, LLM config
6. TestPersonalKeywordsFix — Routing: false positive fixes
"""

import sys
import types
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Break circular import (same pattern as other test files)
_cs_key = "app.services.chat_service"
_svc_key = "app.services"
_had_cs = _cs_key in sys.modules
_orig_cs = sys.modules.get(_cs_key)
if not _had_cs:
    _mock_cs = types.ModuleType(_cs_key)
    _mock_cs.ChatService = type("ChatService", (), {})
    _mock_cs.get_chat_service = lambda: None
    sys.modules[_cs_key] = _mock_cs

from app.engine.multi_agent.agent_config import AgentConfigRegistry
from app.engine.multi_agent.agents.memory_agent import MemoryAgentNode, get_memory_agent_node
from app.engine.multi_agent.supervisor import (
    SupervisorAgent, AgentType, PERSONAL_KEYWORDS,
)

if not _had_cs:
    sys.modules.pop(_cs_key, None)
    sys.modules.pop(_svc_key, None)
elif _orig_cs is not None:
    sys.modules[_cs_key] = _orig_cs


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_memory_engine():
    """Create a mock SemanticMemoryEngine."""
    engine = MagicMock()
    engine.get_user_facts = AsyncMock(return_value={})
    engine._fact_extractor = MagicMock()
    engine._fact_extractor.extract_and_store_facts = AsyncMock(return_value=[])
    return engine


@pytest.fixture
def memory_agent(mock_memory_engine):
    """Create a MemoryAgentNode with mocked engine."""
    return MemoryAgentNode(semantic_memory=mock_memory_engine)


@pytest.fixture
def mock_llm():
    """Create a mock LLM that returns a simple response."""
    llm = AsyncMock()
    llm.ainvoke = AsyncMock(return_value=MagicMock(
        content="Xin chào Minh! Mình đã ghi nhớ thông tin của bạn rồi."
    ))
    return llm


@pytest.fixture
def base_state():
    """Create a basic AgentState."""
    return {
        "query": "Tôi tên là Minh",
        "user_id": "user-123",
        "session_id": "session-abc",
        "context": {},
        "messages": [],
        "current_agent": "",
        "next_agent": "",
        "agent_outputs": {},
        "final_response": "",
        "error": None,
    }


@pytest.fixture
def supervisor():
    """Create SupervisorAgent with mocked LLM (tests rule-based only)."""
    with patch.object(AgentConfigRegistry, "get_llm", return_value=None):
        agent = SupervisorAgent()
        agent._llm = None
        return agent


# =============================================================================
# 1. TestMemoryAgentRetrieve — Phase 1
# =============================================================================

class TestMemoryAgentRetrieve:
    """Phase 1: Retrieve existing user facts from semantic memory."""

    @pytest.mark.asyncio
    async def test_retrieve_returns_facts(self, memory_agent, mock_memory_engine):
        """Existing facts are converted to list of dicts."""
        mock_memory_engine.get_user_facts.return_value = {
            "name": "Minh",
            "role": "sinh viên",
        }
        result = await memory_agent._retrieve_facts("user-123")
        assert len(result) == 2
        assert {"type": "name", "content": "Minh"} in result
        assert {"type": "role", "content": "sinh viên"} in result

    @pytest.mark.asyncio
    async def test_retrieve_empty_when_no_facts(self, memory_agent, mock_memory_engine):
        """Returns empty list when no facts exist."""
        mock_memory_engine.get_user_facts.return_value = {}
        result = await memory_agent._retrieve_facts("user-123")
        assert result == []

    @pytest.mark.asyncio
    async def test_retrieve_empty_without_engine(self):
        """Returns empty list when semantic memory is None."""
        agent = MemoryAgentNode(semantic_memory=None)
        result = await agent._retrieve_facts("user-123")
        assert result == []

    @pytest.mark.asyncio
    async def test_retrieve_empty_without_user_id(self, memory_agent):
        """Returns empty list when user_id is empty."""
        result = await memory_agent._retrieve_facts("")
        assert result == []

    @pytest.mark.asyncio
    async def test_retrieve_handles_exception(self, memory_agent, mock_memory_engine):
        """Returns empty list on exception."""
        mock_memory_engine.get_user_facts.side_effect = Exception("DB error")
        result = await memory_agent._retrieve_facts("user-123")
        assert result == []

    @pytest.mark.asyncio
    async def test_retrieve_handles_list_values(self, memory_agent, mock_memory_engine):
        """Handles list-type fact values (e.g., preferences)."""
        mock_memory_engine.get_user_facts.return_value = {
            "preferences": ["AI", "maritime"],
            "name": "Nam",
        }
        result = await memory_agent._retrieve_facts("user-123")
        assert len(result) == 3
        assert {"type": "name", "content": "Nam"} in result
        assert {"type": "preferences", "content": "AI"} in result
        assert {"type": "preferences", "content": "maritime"} in result


# =============================================================================
# 2. TestMemoryAgentExtract — Phase 2
# =============================================================================

class TestMemoryAgentExtract:
    """Phase 2: Extract facts from current message and store."""

    @pytest.mark.asyncio
    async def test_extract_stores_facts(self, memory_agent, mock_memory_engine):
        """Extracts and stores facts from message."""
        mock_fact = MagicMock()
        mock_fact.to_content.return_value = "Tên: Minh"
        mock_memory_engine._fact_extractor.extract_and_store_facts.return_value = [mock_fact]

        facts, decisions = await memory_agent._extract_and_store_facts("user-123", "Tôi tên là Minh", {})
        assert facts == ["Tên: Minh"]
        assert len(decisions) == 1
        assert decisions[0].action.value == "add"
        assert decisions[0].fact_type == "Tên"
        assert decisions[0].new_value == "Minh"
        mock_memory_engine._fact_extractor.extract_and_store_facts.assert_called_once_with(
            user_id="user-123", message="Tôi tên là Minh", existing_facts={},
        )

    @pytest.mark.asyncio
    async def test_extract_returns_empty_when_no_facts(self, memory_agent, mock_memory_engine):
        """Returns empty list when no facts extracted."""
        mock_memory_engine._fact_extractor.extract_and_store_facts.return_value = []
        result = await memory_agent._extract_and_store_facts("user-123", "Xin chào", {})
        assert result == ([], [])

    @pytest.mark.asyncio
    async def test_extract_empty_without_engine(self):
        """Returns empty list when semantic memory is None."""
        agent = MemoryAgentNode(semantic_memory=None)
        result = await agent._extract_and_store_facts("user-123", "Tôi là Minh", {})
        assert result == ([], [])

    @pytest.mark.asyncio
    async def test_extract_empty_without_user_id(self, memory_agent):
        """Returns empty list when user_id is empty."""
        result = await memory_agent._extract_and_store_facts("", "Tôi là Minh", {})
        assert result == ([], [])

    @pytest.mark.asyncio
    async def test_extract_empty_without_message(self, memory_agent):
        """Returns empty list when message is empty."""
        result = await memory_agent._extract_and_store_facts("user-123", "", {})
        assert result == ([], [])

    @pytest.mark.asyncio
    async def test_extract_handles_exception(self, memory_agent, mock_memory_engine):
        """Returns empty list on extraction error."""
        mock_memory_engine._fact_extractor.extract_and_store_facts.side_effect = Exception("LLM error")
        result = await memory_agent._extract_and_store_facts("user-123", "Tôi là Minh", {})
        assert result == ([], [])


# =============================================================================
# 3. TestMemoryAgentRespond — Phase 3
# =============================================================================

class TestMemoryAgentRespond:
    """Phase 4: LLM response generation with memory context."""

    @pytest.mark.asyncio
    async def test_llm_response_with_context(self, memory_agent, mock_llm, base_state):
        """LLM generates response with existing and new facts."""
        existing = [{"type": "name", "content": "Minh"}]
        new = ["Tuổi: 25"]

        thinking_processor = MagicMock()
        thinking_processor.process.return_value = ("Chào Minh! Mình ghi nhớ bạn 25 tuổi rồi.", "")
        with patch("app.services.thinking_post_processor.get_thinking_processor",
                    return_value=thinking_processor):
            result = await memory_agent._generate_response(
                mock_llm, "Mình 25 tuổi", existing, new, "", base_state,
            )

        assert "Minh" in result or "25" in result or "ghi nhớ" in result
        mock_llm.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_response_preserves_thinking(self, memory_agent, mock_llm, base_state):
        """Thinking content is stored in state."""
        thinking_processor = MagicMock()
        thinking_processor.process.return_value = ("Chào bạn!", "Some thinking")
        with patch("app.services.thinking_post_processor.get_thinking_processor",
                    return_value=thinking_processor):
            await memory_agent._generate_response(
                mock_llm, "Xin chào", [], [], "", base_state,
            )

        assert base_state.get("thinking") == "Some thinking"
        assert base_state.get("_memory_native_thinking") == "Some thinking"

    @pytest.mark.asyncio
    async def test_template_fallback_when_no_llm(self, memory_agent, base_state):
        """Falls back to template when LLM is None."""
        result = await memory_agent._generate_response(
            None, "Tên mình là Minh", [], ["Tên: Minh"], "", base_state,
        )
        assert "ghi nhớ" in result

    @pytest.mark.asyncio
    async def test_template_fallback_on_llm_error(self, memory_agent, base_state):
        """Falls back to template when LLM raises exception."""
        bad_llm = AsyncMock()
        bad_llm.ainvoke.side_effect = Exception("API error")

        result = await memory_agent._generate_response(
            bad_llm, "test", [], ["Tên: Minh"], "", base_state,
        )
        assert "ghi nhớ" in result

    @pytest.mark.asyncio
    async def test_template_with_existing_facts(self, memory_agent, base_state):
        """Template includes existing facts when asking recall."""
        existing = [{"type": "name", "content": "Minh"}, {"type": "age", "content": "25"}]
        result = await memory_agent._generate_response(None, "bạn nhớ gì?", existing, [], "", base_state)
        assert "Minh" in result
        assert "thông tin" in result.lower()

    @pytest.mark.asyncio
    async def test_template_with_no_facts(self, memory_agent, base_state):
        """Template returns friendly no-info message."""
        result = await memory_agent._generate_response(None, "test", [], [], "", base_state)
        assert "chưa có thông tin" in result.lower() or "chia sẻ" in result.lower()

    @pytest.mark.asyncio
    async def test_template_with_changes_summary(self, memory_agent, base_state):
        """Sprint 73: Template uses changes_summary when available."""
        result = await memory_agent._generate_response(
            None, "test", [], [], "Đã ghi nhớ: name: Minh", base_state,
        )
        assert "Đã ghi nhớ" in result


# =============================================================================
# 4. TestMemoryAgentProcess — Full Pipeline
# =============================================================================

class TestMemoryAgentProcess:
    """Full 3-phase pipeline integration tests."""

    @pytest.mark.asyncio
    async def test_full_pipeline_intro(self, memory_agent, mock_memory_engine, mock_llm, base_state):
        """User introduction: retrieve → extract → respond."""
        mock_memory_engine.get_user_facts.return_value = {}
        mock_fact = MagicMock()
        mock_fact.to_content.return_value = "Tên: Minh"
        mock_memory_engine._fact_extractor.extract_and_store_facts.return_value = [mock_fact]

        with patch("app.services.output_processor.extract_thinking_from_response",
                    return_value=("Xin chào Minh! Mình đã ghi nhớ rồi.", "")):
            result = await memory_agent.process(base_state, llm=mock_llm)

        assert result.get("memory_output")
        assert result.get("current_agent") == "memory_agent"
        assert "memory" in result.get("agent_outputs", {})

    @pytest.mark.asyncio
    async def test_full_pipeline_recall(self, memory_agent, mock_memory_engine, mock_llm, base_state):
        """User asks recall: retrieve existing → respond with facts."""
        mock_memory_engine.get_user_facts.return_value = {
            "name": "Minh", "age": "25",
        }
        base_state["query"] = "Bạn nhớ tên mình không?"

        with patch("app.services.output_processor.extract_thinking_from_response",
                    return_value=("Bạn là Minh, 25 tuổi!", "")):
            result = await memory_agent.process(base_state, llm=mock_llm)

        assert result.get("memory_output")
        assert "memory" in result.get("agent_outputs", {})

    @pytest.mark.asyncio
    async def test_full_pipeline_no_engine(self, base_state):
        """Graceful fallback when semantic memory engine is unavailable."""
        agent = MemoryAgentNode(semantic_memory=None)
        result = await agent.process(base_state, llm=None)

        assert result.get("memory_output")
        assert result.get("current_agent") == "memory_agent"
        # Should not contain error message
        assert "lỗi" not in result.get("memory_output", "").lower()
        assert "error" not in result.get("memory_output", "").lower()

    @pytest.mark.asyncio
    async def test_full_pipeline_error_recovery(self, memory_agent, mock_memory_engine, base_state):
        """Graceful recovery when all phases fail."""
        mock_memory_engine.get_user_facts.side_effect = Exception("DB down")
        mock_memory_engine._fact_extractor.extract_and_store_facts.side_effect = Exception("LLM down")

        result = await memory_agent.process(base_state, llm=None)

        assert result.get("memory_output")
        assert result.get("current_agent") == "memory_agent"
        # Never return error string to user
        assert "Không có thông tin về user" not in result.get("memory_output", "")

    @pytest.mark.asyncio
    async def test_no_hardcoded_error_string(self, base_state):
        """The old hardcoded 'Không có thông tin về user' is never returned."""
        agent = MemoryAgentNode(semantic_memory=None)
        result = await agent.process(base_state, llm=None)
        assert "Không có thông tin về user" not in result.get("memory_output", "")


# =============================================================================
# 5. TestMemoryAgentEdge — Graph Edge Configuration
# =============================================================================

class TestMemoryAgentEdge:
    """Graph edge and configuration tests."""

    def test_memory_config_in_registry(self):
        """Memory node has config in AgentConfigRegistry."""
        AgentConfigRegistry.reset()
        AgentConfigRegistry.initialize()
        config = AgentConfigRegistry.get_config("memory")
        assert config.tier == "light"
        assert config.temperature == 0.5

    def test_memory_agent_accepts_llm_param(self, mock_memory_engine, mock_llm):
        """process() accepts llm parameter."""
        agent = MemoryAgentNode(semantic_memory=mock_memory_engine)
        # Just verify the method signature accepts llm=
        import inspect
        sig = inspect.signature(agent.process)
        assert "llm" in sig.parameters

    def test_graph_imports_memory_node(self):
        """Graph module imports memory_agent correctly."""
        from app.engine.multi_agent.graph import memory_node
        assert callable(memory_node)

    def test_node_labels_has_memory_agent(self):
        """Streaming labels include memory_agent."""
        from app.engine.multi_agent.graph_streaming import _NODE_LABELS
        assert "memory_agent" in _NODE_LABELS
        assert _NODE_LABELS["memory_agent"] == "Truy xuất bộ nhớ"


# =============================================================================
# 6. TestPersonalKeywordsFix — Routing False Positive Fixes
# =============================================================================

class TestPersonalKeywordsFix:
    """Sprint 72: 'mình là' and 'tôi là' no longer false-positive."""

    def test_minh_la_not_in_keywords(self):
        """'mình là' removed from PERSONAL_KEYWORDS (too broad)."""
        assert "mình là" not in PERSONAL_KEYWORDS

    def test_toi_la_not_in_keywords(self):
        """'tôi là' removed from PERSONAL_KEYWORDS (too broad)."""
        assert "tôi là" not in PERSONAL_KEYWORDS

    def test_specific_patterns_present(self):
        """Specific name patterns are present."""
        assert "tên mình là" in PERSONAL_KEYWORDS
        assert "tôi tên là" in PERSONAL_KEYWORDS
        assert "mình tên là" in PERSONAL_KEYWORDS
        assert "bạn có nhớ" in PERSONAL_KEYWORDS

    def test_minh_thich_doc_sach_not_memory(self, supervisor):
        """'mình thích đọc sách' should NOT route to MEMORY (Sprint 72 fix)."""
        result = supervisor._rule_based_route("mình thích đọc sách về AI", {})
        # Should route to RAG (>20 chars, no personal keyword)
        assert result != AgentType.MEMORY.value

    def test_toi_la_sinh_vien_not_memory(self, supervisor):
        """'tôi là sinh viên' should NOT route to MEMORY (Sprint 72 fix)."""
        result = supervisor._rule_based_route("tôi là sinh viên", {})
        # Short query, no personal keyword — DIRECT
        assert result != AgentType.MEMORY.value

    def test_ten_minh_la_routes_to_memory(self, supervisor):
        """'tên mình là Minh' should still route to MEMORY."""
        result = supervisor._rule_based_route("tên mình là Minh", {})
        assert result == AgentType.MEMORY.value

    def test_toi_ten_la_routes_to_memory(self, supervisor):
        """'tôi tên là Nam' should route to MEMORY."""
        result = supervisor._rule_based_route("tôi tên là Nam", {})
        assert result == AgentType.MEMORY.value

    def test_ban_co_nho_routes_to_memory(self, supervisor):
        """'bạn có nhớ tên mình không?' should route to MEMORY."""
        result = supervisor._rule_based_route("bạn có nhớ tên mình không?", {})
        assert result == AgentType.MEMORY.value

    def test_remember_still_routes_to_memory(self, supervisor):
        """'remember' keyword still works."""
        result = supervisor._rule_based_route("remember my preference", {})
        assert result == AgentType.MEMORY.value


# =============================================================================
# 7. TestMemoryAgentSingleton
# =============================================================================

class TestMemoryAgentSingleton:
    """Test singleton pattern for MemoryAgentNode."""

    def test_is_available_with_engine(self, mock_memory_engine):
        """is_available returns True when engine is set."""
        agent = MemoryAgentNode(semantic_memory=mock_memory_engine)
        assert agent.is_available() is True

    def test_is_available_without_engine(self):
        """is_available returns False when engine is None."""
        agent = MemoryAgentNode(semantic_memory=None)
        assert agent.is_available() is False
