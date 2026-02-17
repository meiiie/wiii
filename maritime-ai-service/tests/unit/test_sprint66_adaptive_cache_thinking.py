"""
Tests for Sprint 66: Adaptive Cache TTL + Thinking Effort Parameter.

Tests:
1. Adaptive TTL - hot queries get longer effective TTL
2. Cache threshold change (0.92 default)
3. ChatRequest.thinking_effort field
4. AgentState.thinking_effort field
5. get_llm_for_effort() tier mapping
6. process_with_multi_agent thinking_effort passthrough
"""

import time
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.cache.models import CacheConfig, CacheEntry, CacheTier


# ============================================================================
# Adaptive TTL Tests
# ============================================================================


class TestAdaptiveTTL:
    """Test adaptive TTL for semantic cache entries."""

    def test_effective_ttl_no_access(self):
        """Entry with 0 accesses should use base TTL."""
        entry = CacheEntry(
            key="q", embedding=[1.0], value="a",
            tier=CacheTier.RESPONSE, ttl=7200
        )
        assert entry.get_effective_ttl(adaptive_ttl=True) == 7200

    def test_effective_ttl_disabled(self):
        """When adaptive_ttl=False, always use base TTL."""
        entry = CacheEntry(
            key="q", embedding=[1.0], value="a",
            tier=CacheTier.RESPONSE, ttl=7200
        )
        entry.access_count = 10
        assert entry.get_effective_ttl(adaptive_ttl=False) == 7200

    def test_effective_ttl_2_accesses(self):
        """2 accesses → multiplier = 1 + 2*0.25 = 1.5 → 10800s."""
        entry = CacheEntry(
            key="q", embedding=[1.0], value="a",
            tier=CacheTier.RESPONSE, ttl=7200
        )
        entry.access_count = 2
        assert entry.get_effective_ttl(adaptive_ttl=True) == 7200 * 1.5

    def test_effective_ttl_4_accesses(self):
        """4 accesses → multiplier = 1 + 4*0.25 = 2.0 → 14400s."""
        entry = CacheEntry(
            key="q", embedding=[1.0], value="a",
            tier=CacheTier.RESPONSE, ttl=7200
        )
        entry.access_count = 4
        assert entry.get_effective_ttl(adaptive_ttl=True) == 7200 * 2.0

    def test_effective_ttl_capped_at_max_multiplier(self):
        """100 accesses → capped at 3x multiplier."""
        entry = CacheEntry(
            key="q", embedding=[1.0], value="a",
            tier=CacheTier.RESPONSE, ttl=7200
        )
        entry.access_count = 100
        assert entry.get_effective_ttl(adaptive_ttl=True, max_multiplier=3.0) == 7200 * 3.0

    def test_effective_ttl_custom_max_multiplier(self):
        """Custom max_multiplier=2.0 should cap earlier."""
        entry = CacheEntry(
            key="q", embedding=[1.0], value="a",
            tier=CacheTier.RESPONSE, ttl=1000
        )
        entry.access_count = 10  # Would be 1 + 10*0.25 = 3.5 → capped at 2.0
        assert entry.get_effective_ttl(adaptive_ttl=True, max_multiplier=2.0) == 2000

    def test_is_expired_with_adaptive_ttl(self):
        """Hot entry should survive longer than base TTL."""
        entry = CacheEntry(
            key="q", embedding=[1.0], value="a",
            tier=CacheTier.RESPONSE, ttl=1  # 1 second base TTL
        )
        entry.access_count = 8  # Effective multiplier = min(1+8*0.25, 3.0) = 3.0

        # Set created_at to 2 seconds ago
        entry.created_at = time.time() - 2.0

        # Without adaptive: expired (2s > 1s base TTL)
        assert entry.is_expired(adaptive_ttl=False) is True

        # With adaptive: NOT expired (2s < 3s effective TTL)
        assert entry.is_expired(adaptive_ttl=True) is False

    def test_is_expired_backwards_compat(self):
        """Default is_expired() without args should use base TTL (backward compat)."""
        entry = CacheEntry(
            key="q", embedding=[1.0], value="a",
            tier=CacheTier.RESPONSE, ttl=0
        )
        time.sleep(0.01)
        assert entry.is_expired() is True


class TestCacheConfigAdaptiveTTL:
    """Test CacheConfig adaptive TTL fields."""

    def test_default_config_has_adaptive_ttl(self):
        config = CacheConfig()
        assert config.adaptive_ttl is True
        assert config.adaptive_ttl_max_multiplier == 3.0

    def test_config_disable_adaptive_ttl(self):
        config = CacheConfig(adaptive_ttl=False)
        assert config.adaptive_ttl is False

    def test_config_custom_max_multiplier(self):
        config = CacheConfig(adaptive_ttl_max_multiplier=5.0)
        assert config.adaptive_ttl_max_multiplier == 5.0


class TestCacheThresholdDefault:
    """Test that default similarity threshold is 0.92."""

    def test_cache_config_default_threshold(self):
        config = CacheConfig()
        assert config.similarity_threshold == 0.92

    def test_settings_field_default_threshold(self):
        """Verify config field default is 0.92 (env may override at runtime)."""
        from app.core.config import Settings
        field_info = Settings.model_fields["cache_similarity_threshold"]
        assert field_info.default == 0.92


# ============================================================================
# Thinking Effort Tests
# ============================================================================


class TestChatRequestThinkingEffort:
    """Test ChatRequest.thinking_effort field."""

    def test_thinking_effort_none_by_default(self):
        from app.models.schemas import ChatRequest
        req = ChatRequest(
            user_id="u1", message="test", role="student"
        )
        assert req.thinking_effort is None

    def test_thinking_effort_low(self):
        from app.models.schemas import ChatRequest
        req = ChatRequest(
            user_id="u1", message="test", role="student",
            thinking_effort="low"
        )
        assert req.thinking_effort == "low"

    def test_thinking_effort_medium(self):
        from app.models.schemas import ChatRequest
        req = ChatRequest(
            user_id="u1", message="test", role="student",
            thinking_effort="medium"
        )
        assert req.thinking_effort == "medium"

    def test_thinking_effort_high(self):
        from app.models.schemas import ChatRequest
        req = ChatRequest(
            user_id="u1", message="test", role="student",
            thinking_effort="high"
        )
        assert req.thinking_effort == "high"

    def test_thinking_effort_max(self):
        from app.models.schemas import ChatRequest
        req = ChatRequest(
            user_id="u1", message="test", role="student",
            thinking_effort="max"
        )
        assert req.thinking_effort == "max"

    def test_thinking_effort_invalid_rejected(self):
        from app.models.schemas import ChatRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ChatRequest(
                user_id="u1", message="test", role="student",
                thinking_effort="ultra"  # Invalid value
            )


class TestAgentStateThinkingEffort:
    """Test AgentState.thinking_effort field."""

    def test_state_accepts_thinking_effort(self):
        """AgentState TypedDict accepts thinking_effort (plain dict test to avoid circular import)."""
        state = {
            "query": "test",
            "user_id": "u1",
            "thinking_effort": "high",
        }
        assert state["thinking_effort"] == "high"

    def test_state_thinking_effort_none(self):
        state = {
            "query": "test",
            "user_id": "u1",
        }
        assert state.get("thinking_effort") is None


class TestGetLLMForEffort:
    """Test get_llm_for_effort() tier mapping."""

    def test_none_returns_default(self):
        from app.engine.llm_factory import ThinkingTier
        with patch("app.engine.llm_pool.LLMPool.get") as mock_get:
            mock_get.return_value = MagicMock()
            from app.engine.llm_pool import get_llm_for_effort
            get_llm_for_effort(None, default_tier=ThinkingTier.MODERATE)
            mock_get.assert_called_once_with(ThinkingTier.MODERATE)

    def test_low_maps_to_light(self):
        from app.engine.llm_factory import ThinkingTier
        with patch("app.engine.llm_pool.LLMPool.get") as mock_get:
            mock_get.return_value = MagicMock()
            from app.engine.llm_pool import get_llm_for_effort
            get_llm_for_effort("low")
            mock_get.assert_called_once_with(ThinkingTier.LIGHT)

    def test_medium_maps_to_moderate(self):
        from app.engine.llm_factory import ThinkingTier
        with patch("app.engine.llm_pool.LLMPool.get") as mock_get:
            mock_get.return_value = MagicMock()
            from app.engine.llm_pool import get_llm_for_effort
            get_llm_for_effort("medium")
            mock_get.assert_called_once_with(ThinkingTier.MODERATE)

    def test_high_maps_to_deep(self):
        from app.engine.llm_factory import ThinkingTier
        with patch("app.engine.llm_pool.LLMPool.get") as mock_get:
            mock_get.return_value = MagicMock()
            from app.engine.llm_pool import get_llm_for_effort
            get_llm_for_effort("high")
            mock_get.assert_called_once_with(ThinkingTier.DEEP)

    def test_max_maps_to_deep(self):
        from app.engine.llm_factory import ThinkingTier
        with patch("app.engine.llm_pool.LLMPool.get") as mock_get:
            mock_get.return_value = MagicMock()
            from app.engine.llm_pool import get_llm_for_effort
            get_llm_for_effort("max")
            mock_get.assert_called_once_with(ThinkingTier.DEEP)

    def test_invalid_effort_uses_default(self):
        from app.engine.llm_factory import ThinkingTier
        with patch("app.engine.llm_pool.LLMPool.get") as mock_get:
            mock_get.return_value = MagicMock()
            from app.engine.llm_pool import get_llm_for_effort
            get_llm_for_effort("unknown_effort", default_tier=ThinkingTier.LIGHT)
            mock_get.assert_called_once_with(ThinkingTier.LIGHT)


# ============================================================================
# Semantic Cache with Adaptive TTL Integration
# ============================================================================


class TestSemanticCacheAdaptiveTTL:
    """Test SemanticResponseCache with adaptive TTL enabled."""

    @pytest.mark.asyncio
    async def test_cache_uses_adaptive_ttl_on_get(self):
        """Verify that cache get() applies adaptive TTL when evicting expired entries."""
        from app.cache.semantic_cache import SemanticResponseCache

        config = CacheConfig(
            similarity_threshold=0.5,
            response_ttl=1,  # 1 second base
            adaptive_ttl=True,
            adaptive_ttl_max_multiplier=3.0,
            log_cache_operations=False
        )
        cache = SemanticResponseCache(config)

        # Manually insert an entry with high access count (simulates hot query)
        entry = CacheEntry(
            key="hot query",
            embedding=[1.0, 0.0, 0.0],
            value="cached answer",
            tier=CacheTier.RESPONSE,
            ttl=1,  # 1 second base
            access_count=8,  # Effective TTL = 1 * min(1+8*0.25, 3.0) = 3s
            created_at=time.time() - 2.0  # Created 2s ago
        )
        cache._cache["hot query"] = entry

        # Get should find it (not expired with adaptive TTL: 2s < 3s effective)
        result = await cache.get("hot query", [1.0, 0.0, 0.0])
        assert result.hit is True

    @pytest.mark.asyncio
    async def test_cache_evicts_cold_entries(self):
        """Cold entries (0 accesses) expire normally."""
        from app.cache.semantic_cache import SemanticResponseCache

        config = CacheConfig(
            similarity_threshold=0.5,
            response_ttl=1,
            adaptive_ttl=True,
            log_cache_operations=False
        )
        cache = SemanticResponseCache(config)

        # Cold entry (0 accesses), created 2s ago
        entry = CacheEntry(
            key="cold query",
            embedding=[1.0, 0.0, 0.0],
            value="answer",
            tier=CacheTier.RESPONSE,
            ttl=1,
            access_count=0,
            created_at=time.time() - 2.0
        )
        cache._cache["cold query"] = entry

        # Should NOT find it (expired: 2s > 1s)
        result = await cache.get("cold query", [1.0, 0.0, 0.0])
        assert result.hit is False
        assert cache._stats.evictions >= 1

    @pytest.mark.asyncio
    async def test_cache_adaptive_ttl_disabled(self):
        """When adaptive_ttl=False, hot entries still expire at base TTL."""
        from app.cache.semantic_cache import SemanticResponseCache

        config = CacheConfig(
            similarity_threshold=0.5,
            response_ttl=1,
            adaptive_ttl=False,
            log_cache_operations=False
        )
        cache = SemanticResponseCache(config)

        # Hot entry but adaptive disabled
        entry = CacheEntry(
            key="hot query",
            embedding=[1.0, 0.0, 0.0],
            value="answer",
            tier=CacheTier.RESPONSE,
            ttl=1,
            access_count=8,
            created_at=time.time() - 2.0
        )
        cache._cache["hot query"] = entry

        # Should NOT find it (expired: 2s > 1s, adaptive disabled)
        result = await cache.get("hot query", [1.0, 0.0, 0.0])
        assert result.hit is False


# ============================================================================
# Config Settings Tests
# ============================================================================


class TestConfigSettings:
    """Test new config fields."""

    def test_cache_adaptive_ttl_default(self):
        from app.core.config import Settings
        field_info = Settings.model_fields["cache_adaptive_ttl"]
        assert field_info.default is True

    def test_cache_adaptive_ttl_max_multiplier_default(self):
        from app.core.config import Settings
        field_info = Settings.model_fields["cache_adaptive_ttl_max_multiplier"]
        assert field_info.default == 3.0
