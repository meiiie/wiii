"""
Apify Generic Adapter — Runs any Apify actor for product scraping

Sprint 149: Extracted from product_search_tools._search_apify_sync()
Optional fallback for platforms that need deeper scraping (Shopee, TikTok, Lazada, FB).
Most actors require paid Apify subscription.
"""

import logging
from typing import Dict, List

from app.engine.search_platforms.base import (
    BackendType,
    PlatformConfig,
    ProductSearchResult,
    SearchPlatformAdapter,
)

logger = logging.getLogger(__name__)


class ApifyGenericAdapter(SearchPlatformAdapter):
    """
    Generic Apify actor runner.

    Runs a named Apify actor with custom input, normalizes results.
    NOTE: Most actors require paid Apify subscription.
    Actor URLs use ~ separator (not /): e.g. "ywlfff2014~shopee-product-scraper"
    """

    def __init__(self, config: PlatformConfig, actor_id: str, input_builder=None):
        """
        Args:
            config: Platform configuration
            actor_id: Apify actor ID (e.g. "ywlfff2014~shopee-product-scraper")
            input_builder: Optional callable(query, max_results) → dict for actor input.
                           Defaults to {"searchQuery": query, "maxItems": max_results}.
        """
        self._config = config
        self._actor_id = actor_id
        self._input_builder = input_builder

    def get_config(self) -> PlatformConfig:
        return self._config

    def _build_input(self, query: str, max_results: int) -> dict:
        if self._input_builder:
            return self._input_builder(query, max_results)
        return {"searchQuery": query, "maxItems": max_results}

    def validate_credentials(self) -> bool:
        from app.core.config import get_settings
        return bool(get_settings().apify_api_token)

    def search_sync(self, query: str, max_results: int = 20, page: int = 1) -> List[ProductSearchResult]:
        from app.core.config import get_settings
        settings = get_settings()

        token = settings.apify_api_token
        if not token:
            raise ValueError("APIFY_API_TOKEN not configured")

        import httpx
        timeout_sec = settings.product_search_timeout
        search_input = self._build_input(query, max_results)

        # Start actor run and wait for finish
        run_resp = httpx.post(
            f"https://api.apify.com/v2/acts/{self._actor_id}/runs",
            params={"token": token, "waitForFinish": timeout_sec},
            json=search_input,
            timeout=timeout_sec + 10,
        )
        run_resp.raise_for_status()
        run_data = run_resp.json().get("data", {})
        dataset_id = run_data.get("defaultDatasetId")

        if not dataset_id:
            raise ValueError(f"No dataset from Apify actor {self._actor_id}")

        # Fetch dataset items
        items_resp = httpx.get(
            f"https://api.apify.com/v2/datasets/{dataset_id}/items",
            params={"token": token, "limit": max_results},
            timeout=30,
        )
        items_resp.raise_for_status()
        raw_items = items_resp.json()

        results = []
        platform_name = self._config.display_name
        for item in raw_items[:max_results]:
            results.append(ProductSearchResult(
                platform=platform_name,
                title=item.get("title") or item.get("name", ""),
                price=item.get("price") or item.get("priceText", ""),
                seller=item.get("seller") or item.get("shopName") or item.get("sellerName", ""),
                rating=item.get("rating") or item.get("ratingAverage"),
                sold_count=item.get("sold") or item.get("soldCount") or item.get("historicalSold"),
                link=item.get("url") or item.get("link", ""),
                image=item.get("image") or item.get("imageUrl", ""),
                location=item.get("location", ""),
            ))
        return results
