"""
Serper.dev Site-Filtered Adapter — Generic site: filter search

Sprint 149: Extracted from product_search_tools._search_platform_via_serper_sync()
Parameterized by site_filter for Shopee, Lazada, TikTok Shop, FB Marketplace, Instagram.
"""

import logging
from typing import List

from app.engine.search_platforms.base import (
    BackendType,
    PlatformConfig,
    ProductSearchResult,
    SearchPlatformAdapter,
)

logger = logging.getLogger(__name__)


class SerperSiteAdapter(SearchPlatformAdapter):
    """
    Site-filtered search via Serper.dev /search endpoint.

    Subclass or instantiate with different PlatformConfig for each platform.
    Adding a new site-based platform = instantiate with new config. No code changes.
    """

    def __init__(self, config: PlatformConfig):
        self._config = config

    def get_config(self) -> PlatformConfig:
        return self._config

    def search_sync(self, query: str, max_results: int = 20) -> List[ProductSearchResult]:
        from app.core.config import get_settings
        settings = get_settings()

        api_key = settings.serper_api_key
        if not api_key:
            raise ValueError("SERPER_API_KEY not configured")

        site_filter = self._config.site_filter or ""
        full_query = f"{site_filter} {query}" if site_filter else query

        import httpx
        timeout = settings.product_search_timeout

        resp = httpx.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": full_query, "gl": "vn", "hl": "vi", "num": min(max_results, 100)},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in data.get("organic", [])[:max_results]:
            results.append(ProductSearchResult(
                platform=self._config.display_name,
                title=item.get("title", ""),
                price=item.get("priceRange", ""),
                link=item.get("link", ""),
                snippet=item.get("snippet", ""),
                source=item.get("source", ""),
            ))
        return results


# =============================================================================
# Pre-built platform configs — each becomes a tool via auto-generation
# =============================================================================

def create_shopee_adapter() -> SerperSiteAdapter:
    return SerperSiteAdapter(PlatformConfig(
        id="shopee",
        display_name="Shopee",
        backend=BackendType.SERPER_SITE,
        site_filter="site:shopee.vn",
        tool_description_vi=(
            "Search Shopee Vietnam for products. "
            "Returns product listings from shopee.vn with titles, prices, and links.\n\n"
            "Args:\n"
            "    query: Product search query (e.g., \"dây điện Cadivi 2.5mm\")\n"
            "    max_results: Maximum number of results (default 20)"
        ),
    ))


def create_lazada_adapter() -> SerperSiteAdapter:
    return SerperSiteAdapter(PlatformConfig(
        id="lazada",
        display_name="Lazada",
        backend=BackendType.SERPER_SITE,
        site_filter="site:lazada.vn",
        tool_description_vi=(
            "Search Lazada Vietnam for products. "
            "Returns product listings with titles, prices, and links.\n\n"
            "Args:\n"
            "    query: Product search query (e.g., \"dây cáp điện 2.5mm\")\n"
            "    max_results: Maximum number of results (default 20)"
        ),
    ))


def create_tiktok_shop_serper_adapter() -> SerperSiteAdapter:
    """TikTok Shop via Serper site: filter (fallback when native API unavailable)."""
    return SerperSiteAdapter(PlatformConfig(
        id="tiktok_shop",
        display_name="TikTok Shop",
        backend=BackendType.SERPER_SITE,
        site_filter="site:tiktok.com/shop",
        tool_description_vi=(
            "Search TikTok Shop Vietnam for products. "
            "Returns product listings with titles, prices, and links.\n\n"
            "Args:\n"
            "    query: Product search query (e.g., \"dây điện 3x2.5mm\")\n"
            "    max_results: Maximum number of results (default 20)"
        ),
    ))


def create_facebook_marketplace_adapter() -> SerperSiteAdapter:
    return SerperSiteAdapter(PlatformConfig(
        id="facebook_marketplace",
        display_name="Facebook Marketplace",
        backend=BackendType.SERPER_SITE,
        site_filter="site:facebook.com/marketplace",
        tool_description_vi=(
            "Search Facebook Marketplace for products in Vietnam. "
            "Returns products with titles, prices, and links.\n\n"
            "Args:\n"
            "    query: Product search query (e.g., \"cuộn dây điện\")\n"
            "    max_results: Maximum number of results (default 20)"
        ),
    ))


def create_instagram_adapter() -> SerperSiteAdapter:
    return SerperSiteAdapter(PlatformConfig(
        id="instagram",
        display_name="Instagram",
        backend=BackendType.SERPER_SITE,
        site_filter="site:instagram.com",
        tool_description_vi=(
            "Search Instagram for product posts in Vietnam. "
            "Finds public shopping posts, reels, and store pages. "
            "Note: Only finds publicly indexed content — private groups require separate auth.\n\n"
            "Args:\n"
            "    query: Product search query (e.g., \"dây điện 2.5mm\")\n"
            "    max_results: Maximum number of results (default 20)"
        ),
    ))
