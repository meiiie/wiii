"""
Tests for Sprint 42: AdaptivePipelineRouter coverage.

Tests adaptive routing logic including:
- Cache hit routing (CACHED_FAST, CACHED_STANDARD)
- Cache miss routing (STANDARD, FULL)
- Router configuration
- Statistics tracking
"""

import pytest
from unittest.mock import MagicMock


# ============================================================================
# PipelinePath and dataclasses
# ============================================================================


class TestPipelinePath:
    """Test PipelinePath enum."""

    def test_all_paths_defined(self):
        """All 4 pipeline paths are defined."""
        from app.engine.agentic_rag.adaptive_router import PipelinePath
        assert PipelinePath.CACHED_FAST == "cached_fast"
        assert PipelinePath.CACHED_STANDARD == "cached_standard"
        assert PipelinePath.STANDARD == "standard"
        assert PipelinePath.FULL == "full"


class TestRouterConfig:
    """Test RouterConfig defaults."""

    def test_default_config(self):
        """Default config has expected values."""
        from app.engine.agentic_rag.adaptive_router import RouterConfig
        config = RouterConfig()
        assert config.cached_fast_threshold == 0.99
        assert config.cached_standard_threshold == 0.95
        assert config.fast_path_grading == 9.0
        assert config.standard_path_grading == 7.0
        assert config.enable_cached_fast is True
        assert config.enable_cached_standard is True
        assert config.enable_adaptive_routing is True


class TestRoutingDecision:
    """Test RoutingDecision defaults."""

    def test_default_decision(self):
        """Default decision fields."""
        from app.engine.agentic_rag.adaptive_router import RoutingDecision, PipelinePath
        decision = RoutingDecision(path=PipelinePath.FULL, reason="test")
        assert decision.skip_grader is False
        assert decision.skip_verifier is False
        assert decision.use_thinking_adapter is False
        assert decision.estimated_time_ms == 100000


# ============================================================================
# Cache hit routing
# ============================================================================


class TestCacheHitRouting:
    """Test routing decisions for cache hits."""

    @pytest.fixture
    def router(self):
        from app.engine.agentic_rag.adaptive_router import AdaptivePipelineRouter
        return AdaptivePipelineRouter()

    def _make_cache_result(self, hit=True, similarity=0.99):
        result = MagicMock()
        result.hit = hit
        result.similarity = similarity
        return result

    def test_cached_fast_high_similarity(self, router):
        """Similarity >= 0.99 routes to CACHED_FAST."""
        from app.engine.agentic_rag.adaptive_router import PipelinePath
        cache_result = self._make_cache_result(similarity=0.995)
        decision = router.route(cache_result=cache_result)
        assert decision.path == PipelinePath.CACHED_FAST
        assert decision.skip_grader is True
        assert decision.skip_verifier is True
        assert decision.use_thinking_adapter is True
        assert decision.estimated_time_ms == 3000

    def test_cached_standard_medium_similarity(self, router):
        """Similarity >= 0.95 but < 0.99 routes to CACHED_STANDARD."""
        from app.engine.agentic_rag.adaptive_router import PipelinePath
        cache_result = self._make_cache_result(similarity=0.97)
        decision = router.route(cache_result=cache_result)
        assert decision.path == PipelinePath.CACHED_STANDARD
        assert decision.skip_grader is True
        assert decision.skip_verifier is False
        assert decision.use_thinking_adapter is True

    def test_cache_hit_low_similarity_fallback(self, router):
        """Cache hit with low similarity falls back to FULL."""
        from app.engine.agentic_rag.adaptive_router import PipelinePath
        cache_result = self._make_cache_result(similarity=0.80)
        decision = router.route(cache_result=cache_result)
        assert decision.path == PipelinePath.FULL

    def test_cached_fast_at_boundary(self, router):
        """Exactly 0.99 routes to CACHED_FAST."""
        from app.engine.agentic_rag.adaptive_router import PipelinePath
        cache_result = self._make_cache_result(similarity=0.99)
        decision = router.route(cache_result=cache_result)
        assert decision.path == PipelinePath.CACHED_FAST

    def test_cached_fast_disabled(self):
        """Disabling cached_fast skips to cached_standard."""
        from app.engine.agentic_rag.adaptive_router import (
            AdaptivePipelineRouter, RouterConfig, PipelinePath
        )
        config = RouterConfig(enable_cached_fast=False)
        router = AdaptivePipelineRouter(config)
        cache_result = self._make_cache_result(similarity=0.995)
        decision = router.route(cache_result=cache_result)
        assert decision.path == PipelinePath.CACHED_STANDARD

    def _make_cache_result(self, hit=True, similarity=0.99):
        result = MagicMock()
        result.hit = hit
        result.similarity = similarity
        return result


# ============================================================================
# Cache miss routing
# ============================================================================


class TestCacheMissRouting:
    """Test routing decisions for cache misses."""

    @pytest.fixture
    def router(self):
        from app.engine.agentic_rag.adaptive_router import AdaptivePipelineRouter
        return AdaptivePipelineRouter()

    def test_no_cache_result_full_path(self, router):
        """No cache result uses FULL path."""
        from app.engine.agentic_rag.adaptive_router import PipelinePath
        decision = router.route(cache_result=None)
        assert decision.path == PipelinePath.FULL

    def test_cache_miss_no_grading(self, router):
        """Cache miss with no grading score uses FULL path."""
        from app.engine.agentic_rag.adaptive_router import PipelinePath
        cache_result = MagicMock()
        cache_result.hit = False
        decision = router.route(cache_result=cache_result, grading_score=None)
        assert decision.path == PipelinePath.FULL

    def test_high_grading_simple_query(self, router):
        """High grading + simple query routes to STANDARD (skip verifier)."""
        from app.engine.agentic_rag.adaptive_router import PipelinePath
        decision = router.route(
            cache_result=None, grading_score=9.5, query_complexity="simple"
        )
        assert decision.path == PipelinePath.STANDARD
        assert decision.skip_verifier is True

    def test_good_grading_standard_path(self, router):
        """Good grading (>= 7.0) routes to STANDARD."""
        from app.engine.agentic_rag.adaptive_router import PipelinePath
        decision = router.route(
            cache_result=None, grading_score=8.0, query_complexity="medium"
        )
        assert decision.path == PipelinePath.STANDARD
        assert decision.skip_verifier is False

    def test_low_grading_full_path(self, router):
        """Low grading (< 7.0) routes to FULL."""
        from app.engine.agentic_rag.adaptive_router import PipelinePath
        decision = router.route(
            cache_result=None, grading_score=5.0, query_complexity="complex"
        )
        assert decision.path == PipelinePath.FULL

    def test_adaptive_routing_disabled(self):
        """Disabled adaptive routing always uses FULL."""
        from app.engine.agentic_rag.adaptive_router import (
            AdaptivePipelineRouter, RouterConfig, PipelinePath
        )
        config = RouterConfig(enable_adaptive_routing=False)
        router = AdaptivePipelineRouter(config)
        decision = router.route(
            cache_result=None, grading_score=9.5, query_complexity="simple"
        )
        assert decision.path == PipelinePath.FULL


# ============================================================================
# Statistics tracking
# ============================================================================


class TestRouterStatistics:
    """Test routing statistics."""

    def test_stats_initialized_zero(self):
        """Stats start at zero."""
        from app.engine.agentic_rag.adaptive_router import AdaptivePipelineRouter
        router = AdaptivePipelineRouter()
        stats = router.get_stats()
        assert stats["total_decisions"] == 0
        for count in stats["path_distribution"].values():
            assert count == 0

    def test_stats_increment(self):
        """Stats increment correctly."""
        from app.engine.agentic_rag.adaptive_router import AdaptivePipelineRouter
        router = AdaptivePipelineRouter()
        # Make 3 decisions
        router.route(cache_result=None)
        router.route(cache_result=None, grading_score=9.5, query_complexity="simple")
        router.route(cache_result=None, grading_score=3.0)
        stats = router.get_stats()
        assert stats["total_decisions"] == 3

    def test_stats_config_included(self):
        """Stats include config values."""
        from app.engine.agentic_rag.adaptive_router import AdaptivePipelineRouter
        router = AdaptivePipelineRouter()
        stats = router.get_stats()
        assert "config" in stats
        assert "cached_fast_threshold" in stats["config"]
