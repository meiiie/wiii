"""
WebSosanh.vn Price Aggregator Adapter

Sprint 151: "So Sanh Gia" — HTML scraping adapter for websosanh.vn,
Vietnam's largest price comparison site aggregating 94+ shops.

No API available — uses static HTML parsing with BeautifulSoup.
URL pattern: https://websosanh.vn/s/{query+with+plus}.htm?page={N}

HTML selectors (verified live Feb 2026):
- Product container: .product-single-info
- Name: .product-single-name a (inside h2)
- Price: .product-single-price (inside .product-single-price-box)
- Seller: .merchant-name (inside .product-single-merchant)
- Link: .product-single-name a[href] (relative, prepend https://websosanh.vn)
"""

import logging
from typing import List, Optional
from urllib.parse import quote

from app.engine.search_platforms.base import (
    BackendType,
    PlatformConfig,
    ProductSearchResult,
    SearchPlatformAdapter,
)

logger = logging.getLogger(__name__)

_BASE_URL = "https://websosanh.vn/s/"
_USER_AGENT = "WiiiBot/1.0 (+https://wiii.ai; product-search)"


def _parse_vnd_price(price_str: str) -> Optional[float]:
    """Parse a VND price string to float. Delegates to shared utility."""
    from app.engine.search_platforms.utils import parse_vnd_price
    return parse_vnd_price(price_str)


def _build_search_url(query: str, page: int = 1) -> str:
    """Build WebSosanh search URL.

    Spaces are encoded as '+', Vietnamese chars preserved.
    Page param appended as query string for page > 1.
    """
    # WebSosanh uses + for spaces in path, not %20
    encoded = quote(query, safe="").replace("%20", "+")
    url = f"{_BASE_URL}{encoded}.htm"
    if page > 1:
        url += f"?page={page}"
    return url


class WebSosanhAdapter(SearchPlatformAdapter):
    """WebSosanh.vn — price comparison aggregator for 94+ Vietnamese shops."""

    def get_config(self) -> PlatformConfig:
        return PlatformConfig(
            id="websosanh",
            display_name="WebSosanh.vn",
            backend=BackendType.CUSTOM,
            tool_description_vi=(
                "Tim kiem va SO SANH GIA san pham tren WebSosanh.vn — "
                "trang tong hop gia tu 94+ cua hang lon nho tai Viet Nam. "
                "Day la nguon tot nhat de tim gia re nhat vi no aggregates tu "
                "CellphoneS, FPTShop, ShopDunk, Bach Long, va hang tram shop nho khac.\n\n"
                "Args:\n"
                "    query: Ten san pham (e.g., 'MacBook Pro M4 Pro 24GB')\n"
                "    max_results: So ket qua toi da (default 20)\n"
                "    page: Trang ket qua (default 1). Dung page=2,3... de xem them."
            ),
            max_results_default=20,
        )

    def search_sync(self, query: str, max_results: int = 20, page: int = 1) -> List[ProductSearchResult]:
        """Scrape WebSosanh.vn search results."""
        if not query or not query.strip():
            return []

        from app.core.config import get_settings
        settings = get_settings()

        import httpx
        timeout = settings.product_search_timeout

        url = _build_search_url(query.strip(), page)

        try:
            resp = httpx.get(
                url,
                headers={
                    "User-Agent": _USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
                },
                timeout=timeout,
                follow_redirects=True,
            )
            resp.raise_for_status()
        except httpx.TimeoutException:
            logger.warning("[WEBSOSANH] Timeout fetching %s", url)
            return []
        except httpx.HTTPStatusError as e:
            logger.warning("[WEBSOSANH] HTTP %d for %s", e.response.status_code, url)
            return []
        except httpx.HTTPError as e:
            logger.warning("[WEBSOSANH] Connection error for %s: %s", url, e)
            return []

        content_type = resp.headers.get("content-type", "")
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            logger.warning("[WEBSOSANH] Non-HTML response: %s", content_type)
            return []

        return self._parse_html(resp.text, max_results)

    def _parse_html(self, html: str, max_results: int) -> List[ProductSearchResult]:
        """Parse WebSosanh search results HTML."""
        try:
            from bs4 import BeautifulSoup
            try:
                soup = BeautifulSoup(html, "lxml")
            except Exception:
                soup = BeautifulSoup(html, "html.parser")
        except ImportError:
            logger.error("[WEBSOSANH] beautifulsoup4 not installed")
            return []

        # Primary selector (verified live Feb 2026)
        items = soup.select(".product-single-info")
        if not items:
            # Fallback selectors in case of layout change
            items = soup.select(".product-short-info") or soup.select(".product-item")

        results: List[ProductSearchResult] = []
        for item in items[:max_results]:
            try:
                result = self._parse_item(item)
                if result:
                    results.append(result)
            except Exception as e:
                logger.debug("[WEBSOSANH] Failed to parse item: %s", e)
                continue

        logger.info("[WEBSOSANH] Parsed %d results from HTML", len(results))
        return results

    def _parse_item(self, item) -> Optional[ProductSearchResult]:
        """Parse a single product item from BeautifulSoup element."""
        # Title + link — primary: .product-single-name a
        name_el = (
            item.select_one(".product-single-name a")
            or item.select_one(".product-info-name a")
            or item.select_one(".product-name a")
            or item.select_one("a.product-name")
        )

        title = name_el.get_text(strip=True) if name_el else ""
        link = ""
        if name_el and name_el.get("href"):
            href = name_el["href"]
            if href.startswith("/"):
                link = f"https://websosanh.vn{href}"
            elif href.startswith("http"):
                link = href

        # Price — primary: .product-single-price
        price_el = (
            item.select_one(".product-single-price")
            or item.select_one(".product-info-price")
            or item.select_one(".product-price")
        )
        price_text = price_el.get_text(strip=True) if price_el else ""
        extracted_price = _parse_vnd_price(price_text) if price_text else None

        # Seller/merchant — primary: .merchant-name
        seller_el = (
            item.select_one(".merchant-name")
            or item.select_one(".product-single-merchant")
            or item.select_one(".product-info-merchant")
            or item.select_one(".product-shop")
        )
        seller = seller_el.get_text(strip=True) if seller_el else ""

        # Image — try product thumbnail selectors
        image = ""
        img_el = (
            item.select_one(".product-image img")
            or item.select_one(".product-single-image img")
            or item.select_one("img")
        )
        if img_el:
            img_src = img_el.get("src") or img_el.get("data-src") or ""
            if img_src:
                if img_src.startswith("//"):
                    image = f"https:{img_src}"
                elif img_src.startswith("/"):
                    image = f"https://websosanh.vn{img_src}"
                elif img_src.startswith("http"):
                    image = img_src

        if not title and not price_text:
            return None

        return ProductSearchResult(
            platform="WebSosanh.vn",
            title=title,
            price=price_text,
            extracted_price=extracted_price,
            link=link,
            seller=seller,
            image=image,
        )
