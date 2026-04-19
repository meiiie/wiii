"""Playbook-Driven Adapter — generic adapter driven by SitePlaybook YAML config.

For sites with simple HTML CSS extraction (like WebSosanh), this replaces
the need for a dedicated adapter class. Sites requiring complex logic
(Facebook login, GraphQL intercept) still use custom adapters but can
reference playbooks for selectors and URLs.

Feature-gated by settings.enable_site_playbooks (default: False).
"""

from __future__ import annotations

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


def _encode_query(query: str, encoding: str) -> str:
    """Encode query string for URL template."""
    if encoding == "plus":
        return quote(query, safe="").replace("%20", "+")
    elif encoding == "percent":
        return quote(query, safe="")
    return query


class PlaybookDrivenAdapter(SearchPlatformAdapter):
    """Generic adapter driven entirely by a SitePlaybook config.

    Handles:
    - URL building from playbook template
    - HTTP requests with playbook headers
    - HTML CSS extraction with fallback selectors
    - Field mapping (link_base, image_protocol, price parsing)
    """

    def __init__(self, playbook):
        self._playbook = playbook
        try:
            backend = BackendType(playbook.backend)
        except ValueError:
            backend = BackendType.CUSTOM
        self._config = PlatformConfig(
            id=playbook.platform_id,
            display_name=playbook.display_name,
            backend=backend,
            priority=playbook.priority,
            timeout_seconds=playbook.request.timeout_seconds,
        )

    def get_config(self) -> PlatformConfig:
        return self._config

    def search_sync(
        self, query: str, max_results: int = 20, page: int = 1
    ) -> List[ProductSearchResult]:
        """Execute search using playbook-defined config."""
        if not query or not query.strip():
            return []

        pb = self._playbook
        url = self._build_url(query.strip(), page)

        try:
            import httpx

            resp = httpx.get(
                url,
                headers=pb.request.headers or {"User-Agent": "WiiiBot/1.0"},
                timeout=pb.request.timeout_seconds,
                follow_redirects=pb.request.follow_redirects,
            )
            resp.raise_for_status()
        except httpx.TimeoutException:
            logger.warning("[PLAYBOOK_ADAPTER] Timeout fetching %s", url)
            return []
        except Exception as e:
            logger.warning("[PLAYBOOK_ADAPTER] Error fetching %s: %s", url, e)
            return []

        content_type = resp.headers.get("content-type", "")
        if "text/html" not in content_type and "application/json" not in content_type:
            logger.warning("[PLAYBOOK_ADAPTER] Unexpected content type: %s", content_type)
            return []

        if "json" in content_type or pb.extraction.type == "api_json":
            return self._parse_json(resp.json(), max_results)

        return self._parse_html(resp.text, max_results)

    def _build_url(self, query: str, page: int) -> str:
        """Build URL from playbook template."""
        pb = self._playbook
        template = pb.site.url_template
        if not template:
            return pb.site.base_url

        encoded = _encode_query(query, pb.site.query_encoding)
        url = template.replace("{query_encoded}", encoded).replace(
            "{base_url}", pb.site.base_url
        )

        if pb.site.pagination == "query_param":
            if page > 1:
                url = url.replace("{page}", str(page))
            else:
                url = url.replace("?page={page}", "").replace("&page={page}", "")
                url = url.replace("{page}", "1")
        else:
            url = url.replace("{page}", "1")

        return url

    def _parse_html(self, html: str, max_results: int) -> List[ProductSearchResult]:
        """Parse HTML using playbook selectors."""
        try:
            from bs4 import BeautifulSoup

            try:
                soup = BeautifulSoup(html, "lxml")
            except Exception:
                soup = BeautifulSoup(html, "html.parser")
        except ImportError:
            logger.error("[PLAYBOOK_ADAPTER] beautifulsoup4 not installed")
            return []

        pb = self._playbook
        selectors = pb.extraction.selectors
        fallbacks = pb.extraction.fallback_selectors
        mapping = pb.extraction.field_mapping

        container_sel = selectors.get("container", "")
        items = soup.select(container_sel) if container_sel else []

        if not items and fallbacks.get("container"):
            for fb_sel in fallbacks["container"]:
                items = soup.select(fb_sel)
                if items:
                    break

        results: List[ProductSearchResult] = []
        link_base = mapping.get("link_base", "")
        img_protocol = mapping.get("image_protocol", "")

        for item in items[:max_results]:
            result = self._extract_item(item, selectors, fallbacks, link_base, img_protocol)
            if result:
                results.append(result)

        logger.info(
            "[PLAYBOOK_ADAPTER] Parsed %d results from %s",
            len(results),
            pb.platform_id,
        )
        return results

    def _extract_item(
        self,
        item,
        selectors: dict,
        fallbacks: dict,
        link_base: str,
        img_protocol: str,
    ) -> Optional[ProductSearchResult]:
        """Extract a single product from an HTML element."""
        # Title
        title = self._extract_text(item, selectors.get("title", ""), fallbacks.get("title", []))

        # Price
        price_text = self._extract_text(item, selectors.get("price", ""), fallbacks.get("price", []))
        extracted_price = None
        if price_text:
            from app.engine.search_platforms.utils import parse_vnd_price
            extracted_price = parse_vnd_price(price_text)

        # Link
        link = self._extract_attr(
            item, selectors.get("link", ""), fallbacks.get("link", []), "href"
        )
        if link and link.startswith("/") and link_base:
            link = f"{link_base}{link}"

        # Seller
        seller = self._extract_text(
            item, selectors.get("seller", ""), fallbacks.get("seller", [])
        )

        # Image
        image = self._extract_attr(
            item, selectors.get("image", ""), fallbacks.get("image", []), "src"
        )
        if image:
            if image.startswith("//") and img_protocol:
                image = f"{img_protocol}{image}"
            elif image.startswith("/") and link_base:
                image = f"{link_base}{image}"

        if not title and not price_text:
            return None

        return ProductSearchResult(
            platform=self._playbook.display_name,
            title=title,
            price=price_text,
            extracted_price=extracted_price,
            link=link,
            seller=seller,
            image=image,
        )

    def _parse_json(self, data: dict, max_results: int) -> List[ProductSearchResult]:
        """Parse JSON API response using playbook selectors."""
        pb = self._playbook
        selectors = pb.extraction.selectors
        container_path = selectors.get("container", "")

        items = self._resolve_json_path(data, container_path)
        if not isinstance(items, list):
            return []

        results: List[ProductSearchResult] = []
        for item in items[:max_results]:
            title = str(self._resolve_json_path(item, selectors.get("title", "")) or "")
            price_raw = self._resolve_json_path(item, selectors.get("price", ""))
            price_text = str(price_raw) if price_raw else ""
            extracted_price = None
            if price_text:
                try:
                    extracted_price = float(price_text)
                except (ValueError, TypeError):
                    pass

            image = str(self._resolve_json_path(item, selectors.get("image", "")) or "")
            seller = str(self._resolve_json_path(item, selectors.get("seller", "")) or "")

            if not title:
                continue

            results.append(
                ProductSearchResult(
                    platform=pb.display_name,
                    title=title,
                    price=price_text,
                    extracted_price=extracted_price,
                    image=image,
                    seller=seller,
                )
            )
        return results

    @staticmethod
    def _resolve_json_path(data: Any, path: str) -> Any:
        """Resolve a dot-separated path in a JSON structure."""
        if not path or not isinstance(data, dict):
            return None
        current = data
        for key in path.split("."):
            if isinstance(current, dict):
                current = current.get(key)
            elif isinstance(current, list) and key.isdigit():
                idx = int(key)
                current = current[idx] if idx < len(current) else None
            else:
                return None
        return current

    @staticmethod
    def _extract_text(item, selector: str, fallbacks: list) -> str:
        """Extract text from a BeautifulSoup element."""
        if selector:
            el = item.select_one(selector)
            if el:
                return el.get_text(strip=True)
        for fb in fallbacks:
            el = item.select_one(fb)
            if el:
                return el.get_text(strip=True)
        return ""

    @staticmethod
    def _extract_attr(item, selector: str, fallbacks: list, attr: str) -> str:
        """Extract an attribute from a BeautifulSoup element."""
        if selector:
            el = item.select_one(selector)
            if el and el.get(attr):
                return el[attr]
        for fb in fallbacks:
            el = item.select_one(fb)
            if el and el.get(attr):
                return el[attr]
        return ""
