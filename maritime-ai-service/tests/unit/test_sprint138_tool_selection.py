"""
Tests for Sprint 138: Intelligent Tool Selection — Semantic Pre-Filtering.

Tests:
- ToolSelector initialization and embedding caching
- select_tools returns top_k most relevant
- Core tools always included regardless of similarity
- Embedding failure fallback to all tools
- Feature gate off = existing behavior
- Tool description extraction from registry
- ToolSelector cosine similarity correctness
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List


# ============================================================================
# Config Settings
# ============================================================================

class TestToolSelectionConfig:
    """Test Sprint 138 configuration settings."""

    def test_config_has_tool_selection_settings(self):
        from app.core.config import Settings

        s = Settings(
            enable_tool_selection=False,
            tool_selection_top_k=5,
            tool_selection_core_tools=["tool_current_datetime", "tool_knowledge_search"],
        )
        assert s.enable_tool_selection is False
        assert s.tool_selection_top_k == 5
        assert len(s.tool_selection_core_tools) == 2

    def test_config_defaults(self):
        from app.core.config import Settings

        s = Settings()
        assert s.enable_tool_selection is False  # Disabled by default
        assert s.tool_selection_top_k == 5


# ============================================================================
# ToolSelector Creation
# ============================================================================

class TestToolSelectorCreation:
    """Test ToolSelector initialization."""

    def test_tool_selector_import(self):
        from app.engine.tools.tool_selector import ToolSelector

        selector = ToolSelector()
        assert not selector._initialized

    def test_tool_selector_singleton(self):
        import app.engine.tools.tool_selector as mod

        old = mod._selector_instance
        mod._selector_instance = None
        try:
            s1 = mod.get_tool_selector()
            s2 = mod.get_tool_selector()
            assert s1 is s2
        finally:
            mod._selector_instance = old

    @pytest.mark.asyncio
    async def test_initialize_indexes_tools(self):
        from app.engine.tools.tool_selector import ToolSelector

        selector = ToolSelector()

        # Mock tools
        tool1 = MagicMock()
        tool1.name = "tool_search"
        tool1.description = "Search knowledge base"
        tool2 = MagicMock()
        tool2.name = "tool_datetime"
        tool2.description = "Get current date and time"

        # Mock embeddings
        mock_emb = MagicMock()
        mock_emb.aembed_documents = AsyncMock(return_value=[
            [0.1] * 768,
            [0.2] * 768,
        ])

        # Lazy import inside initialize() — patch at source module
        with patch(
            "app.engine.gemini_embedding.GeminiOptimizedEmbeddings",
            return_value=mock_emb,
        ):
            await selector.initialize([tool1, tool2])

        assert selector._initialized
        assert "tool_search" in selector._tool_embeddings
        assert "tool_datetime" in selector._tool_embeddings

    @pytest.mark.asyncio
    async def test_initialize_handles_failure(self):
        from app.engine.tools.tool_selector import ToolSelector

        selector = ToolSelector()

        # Lazy import inside initialize() — patch at source module
        with patch(
            "app.engine.gemini_embedding.GeminiOptimizedEmbeddings",
            side_effect=Exception("No API key"),
        ):
            await selector.initialize([MagicMock(name="t1")])

        assert not selector._initialized


# ============================================================================
# select_tools
# ============================================================================

class TestSelectTools:
    """Test ToolSelector.select_tools method."""

    def _make_tool(self, name: str, desc: str = ""):
        t = MagicMock()
        t.name = name
        t.description = desc or f"Description for {name}"
        return t

    @pytest.mark.asyncio
    async def test_feature_flag_off_returns_all(self):
        """When enable_tool_selection=False, all tools returned."""
        from app.engine.tools.tool_selector import ToolSelector

        selector = ToolSelector()
        tools = [self._make_tool("t1"), self._make_tool("t2"), self._make_tool("t3")]

        # Lazy import: patch settings at source module
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.enable_tool_selection = False
            result = await selector.select_tools("query", tools)

        assert result == tools

    @pytest.mark.asyncio
    async def test_returns_top_k_tools(self):
        """Should return at most top_k tools."""
        from app.engine.tools.tool_selector import ToolSelector

        selector = ToolSelector()
        selector._initialized = True

        # Create 10 tools
        tools = [self._make_tool(f"tool_{i}") for i in range(10)]

        # Mock embeddings
        mock_emb = MagicMock()
        mock_emb.aembed_query = AsyncMock(return_value=[0.5] * 768)
        selector._embeddings = mock_emb

        # Assign different embeddings to each tool
        for i, tool in enumerate(tools):
            name = tool.name
            emb = [0.0] * 768
            emb[i] = 1.0  # Distinct direction
            selector._tool_embeddings[name] = emb
            selector._tool_map[name] = tool

        # Lazy import: patch settings at source module
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.enable_tool_selection = True
            mock_settings.tool_selection_top_k = 3
            mock_settings.tool_selection_core_tools = []
            result = await selector.select_tools(
                "test query", tools, top_k=3, core_tool_names=[]
            )

        assert len(result) <= 3

    @pytest.mark.asyncio
    async def test_core_tools_always_included(self):
        """Core tools must always be in the result."""
        from app.engine.tools.tool_selector import ToolSelector

        selector = ToolSelector()
        selector._initialized = True

        core_tool = self._make_tool("tool_current_datetime")
        other_tool = self._make_tool("tool_search")
        low_score_tool = self._make_tool("tool_rare")

        tools = [core_tool, other_tool, low_score_tool]

        mock_emb = MagicMock()
        mock_emb.aembed_query = AsyncMock(return_value=[1.0] + [0.0] * 767)
        selector._embeddings = mock_emb

        # Give core tool very low similarity
        selector._tool_embeddings["tool_current_datetime"] = [0.0] * 768
        selector._tool_embeddings["tool_search"] = [1.0] + [0.0] * 767
        selector._tool_embeddings["tool_rare"] = [0.0] * 768
        selector._tool_map = {t.name: t for t in tools}

        # Lazy import: patch settings at source module
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.enable_tool_selection = True
            mock_settings.tool_selection_top_k = 2
            mock_settings.tool_selection_core_tools = ["tool_current_datetime"]
            result = await selector.select_tools(
                "search query",
                tools,
                top_k=2,
                core_tool_names=["tool_current_datetime"],
            )

        result_names = [t.name for t in result]
        assert "tool_current_datetime" in result_names

    @pytest.mark.asyncio
    async def test_fallback_on_embedding_failure(self):
        """If query embedding fails, return all tools."""
        from app.engine.tools.tool_selector import ToolSelector

        selector = ToolSelector()
        selector._initialized = True

        mock_emb = MagicMock()
        mock_emb.aembed_query = AsyncMock(return_value=[])  # Empty = failure
        selector._embeddings = mock_emb

        tools = [self._make_tool("t1"), self._make_tool("t2")]

        # Lazy import: patch settings at source module
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.enable_tool_selection = True
            mock_settings.tool_selection_core_tools = []
            result = await selector.select_tools("query", tools)

        assert result == tools

    @pytest.mark.asyncio
    async def test_not_initialized_returns_all(self):
        """If not initialized, return all tools."""
        from app.engine.tools.tool_selector import ToolSelector

        selector = ToolSelector()
        assert not selector._initialized

        tools = [self._make_tool("t1"), self._make_tool("t2")]

        # Lazy imports: patch at source modules
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.enable_tool_selection = True
            mock_settings.tool_selection_core_tools = []
            with patch(
                "app.engine.gemini_embedding.GeminiOptimizedEmbeddings",
                side_effect=Exception("No key"),
            ):
                result = await selector.select_tools("query", tools)

        assert result == tools


# ============================================================================
# Cosine Similarity
# ============================================================================

class TestCosineSimilarity:
    """Test ToolSelector._cosine_similarity static method."""

    def test_identical_vectors(self):
        from app.engine.tools.tool_selector import ToolSelector

        a = [1.0, 0.0, 0.0]
        b = [1.0, 0.0, 0.0]
        assert ToolSelector._cosine_similarity(a, b) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        from app.engine.tools.tool_selector import ToolSelector

        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        assert ToolSelector._cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        from app.engine.tools.tool_selector import ToolSelector

        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert ToolSelector._cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_empty_vectors(self):
        from app.engine.tools.tool_selector import ToolSelector

        assert ToolSelector._cosine_similarity([], []) == 0.0

    def test_zero_vector(self):
        from app.engine.tools.tool_selector import ToolSelector

        a = [0.0, 0.0, 0.0]
        b = [1.0, 0.0, 0.0]
        assert ToolSelector._cosine_similarity(a, b) == 0.0

    def test_different_lengths(self):
        from app.engine.tools.tool_selector import ToolSelector

        a = [1.0, 0.0]
        b = [1.0, 0.0, 0.0]
        assert ToolSelector._cosine_similarity(a, b) == 0.0


# ============================================================================
# Tool Description Export
# ============================================================================

class TestToolDescriptionExport:
    """Test ToolRegistry.get_tool_descriptions method."""

    def test_get_tool_descriptions(self):
        from app.engine.tools.registry import ToolRegistry, ToolCategory, ToolAccess

        registry = ToolRegistry()

        tool1 = MagicMock()
        tool1.name = "tool_search"
        tool1.description = "Search the knowledge base"

        tool2 = MagicMock()
        tool2.name = "tool_datetime"
        tool2.description = "Get current date and time"

        registry.register(tool1, ToolCategory.RAG, description="Search the knowledge base")
        registry.register(tool2, ToolCategory.UTILITY, description="Get current date and time")

        descriptions = registry.get_tool_descriptions()

        assert "tool_search" in descriptions
        assert "tool_datetime" in descriptions
        assert descriptions["tool_search"] == "Search the knowledge base"
        assert descriptions["tool_datetime"] == "Get current date and time"

    def test_get_tool_descriptions_empty(self):
        from app.engine.tools.registry import ToolRegistry

        registry = ToolRegistry()
        descriptions = registry.get_tool_descriptions()
        assert descriptions == {}
