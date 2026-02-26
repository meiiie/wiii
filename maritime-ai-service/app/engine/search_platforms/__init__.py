"""
Search Platforms — Sprint 149: "Cắm & Chạy"

Plugin architecture for product search.
Auto-discovers and registers platform adapters based on config.

Usage:
    from app.engine.search_platforms import init_search_platforms, get_search_platform_registry

    # Initialize at startup (called from tools/__init__.py)
    init_search_platforms()

    # Get all enabled adapters
    registry = get_search_platform_registry()
    for adapter in registry.get_all_enabled():
        results = adapter.search_sync("dây điện 2.5mm")
"""

import logging

from app.engine.search_platforms.base import (
    BackendType,
    PlatformConfig,
    ProductSearchResult,
    SearchPlatformAdapter,
)
from app.engine.search_platforms.registry import (
    SearchPlatformRegistry,
    get_search_platform_registry,
)
from app.engine.search_platforms.circuit_breaker import PerPlatformCircuitBreaker

logger = logging.getLogger(__name__)


def init_search_platforms() -> SearchPlatformRegistry:
    """
    Initialize and register all enabled search platform adapters.

    Reads `product_search_platforms` from config to determine which platforms to enable.
    For TikTok Shop: uses native API when enabled, otherwise Serper fallback.

    Returns:
        The populated SearchPlatformRegistry singleton.
    """
    from app.core.config import get_settings
    settings = get_settings()

    registry = get_search_platform_registry()
    registry.clear()  # Clear for re-init safety

    enabled = set(settings.product_search_platforms)

    # --- Serper-based adapters ---
    if "google_shopping" in enabled:
        from app.engine.search_platforms.adapters.serper_shopping import SerperShoppingAdapter
        registry.register(SerperShoppingAdapter())

    # Site-filtered adapters
    from app.engine.search_platforms.adapters.serper_site import (
        create_shopee_adapter,
        create_lazada_adapter,
        create_tiktok_shop_serper_adapter,
        create_facebook_marketplace_adapter,
        create_instagram_adapter,
    )

    if "shopee" in enabled:
        registry.register(create_shopee_adapter())

    if "lazada" in enabled:
        registry.register(create_lazada_adapter())

    # Facebook: ChainedAdapter [Scrapling → Playwright → Serper] (Sprint 190)
    # Backward compat: preserve old behavior (direct FacebookSearchAdapter) when scrapling disabled
    if "facebook_marketplace" in enabled or "facebook_search" in enabled:
        _use_scrapling = getattr(settings, "enable_scrapling", False) is True
        _scrapling_fb = None

        if _use_scrapling:
            try:
                from app.engine.search_platforms.adapters.scrapling_adapter import create_scrapling_facebook_adapter
                _scrapling_fb = create_scrapling_facebook_adapter()
            except ImportError:
                logger.debug("Scrapling not available for Facebook — skipping")
                _scrapling_fb = None

        if _scrapling_fb is not None:
            # Sprint 190: ChainedAdapter [Scrapling → Playwright → Serper]
            serper_fb = create_facebook_marketplace_adapter()
            _fb_chain = [_scrapling_fb]

            if settings.enable_browser_scraping:
                try:
                    from app.engine.search_platforms.adapters.facebook_search import FacebookSearchAdapter
                    _fb_chain.append(FacebookSearchAdapter(serper_fallback=serper_fb))
                except ImportError:
                    logger.debug("Playwright not available for Facebook — skipping")

            _fb_chain.append(serper_fb)

            from app.engine.search_platforms.chained_adapter import ChainedAdapter
            cb = PerPlatformCircuitBreaker()
            registry.register(ChainedAdapter(
                "facebook_marketplace", "Facebook Marketplace", _fb_chain, cb,
            ))
        else:
            # Pre-Sprint-190 behavior: direct adapter registration
            if settings.enable_browser_scraping:
                try:
                    from app.engine.search_platforms.adapters.facebook_search import FacebookSearchAdapter
                    serper_fallback = create_facebook_marketplace_adapter()
                    registry.register(FacebookSearchAdapter(serper_fallback=serper_fallback))
                except ImportError:
                    registry.register(create_facebook_marketplace_adapter())
            else:
                registry.register(create_facebook_marketplace_adapter())

    if "instagram" in enabled:
        registry.register(create_instagram_adapter())

    # All web search (independent shops)
    if "all_web" in enabled:
        from app.engine.search_platforms.adapters.serper_all_web import SerperAllWebAdapter
        registry.register(SerperAllWebAdapter())

    # WebSosanh.vn price comparison aggregator (94+ Vietnamese shops)
    if "websosanh" in enabled:
        from app.engine.search_platforms.adapters.websosanh import WebSosanhAdapter
        registry.register(WebSosanhAdapter())

    # --- Facebook Group: browser-only, requires cookie (Sprint 155) ---
    if "facebook_group" in enabled:
        if settings.enable_browser_scraping and settings.enable_facebook_cookie:
            try:
                from app.engine.search_platforms.adapters.facebook_group import FacebookGroupSearchAdapter
                # Reuse Serper fallback for non-group FB search
                serper_fb_fallback = create_facebook_marketplace_adapter()
                registry.register(FacebookGroupSearchAdapter(serper_fallback=serper_fb_fallback))
            except ImportError:
                logger.warning("facebook_group adapter skipped — playwright or dependencies missing")
        else:
            logger.info(
                "facebook_group skipped — requires enable_browser_scraping=True + enable_facebook_cookie=True"
            )

    # --- TikTok Shop: native API with Serper fallback ---
    if "tiktok_shop" in enabled:
        if settings.enable_tiktok_native_api:
            from app.engine.search_platforms.adapters.tiktok_research import TikTokResearchAdapter
            serper_fallback = create_tiktok_shop_serper_adapter()
            registry.register(TikTokResearchAdapter(serper_fallback=serper_fallback))
        else:
            registry.register(create_tiktok_shop_serper_adapter())

    # --- Sprint 190: Crawl4AI general adapter for arbitrary Vietnamese dealer sites ---
    if getattr(settings, "enable_crawl4ai", False) is True:
        try:
            from app.engine.search_platforms.adapters.crawl4ai_adapter import create_crawl4ai_generic_adapter
            # Default target URLs for Vietnamese dealer/tech sites
            crawl4ai_urls = [
                "https://www.google.com/search?q={query}+site:vn",
            ]
            registry.register(create_crawl4ai_generic_adapter(
                target_urls=crawl4ai_urls,
                platform_id="crawl4ai_general",
                display_name="Web Crawler (AI)",
            ))
        except ImportError:
            logger.warning("crawl4ai adapter skipped — crawl4ai package not installed")

    # --- Sprint 195: Jina Reader as lightweight fallback ---
    if getattr(settings, "enable_jina_reader", False) is True:
        try:
            from app.engine.search_platforms.adapters.jina_reader_adapter import create_jina_reader_adapter
            registry.register(create_jina_reader_adapter(priority=90))
        except ImportError:
            logger.debug("Jina Reader adapter skipped — httpx not installed")

    logger.info(
        "Search platforms initialized: %d adapters (%s)",
        len(registry),
        ", ".join(registry.list_ids()),
    )
    return registry


__all__ = [
    "BackendType",
    "PlatformConfig",
    "ProductSearchResult",
    "SearchPlatformAdapter",
    "SearchPlatformRegistry",
    "get_search_platform_registry",
    "PerPlatformCircuitBreaker",
    "init_search_platforms",
    # Sprint 190
    "ChainedAdapter",
]
