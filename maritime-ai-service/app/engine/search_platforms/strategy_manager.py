"""
Scraping Strategy Manager — Intelligent Backend Selection

Sprint 190: "Trí Tuệ Săn Hàng" — Enhanced Scraping Backend

Singleton that decides the best scraping backend for a given URL/domain,
based on domain rules, historical metrics, and budget constraints.

Pattern:
- Thread-safe singleton via get_scraping_strategy_manager()
- Domain rules: pre-configured mappings (facebook.com → SCRAPLING, etc.)
- Metrics-driven: reads from scraping_metrics table for historical success rates
- Budget-aware: LLM extraction (Crawl4AI + LLM) only when needed
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
from urllib.parse import urlparse

from app.engine.search_platforms.base import BackendType

logger = logging.getLogger(__name__)


class ScrapingStrategy(str, Enum):
    """Strategy for selecting a scraping backend."""
    RULE_BASED = "rule_based"      # Use domain rules (fastest, no metrics needed)
    METRICS_DRIVEN = "metrics"     # Use historical success rate (requires DB data)
    BUDGET_AWARE = "budget"        # Consider LLM token cost
    ADAPTIVE = "adaptive"          # Rule → metrics → budget (recommended)


@dataclass
class DomainRule:
    """Pre-configured backend rule for a domain pattern."""
    domain_pattern: str            # e.g. "facebook.com", "*.shopee.vn"
    preferred_backend: BackendType
    reason: str                    # Why this backend is preferred
    priority: int = 0              # Lower = higher priority


@dataclass
class BackendMetrics:
    """Aggregated metrics for a backend on a specific platform."""
    backend: BackendType
    total_attempts: int = 0
    successful_attempts: int = 0
    avg_latency_ms: float = 0.0
    last_success_time: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.total_attempts == 0:
            return 0.0
        return self.successful_attempts / self.total_attempts


@dataclass
class StrategyRecommendation:
    """Recommendation from the strategy manager."""
    backend: BackendType
    confidence: float              # 0-1
    reason: str
    fallback_backends: List[BackendType] = field(default_factory=list)


# Default domain rules for Vietnamese market
_DEFAULT_DOMAIN_RULES: List[DomainRule] = [
    # Facebook: anti-bot protection → Scrapling stealth
    DomainRule("facebook.com", BackendType.SCRAPLING, "Facebook anti-bot: Scrapling TLS bypass", 0),
    DomainRule("fb.com", BackendType.SCRAPLING, "Facebook short domain", 0),

    # Shopee/Lazada: Serper usually works, Crawl4AI as fallback for deep scraping
    DomainRule("shopee.vn", BackendType.SERPER_SITE, "Shopee: Serper site-filter reliable", 1),
    DomainRule("lazada.vn", BackendType.SERPER_SITE, "Lazada: Serper site-filter reliable", 1),

    # TikTok: native API when available
    DomainRule("tiktok.com", BackendType.NATIVE_API, "TikTok: native Research API preferred", 0),

    # General Vietnamese e-commerce: Crawl4AI for deep extraction
    DomainRule("websosanh.vn", BackendType.CUSTOM, "WebSosanh: custom HTML scraper", 0),

    # Default for unknown sites
    DomainRule("*", BackendType.CRAWL4AI, "Unknown sites: Crawl4AI general extraction", 99),
]


class ScrapingStrategyManager:
    """
    Singleton that recommends the best scraping backend for a URL/domain.

    Decision pipeline (ADAPTIVE strategy):
    1. Check domain rules (fast, no DB access)
    2. Check historical metrics if available (success rate in last 24h)
    3. Check budget constraints (LLM extraction cost)
    4. Return recommendation with confidence and fallback chain

    Thread-safe, lazy-initialized.
    """

    def __init__(
        self,
        domain_rules: Optional[List[DomainRule]] = None,
        strategy: ScrapingStrategy = ScrapingStrategy.ADAPTIVE,
    ):
        self._domain_rules = domain_rules or list(_DEFAULT_DOMAIN_RULES)
        self._strategy = strategy
        self._metrics_cache: Dict[str, Dict[str, BackendMetrics]] = {}
        self._cache_ttl_seconds = 300  # 5 minutes
        self._cache_updated_at = 0.0
        self._lock = threading.Lock()

    def recommend(
        self,
        url: Optional[str] = None,
        domain: Optional[str] = None,
        platform_id: Optional[str] = None,
    ) -> StrategyRecommendation:
        """
        Recommend the best scraping backend for a URL or domain.

        Args:
            url: Full URL to scrape (domain extracted automatically)
            domain: Domain string (used if url not provided)
            platform_id: Platform identifier for metrics lookup

        Returns:
            StrategyRecommendation with backend, confidence, reason, fallbacks
        """
        # Extract domain from URL
        if url and not domain:
            try:
                parsed = urlparse(url)
                domain = parsed.netloc.lower().lstrip("www.")
            except Exception:
                domain = ""

        if not domain:
            return StrategyRecommendation(
                backend=BackendType.CRAWL4AI,
                confidence=0.3,
                reason="No domain provided, defaulting to Crawl4AI",
                fallback_backends=[BackendType.SERPER],
            )

        # Step 1: Domain rules (always checked first)
        rule = self._match_domain_rule(domain)

        if self._strategy == ScrapingStrategy.RULE_BASED or not platform_id:
            return StrategyRecommendation(
                backend=rule.preferred_backend,
                confidence=0.7,
                reason=rule.reason,
                fallback_backends=self._get_fallback_chain(rule.preferred_backend),
            )

        # Step 2: Check metrics (if METRICS_DRIVEN or ADAPTIVE)
        if self._strategy in (ScrapingStrategy.METRICS_DRIVEN, ScrapingStrategy.ADAPTIVE):
            metrics_rec = self._check_metrics(platform_id, domain)
            if metrics_rec and metrics_rec.confidence > 0.6:
                return metrics_rec

        # Step 3: Fall back to domain rule
        return StrategyRecommendation(
            backend=rule.preferred_backend,
            confidence=0.7,
            reason=rule.reason,
            fallback_backends=self._get_fallback_chain(rule.preferred_backend),
        )

    def _match_domain_rule(self, domain: str) -> DomainRule:
        """Find the best matching domain rule."""
        best_match: Optional[DomainRule] = None
        best_priority = 999

        for rule in self._domain_rules:
            pattern = rule.domain_pattern.lower()

            if pattern == "*":
                if best_match is None:
                    best_match = rule
                continue

            if pattern.startswith("*."):
                # Wildcard subdomain match
                suffix = pattern[2:]
                if domain.endswith(suffix) and rule.priority < best_priority:
                    best_match = rule
                    best_priority = rule.priority
            elif domain == pattern or domain.endswith(f".{pattern}"):
                if rule.priority < best_priority:
                    best_match = rule
                    best_priority = rule.priority

        return best_match or _DEFAULT_DOMAIN_RULES[-1]  # Default to wildcard

    def _check_metrics(
        self, platform_id: str, domain: str
    ) -> Optional[StrategyRecommendation]:
        """Check historical metrics for backend recommendation."""
        with self._lock:
            # Sprint 195: Fix — expire stale cache
            if time.time() - self._cache_updated_at > self._cache_ttl_seconds:
                self._metrics_cache.clear()
                self._cache_updated_at = time.time()
                return None

            platform_metrics = self._metrics_cache.get(platform_id)
            if not platform_metrics:
                return None

            # Find best backend by success rate
            best_backend = None
            best_rate = 0.0
            for key, metrics in platform_metrics.items():
                if metrics.success_rate > best_rate and metrics.total_attempts >= 3:
                    best_rate = metrics.success_rate
                    best_backend = metrics.backend

            if best_backend and best_rate > 0.6:
                return StrategyRecommendation(
                    backend=best_backend,
                    confidence=min(best_rate, 0.95),
                    reason=f"Historical success rate: {best_rate:.0%} ({platform_id})",
                    fallback_backends=self._get_fallback_chain(best_backend),
                )

        return None

    def _get_fallback_chain(self, primary: BackendType) -> List[BackendType]:
        """Build a fallback chain based on the primary backend."""
        all_backends = [
            BackendType.SCRAPLING,
            BackendType.CRAWL4AI,
            BackendType.BROWSER,
            BackendType.SERPER_SITE,
            BackendType.SERPER,
        ]
        return [b for b in all_backends if b != primary][:3]

    def update_metrics(
        self,
        platform_id: str,
        backend: BackendType,
        success: bool,
        latency_ms: int = 0,
    ) -> None:
        """Update in-memory metrics cache after a scraping attempt."""
        with self._lock:
            if platform_id not in self._metrics_cache:
                self._metrics_cache[platform_id] = {}

            key = backend.value
            if key not in self._metrics_cache[platform_id]:
                self._metrics_cache[platform_id][key] = BackendMetrics(backend=backend)

            metrics = self._metrics_cache[platform_id][key]
            metrics.total_attempts += 1
            if success:
                metrics.successful_attempts += 1
                metrics.last_success_time = time.time()
            # EMA for latency
            if latency_ms > 0:
                alpha = 0.3
                metrics.avg_latency_ms = (
                    alpha * latency_ms + (1 - alpha) * metrics.avg_latency_ms
                )
            # Sprint 195: Mark cache as updated
            self._cache_updated_at = time.time()

    def add_domain_rule(self, rule: DomainRule) -> None:
        """Add a domain rule dynamically."""
        with self._lock:
            self._domain_rules.append(rule)

    def get_domain_rules(self) -> List[DomainRule]:
        """Return current domain rules (for inspection/testing)."""
        return list(self._domain_rules)

    def get_metrics_summary(self) -> Dict:
        """Return summary of all metrics (for monitoring/debugging)."""
        with self._lock:
            summary = {}
            for platform_id, backends in self._metrics_cache.items():
                summary[platform_id] = {
                    key: {
                        "backend": m.backend.value,
                        "success_rate": f"{m.success_rate:.1%}",
                        "total_attempts": m.total_attempts,
                        "avg_latency_ms": int(m.avg_latency_ms),
                    }
                    for key, m in backends.items()
                }
            return summary


# =============================================================================
# Singleton Pattern
# =============================================================================

_manager_instance: Optional[ScrapingStrategyManager] = None
_manager_lock = threading.Lock()


def get_scraping_strategy_manager() -> ScrapingStrategyManager:
    """Get or create the singleton ScrapingStrategyManager."""
    global _manager_instance
    if _manager_instance is None:
        with _manager_lock:
            if _manager_instance is None:
                _manager_instance = ScrapingStrategyManager()
    return _manager_instance
