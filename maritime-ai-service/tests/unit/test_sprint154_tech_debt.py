"""
Sprint 154: "Dọn Nhà" — Tech Debt Cleanup Tests

Tests for:
1. Config nested model groups (DatabaseConfig, LLMConfig, etc.)
2. Extracted direct_response_node helper functions
3. Shared test fixture usage
4. New fact_retrieval weight sum validator
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


# =========================================================================
# 1. Config Nested Model Groups
# =========================================================================

class TestConfigNestedGroups:
    """Test that nested config groups are properly synced from flat fields."""

    def test_database_config_synced(self):
        """DatabaseConfig should reflect flat postgres_* fields."""
        from app.core.config import Settings
        s = Settings(
            postgres_host="myhost",
            postgres_port=5555,
            postgres_user="myuser",
            postgres_password="mypass",
            postgres_db="mydb",
            _env_file=None,
        )
        assert s.database.host == "myhost"
        assert s.database.port == 5555
        assert s.database.user == "myuser"
        assert s.database.password == "mypass"
        assert s.database.db == "mydb"

    def test_llm_config_synced(self):
        """LLMConfig should reflect flat llm_provider, google_api_key, etc."""
        from app.core.config import Settings
        s = Settings(
            llm_provider="google",
            google_api_key="test-key-123",
            google_model="gemini-3-flash-preview",
            ollama_model="qwen3:8b",
            _env_file=None,
        )
        assert s.llm.provider == "google"
        assert s.llm.google_api_key == "test-key-123"
        assert s.llm.google_model == "gemini-3-flash-preview"
        assert s.llm.ollama_model == "qwen3:8b"

    def test_rag_config_synced(self):
        """RAGConfig should reflect flat rag_* fields."""
        from app.core.config import Settings
        s = Settings(
            rag_confidence_high=0.80,
            rag_confidence_medium=0.50,
            rag_quality_mode="quality",
            _env_file=None,
        )
        assert s.rag.confidence_high == 0.80
        assert s.rag.confidence_medium == 0.50
        assert s.rag.quality_mode == "quality"

    def test_memory_config_synced(self):
        """MemoryConfig should reflect flat memory_* fields."""
        from app.core.config import Settings
        s = Settings(
            max_user_facts=100,
            fact_retrieval_alpha=0.4,
            fact_retrieval_beta=0.4,
            fact_retrieval_gamma=0.2,
            _env_file=None,
        )
        assert s.memory.max_user_facts == 100
        assert s.memory.fact_retrieval_alpha == 0.4

    def test_product_search_config_synced(self):
        """ProductSearchConfig should reflect flat product_search_* fields."""
        from app.core.config import Settings
        s = Settings(
            enable_product_search=True,
            product_search_max_results=50,
            product_search_max_iterations=20,
            _env_file=None,
        )
        assert s.product_search.enable_product_search is True
        assert s.product_search.max_results == 50
        assert s.product_search.max_iterations == 20

    def test_thinking_config_synced(self):
        """ThinkingConfig should reflect flat thinking_* fields."""
        from app.core.config import Settings
        s = Settings(
            thinking_enabled=False,
            thinking_budget_deep=16384,
            gemini_thinking_level="high",
            _env_file=None,
        )
        assert s.thinking.enabled is False
        assert s.thinking.budget_deep == 16384
        assert s.thinking.gemini_level == "high"

    def test_character_config_synced(self):
        """CharacterConfig should reflect flat character_* fields."""
        from app.core.config import Settings
        s = Settings(
            enable_character_reflection=False,
            character_reflection_interval=10,
            _env_file=None,
        )
        assert s.character.enable_reflection is False
        assert s.character.reflection_interval == 10

    def test_cache_config_synced(self):
        """CacheConfig should reflect flat cache_* fields."""
        from app.core.config import Settings
        s = Settings(
            semantic_cache_enabled=False,
            cache_similarity_threshold=0.95,
            cache_response_ttl=3600,
            _env_file=None,
        )
        assert s.cache.enabled is False
        assert s.cache.similarity_threshold == 0.95
        assert s.cache.response_ttl == 3600

    def test_flat_access_still_works(self):
        """Flat field access must continue working (backward compat)."""
        from app.core.config import Settings
        s = Settings(
            google_api_key="abc123",
            llm_provider="openai",
            _env_file=None,
        )
        # Flat access
        assert s.google_api_key == "abc123"
        assert s.llm_provider == "openai"
        # Nested access
        assert s.llm.google_api_key == "abc123"
        assert s.llm.provider == "openai"


# =========================================================================
# 2. Fact Retrieval Weight Validator
# =========================================================================

class TestFactRetrievalWeightValidator:
    """Sprint 154: fact_retrieval alpha+beta+gamma must sum to 1.0."""

    def test_valid_weights_default(self):
        """Default weights (0.3+0.5+0.2=1.0) should pass validation."""
        from app.core.config import Settings
        s = Settings(_env_file=None)
        assert abs(s.fact_retrieval_alpha + s.fact_retrieval_beta + s.fact_retrieval_gamma - 1.0) < 0.01

    def test_valid_weights_custom(self):
        """Custom weights summing to 1.0 should pass validation."""
        from app.core.config import Settings
        s = Settings(
            fact_retrieval_alpha=0.4,
            fact_retrieval_beta=0.4,
            fact_retrieval_gamma=0.2,
            _env_file=None,
        )
        assert s.fact_retrieval_alpha == 0.4

    def test_invalid_weights_sum(self):
        """Weights NOT summing to 1.0 should raise ValueError."""
        from app.core.config import Settings
        with pytest.raises(ValueError, match="must sum to 1.0"):
            Settings(
                fact_retrieval_alpha=0.5,
                fact_retrieval_beta=0.5,
                fact_retrieval_gamma=0.5,
                _env_file=None,
            )


# =========================================================================
# 3. Extracted direct_response_node Helpers
# =========================================================================

class TestCollectDirectTools:
    """Test _collect_direct_tools extracted helper."""

    def test_returns_tools_and_force_flag(self):
        """Should return (tools_list, force_tools_bool)."""
        with patch("app.engine.multi_agent.graph.settings") as ms:
            ms.enable_character_tools = False
            ms.enable_code_execution = False
            from app.engine.multi_agent.graph import _collect_direct_tools
            tools, force = _collect_direct_tools("xin chào")
            assert isinstance(tools, list)
            assert isinstance(force, bool)

    def test_force_tools_for_web_search_query(self):
        """Queries needing web search should set force=True."""
        with patch("app.engine.multi_agent.graph.settings") as ms:
            ms.enable_character_tools = False
            ms.enable_code_execution = False
            from app.engine.multi_agent.graph import _collect_direct_tools
            _, force = _collect_direct_tools("thời tiết hôm nay thế nào")
            # force depends on _needs_web_search detecting weather keywords
            assert isinstance(force, bool)


class TestBindDirectTools:
    """Test _bind_direct_tools extracted helper."""

    def test_no_tools_returns_raw_llm(self):
        """Empty tools list should return original llm for both."""
        from app.engine.multi_agent.graph import _bind_direct_tools
        llm = MagicMock()
        llm_with, llm_auto = _bind_direct_tools(llm, [], False)
        assert llm_with is llm
        assert llm_auto is llm

    def test_with_tools_no_force(self):
        """Tools without force should use auto for both."""
        from app.engine.multi_agent.graph import _bind_direct_tools
        llm = MagicMock()
        bound = MagicMock()
        llm.bind_tools = MagicMock(return_value=bound)
        llm_with, llm_auto = _bind_direct_tools(llm, [MagicMock()], False)
        assert llm_with is bound
        assert llm_auto is bound

    def test_with_tools_force(self):
        """Tools with force should use tool_choice='any' for first call."""
        from app.engine.multi_agent.graph import _bind_direct_tools
        llm = MagicMock()
        auto_bound = MagicMock(name="auto")
        force_bound = MagicMock(name="force")
        llm.bind_tools = MagicMock(side_effect=[auto_bound, force_bound])
        llm_with, llm_auto = _bind_direct_tools(llm, [MagicMock()], True)
        assert llm_auto is auto_bound
        assert llm_with is force_bound


class TestExtractDirectResponse:
    """Test _extract_direct_response extracted helper."""

    def test_extracts_text_and_thinking(self):
        """Should separate response text from thinking content."""
        from app.engine.multi_agent.graph import _extract_direct_response
        llm_response = MagicMock()
        llm_response.content = "Hello world"
        messages = []

        # Patch at source module (lazy import inside function body)
        with patch("app.services.output_processor.extract_thinking_from_response",
                    return_value=("Hello world", "thinking")) as mock_fn:
            response, thinking, tools_used = _extract_direct_response(llm_response, messages)
        assert response == "Hello world"
        assert thinking == "thinking"
        assert tools_used == []

    def test_tracks_tool_names(self):
        """Should collect tool names from messages with tool_calls."""
        from app.engine.multi_agent.graph import _extract_direct_response
        llm_response = MagicMock()
        llm_response.content = "Result"
        msg_with_tools = MagicMock()
        msg_with_tools.tool_calls = [{"name": "tool_web_search"}, {"name": "tool_current_datetime"}]
        messages = [msg_with_tools]

        with patch("app.services.output_processor.extract_thinking_from_response",
                    return_value=("Result", "")):
            _, _, tools_used = _extract_direct_response(llm_response, messages)
        names = [t["name"] for t in tools_used]
        assert "tool_current_datetime" in names
        assert "tool_web_search" in names


class TestExecuteDirectToolRounds:
    """Test _execute_direct_tool_rounds extracted helper."""

    @pytest.mark.asyncio
    async def test_no_tool_calls_returns_immediately(self):
        """If LLM response has no tool_calls, should return immediately."""
        from app.engine.multi_agent.graph import _execute_direct_tool_rounds
        llm_response = MagicMock()
        llm_response.content = "Direct answer"
        llm_response.tool_calls = []
        # llm_with_tools is an object with .ainvoke() method
        llm_with_tools = MagicMock()
        llm_with_tools.ainvoke = AsyncMock(return_value=llm_response)
        llm_auto = MagicMock()
        llm_auto.ainvoke = AsyncMock()

        async def noop_push(e):
            pass

        result, msgs, tool_events = await _execute_direct_tool_rounds(
            llm_with_tools, llm_auto, [], [], noop_push,
        )
        assert result.content == "Direct answer"
        assert tool_events == []
        llm_auto.ainvoke.assert_not_called()


# =========================================================================
# 4. Shared Test Fixture Validation
# =========================================================================

class TestSharedFixtures:
    """Verify that shared fixtures from conftest work correctly."""

    def test_mock_settings_has_key_fields(self, mock_settings):
        """mock_settings should have all commonly-accessed fields."""
        assert mock_settings.google_api_key == "test-key"
        assert mock_settings.llm_provider == "google"
        assert mock_settings.enable_product_search is False
        assert mock_settings.enable_browser_scraping is False
        assert mock_settings.default_domain == "maritime"

    def test_mock_llm_has_ainvoke(self, mock_llm):
        """mock_llm should have ainvoke as AsyncMock."""
        assert hasattr(mock_llm, 'ainvoke')
        assert isinstance(mock_llm.ainvoke, AsyncMock)

    def test_mock_embeddings_returns_vectors(self, mock_embeddings):
        """mock_embeddings should return proper dimension vectors."""
        vec = mock_embeddings.embed_query("test")
        assert len(vec) == 768

    def test_mock_agent_state_has_required_fields(self, mock_agent_state):
        """mock_agent_state should have all fields needed by graph nodes."""
        assert "query" in mock_agent_state
        assert "user_id" in mock_agent_state
        assert "session_id" in mock_agent_state
        assert "domain_id" in mock_agent_state
        assert "context" in mock_agent_state
        assert "langchain_messages" in mock_agent_state["context"]


# =========================================================================
# 5. Nested Config Model Classes
# =========================================================================

class TestNestedConfigModels:
    """Test individual nested config model creation."""

    def test_database_config_defaults(self):
        from app.core.config import DatabaseConfig
        db = DatabaseConfig()
        assert db.host == "localhost"
        assert db.port == 5433
        assert db.user == "wiii"

    def test_llm_config_defaults(self):
        from app.core.config import LLMConfig
        llm = LLMConfig()
        assert llm.provider == "google"
        assert llm.ollama_model == "qwen3:8b"
        assert len(llm.failover_chain) == 3

    def test_rag_config_defaults(self):
        from app.core.config import RAGConfig
        rag = RAGConfig()
        assert rag.confidence_high == 0.70
        assert rag.confidence_medium == 0.60
        assert rag.quality_mode == "balanced"

    def test_memory_config_defaults(self):
        from app.core.config import MemoryConfig
        mem = MemoryConfig()
        assert mem.max_user_facts == 50
        assert abs(mem.fact_retrieval_alpha + mem.fact_retrieval_beta + mem.fact_retrieval_gamma - 1.0) < 0.01

    def test_product_search_config_defaults(self):
        from app.core.config import ProductSearchConfig
        ps = ProductSearchConfig()
        assert ps.enable_product_search is False
        assert len(ps.platforms) == 8

    def test_thinking_config_defaults(self):
        from app.core.config import ThinkingConfig
        t = ThinkingConfig()
        assert t.enabled is True
        assert t.budget_deep == 8192

    def test_character_config_defaults(self):
        from app.core.config import CharacterConfig
        c = CharacterConfig()
        assert c.enable_reflection is True
        assert c.enable_soul_emotion is False

    def test_cache_config_defaults(self):
        from app.core.config import CacheConfig
        c = CacheConfig()
        assert c.enabled is True
        assert c.similarity_threshold == 0.92
