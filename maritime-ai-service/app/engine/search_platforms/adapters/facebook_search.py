"""
Facebook Search Adapter — Playwright + LLM Extraction

Sprint 152: "Trinh Duyet Thong Minh"
Sprint 154: "Dang Nhap Facebook" — cookie login for Groups/Posts search

Scrapes Facebook using headless Chromium, then uses Gemini Flash LLM to
extract structured product listings.

Without cookie: /marketplace/search/ (public, no login required)
With cookie: /search/posts/?q= (logged-in, Groups + Pages visible)

Fallback: When Playwright not installed or browser fails, falls back to
existing Serper `site:facebook.com` adapter.
"""

import logging
from typing import List, Optional
from urllib.parse import quote_plus

from app.engine.search_platforms.adapters.browser_base import PlaywrightLLMAdapter
from app.engine.search_platforms.base import (
    BackendType,
    PlatformConfig,
    ProductSearchResult,
    SearchPlatformAdapter,
)

logger = logging.getLogger(__name__)


class FacebookSearchAdapter(PlaywrightLLMAdapter):
    """Facebook Marketplace/Posts via Playwright headless browser + LLM extraction."""

    def __init__(self, serper_fallback: Optional[SearchPlatformAdapter] = None):
        super().__init__()
        self._serper_fallback = serper_fallback

    def get_config(self) -> PlatformConfig:
        return PlatformConfig(
            id="facebook_search",
            display_name="Facebook",
            backend=BackendType.BROWSER,
            fallback_backend=BackendType.SERPER_SITE,
            tool_description_vi=(
                "Tim kiem san pham tren Facebook (Marketplace, Groups, Pages) "
                "bang trinh duyet thong minh. Phu hop cho hang cu, handmade, "
                "deal dia phuong.\n\n"
                "Args:\n"
                "    query: Ten san pham (e.g., 'iPhone 16 Pro Max')\n"
                "    max_results: So ket qua toi da (default 20)\n"
                "    page: Khong ho tro phan trang (Facebook dung scroll)"
            ),
            max_results_default=20,
        )

    def _get_cookies(self) -> list:
        """Sprint 154: Read Facebook cookie from per-request ContextVar.

        Called in the asyncio thread BEFORE ThreadPoolExecutor submission.
        Returns Playwright cookie dicts or empty list.
        """
        try:
            from app.core.config import get_settings
            if not get_settings().enable_facebook_cookie:
                return []
            from app.engine.search_platforms.facebook_context import get_facebook_cookie
            raw = get_facebook_cookie()
            if not raw:
                return []
            return self._parse_cookie_string(raw)
        except Exception:
            return []

    @staticmethod
    def _parse_cookie_string(cookie_str: str) -> list:
        """Parse 'name=value; name2=value2' into Playwright cookie dicts."""
        cookies = []
        for pair in cookie_str.split(";"):
            pair = pair.strip()
            if "=" in pair:
                name, _, value = pair.partition("=")
                name = name.strip()
                value = value.strip()
                if name:
                    cookies.append({
                        "name": name,
                        "value": value,
                        "domain": ".facebook.com",
                        "path": "/",
                    })
        return cookies

    def _build_url(self, query: str, page: int = 1) -> str:
        """Build Facebook search URL.

        Sprint 154: Use /search/posts/ when logged in (cookie present),
        /marketplace/search/ otherwise (public, no login).
        """
        has_cookie = bool(self._get_cookies())
        if has_cookie:
            return f"https://www.facebook.com/search/posts/?q={quote_plus(query)}"
        return f"https://www.facebook.com/marketplace/search/?query={quote_plus(query)}"

    def _post_navigate(self, page) -> None:
        """Dismiss Facebook login modal.

        Facebook's modern login modal can't be dismissed with Escape key.
        We remove it from the DOM directly so the content behind is visible
        and screenshots show actual product listings.

        Sprint 155: Scrolling moved to _fetch_page_text_with_scroll() —
        this method now only handles modal dismissal.
        """
        import time
        time.sleep(2)  # Wait for login modal to appear

        # Remove login modal overlay via DOM manipulation
        try:
            page.evaluate("""() => {
                // Remove the login dialog and backdrop
                const selectors = [
                    '[role="dialog"]',
                    '[data-nosnippet="true"]',
                    '.__fb-light-mode div[role="dialog"]',
                ];
                for (const sel of selectors) {
                    document.querySelectorAll(sel).forEach(el => el.remove());
                }
                // Remove any fixed/absolute overlays blocking content
                document.querySelectorAll('div[style*="position: fixed"], div[style*="position:fixed"]').forEach(el => {
                    if (el.querySelector('[role="dialog"]') || el.style.zIndex > 1) {
                        el.remove();
                    }
                });
                // Re-enable scrolling on body (FB disables it when modal is open)
                document.body.style.overflow = 'auto';
                document.documentElement.style.overflow = 'auto';
            }""")
            time.sleep(0.5)
        except Exception:
            # Fallback: try Escape key
            try:
                page.keyboard.press("Escape")
                time.sleep(1)
            except Exception:
                pass

    def _get_extraction_prompt(self) -> str:
        return """Analyze this Facebook search results page text and extract product listings.

IMPORTANT:
- Some posts have a [POST_URL: ...] tag — this is the direct link to the Facebook post. Extract into "link" field.
- Some posts have a [POST_IMAGE: ...] tag — this is the product image URL. Extract into "image" field.

Return ONLY a JSON array (no markdown, no explanation):
[
  {{
    "title": "product name",
    "price": "price as shown (e.g., '900 US$' or '25.000.000 d')",
    "seller": "seller name if visible",
    "link": "the [POST_URL: ...] value if present, otherwise empty string",
    "image": "the [POST_IMAGE: ...] value if present, otherwise empty string",
    "location": "location/city if visible"
  }}
]

Rules:
- Only include items that are clearly products FOR SALE with a price
- Extract prices as-is including currency (US$, VND, d, etc.)
- ALWAYS extract the [POST_URL: ...] value into the "link" field when present
- ALWAYS extract the [POST_IMAGE: ...] value into the "image" field when present
- If no products found, return empty array: []
- Maximum {max_results} items
- Each product typically appears as: price, then title, then location
- Skip navigation items, filter labels, and category names

Page text:
{text}"""

    def search_sync(self, query: str, max_results: int = 20, page: int = 1) -> List[ProductSearchResult]:
        """Search with Playwright scroll-and-extract, fallback to Serper on failure.

        Sprint 155: Uses _run_fetch_with_scroll for enhanced content extraction.
        Sprint 156: Network interception — captures GraphQL structured data
        during scrolling. When >= 3 products intercepted, skips LLM extraction.
        """
        if not query or not query.strip():
            return []

        # Try Playwright with scroll-and-extract
        try:
            from playwright.sync_api import sync_playwright  # noqa: F401 — availability check

            # Get config
            try:
                from app.core.config import get_settings
                settings = get_settings()
                max_scrolls = settings.facebook_scroll_max_scrolls
                use_interception = settings.enable_network_interception
                max_response_size = settings.network_interception_max_response_size
            except Exception:
                max_scrolls = 8
                use_interception = True
                max_response_size = 5_000_000

            url = self._build_url(query.strip(), page)
            # Sprint 157: Use search page URL as source link for results
            search_page_url = url

            if use_interception:
                from app.engine.search_platforms.adapters.browser_base import (
                    _INTERCEPTION_FALLBACK_THRESHOLD,
                )
                dom_text, intercepted = self._run_fetch_with_interception(
                    url,
                    max_scrolls=max_scrolls,
                    max_response_size=max_response_size,
                )
                if len(intercepted) >= _INTERCEPTION_FALLBACK_THRESHOLD:
                    results = [
                        self._map_intercepted_to_result(p)
                        for p in intercepted[:max_results]
                    ]
                    for r in results:
                        if not r.link and search_page_url:
                            r.link = search_page_url
                    return results
                # Fallback to LLM on DOM text
                if dom_text and len(dom_text) >= 100:
                    results = self._llm_extract(dom_text, max_results)
                    if results:
                        for r in results:
                            if not r.link and search_page_url:
                                r.link = search_page_url
                        return results
            else:
                text = self._run_fetch_with_scroll(url, max_scrolls=max_scrolls)
                if text and len(text) >= 100:
                    results = self._llm_extract(text, max_results)
                    if results:
                        for r in results:
                            if not r.link and search_page_url:
                                r.link = search_page_url
                        return results
        except ImportError:
            logger.info("[FACEBOOK] Playwright not installed, using Serper fallback")
        except Exception as e:
            logger.warning("[FACEBOOK] Browser error, falling back to Serper: %s", e)

        # Fallback to Serper site:facebook.com
        if self._serper_fallback:
            return self._serper_fallback.search_sync(query, max_results, page)
        return []
