"""
ChainedAdapter — Meta-adapter with Priority-Based Fallback Chain

Sprint 190: "Trí Tuệ Săn Hàng" — Enhanced Scraping Backend

Pattern: Composite adapter that tries multiple backends in priority order.
Each backend has its own circuit breaker key (platform_id + backend_type).
On failure, automatically falls through to the next backend.

Example fallback chains:
  Facebook: Scrapling (stealth) → Playwright (fine-grained) → Serper (always works)
  Shopee:   Crawl4AI (deep crawl) → Serper (fast, surface-level)
"""

import logging
import time
from typing import List, Optional

from app.engine.search_platforms.base import (
    BackendType,
    PlatformConfig,
    ProductSearchResult,
    SearchPlatformAdapter,
)
from app.engine.search_platforms.circuit_breaker import PerPlatformCircuitBreaker

logger = logging.getLogger(__name__)


class ChainedAdapter(SearchPlatformAdapter):
    """
    Meta-adapter: thử nhiều backends theo thứ tự ưu tiên.

    Per-backend circuit breaker: nếu 1 backend fail `threshold` lần liên tiếp,
    tự skip trong `recovery_seconds` rồi retry (half-open).

    Args:
        platform_id: Unique ID for this chained platform (e.g. "facebook_marketplace")
        display_name: Human-readable name (e.g. "Facebook Marketplace")
        adapters: List of SearchPlatformAdapter instances, sorted by priority (low = high priority)
        circuit_breaker: Shared PerPlatformCircuitBreaker instance
        tool_description_vi: Vietnamese tool description for LLM function calling
    """

    def __init__(
        self,
        platform_id: str,
        display_name: str,
        adapters: List[SearchPlatformAdapter],
        circuit_breaker: Optional[PerPlatformCircuitBreaker] = None,
        tool_description_vi: str = "",
    ):
        self._platform_id = platform_id
        # Sort adapters by priority (lower = higher priority)
        self._adapters = sorted(adapters, key=lambda a: a.get_config().priority)
        self._cb = circuit_breaker or PerPlatformCircuitBreaker()
        self._config = PlatformConfig(
            id=platform_id,
            display_name=display_name,
            backend=BackendType.CUSTOM,
            tool_description_vi=tool_description_vi or f"Tìm kiếm sản phẩm trên {display_name} (đa backend)",
        )

    def get_config(self) -> PlatformConfig:
        """Return platform configuration."""
        return self._config

    def search_sync(
        self, query: str, max_results: int = 20, page: int = 1
    ) -> List[ProductSearchResult]:
        """
        Execute search with priority-based fallback.

        Tries each backend adapter in priority order:
        1. Skip if circuit breaker is open for this backend
        2. Execute search_sync()
        3. On success (non-empty results): record success, return results
        4. On empty results: log, try next backend
        5. On exception: record failure, try next backend
        6. If all backends fail: return empty list

        Args:
            query: Search query string
            max_results: Maximum results to return
            page: Page number (1-based)

        Returns:
            List of ProductSearchResult from the first successful backend
        """
        errors = []

        for adapter in self._adapters:
            adapter_config = adapter.get_config()
            backend_key = f"{self._platform_id}_{adapter_config.backend.value}"

            # Check circuit breaker
            if self._cb.is_open(backend_key):
                logger.info(
                    "ChainedAdapter[%s]: Skipping %s (circuit open)",
                    self._platform_id, backend_key,
                )
                continue

            # Try this backend
            start_time = time.time()
            try:
                results = adapter.search_sync(query, max_results, page)
                elapsed_ms = int((time.time() - start_time) * 1000)

                if results:
                    self._cb.record_success(backend_key)
                    # Sprint 195: Update strategy manager metrics
                    self._update_strategy_metrics(adapter_config.backend, True, elapsed_ms)
                    logger.info(
                        "ChainedAdapter[%s]: ✓ %s returned %d results (%dms)",
                        self._platform_id, backend_key, len(results), elapsed_ms,
                    )
                    return results
                else:
                    # Sprint 195: Empty results = soft failure (triggers circuit breaker)
                    self._cb.record_failure(backend_key)
                    self._update_strategy_metrics(adapter_config.backend, False, elapsed_ms)
                    logger.info(
                        "ChainedAdapter[%s]: ✗ %s returned 0 results (%dms), trying next",
                        self._platform_id, backend_key, elapsed_ms,
                    )
            except Exception as e:
                elapsed_ms = int((time.time() - start_time) * 1000)
                self._cb.record_failure(backend_key)
                self._update_strategy_metrics(adapter_config.backend, False, elapsed_ms)
                error_msg = str(e)[:200]
                errors.append(f"{backend_key}: {error_msg}")
                logger.warning(
                    "ChainedAdapter[%s]: ✗ %s failed (%dms): %s",
                    self._platform_id, backend_key, elapsed_ms, error_msg,
                )

        # All backends failed
        if errors:
            logger.warning(
                "ChainedAdapter[%s]: All %d backends failed. Errors: %s",
                self._platform_id, len(self._adapters), "; ".join(errors),
            )
        return []

    def get_adapter_count(self) -> int:
        """Return number of backend adapters in this chain."""
        return len(self._adapters)

    def get_backend_keys(self) -> List[str]:
        """Return list of backend keys for circuit breaker inspection."""
        return [
            f"{self._platform_id}_{a.get_config().backend.value}"
            for a in self._adapters
        ]

    def get_adapters(self) -> List[SearchPlatformAdapter]:
        """Return the ordered list of backend adapters (for testing/inspection)."""
        return list(self._adapters)

    # ------------------------------------------------------------------
    # Sprint 195: Strategy Manager Integration
    # ------------------------------------------------------------------

    def _update_strategy_metrics(
        self, backend: BackendType, success: bool, latency_ms: int
    ) -> None:
        """Update ScrapingStrategyManager with backend performance data."""
        try:
            from app.engine.search_platforms.strategy_manager import (
                get_scraping_strategy_manager,
            )
            mgr = get_scraping_strategy_manager()
            mgr.update_metrics(self._platform_id, backend, success, latency_ms)
        except Exception as _e:
            logger.debug("[CHAINED] Strategy metrics update failed: %s", _e)
