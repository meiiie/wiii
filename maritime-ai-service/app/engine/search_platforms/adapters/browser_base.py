"""
Playwright + LLM Extraction — Base Class for Browser-Based Adapters

Sprint 152: "Trinh Duyet Thong Minh"

Uses Playwright headless Chromium to fetch pages (bypasses anti-bot),
then Gemini Flash LLM to extract structured product data from visible text.

Advantages over CSS selectors:
- Self-healing: LLM reads semantics, not brittle class names
- Works on any website without per-site selector maintenance
- Facebook/Instagram change CSS frequently — LLM adapts automatically

Subclasses implement:
- get_config() -> PlatformConfig
- _build_url(query, page) -> str
- _get_extraction_prompt() -> str
- _post_navigate(page) -> None (optional: dismiss modals, scroll)
"""

import json
import logging
import re
import threading
from abc import abstractmethod
from typing import List, Optional

from app.engine.search_platforms.base import (
    ProductSearchResult,
    SearchPlatformAdapter,
)

logger = logging.getLogger(__name__)

# Shared browser singleton across all PlaywrightLLMAdapter subclasses
_browser = None
_playwright_instance = None
_browser_lock = threading.Lock()

# Max page text sent to LLM (chars)
_MAX_PAGE_TEXT = 50000
# Max text in LLM prompt (chars) — leave room for prompt template
_MAX_PROMPT_TEXT = 30000
# Sprint 153: Max screenshots per search
_MAX_SCREENSHOTS = 5


def _get_browser():
    """Get or create shared headless Chromium browser (thread-safe singleton)."""
    global _browser, _playwright_instance
    with _browser_lock:
        if _browser is not None and _browser.is_connected():
            return _browser
        from playwright.sync_api import sync_playwright
        _playwright_instance = sync_playwright().start()
        _browser = _playwright_instance.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        return _browser


def close_browser():
    """Cleanup browser — call at app shutdown."""
    global _browser, _playwright_instance
    with _browser_lock:
        if _browser is not None:
            try:
                _browser.close()
            except Exception:
                pass
            _browser = None
        if _playwright_instance is not None:
            try:
                _playwright_instance.stop()
            except Exception:
                pass
            _playwright_instance = None


def _extract_json_array(text: str) -> list:
    """Extract JSON array from LLM response text.

    Handles:
    - Clean JSON array
    - JSON inside ```json ... ``` fences
    - Multiple arrays (returns first)
    """
    if not text:
        return []

    # Try direct parse first
    text = text.strip()
    if text.startswith("["):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    # Try extracting from markdown fences
    fence_match = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", text)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding any JSON array
    arr_match = re.search(r"\[[\s\S]*\]", text)
    if arr_match:
        try:
            return json.loads(arr_match.group(0))
        except json.JSONDecodeError:
            pass

    return []


def _parse_vnd_price(price_str: str) -> Optional[float]:
    """Parse a VND price string to float. Delegates to shared utility."""
    from app.engine.search_platforms.utils import parse_vnd_price
    return parse_vnd_price(price_str)


class PlaywrightLLMAdapter(SearchPlatformAdapter):
    """
    Base class for Playwright + LLM extraction adapters.

    Subclasses must implement:
    - get_config() -> PlatformConfig
    - _build_url(query, page) -> str
    - _get_extraction_prompt() -> str

    Optional override:
    - _post_navigate(page) -> None (dismiss modals, scroll, etc.)
    """

    def __init__(self):
        self._last_screenshots: list = []

    def _capture_screenshot(self, page, label: str) -> None:
        """Sprint 153: Capture JPEG screenshot if browser_screenshots enabled."""
        try:
            from app.core.config import get_settings
            settings = get_settings()
            if not settings.enable_browser_screenshots:
                return
            if len(self._last_screenshots) >= _MAX_SCREENSHOTS:
                return

            import base64
            import time
            quality = settings.browser_screenshot_quality

            raw = page.screenshot(type="jpeg", quality=quality)
            b64 = base64.b64encode(raw).decode("ascii")

            self._last_screenshots.append({
                "label": label,
                "image": b64,
                "url": page.url,
                "timestamp": time.time(),
            })
        except Exception as e:
            logger.debug("[BROWSER] Screenshot failed: %s", e)

    def get_last_screenshots(self) -> list:
        """Sprint 153: Return and clear accumulated screenshots."""
        shots = self._last_screenshots[:]
        self._last_screenshots = []
        return shots

    def _fetch_page_text(self, url: str, timeout: int = 15) -> str:
        """Navigate to URL via headless Chromium, return visible page text."""
        # Sprint 153: SSRF prevention — block private/reserved IPs
        from app.engine.search_platforms.utils import validate_url_for_scraping
        validate_url_for_scraping(url)

        self._last_screenshots = []  # Reset for new search
        browser = _get_browser()
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 720},
            locale="vi-VN",
        )
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
            self._capture_screenshot(page, "Đang tải trang...")
            self._post_navigate(page)
            self._capture_screenshot(page, "Đã tải nội dung")
            text = page.inner_text("body")
            return text[:_MAX_PAGE_TEXT] if text else ""
        finally:
            context.close()

    def _post_navigate(self, page) -> None:
        """Override in subclass for platform-specific actions."""
        pass

    def _llm_extract(self, page_text: str, max_results: int) -> List[ProductSearchResult]:
        """Use Gemini Flash to extract structured product data from page text."""
        from app.engine.llm_pool import get_llm_light
        from langchain_core.messages import HumanMessage

        prompt = self._get_extraction_prompt().format(
            text=page_text[:_MAX_PROMPT_TEXT],
            max_results=max_results,
        )

        llm = get_llm_light()
        response = llm.invoke([HumanMessage(content=prompt)])
        raw = response.content if hasattr(response, "content") else str(response)

        # Gemini may return list[dict] block format instead of plain string
        if isinstance(raw, list):
            content = " ".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in raw
            )
        else:
            content = str(raw)

        products = _extract_json_array(content)
        return [self._map_to_result(p) for p in products[:max_results] if isinstance(p, dict)]

    def _map_to_result(self, item: dict) -> ProductSearchResult:
        """Map LLM-extracted dict to ProductSearchResult."""
        config = self.get_config()
        price_str = str(item.get("price", ""))
        return ProductSearchResult(
            platform=config.display_name,
            title=str(item.get("title", "")),
            price=price_str,
            extracted_price=_parse_vnd_price(price_str),
            link=str(item.get("link", "")),
            seller=str(item.get("seller", "")),
            location=str(item.get("location", "")),
            snippet=str(item.get("description", "")),
        )

    @abstractmethod
    def _build_url(self, query: str, page: int) -> str:
        """Build search URL for the platform."""
        ...

    @abstractmethod
    def _get_extraction_prompt(self) -> str:
        """Return LLM prompt template with {text} and {max_results} placeholders."""
        ...

    def search_sync(self, query: str, max_results: int = 20, page: int = 1) -> List[ProductSearchResult]:
        """Fetch page via Playwright, extract products via LLM.

        Playwright sync API cannot run inside an asyncio event loop, so we
        offload _fetch_page_text to a thread pool when called from async context.
        """
        if not query or not query.strip():
            return []

        url = self._build_url(query.strip(), page)
        try:
            text = self._run_fetch(url)
            if not text or len(text) < 100:
                return []
            return self._llm_extract(text, max_results)
        except ImportError:
            logger.warning("[BROWSER] playwright not installed — cannot scrape")
            return []
        except Exception as e:
            logger.warning("[BROWSER] Error scraping %s: %s", url, e)
            return []

    def _run_fetch(self, url: str) -> str:
        """Run _fetch_page_text, using a thread pool if inside asyncio loop."""
        import asyncio
        try:
            asyncio.get_running_loop()
            # Inside asyncio — must offload to thread
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(self._fetch_page_text, url, self._get_timeout())
                return future.result(timeout=self._get_timeout() + 10)
        except RuntimeError:
            # No asyncio loop — call directly
            return self._fetch_page_text(url, timeout=self._get_timeout())

    def _get_timeout(self) -> int:
        """Get browser timeout from config."""
        try:
            from app.core.config import get_settings
            return get_settings().browser_scraping_timeout
        except Exception:
            return 15
