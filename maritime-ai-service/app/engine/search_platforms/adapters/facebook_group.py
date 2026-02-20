"""
Facebook Group Search Adapter — Search WITHIN a specific Facebook Group

Sprint 155: "Nhom Facebook" — Deep Facebook Group Search

Separate adapter from FacebookSearchAdapter because:
1. Different tool signature: needs group_name_or_url parameter
2. Different flow: 2-phase (discover group → search within group)
3. Feature gate: can enable/disable independently
4. Backward compat: existing tool_search_facebook_search unchanged

Flow:
  User: "tim MacBook trong nhom Vua 2nd"
  → tool_search_facebook_group(group_name_or_url="Vua 2nd", query="MacBook M4 Pro")
  → _resolve_group("Vua 2nd") → discover group URL
  → Navigate to /groups/{id}/search/?q=MacBook+M4+Pro
  → scroll-and-extract (10 iterations, 2.5s delay)
  → LLM extraction → ProductSearchResult[]
"""

import json
import logging
import re
from typing import List, Optional
from urllib.parse import quote_plus

from app.engine.search_platforms.adapters.browser_base import (
    PlaywrightLLMAdapter,
    _extract_json_array,
    _MAX_PROMPT_TEXT,
)
from app.engine.search_platforms.base import (
    BackendType,
    PlatformConfig,
    ProductSearchResult,
    SearchPlatformAdapter,
)

logger = logging.getLogger(__name__)

# Group URL pattern
_GROUP_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?facebook\.com/groups/([^/?#]+)",
    re.IGNORECASE,
)


class FacebookGroupSearchAdapter(PlaywrightLLMAdapter):
    """Search within a specific Facebook Group via Playwright + LLM."""

    def __init__(self, serper_fallback: Optional[SearchPlatformAdapter] = None):
        super().__init__()
        self._serper_fallback = serper_fallback
        self._group_cache: dict[str, str] = {}  # name → group URL

    def get_config(self) -> PlatformConfig:
        return PlatformConfig(
            id="facebook_group",
            display_name="Facebook Group",
            backend=BackendType.BROWSER,
            fallback_backend=BackendType.SERPER_SITE,
            tool_description_vi=(
                "Tim kiem san pham TRONG nhom Facebook cu the. "
                "Can ten nhom hoac URL nhom. Rat huu ich khi user yeu cau "
                "'tim trong nhom Vua 2nd', 'search trong group XYZ'.\n"
                "YEU CAU: Cookie dang nhap Facebook.\n\n"
                "Args:\n"
                "    group_name_or_url: Ten nhom (e.g., 'Vua 2nd') hoac URL nhom Facebook\n"
                "    query: Ten san pham (e.g., 'MacBook M4 Pro')\n"
                "    max_results: So ket qua toi da (default 20)"
            ),
            max_results_default=20,
        )

    def _get_cookies(self) -> list:
        """Read Facebook cookie from per-request ContextVar (same as FacebookSearchAdapter)."""
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
        """Not used directly — group search uses _build_group_search_url."""
        return f"https://www.facebook.com/search/posts/?q={quote_plus(query)}"

    def _build_group_search_url(self, group_url: str, query: str) -> str:
        """Build in-group search URL: /groups/{id}/search/?q={query}"""
        # Normalize group URL — ensure trailing slash
        group_url = group_url.rstrip("/")
        return f"{group_url}/search/?q={quote_plus(query)}"

    def _post_navigate(self, page) -> None:
        """Dismiss Facebook login/cookie modals."""
        import time
        time.sleep(2)

        try:
            page.evaluate("""() => {
                const selectors = [
                    '[role="dialog"]',
                    '[data-nosnippet="true"]',
                    '.__fb-light-mode div[role="dialog"]',
                ];
                for (const sel of selectors) {
                    document.querySelectorAll(sel).forEach(el => el.remove());
                }
                document.querySelectorAll('div[style*="position: fixed"], div[style*="position:fixed"]').forEach(el => {
                    if (el.querySelector('[role="dialog"]') || el.style.zIndex > 1) {
                        el.remove();
                    }
                });
                document.body.style.overflow = 'auto';
                document.documentElement.style.overflow = 'auto';
            }""")
            time.sleep(0.5)
        except Exception:
            try:
                page.keyboard.press("Escape")
                time.sleep(1)
            except Exception:
                pass

    def _get_extraction_prompt(self) -> str:
        """LLM extraction prompt for Facebook group posts."""
        return """Analyze this Facebook Group search results page and extract product listings / sale posts.

IMPORTANT:
- Some posts have a [POST_URL: ...] tag — this is the direct link to the Facebook post. Extract into "link" field.
- Some posts have a [POST_IMAGE: ...] tag — this is the product image URL. Extract into "image" field.

Return ONLY a JSON array (no markdown, no explanation):
[
  {{
    "title": "product name or post title",
    "price": "price as shown (e.g., '25.000.000 d', '900$', 'lien he')",
    "seller": "person or page name posting the item",
    "link": "the [POST_URL: ...] value if present, otherwise empty string",
    "image": "the [POST_IMAGE: ...] value if present, otherwise empty string",
    "location": "city/district if visible",
    "description": "short description of condition, specs, or details"
  }}
]

Rules:
- Include items that are products FOR SALE or trading posts
- Extract prices as-is including currency (VND, $, d, etc.)
- Include "lien he" or "inbox" if no price shown but item is for sale
- ALWAYS extract the [POST_URL: ...] value into the "link" field when present
- ALWAYS extract the [POST_IMAGE: ...] value into the "image" field when present
- If no products found, return empty array: []
- Maximum {max_results} items
- Group posts often show: seller name, then content with price and product details
- Skip admin posts, rules, pinned announcements

Page text:
{text}"""

    def _resolve_group(self, group_name_or_url: str, browser) -> Optional[str]:
        """Resolve group name to URL. If already a URL, use directly.

        Uses cache to avoid repeated lookups.

        Args:
            group_name_or_url: Either a group name ("Vua 2nd") or full URL
            browser: Playwright browser instance

        Returns:
            Full group URL or None if not found
        """
        name_or_url = group_name_or_url.strip()

        # Check if it's already a URL
        if _GROUP_URL_RE.search(name_or_url):
            # Normalize to full URL
            if not name_or_url.startswith("http"):
                name_or_url = f"https://www.facebook.com/groups/{_GROUP_URL_RE.search(name_or_url).group(1)}"
            return name_or_url

        # Check cache
        cache_key = name_or_url.lower()
        if cache_key in self._group_cache:
            return self._group_cache[cache_key]

        # Discover group by searching
        search_url = f"https://www.facebook.com/search/groups/?q={quote_plus(name_or_url)}"
        try:
            cookies = self._get_cookies()
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 720},
                locale="vi-VN",
            )
            if cookies:
                context.add_cookies(cookies)
            page = context.new_page()
            try:
                import time
                page.goto(search_url, wait_until="domcontentloaded", timeout=15000)
                time.sleep(3)
                self._post_navigate(page)
                time.sleep(1)

                # Extract page text and use LLM to find group URL
                text = page.inner_text("body")
                if text:
                    group_url = self._llm_extract_group_url(text[:10000], name_or_url)
                    if group_url:
                        self._group_cache[cache_key] = group_url
                        return group_url
            finally:
                context.close()
        except Exception as e:
            logger.warning("[FB_GROUP] Group discovery failed for '%s': %s", name_or_url, e)

        return None

    def _llm_extract_group_url(self, page_text: str, group_name: str) -> Optional[str]:
        """Use LLM to extract the first matching group URL from search results."""
        try:
            from app.engine.llm_pool import get_llm_light
            from langchain_core.messages import HumanMessage

            prompt = f"""From this Facebook group search results page, find the URL of the group most closely matching "{group_name}".

Return ONLY a JSON object (no markdown, no explanation):
{{"group_url": "https://www.facebook.com/groups/XXXXX", "group_name": "exact group name"}}

If no matching group found, return: {{"group_url": null, "group_name": null}}

Page text:
{page_text}"""

            llm = get_llm_light()
            response = llm.invoke([HumanMessage(content=prompt)])
            raw = response.content if hasattr(response, "content") else str(response)

            if isinstance(raw, list):
                content = " ".join(
                    block.get("text", "") if isinstance(block, dict) else str(block)
                    for block in raw
                )
            else:
                content = str(raw)

            # Parse JSON response
            content = content.strip()
            # Try to extract JSON from fences
            import re as _re
            fence_match = _re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", content)
            if fence_match:
                content = fence_match.group(1)
            # Find JSON object
            obj_match = _re.search(r"\{[\s\S]*\}", content)
            if obj_match:
                data = json.loads(obj_match.group(0))
                url = data.get("group_url")
                if url and "facebook.com/groups/" in url:
                    return url
        except Exception as e:
            logger.debug("[FB_GROUP] LLM group URL extraction failed: %s", e)

        return None

    def search_group_sync(
        self,
        group_name_or_url: str,
        query: str,
        max_results: int = 20,
    ) -> List[ProductSearchResult]:
        """Main entry: resolve group → build URL → scroll-and-extract → LLM parse.

        Sprint 156: Network interception — captures GraphQL structured data
        during scrolling. When >= 3 products intercepted, skips LLM extraction.

        Args:
            group_name_or_url: Group name ("Vua 2nd") or URL
            query: Product search query
            max_results: Max results to return

        Returns:
            List of ProductSearchResult
        """
        if not query or not query.strip():
            return []
        if not group_name_or_url or not group_name_or_url.strip():
            return []

        # Check cookies — groups require login
        cookies = self._get_cookies()
        logger.info("[FB_GROUP] search_group_sync: group=%r, query=%r, cookies=%d",
                    group_name_or_url[:60] if group_name_or_url else "NONE",
                    query[:40] if query else "NONE",
                    len(cookies) if cookies else 0)
        if not cookies:
            logger.warning("[FB_GROUP] No Facebook cookie — cannot search groups")
            return []

        # Get scroll + interception config
        try:
            from app.core.config import get_settings
            settings = get_settings()
            max_scrolls = settings.facebook_group_max_scrolls
            scroll_delay = settings.facebook_group_scroll_delay
            use_interception = settings.enable_network_interception
            max_response_size = settings.network_interception_max_response_size
        except Exception:
            max_scrolls = 10
            scroll_delay = 2.5
            use_interception = True
            max_response_size = 5_000_000

        adapter = self
        group_input = group_name_or_url.strip()
        search_query = query.strip()

        def _do_group_search(browser):
            # Phase 1: Resolve group
            group_url = adapter._resolve_group(group_input, browser)
            if not group_url:
                logger.warning("[FB_GROUP] Could not resolve group: %s", group_input)
                if use_interception:
                    return ("", [])
                return ""

            # Phase 2: Build search URL and fetch
            url = adapter._build_group_search_url(group_url, search_query)
            if use_interception:
                return adapter._fetch_page_with_interception(
                    url,
                    timeout=adapter._get_timeout(),
                    cookies=cookies,
                    _browser=browser,
                    max_scrolls=max_scrolls,
                    scroll_delay=scroll_delay,
                    max_response_size=max_response_size,
                )
            else:
                return adapter._fetch_page_text_with_scroll(
                    url,
                    timeout=adapter._get_timeout(),
                    cookies=cookies,
                    _browser=browser,
                    max_scrolls=max_scrolls,
                    scroll_delay=scroll_delay,
                )

        try:
            from app.engine.search_platforms.adapters.browser_base import (
                _submit_to_pw_worker,
                _INTERCEPTION_FALLBACK_THRESHOLD,
            )
            # Extended timeout for group discovery + scroll
            timeout = self._get_timeout()
            worker_timeout = timeout + 20 + int(max_scrolls * (scroll_delay + 2)) + 15
            result = _submit_to_pw_worker(_do_group_search, timeout=worker_timeout)

            # Sprint 157: Build search page URL for source links
            # Since Facebook React UI doesn't expose individual post URLs,
            # use the group search page as the source link for all results.
            search_page_url = ""
            if _GROUP_URL_RE.search(group_input):
                _resolved = group_input.strip()
                if not _resolved.startswith("http"):
                    _resolved = f"https://www.facebook.com/groups/{_GROUP_URL_RE.search(group_input).group(1)}"
                search_page_url = self._build_group_search_url(_resolved, search_query)
            elif group_input.lower() in self._group_cache:
                search_page_url = self._build_group_search_url(
                    self._group_cache[group_input.lower()], search_query
                )

            if use_interception:
                dom_text, intercepted = result if isinstance(result, tuple) else (result, [])
                logger.info(
                    "[FB_GROUP] Interception: %d products captured, dom_text=%d chars",
                    len(intercepted), len(dom_text) if dom_text else 0,
                )
                if len(intercepted) >= _INTERCEPTION_FALLBACK_THRESHOLD:
                    logger.info("[FB_GROUP] Using GraphQL interception path (%d products)", len(intercepted))
                    results = [
                        self._map_intercepted_to_result(p)
                        for p in intercepted[:max_results]
                    ]
                    # Fill missing links with search page URL
                    for r in results:
                        if not r.link and search_page_url:
                            r.link = search_page_url
                    return results
                # Fallback to LLM on DOM text
                if dom_text and len(dom_text) >= 100:
                    logger.info("[FB_GROUP] Using LLM extraction path on %d chars", len(dom_text))
                    results = self._llm_extract(dom_text, max_results)
                    for r in results:
                        if not r.link and search_page_url:
                            r.link = search_page_url
                    return results
                return []
            else:
                text = result
                if not text or len(text) < 100:
                    return []
                results = self._llm_extract(text, max_results)
                for r in results:
                    if not r.link and search_page_url:
                        r.link = search_page_url
                return results
        except ImportError:
            logger.warning("[FB_GROUP] playwright not installed")
            return []
        except Exception as e:
            logger.warning("[FB_GROUP] Error searching group '%s': %s", group_name_or_url, e)
            return []

    def search_sync(self, query: str, max_results: int = 20, page: int = 1) -> List[ProductSearchResult]:
        """Standard adapter interface — not used for group search.

        Group search uses search_group_sync() with different signature.
        This fallback searches general Facebook posts.
        """
        return super().search_sync(query, max_results, page)
