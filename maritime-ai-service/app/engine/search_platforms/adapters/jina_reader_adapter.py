"""
Jina Reader Adapter — Lightweight Markdown Fallback

Sprint 195: "Nâng Cấp Trí Tuệ" — Jina Reader as free fallback

Uses r.jina.ai/<URL> to convert any web page to clean LLM-ready markdown.
Free API, zero infrastructure, 29 languages (including Vietnamese).

Best used as the last fallback in a ChainedAdapter when Crawl4AI/Scrapling/Serper fail.
"""

import json
import logging
import re
from typing import List, Optional
from urllib.parse import quote_plus

from app.engine.search_platforms.base import (
    BackendType,
    PlatformConfig,
    ProductSearchResult,
    SearchPlatformAdapter,
)

logger = logging.getLogger(__name__)

# Jina Reader endpoints
_JINA_READER_URL = "https://r.jina.ai/"
_JINA_SEARCH_URL = "https://s.jina.ai/"

# Timeout for Jina API calls (seconds)
_JINA_TIMEOUT = 15


class JinaReaderAdapter(SearchPlatformAdapter):
    """
    Adapter using Jina AI Reader for free web-to-markdown conversion.

    Two modes:
    1. Search mode (default): Uses s.jina.ai/<query> for web search
    2. Reader mode: Uses r.jina.ai/<url> for single-page extraction

    Features:
    - Zero cost (free API)
    - LLM-ready markdown output (67% fewer tokens than raw HTML)
    - 29 languages including Vietnamese
    - No anti-bot capabilities (uses simple HTTP fetch)

    Best as a lightweight fallback in ChainedAdapter.
    """

    def __init__(
        self,
        platform_id: str = "jina_reader",
        display_name: str = "Jina Reader",
        search_suffix: str = "mua tại Việt Nam",
        priority: int = 90,
    ):
        self._config = PlatformConfig(
            id=platform_id,
            display_name=display_name,
            backend=BackendType.CUSTOM,
            tool_description_vi=(
                "Tìm kiếm sản phẩm trên web bằng Jina AI Reader. "
                "Trả về kết quả dạng markdown, hỗ trợ tiếng Việt. Miễn phí."
            ),
            priority=priority,
        )
        self._search_suffix = search_suffix

    def get_config(self) -> PlatformConfig:
        return self._config

    def search_sync(
        self, query: str, max_results: int = 10, page: int = 1
    ) -> List[ProductSearchResult]:
        """
        Search via Jina s.jina.ai/ endpoint and parse results.

        Args:
            query: Search query (e.g. "đầu in Zebra ZXP7")
            max_results: Max results to return
            page: Page number (not supported by Jina, ignored)

        Returns:
            List of ProductSearchResult parsed from Jina search markdown
        """
        try:
            import httpx
        except ImportError:
            logger.warning("httpx not installed — JinaReaderAdapter disabled")
            return []

        # Build search query
        search_query = f"{query} {self._search_suffix}".strip()
        url = f"{_JINA_SEARCH_URL}{quote_plus(search_query)}"

        try:
            response = httpx.get(
                url,
                headers={
                    "Accept": "application/json",
                    "X-Return-Format": "text",
                },
                timeout=_JINA_TIMEOUT,
                follow_redirects=True,
            )
            response.raise_for_status()
        except Exception as e:
            logger.warning("Jina search failed for '%s': %s", query, str(e)[:200])
            return []

        # Parse response
        return self._parse_search_results(response.text, query, max_results)

    def read_url(self, url: str) -> Optional[str]:
        """
        Convert a single URL to clean markdown via r.jina.ai/.

        Args:
            url: Full URL to convert

        Returns:
            Markdown string or None on failure
        """
        try:
            import httpx
        except ImportError:
            return None

        reader_url = f"{_JINA_READER_URL}{url}"

        try:
            response = httpx.get(
                reader_url,
                headers={"Accept": "text/markdown"},
                timeout=_JINA_TIMEOUT,
                follow_redirects=True,
            )
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.warning("Jina reader failed for '%s': %s", url, str(e)[:200])
            return None

    def _parse_search_results(
        self, text: str, query: str, max_results: int
    ) -> List[ProductSearchResult]:
        """Parse Jina search response text into ProductSearchResult list."""
        results: List[ProductSearchResult] = []

        # Try JSON first
        try:
            data = json.loads(text)
            if isinstance(data, dict) and "data" in data:
                items = data["data"] if isinstance(data["data"], list) else [data["data"]]
                for item in items[:max_results]:
                    title = item.get("title", "")
                    url = item.get("url", "")
                    description = item.get("description", "") or item.get("content", "")

                    # Extract price from description
                    price, extracted_price = self._extract_price(
                        f"{title} {description}"
                    )

                    results.append(ProductSearchResult(
                        platform="jina_reader",
                        title=title[:200] if title else query,
                        price=price,
                        extracted_price=extracted_price,
                        link=url,
                        snippet=description[:300] if description else "",
                        source="Jina AI Reader",
                    ))
                return results
        except (json.JSONDecodeError, TypeError):
            pass

        # Fallback: parse markdown text
        # Split by markdown headers or numbered items
        sections = re.split(r'\n(?=#{1,3}\s|\d+\.\s)', text)
        for section in sections[:max_results]:
            section = section.strip()
            if not section or len(section) < 20:
                continue

            # Extract title (first line)
            lines = section.split('\n', 1)
            title = re.sub(r'^#+\s*|\d+\.\s*', '', lines[0]).strip()
            body = lines[1].strip() if len(lines) > 1 else ""

            # Extract URL from markdown links
            url_match = re.search(r'\[.*?\]\((https?://[^\s)]+)\)', section)
            link = url_match.group(1) if url_match else ""

            # Extract price
            price, extracted_price = self._extract_price(section)

            if title:
                results.append(ProductSearchResult(
                    platform="jina_reader",
                    title=title[:200],
                    price=price,
                    extracted_price=extracted_price,
                    link=link,
                    snippet=body[:300] if body else "",
                    source="Jina AI Reader",
                ))

        return results[:max_results]

    @staticmethod
    def _extract_price(text: str) -> tuple:
        """
        Extract Vietnamese price from text.

        Handles formats:
        - 12.500.000₫, 12,500,000đ, 12.500.000 VNĐ
        - $495, USD 495
        - 12 triệu, 12tr5

        Returns:
            (price_str, extracted_float) or ("", None)
        """
        # VND patterns
        vnd_match = re.search(
            r'([\d.,]+)\s*(?:₫|đ|VNĐ|VND|vnđ|vnd)',
            text
        )
        if vnd_match:
            price_str = vnd_match.group(0)
            num_str = vnd_match.group(1).replace('.', '').replace(',', '')
            try:
                return price_str, float(num_str)
            except ValueError:
                return price_str, None

        # USD patterns
        usd_match = re.search(
            r'(?:\$|USD\s*)([\d.,]+)',
            text
        )
        if usd_match:
            price_str = usd_match.group(0)
            num_str = usd_match.group(1).replace(',', '')
            try:
                return price_str, float(num_str)
            except ValueError:
                return price_str, None

        # "triệu" pattern
        trieu_match = re.search(r'([\d.,]+)\s*triệu', text)
        if trieu_match:
            price_str = trieu_match.group(0)
            try:
                return price_str, float(trieu_match.group(1).replace(',', '.')) * 1_000_000
            except ValueError:
                return price_str, None

        return "", None


def create_jina_reader_adapter(
    search_suffix: str = "mua tại Việt Nam",
    priority: int = 90,
) -> JinaReaderAdapter:
    """Factory function for JinaReaderAdapter with default config."""
    return JinaReaderAdapter(
        platform_id="jina_reader",
        display_name="Jina Reader",
        search_suffix=search_suffix,
        priority=priority,
    )
