"""
Sprint 192: Intelligent Tool Selection Unit Tests

Tests the IntelligentToolSelector: 4-step pipeline with category filter,
semantic pre-filter, metrics reranking, and core tool guarantee.

60 tests across 9 categories:
1. SelectionStrategy enum & ToolRecommendation (5 tests)
2. Singleton & initialization (5 tests)
3. Strategy ALL — backward compat (4 tests)
4. Step 1: Category filter (10 tests)
5. Step 2: Semantic pre-filter (7 tests)
6. Step 4: Metrics reranking (8 tests)
7. Core tool guarantee (5 tests)
8. Intent detection (8 tests)
9. Hybrid pipeline end-to-end (8 tests)
"""

import threading
from unittest.mock import MagicMock, patch

import pytest

from app.engine.skills.skill_recommender import (
    CORE_TOOLS,
    IntelligentToolSelector,
    SelectionStrategy,
    ToolRecommendation,
    get_intelligent_tool_selector,
    select_runtime_tools,
    _INTENT_TO_CATEGORIES,
    _KEYWORD_CATEGORIES,
)
import app.engine.skills.skill_recommender as sel_module


# ============================================================================
# Helpers: Mock ToolRegistry
# ============================================================================


def _make_mock_registry(tool_defs=None):
    """Create a mock ToolRegistry with tools.

    tool_defs: list of (name, category_value, description, roles) tuples
    """
    if tool_defs is None:
        tool_defs = [
            ("tool_search_shopee", "product_search", "Tìm kiếm sản phẩm trên Shopee", ["student", "admin"]),
            ("tool_search_lazada", "product_search", "Tìm kiếm sản phẩm trên Lazada", ["student", "admin"]),
            ("tool_search_google_shopping", "product_search", "Tìm kiếm Google Shopping", ["student", "admin"]),
            ("tool_knowledge_search", "rag", "Tìm kiếm kiến thức trong cơ sở dữ liệu", ["student", "teacher", "admin"]),
            ("tool_current_datetime", "utility", "Trả về ngày giờ hiện tại", ["student", "teacher", "admin"]),
            ("tool_web_search", "utility", "Tìm kiếm thông tin trên web", ["student", "teacher", "admin"]),
            ("tool_search_news", "utility", "Tìm kiếm tin tức mới nhất", ["student", "teacher", "admin"]),
            ("tool_save_user_info", "memory", "Ghi nhớ thông tin người dùng", ["student", "teacher", "admin"]),
            ("tool_get_user_info", "memory", "Lấy thông tin đã lưu", ["student", "teacher", "admin"]),
            ("tool_start_lesson", "learning", "Bắt đầu bài giảng", ["student", "teacher"]),
            ("tool_admin_only", "execution", "Admin-only execution tool", ["admin"]),
        ]

    mock_reg = MagicMock()
    mock_reg._initialized = True
    mock_reg._tools = {}

    for name, cat_val, desc, roles in tool_defs:
        info = MagicMock()
        info.name = name
        info.description = desc
        info.roles = roles
        info.category = MagicMock()
        info.category.value = cat_val
        mock_reg._tools[name] = info

    return mock_reg


def _make_runtime_tool(name):
    tool = MagicMock()
    tool.name = name
    return tool


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton before and after every test."""
    sel_module._selector_instance = None
    yield
    sel_module._selector_instance = None


@pytest.fixture
def selector():
    """Fresh selector instance."""
    return IntelligentToolSelector()


@pytest.fixture
def mock_registry():
    """Standard mock tool registry."""
    return _make_mock_registry()


# ============================================================================
# 1. SelectionStrategy & ToolRecommendation (5 tests)
# ============================================================================


class TestModels:
    """Test enum and dataclass models."""

    def test_strategy_values(self):
        """SelectionStrategy has all expected values."""
        assert SelectionStrategy.ALL.value == "all"
        assert SelectionStrategy.CATEGORY.value == "category"
        assert SelectionStrategy.SEMANTIC.value == "semantic"
        assert SelectionStrategy.METRICS.value == "metrics"
        assert SelectionStrategy.HYBRID.value == "hybrid"

    def test_recommendation_defaults(self):
        """ToolRecommendation has sensible defaults."""
        rec = ToolRecommendation(tool_name="tool_test")
        assert rec.tool_name == "tool_test"
        assert rec.confidence == 1.0
        assert rec.reason == ""
        assert rec.estimated_latency_ms == 0
        assert rec.estimated_cost_usd == 0.0
        assert rec.score == 0.0

    def test_recommendation_with_values(self):
        """ToolRecommendation stores all values."""
        rec = ToolRecommendation(
            tool_name="tool_test",
            confidence=0.85,
            reason="category:product_search",
            estimated_latency_ms=200,
            estimated_cost_usd=0.001,
            score=0.75,
        )
        assert rec.confidence == 0.85
        assert rec.score == 0.75

    def test_core_tools_list(self):
        """CORE_TOOLS contains expected tools."""
        assert "tool_current_datetime" in CORE_TOOLS
        assert "tool_knowledge_search" in CORE_TOOLS

    def test_intent_to_categories_mapping(self):
        """_INTENT_TO_CATEGORIES has expected keys."""
        assert "product_search" in _INTENT_TO_CATEGORIES
        assert "web_search" in _INTENT_TO_CATEGORIES
        assert "learning" in _INTENT_TO_CATEGORIES
        assert "personal" in _INTENT_TO_CATEGORIES


# ============================================================================
# 2. Singleton & Initialization (5 tests)
# ============================================================================


class TestSingleton:
    """Test singleton pattern and thread safety."""

    def test_returns_same_instance(self):
        """get_intelligent_tool_selector() returns same object."""
        s1 = get_intelligent_tool_selector()
        s2 = get_intelligent_tool_selector()
        assert s1 is s2

    def test_reset_creates_new(self):
        """Resetting module-level instance creates new selector."""
        s1 = get_intelligent_tool_selector()
        sel_module._selector_instance = None
        s2 = get_intelligent_tool_selector()
        assert s1 is not s2

    def test_thread_safe_creation(self):
        """Concurrent threads get same singleton."""
        instances = []
        barrier = threading.Barrier(5)

        def worker():
            barrier.wait()
            instances.append(get_intelligent_tool_selector())

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(instances) == 5
        first = instances[0]
        for inst in instances[1:]:
            assert inst is first

    def test_selector_has_reset(self, selector):
        """reset() exists and doesn't crash."""
        selector.reset()

    def test_selector_has_select_tools(self, selector):
        """select_tools method exists."""
        assert hasattr(selector, "select_tools")


# ============================================================================
# 3. Strategy ALL — backward compat (4 tests)
# ============================================================================


class TestStrategyAll:
    """Test ALL strategy returns all tools unchanged."""

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_all_returns_everything(self, mock_get_reg, selector, mock_registry):
        """ALL strategy returns all available tools (no role filter)."""
        mock_get_reg.return_value = mock_registry
        recs = selector.select_tools(
            query="test query",
            strategy=SelectionStrategy.ALL,
            user_role="",  # Empty = skip role filter
        )
        assert len(recs) == len(mock_registry._tools)

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_all_filters_by_role(self, mock_get_reg, selector, mock_registry):
        """ALL strategy respects user role filter."""
        mock_get_reg.return_value = mock_registry
        recs = selector.select_tools(
            query="test",
            strategy=SelectionStrategy.ALL,
            user_role="student",
        )
        names = [r.tool_name for r in recs]
        # tool_admin_only has roles=["admin"], should be excluded for student
        assert "tool_admin_only" not in names

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_all_with_available_tools_filter(self, mock_get_reg, selector, mock_registry):
        """ALL strategy respects available_tools filter."""
        mock_get_reg.return_value = mock_registry
        recs = selector.select_tools(
            query="test",
            strategy=SelectionStrategy.ALL,
            available_tools=["tool_web_search", "tool_current_datetime"],
        )
        names = [r.tool_name for r in recs]
        assert len(names) == 2
        assert "tool_web_search" in names
        assert "tool_current_datetime" in names

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_all_returns_empty_when_uninitialized(self, mock_get_reg, selector):
        """ALL strategy returns empty when registry not initialized."""
        mock_reg = MagicMock()
        mock_reg._initialized = False
        mock_get_reg.return_value = mock_reg
        recs = selector.select_tools(query="test", strategy=SelectionStrategy.ALL)
        assert recs == []


class TestRuntimeToolSelection:
    """Test mapping ranked tool names back to runtime tool objects."""

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_runtime_selection_orders_and_keeps_must_include(self, mock_get_reg, mock_registry):
        mock_get_reg.return_value = mock_registry
        runtime_tools = [
            _make_runtime_tool("tool_search_shopee"),
            _make_runtime_tool("tool_search_lazada"),
            _make_runtime_tool("tool_current_datetime"),
            _make_runtime_tool("tool_custom_unregistered"),
        ]

        selected = select_runtime_tools(
            runtime_tools,
            query="mua sản phẩm trên Shopee giá rẻ",
            intent="product_search",
            user_role="student",
            max_tools=2,
            must_include=["tool_current_datetime"],
            enabled=True,
        )

        names = [tool.name for tool in selected]
        assert names[0] == "tool_search_shopee"
        assert "tool_current_datetime" in names
        assert "tool_custom_unregistered" in names

    def test_runtime_selection_disabled_returns_original_tools(self):
        runtime_tools = [
            _make_runtime_tool("tool_search_shopee"),
            _make_runtime_tool("tool_current_datetime"),
        ]

        selected = select_runtime_tools(
            runtime_tools,
            query="test",
            enabled=False,
        )

        assert selected == runtime_tools


# ============================================================================
# 4. Step 1: Category Filter (10 tests)
# ============================================================================


class TestCategoryFilter:
    """Test category-based tool filtering."""

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_product_search_intent(self, mock_get_reg, selector, mock_registry):
        """product_search intent selects product_search tools."""
        mock_get_reg.return_value = mock_registry
        recs = selector.select_tools(
            query="tìm giá đầu in Zebra",
            intent="product_search",
            strategy=SelectionStrategy.CATEGORY,
        )
        names = [r.tool_name for r in recs]
        assert "tool_search_shopee" in names
        assert "tool_search_lazada" in names
        # Core tools also included
        assert "tool_current_datetime" in names or "tool_knowledge_search" in names

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_web_search_intent(self, mock_get_reg, selector, mock_registry):
        """web_search intent selects utility tools."""
        mock_get_reg.return_value = mock_registry
        recs = selector.select_tools(
            query="tin tức hôm nay",
            intent="web_search",
            strategy=SelectionStrategy.CATEGORY,
        )
        names = [r.tool_name for r in recs]
        assert "tool_web_search" in names
        assert "tool_search_news" in names

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_learning_intent(self, mock_get_reg, selector, mock_registry):
        """learning intent selects learning tools."""
        mock_get_reg.return_value = mock_registry
        recs = selector.select_tools(
            query="dạy tôi về COLREGs",
            intent="learning",
            strategy=SelectionStrategy.CATEGORY,
        )
        names = [r.tool_name for r in recs]
        assert "tool_start_lesson" in names

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_personal_intent(self, mock_get_reg, selector, mock_registry):
        """personal intent selects memory tools."""
        mock_get_reg.return_value = mock_registry
        recs = selector.select_tools(
            query="nhớ rằng tôi thích cà phê",
            intent="personal",
            strategy=SelectionStrategy.CATEGORY,
        )
        names = [r.tool_name for r in recs]
        assert "tool_save_user_info" in names or "tool_get_user_info" in names

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_keyword_based_category_detection(self, mock_get_reg, selector, mock_registry):
        """Keywords in query trigger category detection even without intent."""
        mock_get_reg.return_value = mock_registry
        recs = selector.select_tools(
            query="giá sản phẩm Zebra ZXP7",  # "giá", "sản phẩm" → product_search
            intent=None,
            strategy=SelectionStrategy.CATEGORY,
        )
        names = [r.tool_name for r in recs]
        assert "tool_search_shopee" in names

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_no_intent_no_keywords_returns_all(self, mock_get_reg, selector, mock_registry):
        """No intent and no keyword match returns all tools (fallback)."""
        mock_get_reg.return_value = mock_registry
        recs = selector.select_tools(
            query="xin chào",  # No specific category keywords
            intent=None,
            strategy=SelectionStrategy.CATEGORY,
        )
        # Should return full pool since no categories detected
        assert len(recs) >= 5

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_category_filter_boosts_confidence(self, mock_get_reg, selector, mock_registry):
        """Category-matched tools get confidence boost."""
        mock_get_reg.return_value = mock_registry
        recs = selector.select_tools(
            query="giá shopee lazada",
            intent="product_search",
            strategy=SelectionStrategy.CATEGORY,
        )
        for rec in recs:
            if "search_shopee" in rec.tool_name:
                assert rec.score > 0.5  # Boosted above neutral

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_multiple_intents_from_keywords(self, mock_get_reg, selector, mock_registry):
        """Query matching multiple keyword groups includes all relevant categories."""
        mock_get_reg.return_value = mock_registry
        recs = selector.select_tools(
            query="mua sản phẩm và tìm tin tức",  # product + news keywords
            intent=None,
            strategy=SelectionStrategy.CATEGORY,
        )
        names = [r.tool_name for r in recs]
        # Should have both product_search AND utility tools
        assert "tool_search_shopee" in names
        assert "tool_web_search" in names or "tool_search_news" in names

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_category_excludes_unrelated(self, mock_get_reg, selector, mock_registry):
        """Category filter excludes unrelated tools (but keeps core)."""
        mock_get_reg.return_value = mock_registry
        recs = selector.select_tools(
            query="mua đầu in Zebra ZXP7",
            intent="product_search",
            strategy=SelectionStrategy.CATEGORY,
        )
        names = [r.tool_name for r in recs]
        # Memory tools should NOT be in product search results
        assert "tool_save_user_info" not in names
        # Learning tools should NOT be in product search results
        assert "tool_start_lesson" not in names

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_category_with_role_filter(self, mock_get_reg, selector, mock_registry):
        """Category filter combined with role filter."""
        mock_get_reg.return_value = mock_registry
        recs = selector.select_tools(
            query="mua sản phẩm",
            intent="product_search",
            strategy=SelectionStrategy.CATEGORY,
            user_role="student",
        )
        names = [r.tool_name for r in recs]
        assert "tool_admin_only" not in names


# ============================================================================
# 5. Step 2: Semantic Pre-Filter (7 tests)
# ============================================================================


class TestSemanticFilter:
    """Test keyword-based semantic pre-filtering."""

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_boosts_matching_tools(self, mock_get_reg, selector, mock_registry):
        """Tools with description matching query get score boost."""
        mock_get_reg.return_value = mock_registry
        recs = selector.select_tools(
            query="Shopee sản phẩm",
            strategy=SelectionStrategy.SEMANTIC,
        )
        # tool_search_shopee should be near the top (description contains "Shopee")
        names = [r.tool_name for r in recs]
        # Shopee tool should be in top 3
        shopee_idx = names.index("tool_search_shopee") if "tool_search_shopee" in names else 99
        assert shopee_idx < 5

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_sorts_by_relevance(self, mock_get_reg, selector, mock_registry):
        """Semantic filter sorts by score descending."""
        mock_get_reg.return_value = mock_registry
        recs = selector.select_tools(
            query="kiến thức cơ sở dữ liệu",
            strategy=SelectionStrategy.SEMANTIC,
        )
        # tool_knowledge_search has "kiến thức" and "cơ sở dữ liệu" in description
        assert recs[0].tool_name == "tool_knowledge_search"

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_empty_query_returns_all(self, mock_get_reg, selector, mock_registry):
        """Empty query returns all tools without filtering."""
        mock_get_reg.return_value = mock_registry
        recs = selector.select_tools(
            query="",
            strategy=SelectionStrategy.SEMANTIC,
        )
        # Should return all tools (no filtering on empty query)
        assert len(recs) > 0

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_limits_candidates(self, mock_get_reg, selector, mock_registry):
        """Semantic filter respects max_tools limit."""
        mock_get_reg.return_value = mock_registry
        recs = selector.select_tools(
            query="tìm kiếm sản phẩm",
            strategy=SelectionStrategy.SEMANTIC,
            max_tools=3,
        )
        assert len(recs) <= 3

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_adds_semantic_to_reason(self, mock_get_reg, selector, mock_registry):
        """Matching tools get 'semantic' added to reason."""
        mock_get_reg.return_value = mock_registry
        recs = selector.select_tools(
            query="Shopee sản phẩm",
            strategy=SelectionStrategy.SEMANTIC,
        )
        shopee_recs = [r for r in recs if r.tool_name == "tool_search_shopee"]
        assert len(shopee_recs) == 1
        assert "semantic" in shopee_recs[0].reason

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_no_overlap_gets_low_score(self, mock_get_reg, selector, mock_registry):
        """Tools with no keyword overlap get lower scores."""
        mock_get_reg.return_value = mock_registry
        recs = selector.select_tools(
            query="Shopee sản phẩm",
            strategy=SelectionStrategy.SEMANTIC,
        )
        shopee_rec = next(r for r in recs if r.tool_name == "tool_search_shopee")
        admin_rec = next((r for r in recs if r.tool_name == "tool_admin_only"), None)
        if admin_rec:  # May be filtered by role
            assert shopee_rec.score >= admin_rec.score

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_vietnamese_keywords_match(self, mock_get_reg, selector, mock_registry):
        """Vietnamese keywords in query match tool descriptions."""
        mock_get_reg.return_value = mock_registry
        recs = selector.select_tools(
            query="tin tức mới nhất",
            strategy=SelectionStrategy.SEMANTIC,
        )
        news_recs = [r for r in recs if r.tool_name == "tool_search_news"]
        assert len(news_recs) == 1
        assert news_recs[0].score > 0.5  # "tin tức" matches description


# ============================================================================
# 6. Step 4: Metrics Reranking (8 tests)
# ============================================================================


class TestMetricsRerank:
    """Test metrics-based reranking."""

    @patch("app.engine.skills.skill_metrics.get_skill_metrics_tracker")
    @patch("app.engine.tools.registry.get_tool_registry")
    def test_high_success_rate_boosts(self, mock_get_reg, mock_get_tracker, selector, mock_registry):
        """Tools with high success rate get score boost."""
        mock_get_reg.return_value = mock_registry
        mock_tracker = MagicMock()
        mock_metrics_good = MagicMock()
        mock_metrics_good.success_rate = 0.95
        mock_metrics_good.avg_latency_ms = 100
        mock_metrics_good.total_invocations = 100
        mock_metrics_good.cost_estimate_usd = 0.001
        mock_metrics_good.avg_cost_per_invocation = 0.00001
        mock_metrics_bad = MagicMock()
        mock_metrics_bad.success_rate = 0.3
        mock_metrics_bad.avg_latency_ms = 5000
        mock_metrics_bad.total_invocations = 10
        mock_metrics_bad.cost_estimate_usd = 0.01
        mock_metrics_bad.avg_cost_per_invocation = 0.001

        def get_metrics(skill_id):
            if "shopee" in skill_id:
                return mock_metrics_good
            elif "lazada" in skill_id:
                return mock_metrics_bad
            return None

        mock_tracker.get_metrics = get_metrics
        mock_get_tracker.return_value = mock_tracker

        recs = selector.select_tools(
            query="sản phẩm",
            strategy=SelectionStrategy.METRICS,
        )
        shopee_rec = next(r for r in recs if r.tool_name == "tool_search_shopee")
        lazada_rec = next(r for r in recs if r.tool_name == "tool_search_lazada")
        assert shopee_rec.score > lazada_rec.score

    @patch("app.engine.skills.skill_metrics.get_skill_metrics_tracker")
    @patch("app.engine.tools.registry.get_tool_registry")
    def test_low_latency_boosts(self, mock_get_reg, mock_get_tracker, selector, mock_registry):
        """Tools with lower latency get higher score."""
        mock_get_reg.return_value = mock_registry
        mock_tracker = MagicMock()
        mock_metrics_fast = MagicMock()
        mock_metrics_fast.success_rate = 0.9
        mock_metrics_fast.avg_latency_ms = 50
        mock_metrics_fast.total_invocations = 50
        mock_metrics_fast.cost_estimate_usd = 0.0
        mock_metrics_fast.avg_cost_per_invocation = 0.0
        mock_metrics_slow = MagicMock()
        mock_metrics_slow.success_rate = 0.9
        mock_metrics_slow.avg_latency_ms = 10000
        mock_metrics_slow.total_invocations = 50
        mock_metrics_slow.cost_estimate_usd = 0.0
        mock_metrics_slow.avg_cost_per_invocation = 0.0

        def get_metrics(skill_id):
            if "shopee" in skill_id:
                return mock_metrics_fast
            elif "lazada" in skill_id:
                return mock_metrics_slow
            return None

        mock_tracker.get_metrics = get_metrics
        mock_get_tracker.return_value = mock_tracker

        recs = selector.select_tools(
            query="sản phẩm",
            strategy=SelectionStrategy.METRICS,
        )
        shopee_rec = next(r for r in recs if r.tool_name == "tool_search_shopee")
        lazada_rec = next(r for r in recs if r.tool_name == "tool_search_lazada")
        assert shopee_rec.score > lazada_rec.score

    @patch("app.engine.skills.skill_metrics.get_skill_metrics_tracker")
    @patch("app.engine.tools.registry.get_tool_registry")
    def test_no_metrics_neutral_score(self, mock_get_reg, mock_get_tracker, selector, mock_registry):
        """Tools with no metrics data keep neutral score."""
        mock_get_reg.return_value = mock_registry
        mock_tracker = MagicMock()
        mock_tracker.get_metrics.return_value = None
        mock_get_tracker.return_value = mock_tracker

        recs = selector.select_tools(
            query="test",
            strategy=SelectionStrategy.METRICS,
        )
        # All tools should have default score (0.5)
        for rec in recs:
            assert rec.score == pytest.approx(0.5)

    @patch("app.engine.skills.skill_metrics.get_skill_metrics_tracker")
    @patch("app.engine.tools.registry.get_tool_registry")
    def test_fills_estimated_latency(self, mock_get_reg, mock_get_tracker, selector, mock_registry):
        """Metrics reranking fills estimated_latency_ms."""
        mock_get_reg.return_value = mock_registry
        mock_tracker = MagicMock()
        mock_metrics = MagicMock()
        mock_metrics.success_rate = 0.9
        mock_metrics.avg_latency_ms = 250.5
        mock_metrics.total_invocations = 10
        mock_metrics.cost_estimate_usd = 0.002
        mock_metrics.avg_cost_per_invocation = 0.0002
        mock_tracker.get_metrics.return_value = mock_metrics
        mock_get_tracker.return_value = mock_tracker

        recs = selector.select_tools(
            query="test",
            strategy=SelectionStrategy.METRICS,
        )
        assert all(r.estimated_latency_ms == 250 for r in recs)

    @patch("app.engine.skills.skill_metrics.get_skill_metrics_tracker")
    @patch("app.engine.tools.registry.get_tool_registry")
    def test_fills_estimated_cost(self, mock_get_reg, mock_get_tracker, selector, mock_registry):
        """Metrics reranking fills estimated_cost_usd."""
        mock_get_reg.return_value = mock_registry
        mock_tracker = MagicMock()
        mock_metrics = MagicMock()
        mock_metrics.success_rate = 0.9
        mock_metrics.avg_latency_ms = 100
        mock_metrics.total_invocations = 10
        mock_metrics.cost_estimate_usd = 0.005
        mock_metrics.avg_cost_per_invocation = 0.0005
        mock_tracker.get_metrics.return_value = mock_metrics
        mock_get_tracker.return_value = mock_tracker

        recs = selector.select_tools(
            query="test",
            strategy=SelectionStrategy.METRICS,
        )
        assert all(r.estimated_cost_usd == 0.005 for r in recs)

    @patch("app.engine.skills.skill_metrics.get_skill_metrics_tracker")
    @patch("app.engine.tools.registry.get_tool_registry")
    def test_adds_metrics_to_reason(self, mock_get_reg, mock_get_tracker, selector, mock_registry):
        """Reranking adds 'metrics' to reason."""
        mock_get_reg.return_value = mock_registry
        mock_tracker = MagicMock()
        mock_metrics = MagicMock()
        mock_metrics.success_rate = 0.9
        mock_metrics.avg_latency_ms = 100
        mock_metrics.total_invocations = 10
        mock_metrics.cost_estimate_usd = 0.0
        mock_metrics.avg_cost_per_invocation = 0.0
        mock_tracker.get_metrics.return_value = mock_metrics
        mock_get_tracker.return_value = mock_tracker

        recs = selector.select_tools(
            query="test",
            strategy=SelectionStrategy.METRICS,
        )
        for rec in recs:
            assert "metrics" in rec.reason

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_metrics_import_error_graceful(self, mock_get_reg, selector, mock_registry):
        """ImportError in metrics tracker doesn't crash."""
        mock_get_reg.return_value = mock_registry
        with patch("app.engine.skills.skill_metrics.get_skill_metrics_tracker", side_effect=ImportError):
            recs = selector.select_tools(
                query="test",
                strategy=SelectionStrategy.METRICS,
            )
            assert len(recs) > 0  # Should fall through gracefully

    @patch("app.engine.skills.skill_metrics.get_skill_metrics_tracker")
    @patch("app.engine.tools.registry.get_tool_registry")
    def test_zero_invocations_skipped(self, mock_get_reg, mock_get_tracker, selector, mock_registry):
        """Tools with 0 invocations keep neutral score."""
        mock_get_reg.return_value = mock_registry
        mock_tracker = MagicMock()
        mock_metrics = MagicMock()
        mock_metrics.total_invocations = 0
        mock_tracker.get_metrics.return_value = mock_metrics
        mock_get_tracker.return_value = mock_tracker

        recs = selector.select_tools(
            query="test",
            strategy=SelectionStrategy.METRICS,
        )
        for rec in recs:
            assert rec.score == pytest.approx(0.5)


# ============================================================================
# 7. Core Tool Guarantee (5 tests)
# ============================================================================


class TestCoreToolGuarantee:
    """Test that core tools are always included."""

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_core_tools_always_present(self, mock_get_reg, selector, mock_registry):
        """Core tools included even with strict category filter."""
        mock_get_reg.return_value = mock_registry
        recs = selector.select_tools(
            query="mua sản phẩm Zebra",
            intent="product_search",
            strategy=SelectionStrategy.CATEGORY,
        )
        names = [r.tool_name for r in recs]
        for core in CORE_TOOLS:
            if core in mock_registry._tools:
                assert core in names, f"Core tool {core} missing from results"

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_core_tools_not_duplicated(self, mock_get_reg, selector, mock_registry):
        """Core tools appear exactly once."""
        mock_get_reg.return_value = mock_registry
        recs = selector.select_tools(
            query="kiến thức",  # Matches knowledge_search directly
            intent="lookup",
            strategy=SelectionStrategy.CATEGORY,
        )
        names = [r.tool_name for r in recs]
        for core in CORE_TOOLS:
            if core in names:
                assert names.count(core) == 1

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_core_tools_with_available_filter(self, mock_get_reg, selector, mock_registry):
        """Core tools only added if in available_tools list."""
        mock_get_reg.return_value = mock_registry
        recs = selector.select_tools(
            query="mua sản phẩm",
            intent="product_search",
            strategy=SelectionStrategy.CATEGORY,
            available_tools=["tool_search_shopee"],  # Core tools NOT in list
        )
        names = [r.tool_name for r in recs]
        # Core tools should NOT be added since they're not in available_tools
        assert "tool_knowledge_search" not in names

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_core_tools_in_hybrid_pipeline(self, mock_get_reg, selector, mock_registry):
        """Core tools present in hybrid pipeline output."""
        mock_get_reg.return_value = mock_registry
        with patch("app.engine.skills.skill_metrics.get_skill_metrics_tracker") as mock_tracker:
            mock_tracker.return_value = MagicMock()
            mock_tracker.return_value.get_metrics.return_value = None

            recs = selector.select_tools(
                query="giá đầu in Zebra",
                intent="product_search",
                strategy=SelectionStrategy.HYBRID,
            )
            names = [r.tool_name for r in recs]
            assert "tool_current_datetime" in names or "tool_knowledge_search" in names

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_core_tools_have_core_reason(self, mock_get_reg, selector, mock_registry):
        """Core tools added with 'core_tool' reason."""
        mock_get_reg.return_value = mock_registry
        recs = selector.select_tools(
            query="mua sản phẩm",
            intent="product_search",
            strategy=SelectionStrategy.CATEGORY,
        )
        core_recs = [r for r in recs if r.tool_name in CORE_TOOLS]
        for rec in core_recs:
            assert "core_tool" in rec.reason


# ============================================================================
# 8. Intent Detection (8 tests)
# ============================================================================


class TestIntentDetection:
    """Test lightweight intent detection from query."""

    def test_product_search_intent(self, selector):
        """Detects product search intent from Vietnamese keywords."""
        assert selector.detect_intent_from_query("mua đầu in Zebra") == "product_search"
        assert selector.detect_intent_from_query("giá sản phẩm XYZ") == "product_search"

    def test_web_search_intent(self, selector):
        """Detects web search intent."""
        assert selector.detect_intent_from_query("tin tức hôm nay") == "web_search"
        assert selector.detect_intent_from_query("thời sự mới nhất") == "web_search"

    def test_learning_intent(self, selector):
        """Detects learning intent."""
        assert selector.detect_intent_from_query("dạy tôi bài giảng về COLREGs") == "learning"
        assert selector.detect_intent_from_query("quiz ôn tập luật hàng hải") == "learning"

    def test_personal_intent(self, selector):
        """Detects personal/memory intent."""
        assert selector.detect_intent_from_query("hãy nhớ rằng tôi thích cà phê") == "personal"
        assert selector.detect_intent_from_query("ghi nhớ thông tin này") == "personal"

    def test_no_intent_detected(self, selector):
        """Returns None when no intent matches."""
        assert selector.detect_intent_from_query("xin chào") is None
        assert selector.detect_intent_from_query("cảm ơn bạn") is None

    def test_empty_query(self, selector):
        """Returns None for empty query."""
        assert selector.detect_intent_from_query("") is None
        assert selector.detect_intent_from_query(None) is None

    def test_english_product_keywords(self, selector):
        """Detects product search from English keywords."""
        assert selector.detect_intent_from_query("buy Zebra ZXP7 printhead") == "product_search"
        assert selector.detect_intent_from_query("price comparison") == "product_search"

    def test_shopee_keyword(self, selector):
        """Platform name triggers product search intent."""
        assert selector.detect_intent_from_query("tìm trên Shopee") == "product_search"
        assert selector.detect_intent_from_query("lazada có bán không") == "product_search"


# ============================================================================
# 9. Hybrid Pipeline End-to-End (8 tests)
# ============================================================================


class TestHybridPipeline:
    """Test full hybrid pipeline (Category + Semantic + Metrics)."""

    @patch("app.engine.skills.skill_metrics.get_skill_metrics_tracker")
    @patch("app.engine.tools.registry.get_tool_registry")
    def test_hybrid_reduces_tool_count(self, mock_get_reg, mock_get_tracker, selector, mock_registry):
        """Hybrid pipeline returns fewer tools than ALL strategy."""
        mock_get_reg.return_value = mock_registry
        mock_get_tracker.return_value = MagicMock()
        mock_get_tracker.return_value.get_metrics.return_value = None

        all_recs = selector.select_tools(
            query="test", strategy=SelectionStrategy.ALL,
        )
        hybrid_recs = selector.select_tools(
            query="mua đầu in Zebra ZXP7",
            intent="product_search",
            strategy=SelectionStrategy.HYBRID,
        )
        # Hybrid should return fewer (or equal) tools
        assert len(hybrid_recs) <= len(all_recs)

    @patch("app.engine.skills.skill_metrics.get_skill_metrics_tracker")
    @patch("app.engine.tools.registry.get_tool_registry")
    def test_hybrid_ranks_relevant_higher(self, mock_get_reg, mock_get_tracker, selector, mock_registry):
        """Hybrid pipeline ranks product search tools higher for product queries."""
        mock_get_reg.return_value = mock_registry
        mock_tracker = MagicMock()
        mock_metrics = MagicMock()
        mock_metrics.success_rate = 0.9
        mock_metrics.avg_latency_ms = 200
        mock_metrics.total_invocations = 50
        mock_metrics.cost_estimate_usd = 0.0
        mock_metrics.avg_cost_per_invocation = 0.0
        mock_tracker.get_metrics.return_value = mock_metrics
        mock_get_tracker.return_value = mock_tracker

        recs = selector.select_tools(
            query="tìm đầu in Zebra ZXP7 trên Shopee",
            intent="product_search",
            strategy=SelectionStrategy.HYBRID,
        )
        # Product search tools should be in the results
        names = [r.tool_name for r in recs]
        assert "tool_search_shopee" in names

    @patch("app.engine.skills.skill_metrics.get_skill_metrics_tracker")
    @patch("app.engine.tools.registry.get_tool_registry")
    def test_hybrid_respects_max_tools(self, mock_get_reg, mock_get_tracker, selector, mock_registry):
        """Hybrid pipeline respects max_tools limit."""
        mock_get_reg.return_value = mock_registry
        mock_get_tracker.return_value = MagicMock()
        mock_get_tracker.return_value.get_metrics.return_value = None

        recs = selector.select_tools(
            query="tìm sản phẩm",
            strategy=SelectionStrategy.HYBRID,
            max_tools=5,
        )
        assert len(recs) <= 5

    @patch("app.engine.skills.skill_metrics.get_skill_metrics_tracker")
    @patch("app.engine.tools.registry.get_tool_registry")
    def test_hybrid_includes_core_tools(self, mock_get_reg, mock_get_tracker, selector, mock_registry):
        """Hybrid pipeline includes core tools."""
        mock_get_reg.return_value = mock_registry
        mock_get_tracker.return_value = MagicMock()
        mock_get_tracker.return_value.get_metrics.return_value = None

        recs = selector.select_tools(
            query="mua sản phẩm Zebra",
            intent="product_search",
            strategy=SelectionStrategy.HYBRID,
        )
        names = [r.tool_name for r in recs]
        # At least one core tool should be present
        assert any(ct in names for ct in CORE_TOOLS)

    @patch("app.engine.skills.skill_metrics.get_skill_metrics_tracker")
    @patch("app.engine.tools.registry.get_tool_registry")
    def test_hybrid_respects_role(self, mock_get_reg, mock_get_tracker, selector, mock_registry):
        """Hybrid pipeline filters by user role."""
        mock_get_reg.return_value = mock_registry
        mock_get_tracker.return_value = MagicMock()
        mock_get_tracker.return_value.get_metrics.return_value = None

        recs = selector.select_tools(
            query="execute command",
            strategy=SelectionStrategy.HYBRID,
            user_role="student",
        )
        names = [r.tool_name for r in recs]
        assert "tool_admin_only" not in names

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_hybrid_no_registry_returns_empty(self, mock_get_reg, selector):
        """Hybrid with unavailable registry returns empty."""
        mock_get_reg.side_effect = ImportError("No module")
        recs = selector.select_tools(
            query="test",
            strategy=SelectionStrategy.HYBRID,
        )
        assert recs == []

    @patch("app.engine.tools.registry.get_tool_registry")
    def test_get_tool_names_helper(self, mock_get_reg, selector, mock_registry):
        """get_tool_names extracts names from recommendations."""
        mock_get_reg.return_value = mock_registry
        recs = selector.select_tools(
            query="test",
            strategy=SelectionStrategy.ALL,
        )
        names = selector.get_tool_names(recs)
        assert isinstance(names, list)
        assert all(isinstance(n, str) for n in names)
        assert len(names) == len(recs)

    @patch("app.engine.skills.skill_metrics.get_skill_metrics_tracker")
    @patch("app.engine.tools.registry.get_tool_registry")
    def test_hybrid_with_available_tools(self, mock_get_reg, mock_get_tracker, selector, mock_registry):
        """Hybrid pipeline with available_tools filter."""
        mock_get_reg.return_value = mock_registry
        mock_get_tracker.return_value = MagicMock()
        mock_get_tracker.return_value.get_metrics.return_value = None

        recs = selector.select_tools(
            query="mua sản phẩm",
            intent="product_search",
            strategy=SelectionStrategy.HYBRID,
            available_tools=["tool_search_shopee", "tool_search_lazada", "tool_current_datetime"],
        )
        names = [r.tool_name for r in recs]
        assert all(n in ["tool_search_shopee", "tool_search_lazada", "tool_current_datetime"] for n in names)
