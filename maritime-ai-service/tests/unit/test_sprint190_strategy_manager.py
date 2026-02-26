"""
Sprint 190: ScrapingStrategyManager Unit Tests

Tests the singleton ScrapingStrategyManager that recommends the best
scraping backend for a URL/domain based on domain rules, metrics, and strategy.

31 tests across 7 categories:
1. Singleton pattern (3 tests)
2. Domain rules matching (10 tests)
3. URL parsing (5 tests)
4. Metrics-driven recommendation (7 tests)
5. Strategy modes (3 tests)
6. Fallback chain (3 tests)
7. Edge cases & data models (additional)
"""

import threading
import time
from unittest.mock import patch

import pytest

from app.engine.search_platforms.base import BackendType
from app.engine.search_platforms.strategy_manager import (
    BackendMetrics,
    DomainRule,
    ScrapingStrategy,
    ScrapingStrategyManager,
    StrategyRecommendation,
    get_scraping_strategy_manager,
)
import app.engine.search_platforms.strategy_manager as sm_module


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton before and after every test for isolation."""
    sm_module._manager_instance = None
    yield
    sm_module._manager_instance = None


@pytest.fixture
def manager():
    """Create a fresh ScrapingStrategyManager with default rules."""
    return ScrapingStrategyManager()


@pytest.fixture
def adaptive_manager():
    """Manager in ADAPTIVE strategy mode."""
    return ScrapingStrategyManager(strategy=ScrapingStrategy.ADAPTIVE)


@pytest.fixture
def rule_based_manager():
    """Manager in RULE_BASED strategy mode."""
    return ScrapingStrategyManager(strategy=ScrapingStrategy.RULE_BASED)


@pytest.fixture
def metrics_driven_manager():
    """Manager in METRICS_DRIVEN strategy mode."""
    return ScrapingStrategyManager(strategy=ScrapingStrategy.METRICS_DRIVEN)


# ============================================================================
# 1. Singleton Pattern (3 tests)
# ============================================================================


class TestSingletonPattern:
    """Verify singleton get_scraping_strategy_manager() behavior."""

    def test_returns_same_instance(self):
        """get_scraping_strategy_manager() returns the same object."""
        mgr1 = get_scraping_strategy_manager()
        mgr2 = get_scraping_strategy_manager()
        assert mgr1 is mgr2

    def test_thread_safe_creation(self):
        """Concurrent threads all get the same instance."""
        instances = []
        barrier = threading.Barrier(5)

        def worker():
            barrier.wait()
            instances.append(get_scraping_strategy_manager())

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(instances) == 5
        first = instances[0]
        for inst in instances[1:]:
            assert inst is first

    def test_reset_singleton_creates_new_instance(self):
        """After reset, a new instance is created."""
        mgr1 = get_scraping_strategy_manager()
        sm_module._manager_instance = None
        mgr2 = get_scraping_strategy_manager()
        assert mgr1 is not mgr2


# ============================================================================
# 2. Domain Rules Matching (10 tests)
# ============================================================================


class TestDomainRulesMatching:
    """Domain pattern matching against the default rule table."""

    def test_facebook_maps_to_scrapling(self, manager):
        """facebook.com -> SCRAPLING."""
        rec = manager.recommend(domain="facebook.com")
        assert rec.backend == BackendType.SCRAPLING

    def test_fb_com_maps_to_scrapling(self, manager):
        """fb.com -> SCRAPLING."""
        rec = manager.recommend(domain="fb.com")
        assert rec.backend == BackendType.SCRAPLING

    def test_shopee_maps_to_serper_site(self, manager):
        """shopee.vn -> SERPER_SITE."""
        rec = manager.recommend(domain="shopee.vn")
        assert rec.backend == BackendType.SERPER_SITE

    def test_lazada_maps_to_serper_site(self, manager):
        """lazada.vn -> SERPER_SITE."""
        rec = manager.recommend(domain="lazada.vn")
        assert rec.backend == BackendType.SERPER_SITE

    def test_tiktok_maps_to_native_api(self, manager):
        """tiktok.com -> NATIVE_API."""
        rec = manager.recommend(domain="tiktok.com")
        assert rec.backend == BackendType.NATIVE_API

    def test_websosanh_maps_to_custom(self, manager):
        """websosanh.vn -> CUSTOM."""
        rec = manager.recommend(domain="websosanh.vn")
        assert rec.backend == BackendType.CUSTOM

    def test_unknown_domain_falls_back_to_crawl4ai(self, manager):
        """Unknown domain -> wildcard * -> CRAWL4AI."""
        rec = manager.recommend(domain="randomshop.com.vn")
        assert rec.backend == BackendType.CRAWL4AI

    def test_subdomain_matching_www_facebook(self, manager):
        """www.facebook.com matches facebook.com rule."""
        rec = manager.recommend(domain="www.facebook.com")
        assert rec.backend == BackendType.SCRAPLING

    def test_dynamic_domain_rule_added(self, manager):
        """Dynamically added rule takes effect."""
        rule = DomainRule(
            domain_pattern="sendo.vn",
            preferred_backend=BackendType.BROWSER,
            reason="Sendo: Playwright required",
            priority=0,
        )
        manager.add_domain_rule(rule)
        rec = manager.recommend(domain="sendo.vn")
        assert rec.backend == BackendType.BROWSER

    def test_priority_ordering_of_rules(self, manager):
        """Lower priority number wins when multiple rules match."""
        high_prio = DomainRule(
            domain_pattern="facebook.com",
            preferred_backend=BackendType.CRAWL4AI,
            reason="Override: Crawl4AI for Facebook",
            priority=-1,
        )
        manager.add_domain_rule(high_prio)
        rec = manager.recommend(domain="facebook.com")
        assert rec.backend == BackendType.CRAWL4AI


# ============================================================================
# 3. URL Parsing (5 tests)
# ============================================================================


class TestURLParsing:
    """URL-based domain extraction and edge cases."""

    def test_url_extracts_domain_facebook(self, manager):
        """Full Facebook URL resolves to SCRAPLING."""
        rec = manager.recommend(url="https://www.facebook.com/marketplace/hanoi/search?query=laptop")
        assert rec.backend == BackendType.SCRAPLING

    def test_url_extracts_domain_shopee(self, manager):
        """Shopee URL resolves to SERPER_SITE."""
        rec = manager.recommend(url="https://shopee.vn/search?q=iphone+15")
        assert rec.backend == BackendType.SERPER_SITE

    def test_domain_kwarg_used_directly(self, manager):
        """domain= passed directly works without URL parsing."""
        rec = manager.recommend(domain="facebook.com")
        assert rec.backend == BackendType.SCRAPLING
        assert rec.confidence == 0.7

    def test_no_args_returns_low_confidence_fallback(self, manager):
        """recommend() with no args -> fallback with low confidence."""
        rec = manager.recommend()
        assert rec.backend == BackendType.CRAWL4AI
        assert rec.confidence == 0.3
        assert "No domain" in rec.reason

    def test_malformed_url_does_not_crash(self, manager):
        """Invalid URL does not raise, returns fallback."""
        rec = manager.recommend(url="not-a-url-at-all")
        assert rec.backend == BackendType.CRAWL4AI
        assert rec.confidence <= 0.7


# ============================================================================
# 4. Metrics-Driven Recommendation (7 tests)
# ============================================================================


class TestMetricsDriven:
    """Metrics recording and metrics-based recommendations."""

    def test_update_metrics_records_success(self, manager):
        """update_metrics with success=True increments successful_attempts."""
        manager.update_metrics("shopee", BackendType.SERPER_SITE, success=True, latency_ms=200)
        summary = manager.get_metrics_summary()
        assert summary["shopee"]["serper_site"]["total_attempts"] == 1
        assert "100.0%" in summary["shopee"]["serper_site"]["success_rate"]

    def test_update_metrics_records_failure(self, manager):
        """update_metrics with success=False increments total only."""
        manager.update_metrics("shopee", BackendType.SERPER_SITE, success=False, latency_ms=500)
        summary = manager.get_metrics_summary()
        assert summary["shopee"]["serper_site"]["total_attempts"] == 1
        assert "0.0%" in summary["shopee"]["serper_site"]["success_rate"]

    def test_ema_latency_calculation(self, manager):
        """EMA latency: new_avg = 0.3 * current + 0.7 * prev."""
        manager.update_metrics("shopee", BackendType.SERPER_SITE, success=True, latency_ms=1000)
        summary = manager.get_metrics_summary()
        # First call: 0.3 * 1000 + 0.7 * 0 = 300
        assert summary["shopee"]["serper_site"]["avg_latency_ms"] == 300

        manager.update_metrics("shopee", BackendType.SERPER_SITE, success=True, latency_ms=1000)
        summary = manager.get_metrics_summary()
        # Second call: 0.3 * 1000 + 0.7 * 300 = 510
        assert summary["shopee"]["serper_site"]["avg_latency_ms"] == 510

    def test_success_rate_property(self):
        """BackendMetrics.success_rate calculates correctly."""
        m = BackendMetrics(
            backend=BackendType.SERPER,
            total_attempts=10,
            successful_attempts=8,
        )
        assert m.success_rate == pytest.approx(0.8)

    def test_success_rate_zero_attempts(self):
        """success_rate is 0 when total_attempts is 0."""
        m = BackendMetrics(backend=BackendType.SERPER, total_attempts=0)
        assert m.success_rate == 0.0

    def test_metrics_below_threshold_not_trusted(self, adaptive_manager):
        """Metrics with < 3 attempts fall back to rules."""
        mgr = adaptive_manager
        mgr.update_metrics("shopee", BackendType.CRAWL4AI, success=True, latency_ms=100)
        mgr.update_metrics("shopee", BackendType.CRAWL4AI, success=True, latency_ms=100)
        rec = mgr.recommend(domain="shopee.vn", platform_id="shopee")
        assert rec.backend == BackendType.SERPER_SITE

    def test_metrics_high_success_rate_overrides_rules(self, adaptive_manager):
        """Metrics with high success rate + enough data override domain rules."""
        mgr = adaptive_manager
        for _ in range(5):
            mgr.update_metrics("shopee", BackendType.CRAWL4AI, success=True, latency_ms=200)
        rec = mgr.recommend(domain="shopee.vn", platform_id="shopee")
        assert rec.backend == BackendType.CRAWL4AI
        assert rec.confidence >= 0.9


# ============================================================================
# 5. Strategy Modes (3 tests)
# ============================================================================


class TestStrategyModes:
    """Verify each ScrapingStrategy mode."""

    def test_rule_based_ignores_metrics(self, rule_based_manager):
        """RULE_BASED always uses domain rules."""
        mgr = rule_based_manager
        for _ in range(10):
            mgr.update_metrics("shopee", BackendType.CRAWL4AI, success=True, latency_ms=100)
        rec = mgr.recommend(domain="shopee.vn", platform_id="shopee")
        assert rec.backend == BackendType.SERPER_SITE

    def test_metrics_driven_prefers_metrics(self, metrics_driven_manager):
        """METRICS_DRIVEN prefers good metrics over domain rules."""
        mgr = metrics_driven_manager
        for _ in range(5):
            mgr.update_metrics("shopee", BackendType.BROWSER, success=True, latency_ms=300)
        rec = mgr.recommend(domain="shopee.vn", platform_id="shopee")
        assert rec.backend == BackendType.BROWSER
        assert rec.confidence >= 0.9

    def test_adaptive_falls_back_to_rules_without_metrics(self, adaptive_manager):
        """ADAPTIVE without metrics data falls back to domain rules."""
        mgr = adaptive_manager
        rec = mgr.recommend(domain="tiktok.com", platform_id="tiktok")
        assert rec.backend == BackendType.NATIVE_API
        assert rec.confidence == 0.7


# ============================================================================
# 6. Fallback Chain (3 tests)
# ============================================================================


class TestFallbackChain:
    """Verify fallback backend generation."""

    def test_fallback_chain_excludes_primary(self, manager):
        """Fallback chain excludes the primary backend."""
        rec = manager.recommend(domain="facebook.com")
        assert rec.backend == BackendType.SCRAPLING
        assert BackendType.SCRAPLING not in rec.fallback_backends

    def test_fallback_chain_max_three(self, manager):
        """Fallback chain has at most 3 alternatives."""
        rec = manager.recommend(domain="shopee.vn")
        assert len(rec.fallback_backends) <= 3
        for fb in rec.fallback_backends:
            assert isinstance(fb, BackendType)

    def test_fallback_chain_populated(self, manager):
        """Every domain recommendation has at least one fallback."""
        rec = manager.recommend(domain="websosanh.vn")
        assert len(rec.fallback_backends) > 0


# ============================================================================
# 7. Edge Cases & Data Models
# ============================================================================


class TestEdgeCasesAndModels:
    """Additional edge cases and dataclass validation."""

    def test_strategy_recommendation_fields(self):
        """StrategyRecommendation has all expected fields."""
        rec = StrategyRecommendation(
            backend=BackendType.SERPER,
            confidence=0.85,
            reason="Test reason",
            fallback_backends=[BackendType.CRAWL4AI],
        )
        assert rec.backend == BackendType.SERPER
        assert rec.confidence == 0.85
        assert rec.reason == "Test reason"
        assert rec.fallback_backends == [BackendType.CRAWL4AI]

    def test_strategy_recommendation_default_fallbacks(self):
        """Default fallback_backends is empty list."""
        rec = StrategyRecommendation(
            backend=BackendType.SERPER,
            confidence=0.5,
            reason="minimal",
        )
        assert rec.fallback_backends == []

    def test_domain_rule_dataclass(self):
        """DomainRule has expected fields and defaults."""
        rule = DomainRule(
            domain_pattern="test.com",
            preferred_backend=BackendType.CRAWL4AI,
            reason="Testing",
        )
        assert rule.priority == 0
        assert rule.domain_pattern == "test.com"

    def test_get_domain_rules_returns_copy(self, manager):
        """get_domain_rules() returns a copy."""
        rules = manager.get_domain_rules()
        original_len = len(rules)
        rules.append(DomainRule("extra.com", BackendType.SERPER, "extra"))
        assert len(manager.get_domain_rules()) == original_len

    def test_metrics_summary_empty_when_no_data(self, manager):
        """get_metrics_summary() returns empty dict with no data."""
        assert manager.get_metrics_summary() == {}

    def test_scrapingstrategy_enum_values(self):
        """ScrapingStrategy enum has expected string values."""
        assert ScrapingStrategy.RULE_BASED.value == "rule_based"
        assert ScrapingStrategy.METRICS_DRIVEN.value == "metrics"
        assert ScrapingStrategy.BUDGET_AWARE.value == "budget"
        assert ScrapingStrategy.ADAPTIVE.value == "adaptive"

    def test_custom_rules_override_defaults(self):
        """Manager with custom rules uses only those rules."""
        custom_rules = [
            DomainRule("mysite.com", BackendType.BROWSER, "Custom only", 0),
            DomainRule("*", BackendType.SERPER, "Custom wildcard", 99),
        ]
        mgr = ScrapingStrategyManager(domain_rules=custom_rules)
        rec = mgr.recommend(domain="mysite.com")
        assert rec.backend == BackendType.BROWSER
        rec2 = mgr.recommend(domain="other.com")
        assert rec2.backend == BackendType.SERPER
