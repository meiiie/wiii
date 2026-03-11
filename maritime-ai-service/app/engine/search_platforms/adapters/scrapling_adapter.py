"""
Scrapling Adapter — Stealth Scraper for Anti-Bot Protected Sites

Sprint 190: "Trí Tuệ Săn Hàng" — Enhanced Scraping Backend

Scrapling: Best-in-class anti-bot bypass via TLS fingerprint spoofing.
Best for: Facebook (Cloudflare), protected e-commerce sites, sites with CAPTCHA.

Pattern:
- Lazy-import scrapling (separate dependency from Playwright)
- Feature-gated: only loaded when `enable_scrapling=True`
- Uses StealthyFetcher for Cloudflare/anti-bot bypass
- Falls back to Fetcher (basic) when stealth not needed
- Adaptive CSS/XPath extraction via Scrapling's Adaptor

Dependencies:
    pip install scrapling
"""

import logging
import re
from typing import Dict, List, Optional
from urllib.parse import quote_plus

from app.engine.search_platforms.base import (
    BackendType,
    PlatformConfig,
    ProductSearchResult,
    SearchPlatformAdapter,
)

logger = logging.getLogger(__name__)

# Vietnamese price pattern
_VND_PRICE_RE = re.compile(
    r"([\d.,]+)\s*(?:₫|đ|VND|vnđ|VNĐ|dong)",
    re.IGNORECASE,
)


def _extract_vnd_price(price_str: str) -> Optional[float]:
    """Extract numeric VND price from a string."""
    if not price_str:
        return None
    match = _VND_PRICE_RE.search(price_str)
    if match:
        num_str = match.group(1).replace(".", "").replace(",", "")
        try:
            return float(num_str)
        except ValueError:
            return None
    digits = re.sub(r"[^\d]", "", price_str)
    if digits and len(digits) >= 4:
        try:
            return float(digits)
        except ValueError:
            return None
    return None


class ScraplingStealthAdapter(SearchPlatformAdapter):
    """
    Stealth scraper via Scrapling — best for anti-bot protected sites.

    Capabilities:
    - TLS fingerprint spoofing (bypass Cloudflare, Akamai)
    - Real browser simulation via StealthyFetcher
    - Adaptive CSS/XPath extraction (tolerant of layout changes)

    Args:
        target_urls: List of URL templates. Use {query} for search query.
        platform_id: Unique ID for this adapter instance
        display_name: Human-readable name
        css_selectors: Dict of CSS selectors for product extraction.
            Keys: "container", "title", "price", "link", "image", "seller"
        use_stealth: Whether to use StealthyFetcher (slower but bypasses anti-bot).
            If False, uses basic Fetcher (faster, for non-protected sites).
        priority: Priority in ChainedAdapter (lower = higher priority)
    """

    def __init__(
        self,
        target_urls: Optional[List[str]] = None,
        platform_id: str = "scrapling_general",
        display_name: str = "Stealth Scraper",
        css_selectors: Optional[Dict[str, str]] = None,
        use_stealth: bool = True,
        priority: int = 3,
    ):
        self._target_urls = target_urls or []
        self._css_selectors = css_selectors or {}
        self._use_stealth = use_stealth
        self._config = PlatformConfig(
            id=platform_id,
            display_name=display_name,
            backend=BackendType.SCRAPLING,
            tool_description_vi=f"Tìm kiếm sản phẩm trên {display_name} (bypass anti-bot)",
            priority=priority,
        )

    def get_config(self) -> PlatformConfig:
        """Return platform configuration."""
        return self._config

    def search_sync(
        self, query: str, max_results: int = 20, page: int = 1
    ) -> List[ProductSearchResult]:
        """
        Execute search by fetching target URLs with stealth mode.

        Steps:
        1. Build search URLs from target_urls + query
        2. Lazy-import scrapling
        3. Fetch each URL with StealthyFetcher (auto Cloudflare bypass)
        4. Parse with Scrapling Adaptor (CSS/XPath + adaptive matching)
        5. Normalize to ProductSearchResult

        Args:
            query: Search query string
            max_results: Maximum results to return
            page: Page number (1-based)

        Returns:
            List of normalized ProductSearchResult
        """
        if not self._target_urls:
            logger.warning("ScraplingStealthAdapter[%s]: No target URLs configured", self._config.id)
            return []

        # Build search URLs
        encoded_query = quote_plus(query)
        urls = []
        for url_template in self._target_urls:
            url = url_template.replace("{query}", encoded_query)
            if page > 1 and "{page}" in url_template:
                url = url.replace("{page}", str(page))
            urls.append(url)

        # Fetch and extract
        try:
            return self._fetch_and_extract(urls, query, max_results)
        except ImportError as e:
            logger.error(
                "Scrapling not installed. Run: pip install scrapling. Error: %s", e
            )
            return []
        except Exception as e:
            logger.error(
                "ScraplingStealthAdapter[%s] search failed: %s",
                self._config.id, str(e)[:300],
            )
            return []

    def _fetch_and_extract(
        self, urls: List[str], query: str, max_results: int
    ) -> List[ProductSearchResult]:
        """Fetch URLs with Scrapling and extract product data."""
        # Lazy import
        if self._use_stealth:
            from scrapling import StealthyFetcher as Fetcher
        else:
            from scrapling import Fetcher

        all_results: List[ProductSearchResult] = []
        fetcher = Fetcher()

        for url in urls:
            if len(all_results) >= max_results:
                break

            try:
                response = fetcher.get(
                    url,
                    timeout=self._config.timeout_seconds,
                    follow_redirects=True,
                )

                if response.status != 200:
                    logger.warning(
                        "Scrapling[%s]: HTTP %d for %s",
                        self._config.id, response.status, url,
                    )
                    continue

                # Extract products
                products = self._extract_products(response, url, query)
                all_results.extend(products)
                logger.info(
                    "Scrapling[%s] extracted %d products from %s",
                    self._config.id, len(products), url,
                )

            except Exception as e:
                logger.warning(
                    "Scrapling[%s] error fetching %s: %s",
                    self._config.id, url, str(e)[:200],
                )

        return all_results[:max_results]

    def _extract_products(
        self, response, source_url: str, query: str
    ) -> List[ProductSearchResult]:
        """
        Extract product data from Scrapling response using CSS selectors.

        Falls back to heuristic text extraction when selectors not configured.
        """
        # If CSS selectors provided, use structured extraction
        if self._css_selectors.get("container"):
            return self._extract_with_selectors(response, source_url)

        # Fallback: extract from page text content
        return self._extract_from_text(response, source_url, query)

    @staticmethod
    def _css_first(element, selector: str):
        """Get first element matching CSS selector (scrapling 0.4+ has no css_first)."""
        if not selector:
            return None
        try:
            matches = element.css(selector)
            return matches[0] if matches else None
        except Exception:
            return None

    @staticmethod
    def _el_text(element) -> str:
        """Extract text from a scrapling element (v0.4 API: .text is TextHandler, not callable)."""
        if element is None:
            return ""
        try:
            if hasattr(element, "get_all_text"):
                return element.get_all_text() or ""
            return str(element.text) if element.text else ""
        except Exception:
            return ""

    def _extract_with_selectors(
        self, response, source_url: str
    ) -> List[ProductSearchResult]:
        """Extract products using configured CSS selectors."""
        results: List[ProductSearchResult] = []
        container_sel = self._css_selectors.get("container", "")

        try:
            containers = response.css(container_sel)
            for container in containers:
                title_el = self._css_first(container, self._css_selectors.get("title", ""))
                title = self._el_text(title_el)
                if not title:
                    continue

                price_el = self._css_first(container, self._css_selectors.get("price", ""))
                price_str = self._el_text(price_el)

                link_el = self._css_first(container, self._css_selectors.get("link", "a"))
                link = link_el.attrib.get("href", source_url) if link_el else source_url

                image_el = self._css_first(container, self._css_selectors.get("image", "img"))
                image = image_el.attrib.get("src", "") if image_el else ""

                seller_el = self._css_first(container, self._css_selectors.get("seller", ""))
                seller = self._el_text(seller_el)

                results.append(ProductSearchResult(
                    platform=self._config.id,
                    title=title[:200],
                    price=price_str,
                    extracted_price=_extract_vnd_price(price_str),
                    link=link,
                    seller=seller,
                    image=image,
                    source=source_url,
                ))
        except Exception as e:
            logger.warning(
                "Scrapling[%s] CSS extraction failed: %s",
                self._config.id, str(e)[:200],
            )

        return results

    def _extract_from_text(
        self, response, source_url: str, query: str
    ) -> List[ProductSearchResult]:
        """Fallback: extract products from page text using heuristics."""
        results: List[ProductSearchResult] = []

        try:
            # scrapling 0.4: response.text is TextHandler, use get_all_text()
            text = response.get_all_text() if hasattr(response, "get_all_text") else ""
            if not text or len(text) < 50:
                return results

            # Split query into words for matching (original query, not URL-encoded)
            query_words = set(w.lower() for w in query.split() if len(w) >= 2)
            if not query_words:
                query_words = {query.lower()}

            # Broad CSS selectors covering Vietnamese e-commerce sites
            product_elements = response.css(
                "[class*='product'], [class*='item'], [class*='card'], "
                "[class*='listing'], [class*='result'], "
                "[data-product], .product-item, .search-result, "
                ".product-single, .product-card, .sp-item"
            )

            seen_titles = set()  # dedup by title+price

            for element in product_elements[:30]:
                el_text = self._el_text(element)
                if not el_text or len(el_text) < 10:
                    continue

                el_text_lower = el_text.lower()
                # Match: at least one query word found in element text
                if not any(w in el_text_lower for w in query_words):
                    continue

                # Extract title from sub-elements or first substantial line
                title = ""
                # Try common title selectors first
                for title_sel in [
                    "[class*='name']", "[class*='title']",
                    "h2", "h3", "h4", "a[title]",
                ]:
                    title_el = self._css_first(element, title_sel)
                    if title_el:
                        candidate = self._el_text(title_el).strip()
                        if len(candidate) > 5:
                            title = candidate
                            break

                # Fallback: first substantial line
                if not title:
                    for part in el_text.split("\n"):
                        part = part.strip()
                        if len(part) > 10 and not _VND_PRICE_RE.match(part):
                            title = part
                            break

                if not title:
                    continue

                # Extract price
                price_match = _VND_PRICE_RE.search(el_text)
                price_str = price_match.group(0) if price_match else ""

                # Dedup by (title, price) — same product listed multiple times
                dedup_key = (title[:50].lower(), price_str)
                if dedup_key in seen_titles:
                    continue
                seen_titles.add(dedup_key)

                # Extract seller from common selectors
                seller = ""
                for seller_sel in ["[class*='merchant']", "[class*='seller']", "[class*='shop']", "[class*='store']"]:
                    seller_el = self._css_first(element, seller_sel)
                    if seller_el:
                        seller = self._el_text(seller_el).strip()
                        if seller:
                            break

                # Try to find link
                link_el = self._css_first(element, "a[href]")
                link = link_el.attrib.get("href", source_url) if link_el else source_url

                # Try to find image
                img_el = self._css_first(element, "img[src]")
                image = img_el.attrib.get("src", "") if img_el else ""

                results.append(ProductSearchResult(
                    platform=self._config.id,
                    title=title[:200],
                    price=price_str,
                    extracted_price=_extract_vnd_price(price_str),
                    link=link,
                    seller=seller,
                    image=image,
                    source=source_url,
                    snippet=el_text[:300].replace("\n", " "),
                ))

        except Exception as e:
            logger.warning(
                "Scrapling[%s] text extraction failed: %s",
                self._config.id, str(e)[:200],
            )

        return results


# ============================================================================
# Factory functions for specific platforms
# ============================================================================

def create_scrapling_facebook_adapter() -> ScraplingStealthAdapter:
    """Create a Scrapling adapter for Facebook Marketplace search."""
    return ScraplingStealthAdapter(
        target_urls=[
            "https://www.facebook.com/marketplace/search/?query={query}",
        ],
        platform_id="scrapling_facebook",
        display_name="Facebook (Stealth)",
        use_stealth=True,
        priority=2,  # High priority (before Playwright)
    )


def create_scrapling_general_adapter(
    target_urls: List[str],
    platform_id: str = "scrapling_general",
    display_name: str = "Stealth Scraper",
) -> ScraplingStealthAdapter:
    """Create a general Scrapling adapter for any anti-bot protected site."""
    return ScraplingStealthAdapter(
        target_urls=target_urls,
        platform_id=platform_id,
        display_name=display_name,
        use_stealth=True,
        priority=3,
    )
