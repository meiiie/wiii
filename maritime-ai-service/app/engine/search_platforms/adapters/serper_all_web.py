"""
Serper.dev All Web Adapter — Excludes major platforms

Sprint 149: Extracted from product_search_tools.tool_search_all_web()
Finds B2B, wholesale, and independent Vietnamese shops.
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

# Exclude major e-commerce platforms to find independent shops
_EXCLUDE_SITES = "-site:shopee.vn -site:lazada.vn -site:tiki.vn"


class SerperAllWebAdapter(SearchPlatformAdapter):
    """Search all web for products, excluding major platforms."""

    def get_config(self) -> PlatformConfig:
        return PlatformConfig(
            id="all_web",
            display_name="Web (all)",
            backend=BackendType.SERPER,
            tool_description_vi=(
                "Search ALL websites for product prices — not just major platforms. "
                "This finds small/independent Vietnamese shops, B2B suppliers, wholesale distributors, "
                "and niche stores that often have better prices than Shopee/Lazada. "
                "Uses Google web search with Vietnamese locale.\n\n"
                "Args:\n"
                "    query: Product search query with \"giá\" or \"mua\" for best results "
                "(e.g., \"giá dây điện 3 ruột 2.5mm mua ở đâu\")\n"
                "    max_results: Maximum number of results (default 20)"
            ),
            max_results_default=20,
        )

    def search_sync(self, query: str, max_results: int = 20) -> List[ProductSearchResult]:
        from app.core.config import get_settings
        settings = get_settings()

        api_key = settings.serper_api_key
        if not api_key:
            raise ValueError("SERPER_API_KEY not configured")

        import httpx
        timeout = settings.product_search_timeout

        search_query = f"{query} giá bán {_EXCLUDE_SITES}"
        resp = httpx.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": search_query, "gl": "vn", "hl": "vi", "num": min(max_results, 100)},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in data.get("organic", [])[:max_results]:
            results.append(ProductSearchResult(
                platform="Web",
                title=item.get("title", ""),
                price=item.get("priceRange", ""),
                link=item.get("link", ""),
                snippet=item.get("snippet", ""),
                source=item.get("source", ""),
            ))
        return results
