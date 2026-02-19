"""
Facebook Search Adapter — Playwright + LLM Extraction

Sprint 152: "Trinh Duyet Thong Minh"

Scrapes public Facebook Marketplace results using headless Chromium (no login),
then uses Gemini Flash LLM to extract structured product listings.

Note: /search/top/ requires login, but /marketplace/search/ is public.
Legal basis: Meta v. Bright Data (01/2024) — scraping public data without
login is legal.

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
    """Facebook Marketplace via Playwright headless browser + LLM extraction."""

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

    def _build_url(self, query: str, page: int = 1) -> str:
        """Build Facebook Marketplace search URL.

        /marketplace/search/ is public (no login required).
        /search/top/ requires login — don't use it.
        """
        return f"https://www.facebook.com/marketplace/search/?query={quote_plus(query)}"

    def _post_navigate(self, page) -> None:
        """Dismiss Facebook login modal and scroll to load content.

        Facebook's modern login modal can't be dismissed with Escape key.
        We remove it from the DOM directly so the content behind is visible
        and screenshots show actual product listings.
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

        # Scroll down to load more results
        for _ in range(3):
            page.evaluate("window.scrollBy(0, 1000)")
            time.sleep(1)

    def _get_extraction_prompt(self) -> str:
        return """Analyze this Facebook Marketplace search results page text and extract product listings.

Return ONLY a JSON array (no markdown, no explanation):
[
  {{
    "title": "product name",
    "price": "price as shown (e.g., '900 US$' or '25.000.000 d')",
    "seller": "seller name if visible",
    "link": "",
    "location": "location/city if visible"
  }}
]

Rules:
- Only include items that are clearly products FOR SALE with a price
- Extract prices as-is including currency (US$, VND, d, etc.)
- If no products found, return empty array: []
- Maximum {max_results} items
- Each product typically appears as: price, then title, then location
- Skip navigation items, filter labels, and category names

Page text:
{text}"""

    def search_sync(self, query: str, max_results: int = 20, page: int = 1) -> List[ProductSearchResult]:
        """Search with Playwright, fallback to Serper on failure."""
        if not query or not query.strip():
            return []

        # Try Playwright first
        try:
            from playwright.sync_api import sync_playwright  # noqa: F401 — availability check
            results = super().search_sync(query, max_results, page)
            if results:
                return results
        except ImportError:
            logger.info("[FACEBOOK] Playwright not installed, using Serper fallback")
        except Exception as e:
            logger.warning("[FACEBOOK] Browser error, falling back to Serper: %s", e)

        # Fallback to Serper site:facebook.com
        if self._serper_fallback:
            return self._serper_fallback.search_sync(query, max_results, page)
        return []
