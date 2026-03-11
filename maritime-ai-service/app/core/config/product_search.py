"""ProductSearchConfig — product search platforms, scraping, browser."""
from typing import Optional

from pydantic import BaseModel


class ProductSearchConfig(BaseModel):
    """Product search — platforms, scraping, browser."""
    enable_product_search: bool = False
    serper_api_key: Optional[str] = None
    apify_api_token: Optional[str] = None
    max_results: int = 30
    timeout: int = 30
    platforms: list[str] = [
        "google_shopping", "shopee", "tiktok_shop", "lazada",
        "facebook_marketplace", "all_web", "instagram", "websosanh",
    ]
    max_iterations: int = 15
    scrape_timeout: int = 10
    max_scrape_pages: int = 10
    enable_tiktok_native_api: bool = False
    enable_browser_scraping: bool = False
    browser_scraping_timeout: int = 15
    enable_browser_screenshots: bool = False
    browser_screenshot_quality: int = 40
    enable_network_interception: bool = True
    network_interception_max_response_size: int = 5_000_000
    enable_auto_group_discovery: bool = False
    auto_group_max_groups: int = 3
