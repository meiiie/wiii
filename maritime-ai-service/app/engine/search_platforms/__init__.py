"""Search platform package boundary with lazy adapter loading."""

from __future__ import annotations

import logging
from importlib import import_module
from typing import Any

logger = logging.getLogger(__name__)


def _load_attr(module_path: str, attr_name: str) -> Any:
    module = import_module(module_path)
    return getattr(module, attr_name)


def __getattr__(name: str) -> Any:
    binding_map = {
        "BackendType": ("app.engine.search_platforms.base", "BackendType"),
        "PlatformConfig": ("app.engine.search_platforms.base", "PlatformConfig"),
        "ProductSearchResult": (
            "app.engine.search_platforms.base",
            "ProductSearchResult",
        ),
        "SearchPlatformAdapter": (
            "app.engine.search_platforms.base",
            "SearchPlatformAdapter",
        ),
        "SearchPlatformRegistry": (
            "app.engine.search_platforms.registry",
            "SearchPlatformRegistry",
        ),
        "get_search_platform_registry": (
            "app.engine.search_platforms.registry",
            "get_search_platform_registry",
        ),
        "PerPlatformCircuitBreaker": (
            "app.engine.search_platforms.circuit_breaker",
            "PerPlatformCircuitBreaker",
        ),
        "ChainedAdapter": (
            "app.engine.search_platforms.chained_adapter",
            "ChainedAdapter",
        ),
    }
    target = binding_map.get(name)
    if target is None:
        raise AttributeError(name)
    return _load_attr(*target)


def init_search_platforms():
    """Initialize and register all enabled search platform adapters."""
    settings = _load_attr("app.core.config", "get_settings")()

    registry = _load_attr(
        "app.engine.search_platforms.registry",
        "get_search_platform_registry",
    )()
    registry.clear()

    enabled = set(settings.product_search_platforms)

    if "google_shopping" in enabled:
        serper_shopping_adapter_cls = _load_attr(
            "app.engine.search_platforms.adapters.serper_shopping",
            "SerperShoppingAdapter",
        )
        registry.register(serper_shopping_adapter_cls())

    create_shopee_adapter = _load_attr(
        "app.engine.search_platforms.adapters.serper_site",
        "create_shopee_adapter",
    )
    create_lazada_adapter = _load_attr(
        "app.engine.search_platforms.adapters.serper_site",
        "create_lazada_adapter",
    )
    create_tiktok_shop_serper_adapter = _load_attr(
        "app.engine.search_platforms.adapters.serper_site",
        "create_tiktok_shop_serper_adapter",
    )
    create_facebook_marketplace_adapter = _load_attr(
        "app.engine.search_platforms.adapters.serper_site",
        "create_facebook_marketplace_adapter",
    )
    create_instagram_adapter = _load_attr(
        "app.engine.search_platforms.adapters.serper_site",
        "create_instagram_adapter",
    )

    if "shopee" in enabled:
        registry.register(create_shopee_adapter())

    if "lazada" in enabled:
        registry.register(create_lazada_adapter())

    if "facebook_marketplace" in enabled or "facebook_search" in enabled:
        use_scrapling = getattr(settings, "enable_scrapling", False) is True
        scrapling_adapter = None

        if use_scrapling:
            try:
                create_scrapling_facebook_adapter = _load_attr(
                    "app.engine.search_platforms.adapters.scrapling_adapter",
                    "create_scrapling_facebook_adapter",
                )
                scrapling_adapter = create_scrapling_facebook_adapter()
            except ImportError:
                logger.debug("Scrapling not available for Facebook - skipping")

        if scrapling_adapter is not None:
            serper_fb = create_facebook_marketplace_adapter()
            fb_chain = [scrapling_adapter]

            if settings.enable_browser_scraping:
                try:
                    facebook_search_adapter_cls = _load_attr(
                        "app.engine.search_platforms.adapters.facebook_search",
                        "FacebookSearchAdapter",
                    )
                    fb_chain.append(
                        facebook_search_adapter_cls(serper_fallback=serper_fb)
                    )
                except ImportError:
                    logger.debug("Playwright not available for Facebook - skipping")

            fb_chain.append(serper_fb)

            chained_adapter_cls = _load_attr(
                "app.engine.search_platforms.chained_adapter",
                "ChainedAdapter",
            )
            circuit_breaker_cls = _load_attr(
                "app.engine.search_platforms.circuit_breaker",
                "PerPlatformCircuitBreaker",
            )
            registry.register(
                chained_adapter_cls(
                    "facebook_marketplace",
                    "Facebook Marketplace",
                    fb_chain,
                    circuit_breaker_cls(),
                )
            )
        else:
            if settings.enable_browser_scraping:
                try:
                    facebook_search_adapter_cls = _load_attr(
                        "app.engine.search_platforms.adapters.facebook_search",
                        "FacebookSearchAdapter",
                    )
                    serper_fallback = create_facebook_marketplace_adapter()
                    registry.register(
                        facebook_search_adapter_cls(
                            serper_fallback=serper_fallback
                        )
                    )
                except ImportError:
                    registry.register(create_facebook_marketplace_adapter())
            else:
                registry.register(create_facebook_marketplace_adapter())

    if "instagram" in enabled:
        registry.register(create_instagram_adapter())

    if "all_web" in enabled:
        serper_all_web_adapter_cls = _load_attr(
            "app.engine.search_platforms.adapters.serper_all_web",
            "SerperAllWebAdapter",
        )
        registry.register(serper_all_web_adapter_cls())

    if "websosanh" in enabled:
        websosanh_adapter_cls = _load_attr(
            "app.engine.search_platforms.adapters.websosanh",
            "WebSosanhAdapter",
        )
        registry.register(websosanh_adapter_cls())

    if "facebook_group" in enabled:
        if settings.enable_browser_scraping and settings.enable_facebook_cookie:
            try:
                facebook_group_adapter_cls = _load_attr(
                    "app.engine.search_platforms.adapters.facebook_group",
                    "FacebookGroupSearchAdapter",
                )
                serper_fb_fallback = create_facebook_marketplace_adapter()
                registry.register(
                    facebook_group_adapter_cls(
                        serper_fallback=serper_fb_fallback
                    )
                )
            except ImportError:
                logger.warning(
                    "facebook_group adapter skipped - playwright or dependencies missing"
                )
        else:
            logger.info(
                "facebook_group skipped - requires enable_browser_scraping=True + enable_facebook_cookie=True"
            )

    if "tiktok_shop" in enabled:
        if settings.enable_tiktok_native_api:
            tiktok_research_adapter_cls = _load_attr(
                "app.engine.search_platforms.adapters.tiktok_research",
                "TikTokResearchAdapter",
            )
            serper_fallback = create_tiktok_shop_serper_adapter()
            registry.register(
                tiktok_research_adapter_cls(serper_fallback=serper_fallback)
            )
        else:
            registry.register(create_tiktok_shop_serper_adapter())

    if getattr(settings, "enable_crawl4ai", False) is True:
        try:
            create_crawl4ai_generic_adapter = _load_attr(
                "app.engine.search_platforms.adapters.crawl4ai_adapter",
                "create_crawl4ai_generic_adapter",
            )
            registry.register(
                create_crawl4ai_generic_adapter(
                    target_urls=[
                        "https://www.google.com/search?q={query}+site:vn",
                    ],
                    platform_id="crawl4ai_general",
                    display_name="Web Crawler (AI)",
                )
            )
        except ImportError:
            logger.warning(
                "crawl4ai adapter skipped - crawl4ai package not installed"
            )

    if getattr(settings, "enable_jina_reader", False) is True:
        try:
            create_jina_reader_adapter = _load_attr(
                "app.engine.search_platforms.adapters.jina_reader_adapter",
                "create_jina_reader_adapter",
            )
            registry.register(create_jina_reader_adapter(priority=90))
        except ImportError:
            logger.debug("Jina Reader adapter skipped - httpx not installed")

    logger.info(
        "Search platforms initialized: %d adapters (%s)",
        len(registry),
        ", ".join(registry.list_ids()),
    )

    # --- Site Playbooks (Firecrawl pattern) ---
    if getattr(settings, "enable_site_playbooks", False) is True:
        try:
            from app.engine.search_platforms.playbook_loader import get_playbook_loader
            from app.engine.search_platforms.playbook_adapter import PlaybookDrivenAdapter

            loader = get_playbook_loader()
            existing_ids = set(registry.list_ids())
            playbook_count = 0
            for playbook in loader.get_all():
                if playbook.enabled and playbook.platform_id not in existing_ids:
                    adapter = PlaybookDrivenAdapter(playbook)
                    registry.register(adapter)
                    playbook_count += 1
            if playbook_count:
                logger.info("[PLAYBOOK] Registered %d playbook-driven adapters", playbook_count)
        except Exception as exc:
            logger.warning("[PLAYBOOK] Playbook registration failed: %s", exc)

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
    "ChainedAdapter",
]
