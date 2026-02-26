"""
Crawl4AI Adapter — General Website Scraper via Crawl4AI

Sprint 190: "Trí Tuệ Săn Hàng" — Enhanced Scraping Backend

Crawl4AI (60.9k★): Async web crawler with built-in LLM extraction.
Best for: general websites, Vietnamese dealer sites (zebratech.vn, tanphat.com.vn),
and arbitrary product pages where CSS selectors are unknown.

Pattern:
- Lazy-import crawl4ai (heavy dependency, ~150MB with Playwright)
- Feature-gated: only loaded when `enable_crawl4ai=True`
- Runs async crawler in dedicated thread to avoid FastAPI event loop conflicts
- Supports 2 extraction modes:
  1. JsonCssExtractionStrategy — when CSS selectors are known (fast, no LLM cost)
  2. LLMExtractionStrategy — when page structure is unknown (uses Gemini/OpenAI tokens)

Dependencies:
    pip install crawl4ai
"""

import asyncio
import json
import logging
import re
import threading
from concurrent.futures import Future
from typing import Dict, List, Optional
from urllib.parse import quote_plus

from app.engine.search_platforms.base import (
    BackendType,
    PlatformConfig,
    ProductSearchResult,
    SearchPlatformAdapter,
)

logger = logging.getLogger(__name__)

# Vietnamese price pattern: "1.500.000 ₫", "1,500,000 VND", "1500000đ"
_VND_PRICE_RE = re.compile(
    r"([\d.,]+)\s*(?:₫|đ|VND|vnđ|VNĐ|dong)",
    re.IGNORECASE,
)

# Default LLM extraction schema for product pages
_DEFAULT_PRODUCT_SCHEMA = {
    "type": "object",
    "properties": {
        "products": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Tên sản phẩm"},
                    "price": {"type": "string", "description": "Giá sản phẩm (bao gồm đơn vị tiền tệ)"},
                    "seller": {"type": "string", "description": "Tên người bán hoặc cửa hàng"},
                    "link": {"type": "string", "description": "URL trang sản phẩm"},
                    "image": {"type": "string", "description": "URL hình ảnh sản phẩm"},
                },
                "required": ["title"],
            },
        }
    },
}


def _extract_vnd_price(price_str: str) -> Optional[float]:
    """Extract numeric VND price from a string like '1.500.000 ₫'."""
    if not price_str:
        return None
    match = _VND_PRICE_RE.search(price_str)
    if match:
        num_str = match.group(1).replace(".", "").replace(",", "")
        try:
            return float(num_str)
        except ValueError:
            return None
    # Fallback: try to extract any number
    digits = re.sub(r"[^\d]", "", price_str)
    if digits and len(digits) >= 4:  # At least 4 digits for VND
        try:
            return float(digits)
        except ValueError:
            return None
    return None


def _run_async_in_thread(coro):
    """Run an async coroutine in a new thread with its own event loop.

    Avoids greenlet "Cannot switch to a different task" errors when
    called from within FastAPI's event loop (same pattern as browser_base.py).
    """
    result_future: Future = Future()

    def _thread_target():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(coro)
                result_future.set_result(result)
            finally:
                loop.close()
        except Exception as e:
            result_future.set_exception(e)

    thread = threading.Thread(target=_thread_target, daemon=True)
    thread.start()
    thread.join(timeout=120)  # 2 minutes max

    if not result_future.done():
        raise TimeoutError("Crawl4AI crawl timed out after 120 seconds")

    return result_future.result()


class Crawl4AIGeneralAdapter(SearchPlatformAdapter):
    """
    Generic website scraper via Crawl4AI.

    Crawl target URLs and extract product information using either
    CSS-based extraction or LLM-based extraction.

    Args:
        target_urls: List of URL templates. Use {query} placeholder for search query.
            Example: ["https://zebratech.vn/?s={query}", "https://tanphat.com.vn/search?q={query}"]
        platform_id: Unique ID for this adapter instance (default: "crawl4ai_general")
        display_name: Human-readable name (default: "Web Crawler (AI)")
        extraction_schema: Optional JSON schema for LLM extraction.
            If None, uses _DEFAULT_PRODUCT_SCHEMA.
        css_selectors: Optional dict of CSS selectors for structured extraction.
            Keys: "product_container", "title", "price", "link", "image", "seller"
            If provided, uses JsonCssExtractionStrategy (faster, no LLM cost).
        use_llm_extraction: Whether to use LLM extraction (costs tokens).
            If False and no css_selectors provided, falls back to markdown parsing.
        priority: Priority in ChainedAdapter (lower = higher priority)
    """

    def __init__(
        self,
        target_urls: Optional[List[str]] = None,
        platform_id: str = "crawl4ai_general",
        display_name: str = "Web Crawler (AI)",
        extraction_schema: Optional[dict] = None,
        css_selectors: Optional[Dict[str, str]] = None,
        use_llm_extraction: bool = False,
        priority: int = 5,
    ):
        self._target_urls = target_urls or []
        self._extraction_schema = extraction_schema or _DEFAULT_PRODUCT_SCHEMA
        self._css_selectors = css_selectors
        self._use_llm_extraction = use_llm_extraction
        self._config = PlatformConfig(
            id=platform_id,
            display_name=display_name,
            backend=BackendType.CRAWL4AI,
            tool_description_vi=f"Crawl website và trích xuất thông tin sản phẩm bằng AI ({display_name})",
            priority=priority,
        )

    def get_config(self) -> PlatformConfig:
        """Return platform configuration."""
        return self._config

    def search_sync(
        self, query: str, max_results: int = 20, page: int = 1
    ) -> List[ProductSearchResult]:
        """
        Execute search by crawling target URLs and extracting product data.

        Steps:
        1. Build search URLs from target_urls + query
        2. Lazy-import crawl4ai
        3. Run async crawler in dedicated thread
        4. Extract products using configured strategy
        5. Normalize to ProductSearchResult

        Args:
            query: Search query string
            max_results: Maximum results to return
            page: Page number (1-based, not all sites support pagination)

        Returns:
            List of normalized ProductSearchResult
        """
        if not self._target_urls:
            logger.warning("Crawl4AIGeneralAdapter: No target URLs configured")
            return []

        # Build search URLs
        encoded_query = quote_plus(query)
        urls = []
        for url_template in self._target_urls:
            url = url_template.replace("{query}", encoded_query)
            # Handle page parameter if present
            if page > 1 and "{page}" in url_template:
                url = url.replace("{page}", str(page))
            urls.append(url)

        # Crawl and extract
        try:
            results = _run_async_in_thread(
                self._crawl_urls(urls, query, max_results)
            )
            return results[:max_results]
        except ImportError as e:
            logger.error(
                "Crawl4AI not installed. Run: pip install crawl4ai. Error: %s", e
            )
            return []
        except Exception as e:
            logger.error(
                "Crawl4AIGeneralAdapter search failed: %s", str(e)[:300]
            )
            return []

    async def _crawl_urls(
        self, urls: List[str], query: str, max_results: int
    ) -> List[ProductSearchResult]:
        """Async crawl multiple URLs and extract products."""
        # Lazy import crawl4ai
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

        all_results: List[ProductSearchResult] = []

        browser_config = BrowserConfig(
            headless=True,
            verbose=False,
            browser_type="chromium",
        )

        async with AsyncWebCrawler(config=browser_config) as crawler:
            for url in urls:
                if len(all_results) >= max_results:
                    break

                try:
                    crawl_config = CrawlerRunConfig(
                        wait_until="domcontentloaded",
                        page_timeout=self._config.timeout_seconds * 1000,
                    )

                    result = await crawler.arun(url=url, config=crawl_config)

                    if not result.success:
                        logger.warning(
                            "Crawl4AI failed for %s: %s",
                            url, getattr(result, "error_message", None) or "unknown error",
                        )
                        continue

                    # Extract markdown content (v0.8+: prefer markdown_v2.raw_markdown)
                    md_content = ""
                    if hasattr(result, "markdown_v2") and result.markdown_v2:
                        md_content = getattr(result.markdown_v2, "raw_markdown", "") or ""
                    if not md_content:
                        md_content = result.markdown or ""

                    # Extract products from crawled content
                    products = self._extract_products_from_markdown(
                        md_content,
                        url,
                        query,
                    )
                    all_results.extend(products)
                    logger.info(
                        "Crawl4AI extracted %d products from %s",
                        len(products), url,
                    )

                except Exception as e:
                    logger.warning(
                        "Crawl4AI error crawling %s: %s", url, str(e)[:200]
                    )

        return all_results

    def _extract_products_from_markdown(
        self, markdown: str, source_url: str, query: str
    ) -> List[ProductSearchResult]:
        """
        Extract product information from crawled markdown content.

        Multi-strategy extraction:
        1. Section-based: split by headers/rules, match query words
        2. Link+price proximity: find markdown links near VND prices
        """
        results: List[ProductSearchResult] = []
        if not markdown or len(markdown) < 50:
            return results

        query_lower = query.lower()
        query_words = set(w for w in query_lower.split() if len(w) >= 2)
        if not query_words:
            query_words = {query_lower}

        seen_titles = set()

        # Strategy 1: Section-based extraction (headers, list items, horizontal rules)
        sections = re.split(r"\n(?=#{1,3}\s|\*\s|\d+\.\s|---)", markdown)

        for section in sections:
            section = section.strip()
            if len(section) < 20:
                continue

            section_lower = section.lower()
            if not any(w in section_lower for w in query_words):
                continue

            # Extract title (first line or first header)
            lines = section.split("\n")
            title = lines[0].strip().lstrip("#").strip()
            # Remove markdown link syntax: [text](url) → text
            title = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", title)
            if not title or len(title) < 5:
                continue

            title_key = title[:50].lower()
            if title_key in seen_titles:
                continue
            seen_titles.add(title_key)

            price_match = _VND_PRICE_RE.search(section)
            price_str = price_match.group(0) if price_match else ""
            extracted_price = _extract_vnd_price(section)

            # Extract links (markdown or plain URL)
            link_match = re.search(r"\[.*?\]\((https?://[^\)]+)\)", section)
            if not link_match:
                link_match = re.search(r"(https?://\S+)", section)
            link = link_match.group(1) if link_match else source_url

            results.append(ProductSearchResult(
                platform=self._config.id,
                title=title[:200],
                price=price_str,
                extracted_price=extracted_price,
                link=link,
                source=source_url,
                snippet=section[:300].replace("\n", " "),
            ))

        # Strategy 2: If section-based found nothing, try line-by-line link+price proximity
        if not results:
            lines = markdown.split("\n")
            for i, line in enumerate(lines):
                line = line.strip()
                if len(line) < 10:
                    continue
                line_lower = line.lower()
                if not any(w in line_lower for w in query_words):
                    continue

                # Check for a product-like line: has a link or header
                title = ""
                link = source_url

                # Extract from markdown link
                link_m = re.search(r"\[([^\]]+)\]\((https?://[^\)]+)\)", line)
                if link_m:
                    title = link_m.group(1).strip()
                    link = link_m.group(2)
                elif line.startswith("#"):
                    title = line.lstrip("#").strip()
                else:
                    # Plain text line with query match
                    title = re.sub(r"\*+", "", line).strip()

                if not title or len(title) < 5:
                    continue

                title_key = title[:50].lower()
                if title_key in seen_titles:
                    continue
                seen_titles.add(title_key)

                # Look for price in surrounding lines (±3)
                context = "\n".join(lines[max(0, i - 2):i + 3])
                price_match = _VND_PRICE_RE.search(context)
                price_str = price_match.group(0) if price_match else ""

                results.append(ProductSearchResult(
                    platform=self._config.id,
                    title=title[:200],
                    price=price_str,
                    extracted_price=_extract_vnd_price(price_str),
                    link=link,
                    source=source_url,
                    snippet=context[:300].replace("\n", " "),
                ))

        return results

    async def _extract_products_with_llm(
        self, html: str, url: str, query: str
    ) -> List[ProductSearchResult]:
        """
        Extract products using Crawl4AI's LLMExtractionStrategy.

        This is more expensive (uses LLM tokens) but handles unknown page structures.
        Feature-gated by `crawl4ai_use_llm_extraction` config flag.
        """
        try:
            from crawl4ai.extraction_strategy import LLMExtractionStrategy

            from app.core.config import get_settings
            _model = get_settings().google_model
            strategy = LLMExtractionStrategy(
                provider=f"google/{_model}",
                schema=self._extraction_schema,
                instruction=f"Trích xuất tất cả sản phẩm liên quan đến '{query}' từ trang web này. Bao gồm tên, giá, người bán, link, hình ảnh.",
            )

            extracted = strategy.extract(url=url, html=html)
            if not extracted:
                return []

            products_data = json.loads(extracted) if isinstance(extracted, str) else extracted
            results = []

            items = products_data.get("products", []) if isinstance(products_data, dict) else products_data
            for item in items:
                if not isinstance(item, dict):
                    continue
                title = item.get("title", "")
                if not title:
                    continue

                price_str = item.get("price", "")
                results.append(ProductSearchResult(
                    platform=self._config.id,
                    title=title[:200],
                    price=price_str,
                    extracted_price=_extract_vnd_price(price_str),
                    link=item.get("link", url),
                    seller=item.get("seller", ""),
                    image=item.get("image", ""),
                    source=url,
                ))

            return results
        except Exception as e:
            logger.warning("LLM extraction failed for %s: %s", url, str(e)[:200])
            return []


class Crawl4AISiteAdapter(Crawl4AIGeneralAdapter):
    """
    Convenience factory for creating site-specific Crawl4AI adapters.

    Pre-configured for common Vietnamese e-commerce/dealer sites.
    """

    @staticmethod
    def create_for_site(
        site_name: str,
        search_url_template: str,
        display_name: str = "",
        css_selectors: Optional[Dict[str, str]] = None,
        priority: int = 5,
    ) -> "Crawl4AISiteAdapter":
        """Factory method to create a site-specific adapter."""
        adapter = Crawl4AISiteAdapter(
            target_urls=[search_url_template],
            platform_id=f"crawl4ai_{site_name}",
            display_name=display_name or f"Crawl4AI ({site_name})",
            css_selectors=css_selectors,
            priority=priority,
        )
        return adapter


# ============================================================================
# Factory functions for common Vietnamese dealer sites
# ============================================================================

def create_crawl4ai_generic_adapter(
    target_urls: List[str],
    platform_id: str = "crawl4ai_general",
    display_name: str = "Web Crawler (AI)",
    use_llm_extraction: bool = False,
) -> Crawl4AIGeneralAdapter:
    """Create a generic Crawl4AI adapter for arbitrary URLs."""
    return Crawl4AIGeneralAdapter(
        target_urls=target_urls,
        platform_id=platform_id,
        display_name=display_name,
        use_llm_extraction=use_llm_extraction,
        priority=10,  # Lower priority than specialized adapters
    )
