"""
Sprint 195: "Nâng Cấp Trí Tuệ" — Search & Skill Architecture Upgrade Tests

Tests cover:
1. unified_index.py registry._initialized fix
2. skill_metrics.py flush reliability (re-queue on failure)
3. ChainedAdapter + StrategyManager integration
4. ChainedAdapter empty results = soft failure
5. StrategyManager cache TTL expiration
6. JinaReaderAdapter
7. Progressive disclosure (L1/L2/L3) on UnifiedSkillManifest
8. BM25 skill search (skill_search.py)
9. Cost tracking in SkillMetricsTracker
10. Cost factor in IntelligentToolSelector metrics reranking
"""

import math
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ======================================================================
# 1. unified_index.py — registry._initialized fix
# ======================================================================


class TestUnifiedIndexRegistryFix:
    """Verify UnifiedSkillIndex no longer checks registry._initialized."""

    def test_load_from_tool_registry_with_tools(self):
        """Should load tools when registry has _tools populated."""
        from app.engine.skills.unified_index import _load_from_tool_registry

        mock_registry = MagicMock()
        mock_registry._tools = {
            "tool_search_shopee": MagicMock(
                description="Search Shopee",
                category=MagicMock(value="product_search"),
                roles=["student", "admin"],
                name="tool_search_shopee",
            ),
        }

        with patch(
            "app.engine.tools.registry.get_tool_registry",
            return_value=mock_registry,
        ):
            results = _load_from_tool_registry()

        assert len(results) == 1
        assert results[0].id == "tool:tool_search_shopee"
        assert results[0].name == "tool_search_shopee"

    def test_load_from_tool_registry_empty(self):
        """Should return empty list when registry has no tools."""
        from app.engine.skills.unified_index import _load_from_tool_registry

        mock_registry = MagicMock()
        mock_registry._tools = {}

        with patch(
            "app.engine.tools.registry.get_tool_registry",
            return_value=mock_registry,
        ):
            results = _load_from_tool_registry()

        assert results == []

    def test_load_from_tool_registry_no_initialized_attr(self):
        """Should NOT crash when registry lacks _initialized attribute."""
        from app.engine.skills.unified_index import _load_from_tool_registry

        mock_registry = MagicMock(spec=[])  # No attributes at all
        mock_registry._tools = {"test": MagicMock(
            description="test", category=None, roles=None, name="test",
        )}

        with patch(
            "app.engine.tools.registry.get_tool_registry",
            return_value=mock_registry,
        ):
            results = _load_from_tool_registry()

        assert len(results) == 1

    def test_skill_recommender_registry_fix(self):
        """IntelligentToolSelector._get_tool_pool should also handle missing _initialized."""
        from app.engine.skills.skill_recommender import IntelligentToolSelector

        selector = IntelligentToolSelector()
        mock_registry = MagicMock()
        mock_registry._tools = {}

        with patch(
            "app.engine.tools.registry.get_tool_registry",
            return_value=mock_registry,
        ):
            pool = selector._get_tool_pool(None, "student")

        assert pool == []


# ======================================================================
# 2. skill_metrics.py — flush reliability
# ======================================================================


class TestSkillMetricsFlushReliability:
    """Verify metrics are re-queued on flush failure."""

    def test_flush_re_queues_on_sync_failure(self):
        """When sync flush fails, records should be re-queued."""
        from app.engine.skills.skill_metrics import SkillMetricsTracker

        tracker = SkillMetricsTracker()
        tracker.record_invocation("tool:test", True, latency_ms=100)
        assert tracker.pending_count == 1

        # Mock DB write to fail
        with patch.object(tracker, '_write_records_to_db', side_effect=Exception("DB down")):
            flushed = tracker.flush_to_db()

        assert flushed == 0
        assert tracker.pending_count == 1  # Re-queued

    def test_flush_clears_on_success(self):
        """When flush succeeds, pending records should be cleared."""
        from app.engine.skills.skill_metrics import SkillMetricsTracker

        tracker = SkillMetricsTracker()
        tracker.record_invocation("tool:test", True, latency_ms=100)

        with patch.object(tracker, '_write_records_to_db'):
            flushed = tracker.flush_to_db()

        assert flushed == 1
        assert tracker.pending_count == 0

    def test_ema_latency_calculation(self):
        """EMA latency should weight 30% new, 70% old."""
        from app.engine.skills.skill_metrics import SkillMetricsTracker

        tracker = SkillMetricsTracker()
        tracker.record_invocation("tool:a", True, latency_ms=1000)
        m = tracker.get_metrics("tool:a")
        assert m.avg_latency_ms == pytest.approx(300.0, abs=1)  # 0.3 * 1000

        tracker.record_invocation("tool:a", True, latency_ms=500)
        m = tracker.get_metrics("tool:a")
        # 0.3 * 500 + 0.7 * 300 = 150 + 210 = 360
        assert m.avg_latency_ms == pytest.approx(360.0, abs=1)


# ======================================================================
# 3. ChainedAdapter + StrategyManager integration
# ======================================================================


class TestChainedAdapterStrategyIntegration:
    """Verify ChainedAdapter feeds metrics to ScrapingStrategyManager."""

    def _make_adapter(self, backend_value, results=None, raises=None):
        """Create a mock adapter."""
        from app.engine.search_platforms.base import BackendType, PlatformConfig

        adapter = MagicMock()
        config = PlatformConfig(
            id=f"test_{backend_value}",
            display_name=f"Test {backend_value}",
            backend=BackendType(backend_value) if backend_value in [bt.value for bt in BackendType] else BackendType.CUSTOM,
            priority=0,
        )
        adapter.get_config.return_value = config

        if raises:
            adapter.search_sync.side_effect = raises
        else:
            adapter.search_sync.return_value = results or []

        return adapter

    def test_success_updates_strategy_metrics(self):
        """On success, ChainedAdapter should call _update_strategy_metrics."""
        from app.engine.search_platforms.base import BackendType, ProductSearchResult
        from app.engine.search_platforms.chained_adapter import ChainedAdapter

        result = ProductSearchResult(platform="test", title="Test Product")
        adapter = self._make_adapter("serper", results=[result])
        chain = ChainedAdapter("test_platform", "Test", [adapter])

        with patch.object(chain, '_update_strategy_metrics') as mock_update:
            results = chain.search_sync("test query")

        assert len(results) == 1
        mock_update.assert_called_once()
        args = mock_update.call_args
        assert args[0][1] is True  # success=True

    def test_failure_updates_strategy_metrics(self):
        """On exception, ChainedAdapter should call _update_strategy_metrics with success=False."""
        from app.engine.search_platforms.chained_adapter import ChainedAdapter

        adapter = self._make_adapter("serper", raises=Exception("timeout"))
        chain = ChainedAdapter("test_platform", "Test", [adapter])

        with patch.object(chain, '_update_strategy_metrics') as mock_update:
            results = chain.search_sync("test query")

        assert len(results) == 0
        mock_update.assert_called_once()
        args = mock_update.call_args
        assert args[0][1] is False  # success=False

    def test_empty_results_treated_as_soft_failure(self):
        """Empty results should trigger circuit breaker (soft failure)."""
        from app.engine.search_platforms.chained_adapter import ChainedAdapter
        from app.engine.search_platforms.circuit_breaker import PerPlatformCircuitBreaker

        adapter = self._make_adapter("serper", results=[])
        cb = PerPlatformCircuitBreaker()
        chain = ChainedAdapter("test_platform", "Test", [adapter], circuit_breaker=cb)

        with patch.object(chain, '_update_strategy_metrics'):
            results = chain.search_sync("test query")

        assert len(results) == 0
        backend_key = chain.get_backend_keys()[0]
        # Should have 1 failure recorded
        assert cb.get_failure_count(backend_key) >= 1

    def test_update_strategy_metrics_best_effort(self):
        """_update_strategy_metrics should not crash if StrategyManager import fails."""
        from app.engine.search_platforms.base import BackendType
        from app.engine.search_platforms.chained_adapter import ChainedAdapter

        chain = ChainedAdapter("test", "Test", [])

        # Should not raise even if import fails
        with patch(
            "app.engine.search_platforms.strategy_manager.get_scraping_strategy_manager",
            side_effect=ImportError("not available"),
        ):
            chain._update_strategy_metrics(BackendType.SERPER, True, 100)


# ======================================================================
# 4. StrategyManager cache TTL fix
# ======================================================================


class TestStrategyManagerCacheTTL:
    """Verify cache expires after TTL."""

    def test_cache_expires_after_ttl(self):
        """Metrics cache should be cleared when TTL is exceeded."""
        from app.engine.search_platforms.base import BackendType
        from app.engine.search_platforms.strategy_manager import ScrapingStrategyManager

        mgr = ScrapingStrategyManager()
        mgr._cache_ttl_seconds = 1  # 1 second TTL for testing

        # Add some metrics
        mgr.update_metrics("shopee", BackendType.SERPER, True, 200)
        assert len(mgr._metrics_cache) == 1

        # Wait for TTL to expire
        time.sleep(1.1)

        # _check_metrics should clear the cache
        result = mgr._check_metrics("shopee", "shopee.vn")
        assert result is None
        assert len(mgr._metrics_cache) == 0

    def test_cache_updated_on_metrics_update(self):
        """_cache_updated_at should be set when metrics are updated."""
        from app.engine.search_platforms.base import BackendType
        from app.engine.search_platforms.strategy_manager import ScrapingStrategyManager

        mgr = ScrapingStrategyManager()
        before = mgr._cache_updated_at

        mgr.update_metrics("test", BackendType.CRAWL4AI, True, 100)

        assert mgr._cache_updated_at > before

    def test_recommend_with_metrics(self):
        """Recommend should use metrics when success rate is high."""
        from app.engine.search_platforms.base import BackendType
        from app.engine.search_platforms.strategy_manager import ScrapingStrategyManager

        mgr = ScrapingStrategyManager()

        # Build up metrics for SCRAPLING on facebook
        for _ in range(10):
            mgr.update_metrics("facebook_marketplace", BackendType.SCRAPLING, True, 300)

        rec = mgr.recommend(domain="facebook.com", platform_id="facebook_marketplace")
        assert rec.backend == BackendType.SCRAPLING
        assert rec.confidence >= 0.7


# ======================================================================
# 5. JinaReaderAdapter
# ======================================================================


class TestJinaReaderAdapter:
    """Verify JinaReaderAdapter works correctly."""

    def test_config(self):
        """Adapter config should have correct ID and backend."""
        from app.engine.search_platforms.adapters.jina_reader_adapter import JinaReaderAdapter

        adapter = JinaReaderAdapter()
        config = adapter.get_config()

        assert config.id == "jina_reader"
        assert config.display_name == "Jina Reader"
        assert config.priority == 90  # Low priority (fallback)

    def test_search_sync_json_response(self):
        """Should parse Jina JSON search response."""
        import json
        from app.engine.search_platforms.adapters.jina_reader_adapter import JinaReaderAdapter

        adapter = JinaReaderAdapter()

        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "data": [
                {
                    "title": "Đầu in Zebra ZXP7 - Tân Phát",
                    "url": "https://tanphat.com.vn/dau-in-zebra-zxp7",
                    "description": "Đầu in Zebra ZXP7 giá 12.500.000₫ - chính hãng",
                },
                {
                    "title": "Zebra ZXP7 Printhead - Amazon",
                    "url": "https://amazon.com/zebra-zxp7",
                    "description": "Zebra ZXP7 printhead $495",
                },
            ]
        })
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.get", return_value=mock_response):
            results = adapter.search_sync("đầu in Zebra ZXP7")

        assert len(results) == 2
        assert results[0].platform == "jina_reader"
        assert "Tân Phát" in results[0].title
        assert results[0].extracted_price == 12500000.0
        assert results[1].extracted_price == 495.0

    def test_search_sync_httpx_failure(self):
        """Should return empty list on HTTP failure."""
        from app.engine.search_platforms.adapters.jina_reader_adapter import JinaReaderAdapter

        adapter = JinaReaderAdapter()

        with patch("httpx.get", side_effect=Exception("Connection refused")):
            results = adapter.search_sync("test query")

        assert results == []

    def test_price_extraction_vnd(self):
        """Should extract VND prices correctly."""
        from app.engine.search_platforms.adapters.jina_reader_adapter import JinaReaderAdapter

        price_str, price_val = JinaReaderAdapter._extract_price("Giá: 12.500.000₫")
        assert price_val == 12500000.0

        price_str, price_val = JinaReaderAdapter._extract_price("15,000,000 VNĐ")
        assert price_val == 15000000.0

    def test_price_extraction_usd(self):
        """Should extract USD prices correctly."""
        from app.engine.search_platforms.adapters.jina_reader_adapter import JinaReaderAdapter

        price_str, price_val = JinaReaderAdapter._extract_price("Price: $495")
        assert price_val == 495.0

        price_str, price_val = JinaReaderAdapter._extract_price("USD 1,200")
        assert price_val == 1200.0

    def test_price_extraction_trieu(self):
        """Should extract 'triệu' (million) prices."""
        from app.engine.search_platforms.adapters.jina_reader_adapter import JinaReaderAdapter

        price_str, price_val = JinaReaderAdapter._extract_price("Khoảng 12.5 triệu")
        assert price_val == 12500000.0

    def test_price_extraction_no_price(self):
        """Should return empty tuple when no price found."""
        from app.engine.search_platforms.adapters.jina_reader_adapter import JinaReaderAdapter

        price_str, price_val = JinaReaderAdapter._extract_price("No price info here")
        assert price_str == ""
        assert price_val is None

    def test_read_url(self):
        """Should call r.jina.ai/ for URL reading."""
        from app.engine.search_platforms.adapters.jina_reader_adapter import JinaReaderAdapter

        adapter = JinaReaderAdapter()
        mock_response = MagicMock()
        mock_response.text = "# Page Title\n\nSome content"
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.get", return_value=mock_response) as mock_get:
            result = adapter.read_url("https://example.com")

        assert result == "# Page Title\n\nSome content"
        call_url = mock_get.call_args[0][0]
        assert call_url.startswith("https://r.jina.ai/")

    def test_factory_function(self):
        """create_jina_reader_adapter should return configured adapter."""
        from app.engine.search_platforms.adapters.jina_reader_adapter import create_jina_reader_adapter

        adapter = create_jina_reader_adapter(search_suffix="giá rẻ", priority=95)
        assert adapter.get_config().priority == 95
        assert adapter._search_suffix == "giá rẻ"


# ======================================================================
# 6. Progressive Disclosure on UnifiedSkillManifest
# ======================================================================


class TestProgressiveDisclosure:
    """Verify L1/L2/L3 fields on UnifiedSkillManifest."""

    def test_default_disclosure_level(self):
        """Default disclosure level should be 1 (metadata only)."""
        from app.engine.skills.skill_manifest_v2 import SkillType, UnifiedSkillManifest

        m = UnifiedSkillManifest(
            id="tool:test",
            name="Test Tool",
            description="A test tool",
            skill_type=SkillType.TOOL,
        )
        assert m.disclosure_level == 1
        assert m.description_short == ""
        assert m.instructions == ""

    def test_l1_metadata_fields(self):
        """L1 should include id, name, description_short."""
        from app.engine.skills.skill_manifest_v2 import SkillType, UnifiedSkillManifest

        m = UnifiedSkillManifest(
            id="tool:search_shopee",
            name="Shopee Search",
            description="Search products on Shopee Vietnam e-commerce platform with price comparison",
            skill_type=SkillType.TOOL,
            description_short="Search Shopee for products",
            disclosure_level=1,
        )
        assert m.description_short == "Search Shopee for products"
        assert m.disclosure_level == 1

    def test_l2_instructions_field(self):
        """L2 should include full instructions."""
        from app.engine.skills.skill_manifest_v2 import SkillType, UnifiedSkillManifest

        m = UnifiedSkillManifest(
            id="domain:maritime:colregs",
            name="COLREGs Rules",
            description="International Regulations for Preventing Collisions at Sea",
            skill_type=SkillType.DOMAIN_KNOWLEDGE,
            instructions="Use this skill when the user asks about maritime collision avoidance rules...",
            disclosure_level=2,
        )
        assert m.instructions.startswith("Use this skill")
        assert m.disclosure_level == 2


# ======================================================================
# 7. BM25 Skill Search
# ======================================================================


class TestBM25SkillSearch:
    """Verify BM25 search engine for skill discovery."""

    def _make_skills(self):
        """Create test skill manifests."""
        from app.engine.skills.skill_manifest_v2 import SkillType, UnifiedSkillManifest

        return [
            UnifiedSkillManifest(
                id="tool:tool_search_shopee",
                name="Shopee Search",
                description="Tìm kiếm sản phẩm trên Shopee Việt Nam",
                skill_type=SkillType.TOOL,
                category="product_search",
                triggers=["mua", "shopee", "giá"],
            ),
            UnifiedSkillManifest(
                id="tool:tool_search_lazada",
                name="Lazada Search",
                description="Tìm kiếm sản phẩm trên Lazada Việt Nam",
                skill_type=SkillType.TOOL,
                category="product_search",
                triggers=["mua", "lazada", "giá"],
            ),
            UnifiedSkillManifest(
                id="tool:tool_knowledge_search",
                name="Knowledge Search",
                description="Tìm kiếm tri thức trong cơ sở kiến thức hàng hải",
                skill_type=SkillType.TOOL,
                category="rag",
                triggers=["colregs", "solas", "hàng hải"],
            ),
            UnifiedSkillManifest(
                id="tool:tool_current_datetime",
                name="Current DateTime",
                description="Trả về ngày giờ hiện tại",
                skill_type=SkillType.TOOL,
                category="utility",
                triggers=["giờ", "ngày", "hôm nay"],
            ),
            UnifiedSkillManifest(
                id="domain:maritime:colregs",
                name="COLREGs",
                description="Quy tắc phòng ngừa va chạm trên biển quốc tế",
                skill_type=SkillType.DOMAIN_KNOWLEDGE,
                domain_id="maritime",
                triggers=["colregs", "va chạm", "luật biển"],
            ),
        ]

    def test_build_index(self):
        """Should build index from skill manifests."""
        from app.engine.skills.skill_search import SkillSearch

        search = SkillSearch()
        count = search.build_index(self._make_skills())

        assert count == 5
        assert search.doc_count == 5
        assert search.is_indexed is True

    def test_search_product_query(self):
        """Search for product-related query should rank product tools higher."""
        from app.engine.skills.skill_search import SkillSearch

        search = SkillSearch()
        search.build_index(self._make_skills())

        results = search.search("tìm sản phẩm shopee")
        assert len(results) > 0
        assert results[0].skill_id == "tool:tool_search_shopee"

    def test_search_maritime_query(self):
        """Search for maritime query should rank maritime skills higher."""
        from app.engine.skills.skill_search import SkillSearch

        search = SkillSearch()
        search.build_index(self._make_skills())

        results = search.search("colregs hàng hải")
        assert len(results) > 0
        # Both tool:knowledge_search and domain:maritime:colregs should appear
        result_ids = [r.skill_id for r in results]
        assert "domain:maritime:colregs" in result_ids

    def test_search_empty_query(self):
        """Empty query should return empty results."""
        from app.engine.skills.skill_search import SkillSearch

        search = SkillSearch()
        search.build_index(self._make_skills())

        assert search.search("") == []
        assert search.search("   ") == []

    def test_search_no_match(self):
        """Query with no matching terms should return empty."""
        from app.engine.skills.skill_search import SkillSearch

        search = SkillSearch()
        search.build_index(self._make_skills())

        results = search.search("xyznonexistent")
        assert len(results) == 0

    def test_search_limit(self):
        """Should respect limit parameter."""
        from app.engine.skills.skill_search import SkillSearch

        search = SkillSearch()
        search.build_index(self._make_skills())

        results = search.search("tìm kiếm", limit=2)
        assert len(results) <= 2

    def test_search_ids_convenience(self):
        """search_ids should return just skill IDs."""
        from app.engine.skills.skill_search import SkillSearch

        search = SkillSearch()
        search.build_index(self._make_skills())

        ids = search.search_ids("shopee sản phẩm", limit=3)
        assert isinstance(ids, list)
        assert all(isinstance(i, str) for i in ids)

    def test_vietnamese_tokenization(self):
        """Should handle Vietnamese diacritics correctly."""
        from app.engine.skills.skill_search import SkillSearch

        tokens = SkillSearch._tokenize("Tìm kiếm sản phẩm trên Shopee Việt Nam")
        assert "tìm" in tokens
        assert "kiếm" in tokens
        assert "sản" in tokens
        assert "phẩm" in tokens
        assert "shopee" in tokens
        assert "việt" in tokens
        assert "nam" in tokens
        # "trên" is a Vietnamese stop word BUT len("trên") >= 2 and may not be in stop list
        # Verify the tokenizer doesn't crash and produces valid output
        assert all(len(t) >= 2 for t in tokens)

    def test_stop_words_removed(self):
        """Vietnamese and English stop words should be filtered."""
        from app.engine.skills.skill_search import SkillSearch

        tokens = SkillSearch._tokenize("là và của the a an is are")
        assert len(tokens) == 0

    def test_reset(self):
        """Reset should clear the index."""
        from app.engine.skills.skill_search import SkillSearch

        search = SkillSearch()
        search.build_index(self._make_skills())
        assert search.is_indexed is True

        search.reset()
        assert search.is_indexed is False
        assert search.doc_count == 0

    def test_bm25_idf_scoring(self):
        """Rare terms should have higher IDF than common terms."""
        from app.engine.skills.skill_search import SkillSearch

        search = SkillSearch()
        search.build_index(self._make_skills())

        # "shopee" appears in 1 doc (rare) vs "tìm" appears in multiple (common)
        idf_shopee = search._idf_cache.get("shopee", 0)
        idf_tim = search._idf_cache.get("tìm", 0)

        # Shopee is rarer → higher IDF
        assert idf_shopee >= idf_tim

    def test_matched_terms_returned(self):
        """Search results should include matched terms."""
        from app.engine.skills.skill_search import SkillSearch

        search = SkillSearch()
        search.build_index(self._make_skills())

        results = search.search("shopee giá")
        assert len(results) > 0
        assert len(results[0].matched_terms) > 0

    def test_singleton_pattern(self):
        """get_skill_search should return singleton."""
        import app.engine.skills.skill_search as mod

        old = mod._search_instance
        try:
            mod._search_instance = None
            s1 = mod.get_skill_search()
            s2 = mod.get_skill_search()
            assert s1 is s2
        finally:
            mod._search_instance = old


# ======================================================================
# 8. Cost Tracking in SkillMetricsTracker
# ======================================================================


class TestCostTracking:
    """Verify cost tracking additions to SkillMetricsTracker."""

    def test_record_token_cost(self):
        """Should track EMA token cost."""
        from app.engine.skills.skill_metrics import SkillMetricsTracker

        tracker = SkillMetricsTracker()
        tracker.record_invocation(
            "tool:test", True, latency_ms=100,
            token_cost=0.01, api_cost=0.005,
        )

        m = tracker.get_metrics("tool:test")
        assert m.estimated_token_cost == pytest.approx(0.003, abs=0.001)  # 0.3 * 0.01
        assert m.estimated_api_cost == pytest.approx(0.0015, abs=0.001)  # 0.3 * 0.005

    def test_ema_cost_accumulation(self):
        """Cost EMA should smooth over multiple invocations."""
        from app.engine.skills.skill_metrics import SkillMetricsTracker

        tracker = SkillMetricsTracker()
        tracker.record_invocation("tool:test", True, token_cost=0.10)
        tracker.record_invocation("tool:test", True, token_cost=0.20)

        m = tracker.get_metrics("tool:test")
        # First: 0.3 * 0.10 = 0.03
        # Second: 0.3 * 0.20 + 0.7 * 0.03 = 0.06 + 0.021 = 0.081
        assert m.estimated_token_cost == pytest.approx(0.081, abs=0.01)

    def test_avg_cost_per_invocation(self):
        """avg_cost_per_invocation property should calculate correctly."""
        from app.engine.skills.skill_manifest_v2 import SkillMetrics

        m = SkillMetrics(
            total_invocations=10,
            cost_estimate_usd=0.50,
        )
        assert m.avg_cost_per_invocation == pytest.approx(0.05)

    def test_avg_cost_zero_invocations(self):
        """avg_cost_per_invocation should return 0 for no invocations."""
        from app.engine.skills.skill_manifest_v2 import SkillMetrics

        m = SkillMetrics()
        assert m.avg_cost_per_invocation == 0.0

    def test_cost_factor_in_selector_reranking(self):
        """IntelligentToolSelector should include cost factor in metrics reranking."""
        from app.engine.skills.skill_manifest_v2 import SkillMetrics
        from app.engine.skills.skill_metrics import SkillMetricsTracker
        from app.engine.skills.skill_recommender import (
            IntelligentToolSelector,
            ToolRecommendation,
        )

        selector = IntelligentToolSelector()

        # Create two tools: one cheap, one expensive
        cheap_rec = ToolRecommendation(tool_name="cheap_tool", score=0.5)
        expensive_rec = ToolRecommendation(tool_name="expensive_tool", score=0.5)

        mock_tracker = MagicMock()

        cheap_metrics = SkillMetrics(
            total_invocations=20,
            successful_invocations=18,
            avg_latency_ms=200,
            cost_estimate_usd=0.01,
        )
        expensive_metrics = SkillMetrics(
            total_invocations=20,
            successful_invocations=18,
            avg_latency_ms=200,
            cost_estimate_usd=2.0,
        )

        def get_metrics(skill_id):
            if "cheap" in skill_id:
                return cheap_metrics
            return expensive_metrics

        mock_tracker.get_metrics.side_effect = get_metrics

        with patch(
            "app.engine.skills.skill_metrics.get_skill_metrics_tracker",
            return_value=mock_tracker,
        ):
            result = selector._step4_metrics_rerank([cheap_rec, expensive_rec])

        # Cheap tool should rank higher due to cost factor
        assert result[0].tool_name == "cheap_tool"


# ======================================================================
# 9. UnifiedSkillIndex BM25 Integration
# ======================================================================


class TestUnifiedIndexBM25Integration:
    """Verify UnifiedSkillIndex uses BM25 when available."""

    def test_search_uses_bm25_by_default(self):
        """search() should try BM25 first."""
        from app.engine.skills.skill_manifest_v2 import SkillType, UnifiedSkillManifest
        from app.engine.skills.unified_index import UnifiedSkillIndex

        idx = UnifiedSkillIndex()
        # Manually populate cache
        skill = UnifiedSkillManifest(
            id="tool:shopee",
            name="Shopee Search",
            description="Tìm kiếm Shopee",
            skill_type=SkillType.TOOL,
        )
        idx._cache = {"tool:shopee": skill}
        idx._last_refresh = time.time()

        with patch("app.engine.skills.skill_search.get_skill_search") as mock_search:
            mock_bm25 = MagicMock()
            mock_bm25.is_indexed = True
            mock_bm25.search.return_value = [
                MagicMock(skill_id="tool:shopee", score=2.5)
            ]
            mock_search.return_value = mock_bm25

            results = idx.search("shopee")

        assert len(results) == 1
        assert results[0].id == "tool:shopee"

    def test_search_falls_back_without_bm25(self):
        """search() should fall back to word overlap when BM25 fails."""
        from app.engine.skills.skill_manifest_v2 import SkillType, UnifiedSkillManifest
        from app.engine.skills.unified_index import UnifiedSkillIndex

        idx = UnifiedSkillIndex()
        skill = UnifiedSkillManifest(
            id="tool:shopee",
            name="Shopee Search",
            description="Tìm kiếm sản phẩm",
            skill_type=SkillType.TOOL,
        )
        idx._cache = {"tool:shopee": skill}
        idx._last_refresh = time.time()

        with patch(
            "app.engine.skills.skill_search.get_skill_search",
            side_effect=ImportError("not available"),
        ):
            results = idx.search("shopee")

        assert len(results) == 1

    def test_search_bm25_disabled(self):
        """search(use_bm25=False) should skip BM25."""
        from app.engine.skills.skill_manifest_v2 import SkillType, UnifiedSkillManifest
        from app.engine.skills.unified_index import UnifiedSkillIndex

        idx = UnifiedSkillIndex()
        skill = UnifiedSkillManifest(
            id="tool:shopee",
            name="Shopee Search",
            description="Tìm sản phẩm",
            skill_type=SkillType.TOOL,
        )
        idx._cache = {"tool:shopee": skill}
        idx._last_refresh = time.time()

        with patch("app.engine.skills.skill_search.get_skill_search") as mock_search:
            results = idx.search("shopee", use_bm25=False)
            mock_search.assert_not_called()

        assert len(results) == 1


# ======================================================================
# 10. Config Flag for Jina Reader
# ======================================================================


class TestConfigFlags:
    """Verify Sprint 195 config flags exist."""

    def test_enable_jina_reader_flag(self):
        """enable_jina_reader should exist with default False."""
        from app.core.config import Settings

        settings = Settings(
            google_api_key="test",
            api_key="test",
        )
        assert settings.enable_jina_reader is False

    def test_enable_jina_reader_true(self):
        """enable_jina_reader should be configurable."""
        from app.core.config import Settings

        settings = Settings(
            google_api_key="test",
            api_key="test",
            enable_jina_reader=True,
        )
        assert settings.enable_jina_reader is True
