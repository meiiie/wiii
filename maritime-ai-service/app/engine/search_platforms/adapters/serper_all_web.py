"""
Serper.dev All Web Adapter — Excludes major platforms

Sprint 149: Extracted from product_search_tools.tool_search_all_web()
Finds B2B, wholesale, and independent Vietnamese shops.
"""

import logging
import re
from typing import List

from app.engine.search_platforms.base import (
    BackendType,
    PlatformConfig,
    ProductSearchResult,
    SearchPlatformAdapter,
)
from app.engine.search_platforms.utils import parse_vnd_price

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
                "    max_results: Maximum number of results (default 20)\n"
                "    page: Page number for pagination (default 1). Use page=2, 3... to get more results."
            ),
            max_results_default=20,
        )

    def search_sync(self, query: str, max_results: int = 20, page: int = 1) -> List[ProductSearchResult]:
        from app.core.config import get_settings
        settings = get_settings()

        api_key = settings.serper_api_key
        if not api_key:
            raise ValueError("SERPER_API_KEY not configured")

        import httpx
        timeout = settings.product_search_timeout

        # Smart query: skip appending "giá bán" if query already contains price-related keywords
        _price_keywords = re.compile(r"(?:giá|gia|bán|ban|mua)", re.IGNORECASE)
        price_suffix = "" if _price_keywords.search(query) else " giá bán"
        search_query = f"{query}{price_suffix} {_EXCLUDE_SITES}"
        payload = {"q": search_query, "gl": "vn", "hl": "vi", "num": min(max_results, 100)}
        if page > 1:
            payload["page"] = page

        resp = httpx.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json=payload,
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in data.get("organic", [])[:max_results]:
            price_str = item.get("priceRange", "")
            results.append(ProductSearchResult(
                platform="Web",
                title=item.get("title", ""),
                price=price_str,
                extracted_price=parse_vnd_price(price_str),
                link=item.get("link", ""),
                snippet=item.get("snippet", ""),
                source=item.get("source", ""),
            ))
        return results
