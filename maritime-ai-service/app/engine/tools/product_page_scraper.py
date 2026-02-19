"""
Product Page Scraper Tool — Sprint 150: "Tìm Sâu"

Fetches a product page URL and extracts structured price/detail data.
Uses static HTML parsing only (no JS execution) for speed and safety.

Extraction priority:
1. JSON-LD structured data (<script type="application/ld+json"> with @type: Product)
2. Open Graph meta tags (og:price:amount, product:price:amount)
3. Meta tags (<meta name="price">)
4. Regex fallback for Vietnamese price patterns (₫, đ, VND)
"""

import json
import logging
import re
from typing import Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Limits
_DEFAULT_TIMEOUT = 10  # seconds
_MAX_CONTENT_BYTES = 500 * 1024  # 500KB
_USER_AGENT = "WiiiBot/1.0 (+https://wiii.ai; product-search)"

# Vietnamese price regex: matches "1.234.567₫", "1,234,567 VND", "1234567đ", etc.
_PRICE_PATTERN = re.compile(
    r"(\d[\d.,]*\d)\s*(?:₫|đ|VNĐ|VND|vnđ|vnd)",
    re.IGNORECASE,
)

# Also match "đ 1.234.567" or "VND 1,234,567" (prefix format)
_PRICE_PATTERN_PREFIX = re.compile(
    r"(?:₫|đ|VNĐ|VND)\s*(\d[\d.,]*\d)",
    re.IGNORECASE,
)


def _parse_vnd_price(price_str: str) -> Optional[float]:
    """Parse a VND price string to float. Delegates to shared utility."""
    from app.engine.search_platforms.utils import parse_vnd_price
    return parse_vnd_price(price_str)


def _extract_from_json_ld(html: str) -> Optional[dict]:
    """Extract product data from JSON-LD structured data."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
    except (ImportError, Exception):
        # Catches both missing bs4 and bs4.FeatureNotFound when lxml missing
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")

    scripts = soup.find_all("script", type="application/ld+json")
    for script in scripts:
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        # Handle @graph arrays
        items = [data] if isinstance(data, dict) else data if isinstance(data, list) else []
        if isinstance(data, dict) and "@graph" in data:
            items = data["@graph"]

        for item in items:
            if not isinstance(item, dict):
                continue
            item_type = item.get("@type", "")
            if isinstance(item_type, list):
                item_type = " ".join(item_type)
            if "Product" not in str(item_type):
                continue

            result = {
                "name": item.get("name", ""),
                "description": (item.get("description") or "")[:300],
                "brand": "",
                "price": "",
                "currency": "",
                "availability": "",
                "image": "",
            }

            # Brand
            brand = item.get("brand")
            if isinstance(brand, dict):
                result["brand"] = brand.get("name", "")
            elif isinstance(brand, str):
                result["brand"] = brand

            # Image
            img = item.get("image")
            if isinstance(img, list) and img:
                img = img[0]
            if isinstance(img, dict):
                img = img.get("url", "")
            if isinstance(img, str):
                result["image"] = img

            # Price — can be in offers or directly on product
            offers = item.get("offers")
            if isinstance(offers, dict):
                offers = [offers]
            elif not isinstance(offers, list):
                offers = []

            for offer in offers:
                if not isinstance(offer, dict):
                    continue
                offer_type = offer.get("@type", "")
                if isinstance(offer_type, list):
                    offer_type = " ".join(offer_type)

                if "AggregateOffer" in str(offer_type):
                    low = offer.get("lowPrice", "")
                    high = offer.get("highPrice", "")
                    result["price"] = f"{low}-{high}" if low and high and low != high else str(low or high)
                else:
                    result["price"] = str(offer.get("price", ""))

                result["currency"] = offer.get("priceCurrency", "VND")

                avail = offer.get("availability", "")
                if "InStock" in str(avail):
                    result["availability"] = "Còn hàng"
                elif "OutOfStock" in str(avail):
                    result["availability"] = "Hết hàng"
                elif avail:
                    result["availability"] = str(avail).split("/")[-1]

                if result["price"]:
                    break

            if result["name"] or result["price"]:
                return result

    return None


def _extract_from_og_meta(html: str) -> Optional[dict]:
    """Extract product data from Open Graph / product meta tags."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
    except (ImportError, Exception):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")

    result = {}

    # OG meta tags
    og_map = {
        "og:title": "name",
        "og:description": "description",
        "og:image": "image",
        "og:price:amount": "price",
        "og:price:currency": "currency",
        "product:price:amount": "price",
        "product:price:currency": "currency",
        "product:brand": "brand",
        "product:availability": "availability",
    }

    for meta in soup.find_all("meta"):
        prop = meta.get("property", "") or meta.get("name", "")
        content = meta.get("content", "")
        if prop in og_map and content:
            key = og_map[prop]
            if key == "description":
                content = content[:300]
            result[key] = content

    # Also check plain meta tags
    price_meta = soup.find("meta", attrs={"name": "price"})
    if price_meta and not result.get("price"):
        result["price"] = price_meta.get("content", "")

    if result.get("price") or result.get("name"):
        result.setdefault("currency", "VND")
        return result

    return None


def _extract_from_regex(html: str) -> Optional[dict]:
    """Fallback: extract Vietnamese prices from raw HTML text."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
    except (ImportError, Exception):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")

    # Get page title
    title = ""
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)[:200]

    # Get visible text (not script/style)
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)[:50000]

    # Find prices
    prices = []
    for match in _PRICE_PATTERN.finditer(text):
        parsed = _parse_vnd_price(match.group(1))
        if parsed:
            prices.append(parsed)
    for match in _PRICE_PATTERN_PREFIX.finditer(text):
        parsed = _parse_vnd_price(match.group(1))
        if parsed:
            prices.append(parsed)

    if not prices and not title:
        return None

    result = {"name": title, "currency": "VND"}

    if prices:
        prices = sorted(set(prices))
        if len(prices) == 1:
            result["price"] = str(int(prices[0]))
        else:
            result["price"] = f"{int(prices[0])}-{int(prices[-1])}"
        result["extracted_prices"] = [int(p) for p in prices[:10]]

    return result


def _fetch_page(url: str, timeout: int = _DEFAULT_TIMEOUT) -> str:
    """Fetch page HTML with safety limits."""
    import httpx

    headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
    }

    with httpx.Client(timeout=timeout, follow_redirects=True, max_redirects=5) as client:
        resp = client.get(url, headers=headers)
        resp.raise_for_status()

        # Check content size
        content_length = resp.headers.get("content-length")
        if content_length and int(content_length) > _MAX_CONTENT_BYTES:
            raise ValueError(f"Page too large: {content_length} bytes (max {_MAX_CONTENT_BYTES})")

        # Check content type
        content_type = resp.headers.get("content-type", "")
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            raise ValueError(f"Not an HTML page: {content_type}")

        return resp.text[:_MAX_CONTENT_BYTES]


@tool
def tool_fetch_product_detail(url: str) -> str:
    """Truy cập trang sản phẩm để lấy giá chính xác, specs, và thông tin chi tiết.
    Dùng khi cần xác nhận giá thật từ link sản phẩm đã tìm được.

    Args:
        url: URL trang sản phẩm (e.g., "https://cellphones.com.vn/macbook-pro-14...")
    """
    from app.core.config import get_settings
    settings = get_settings()
    timeout = getattr(settings, "product_search_scrape_timeout", _DEFAULT_TIMEOUT)

    # Sprint 153: SSRF prevention — block private/reserved IPs
    try:
        from app.engine.search_platforms.utils import validate_url_for_scraping
        validate_url_for_scraping(url)
    except ValueError as e:
        return json.dumps(
            {"error": f"URL không hợp lệ: {str(e)[:200]}", "url": url},
            ensure_ascii=False,
        )

    try:
        html = _fetch_page(url, timeout=timeout)
    except Exception as e:
        return json.dumps(
            {"error": f"Không thể truy cập trang: {str(e)[:200]}", "url": url},
            ensure_ascii=False,
        )

    # Try extraction methods in priority order
    result = _extract_from_json_ld(html)
    source = "json_ld"

    if not result:
        result = _extract_from_og_meta(html)
        source = "og_meta"

    if not result:
        result = _extract_from_regex(html)
        source = "regex_fallback"

    if not result:
        return json.dumps(
            {"error": "Không tìm thấy thông tin giá trên trang này", "url": url},
            ensure_ascii=False,
        )

    result["url"] = url
    result["extraction_method"] = source

    return json.dumps(result, ensure_ascii=False)


def get_product_page_scraper_tools() -> list:
    """Return the list of scraper tools for registration."""
    return [tool_fetch_product_detail]
