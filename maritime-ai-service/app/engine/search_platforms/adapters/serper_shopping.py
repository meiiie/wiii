"""
Serper.dev Google Shopping Adapter

Sprint 149: Extracted from product_search_tools._search_google_shopping_sync()
Uses Serper /shopping endpoint for structured product data.
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


class SerperShoppingAdapter(SearchPlatformAdapter):
    """Google Shopping search via Serper.dev /shopping endpoint."""

    def get_config(self) -> PlatformConfig:
        return PlatformConfig(
            id="google_shopping",
            display_name="Google Shopping",
            backend=BackendType.SERPER,
            tool_description_vi=(
                "Search Google Shopping for products in Vietnam. "
                "Returns structured product data including prices, ratings, and links. "
                "Use this for the fastest, most structured results across many Vietnamese e-commerce platforms.\n\n"
                "Args:\n"
                "    query: Product search query (e.g., \"cuộn dây điện 3 ruột 2.5mm²\")\n"
                "    max_results: Maximum number of results (default 20, max 100)\n"
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

        payload = {"q": query, "gl": "vn", "hl": "vi", "num": min(max_results, 100)}
        if page > 1:
            payload["page"] = page

        resp = httpx.post(
            "https://google.serper.dev/shopping",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json=payload,
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in data.get("shopping", [])[:max_results]:
            results.append(ProductSearchResult(
                platform="Google Shopping",
                title=item.get("title", ""),
                price=item.get("price", ""),
                extracted_price=item.get("extracted_price"),
                source=item.get("source", ""),
                rating=item.get("rating"),
                reviews=item.get("ratingCount"),
                link=item.get("link", ""),
                image=item.get("imageUrl", ""),
                delivery=item.get("delivery", ""),
            ))
        return results
