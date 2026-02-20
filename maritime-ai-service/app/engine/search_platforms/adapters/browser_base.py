"""
Playwright + LLM Extraction — Base Class for Browser-Based Adapters

Sprint 152: "Trinh Duyet Thong Minh"
Sprint 154b: Dedicated worker thread (fixes greenlet "Cannot switch" errors)

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

import concurrent.futures
import json
import logging
import queue as _queue_mod
import re
import threading
from abc import abstractmethod
from typing import List, Optional

from app.engine.search_platforms.base import (
    ProductSearchResult,
    SearchPlatformAdapter,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Legacy browser singleton — used in non-asyncio path (tests, CLI).
# Production asyncio path uses the dedicated worker thread instead.
# ---------------------------------------------------------------------------
_browser = None
_playwright_instance = None
_browser_lock = threading.Lock()

# Max page text sent to LLM (chars)
_MAX_PAGE_TEXT = 50000
# Max text in LLM prompt (chars) — leave room for prompt template
_MAX_PROMPT_TEXT = 30000
# Sprint 153: Max screenshots per search
_MAX_SCREENSHOTS = 5

# ---------------------------------------------------------------------------
# Sprint 156: Network Interception — GraphQL structured data capture
# ---------------------------------------------------------------------------
_FOR_LOOP_PREFIX = "for (;;);"
_GRAPHQL_ENDPOINT = "/api/graphql/"
_PRODUCT_INDICATOR_FIELDS = frozenset({
    "marketplace_listing_title", "listing_price",
    "primary_listing_photo", "marketplace_listing_seller",
})
_MIN_INDICATOR_MATCH = 2
_INTERCEPTION_FALLBACK_THRESHOLD = 3

# ---------------------------------------------------------------------------
# Dedicated Playwright worker thread (Sprint 154b)
# ---------------------------------------------------------------------------
# Playwright sync API uses greenlets internally. The browser singleton is
# bound to the greenlet of the thread that created it. ThreadPoolExecutor's
# submit() runs each task in a potentially different greenlet context, causing
# "Cannot switch to a different thread" on subsequent calls. This dedicated
# worker keeps the browser + greenlet alive across all calls.
_pw_task_queue: Optional[_queue_mod.Queue] = None
_pw_worker_thread: Optional[threading.Thread] = None
_pw_worker_lock = threading.Lock()


def _pw_worker_loop(task_queue: _queue_mod.Queue) -> None:
    """Dedicated thread: creates Playwright browser once, processes tasks.

    All Playwright operations run in THIS thread's main greenlet, ensuring
    the browser singleton can be reused across multiple calls without
    "Cannot switch to a different thread" errors.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        # Playwright not installed — drain tasks with ImportError
        while True:
            item = task_queue.get()
            if item is None:
                break
            _, result_future = item
            if not result_future.cancelled():
                result_future.set_exception(
                    ImportError("playwright not installed")
                )
        return

    pw = sync_playwright().start()
    browser = pw.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
        ],
    )
    logger.info("[BROWSER] Playwright worker started, browser launched")

    try:
        while True:
            item = task_queue.get()
            if item is None:  # Shutdown signal
                break
            fn, result_future = item
            try:
                # Auto-reconnect if browser died
                if not browser.is_connected():
                    logger.info("[BROWSER] Reconnecting browser...")
                    browser = pw.chromium.launch(
                        headless=True,
                        args=[
                            "--no-sandbox",
                            "--disable-blink-features=AutomationControlled",
                        ],
                    )
                result = fn(browser)
                if not result_future.cancelled():
                    result_future.set_result(result)
            except Exception as e:
                if not result_future.cancelled():
                    result_future.set_exception(e)
    finally:
        try:
            browser.close()
        except Exception:
            pass
        try:
            pw.stop()
        except Exception:
            pass
        logger.info("[BROWSER] Playwright worker stopped")


def _ensure_pw_worker() -> _queue_mod.Queue:
    """Start the Playwright worker thread if not running. Returns task queue."""
    global _pw_task_queue, _pw_worker_thread
    with _pw_worker_lock:
        if _pw_worker_thread is None or not _pw_worker_thread.is_alive():
            _pw_task_queue = _queue_mod.Queue()
            _pw_worker_thread = threading.Thread(
                target=_pw_worker_loop,
                args=(_pw_task_queue,),
                daemon=True,
                name="playwright-worker",
            )
            _pw_worker_thread.start()
    return _pw_task_queue


def _submit_to_pw_worker(fn, timeout: float = 30):
    """Submit fn(browser) to Playwright worker. Blocks until result ready."""
    q = _ensure_pw_worker()
    future = concurrent.futures.Future()
    q.put((fn, future))
    return future.result(timeout=timeout)


def _get_browser():
    """Get or create shared headless Chromium browser (thread-safe singleton).

    Used in non-asyncio path (tests, CLI). Production asyncio path uses
    the dedicated worker thread instead — see _submit_to_pw_worker().
    """
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
    """Cleanup browser and worker thread — call at app shutdown."""
    global _browser, _playwright_instance, _pw_worker_thread, _pw_task_queue
    # Legacy singleton cleanup (tests, non-asyncio path)
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
    # Worker thread shutdown (production asyncio path)
    with _pw_worker_lock:
        if _pw_task_queue is not None:
            _pw_task_queue.put(None)  # Shutdown signal
        if _pw_worker_thread is not None:
            _pw_worker_thread.join(timeout=5)
            _pw_worker_thread = None
        _pw_task_queue = None


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

    def _get_cookies(self) -> list:
        """Override in subclass to provide cookies for Playwright context.

        Returns list of Playwright cookie dicts: [{name, value, domain, path}]
        Called in the calling thread (asyncio) before worker thread submission.
        """
        return []

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

    def _fetch_page_text(self, url: str, timeout: int = 15,
                         cookies: list | None = None,
                         _browser=None) -> str:
        """Navigate to URL via headless Chromium, return visible page text.

        Args:
            url: Target URL (validated for SSRF).
            timeout: Page load timeout in seconds.
            cookies: Sprint 154 — Playwright cookie dicts to inject.
            _browser: Sprint 154b — Browser from worker thread. When None,
                      uses legacy _get_browser() singleton (tests/CLI).
        """
        # Sprint 153: SSRF prevention — block private/reserved IPs
        from app.engine.search_platforms.utils import validate_url_for_scraping
        validate_url_for_scraping(url)

        self._last_screenshots = []  # Reset for new search
        browser = _browser if _browser is not None else _get_browser()
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 720},
            locale="vi-VN",
        )
        # Sprint 154: Inject cookies before navigation (e.g. Facebook login)
        if cookies:
            context.add_cookies(cookies)
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

    # ------------------------------------------------------------------
    # Sprint 155: Scroll-and-extract for virtual-scrolling pages
    # ------------------------------------------------------------------

    def _fetch_page_text_with_scroll(
        self,
        url: str,
        timeout: int = 15,
        cookies: list | None = None,
        _browser=None,
        max_scrolls: int = 8,
        scroll_delay: float = 2.5,
        scroll_distance: int = 800,
    ) -> str:
        """Navigate + scroll-and-extract for virtual scrolling pages.

        Facebook uses DOM recycling — old articles are REMOVED from the DOM
        when you scroll past them.  If we scroll first then extract, we only
        get the last batch.  This method extracts DURING each scroll
        iteration and accumulates unique content.

        Algorithm:
        1. Navigate to URL, inject cookies
        2. Dismiss modals via _post_navigate()
        3. For each scroll iteration:
           a. Extract text from div[role="article"] (fallback: body)
           b. Dedup: first 200 chars as key
           c. End detection: 3 consecutive scrolls with no new content → break
           d. Screenshot at midpoint
        4. Return accumulated text (joined all unique articles)
        """
        import time

        from app.engine.search_platforms.utils import validate_url_for_scraping
        validate_url_for_scraping(url)

        self._last_screenshots = []
        browser = _browser if _browser is not None else _get_browser()
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
            page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
            self._capture_screenshot(page, "Đang tải trang...")
            self._post_navigate(page)

            # Accumulate unique articles across scrolls
            seen_keys: set = set()
            all_parts: list = []
            no_new_count = 0

            for i in range(max_scrolls):
                # 1. Extract visible articles via JS
                try:
                    articles = page.evaluate("""() => {
                        const els = document.querySelectorAll('div[role="article"]');
                        if (els.length > 0) {
                            return Array.from(els).map(a => a.innerText);
                        }
                        return [];
                    }""")
                except Exception:
                    articles = []

                # Fallback if no article elements found
                if not articles:
                    try:
                        body_text = page.inner_text("body")
                        articles = [body_text] if body_text else []
                    except Exception:
                        articles = []

                # 2. Dedup by first 200 chars
                new_count = 0
                for article in articles:
                    if not article or not article.strip():
                        continue
                    key = article[:200].strip()
                    if key not in seen_keys:
                        seen_keys.add(key)
                        all_parts.append(article)
                        new_count += 1

                # 3. End detection: 3 empty scrolls → done
                if new_count == 0:
                    no_new_count += 1
                else:
                    no_new_count = 0
                if no_new_count >= 3:
                    break

                # 4. Screenshot at midpoint
                if i == max_scrolls // 2:
                    self._capture_screenshot(page, "Cuộn trang...")

                # 5. Scroll + human delay
                page.evaluate(f"window.scrollBy(0, {scroll_distance})")
                time.sleep(scroll_delay)

            self._capture_screenshot(page, "Đã tải xong nội dung")
            text = "\n\n---\n\n".join(all_parts)
            return text[:_MAX_PAGE_TEXT] if text else ""
        finally:
            context.close()

    def _run_fetch_with_scroll(
        self,
        url: str,
        max_scrolls: int = 8,
        scroll_delay: float = 2.5,
        scroll_distance: int = 800,
    ) -> str:
        """Submit scroll-and-extract to Playwright worker thread.

        Like _run_fetch() but uses _fetch_page_text_with_scroll() instead
        of _fetch_page_text().  Extended timeout to account for scrolling.
        """
        cookies = self._get_cookies()
        timeout = self._get_timeout()
        adapter = self

        def _do_fetch(browser):
            return adapter._fetch_page_text_with_scroll(
                url,
                timeout=timeout,
                cookies=cookies,
                _browser=browser,
                max_scrolls=max_scrolls,
                scroll_delay=scroll_delay,
                scroll_distance=scroll_distance,
            )

        # Extended timeout: base + scrolling time + buffer
        worker_timeout = timeout + int(max_scrolls * (scroll_delay + 2)) + 15
        return _submit_to_pw_worker(_do_fetch, timeout=worker_timeout)

    # ------------------------------------------------------------------
    # Sprint 156: Network Interception — GraphQL structured data
    # ------------------------------------------------------------------

    @staticmethod
    def _scan_for_products(data, max_depth: int = 20) -> list:
        """Recursively scan JSON for dicts with 2+ product indicator fields.

        Content-based matching: finds dicts containing fields like
        marketplace_listing_title, listing_price, etc. Resilient to
        Facebook API changes (doc_id changes every deployment).

        Returns list of raw dicts (product nodes).
        """
        results = []

        def _walk(obj, depth):
            if depth <= 0:
                return
            if isinstance(obj, dict):
                matched = sum(1 for k in obj if k in _PRODUCT_INDICATOR_FIELDS)
                if matched >= _MIN_INDICATOR_MATCH:
                    results.append(obj)
                for v in obj.values():
                    if isinstance(v, (dict, list)):
                        _walk(v, depth - 1)
            elif isinstance(obj, list):
                for item in obj:
                    if isinstance(item, (dict, list)):
                        _walk(item, depth - 1)

        _walk(data, max_depth)
        return results

    @staticmethod
    def _extract_product_from_node(node: dict) -> Optional[dict]:
        """Map a GraphQL product node to a normalized dict.

        Field mapping:
        - Title: marketplace_listing_title → name → title
        - Price: listing_price.formatted_amount → listing_price.amount + currency
        - Image: primary_listing_photo.image.uri
        - Seller: marketplace_listing_seller.name
        - Location: location.reverse_geocode.city_page.name
        """
        if not isinstance(node, dict):
            return None

        # Title
        title = (
            node.get("marketplace_listing_title")
            or node.get("name")
            or node.get("title")
        )
        if not title:
            return None

        # Price
        price = ""
        price_obj = node.get("listing_price")
        if isinstance(price_obj, dict):
            price = price_obj.get("formatted_amount", "")
            if not price:
                amount = price_obj.get("amount")
                currency = price_obj.get("currency", "")
                if amount is not None:
                    price = f"{amount} {currency}".strip()

        # Image
        image = ""
        photo = node.get("primary_listing_photo")
        if isinstance(photo, dict):
            img_obj = photo.get("image")
            if isinstance(img_obj, dict):
                image = img_obj.get("uri", "")
            elif isinstance(photo.get("uri"), str):
                image = photo["uri"]

        # Seller
        seller = ""
        seller_obj = node.get("marketplace_listing_seller")
        if isinstance(seller_obj, dict):
            seller = seller_obj.get("name", "")

        # Location
        location = ""
        loc_obj = node.get("location")
        if isinstance(loc_obj, dict):
            geo = loc_obj.get("reverse_geocode")
            if isinstance(geo, dict):
                city = geo.get("city_page")
                if isinstance(city, dict):
                    location = city.get("name", "")
                elif isinstance(geo.get("city"), str):
                    location = geo["city"]

        return {
            "title": str(title),
            "price": str(price),
            "image": str(image),
            "seller": str(seller),
            "location": str(location),
        }

    def _fetch_page_with_interception(
        self,
        url: str,
        timeout: int = 15,
        cookies: list | None = None,
        _browser=None,
        max_scrolls: int = 8,
        scroll_delay: float = 2.5,
        scroll_distance: int = 800,
        max_response_size: int = 5_000_000,
    ) -> tuple:
        """Navigate + scroll with GraphQL response interception.

        Like _fetch_page_text_with_scroll but also captures structured
        product data from Facebook's GraphQL API responses.

        Returns (dom_text: str, intercepted_products: list[dict])
        """
        import time

        from app.engine.search_platforms.utils import validate_url_for_scraping
        validate_url_for_scraping(url)

        self._last_screenshots = []
        browser = _browser if _browser is not None else _get_browser()
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

        # Interception state (written only from page.on callback, same thread)
        intercepted: list = []
        seen_titles: set = set()

        def _on_response(response):
            """Filter and parse GraphQL responses for product data."""
            try:
                req = response.request
                if req.method != "POST":
                    return
                if _GRAPHQL_ENDPOINT not in response.url:
                    return

                # Skip oversized responses
                headers = response.headers
                content_length = headers.get("content-length", "0")
                try:
                    if int(content_length) > max_response_size:
                        return
                except (ValueError, TypeError):
                    pass

                body = response.body()
                if len(body) > max_response_size:
                    return

                text = body.decode("utf-8", errors="ignore")

                # Strip Facebook's JSONP prevention prefix
                if text.startswith(_FOR_LOOP_PREFIX):
                    text = text[len(_FOR_LOOP_PREFIX):]
                text = text.lstrip()

                if not text:
                    return

                data = json.loads(text)
                nodes = PlaywrightLLMAdapter._scan_for_products(data)
                for node in nodes:
                    product = PlaywrightLLMAdapter._extract_product_from_node(node)
                    if product and product.get("title"):
                        # Dedup by title prefix (case-insensitive)
                        dedup_key = product["title"][:100].lower()
                        if dedup_key not in seen_titles:
                            seen_titles.add(dedup_key)
                            intercepted.append(product)

            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
            except Exception as e:
                logger.debug("[INTERCEPT] Response parse error: %s", e)

        try:
            # Register interception listener BEFORE navigation
            page.on("response", _on_response)

            page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
            self._capture_screenshot(page, "Đang tải trang...")
            self._post_navigate(page)

            # Scroll-and-extract (same as _fetch_page_text_with_scroll)
            seen_keys: set = set()
            all_parts: list = []
            no_new_count = 0

            for i in range(max_scrolls):
                try:
                    articles = page.evaluate("""() => {
                        const els = document.querySelectorAll('div[role="article"]');
                        if (els.length > 0) {
                            return Array.from(els).map(a => a.innerText);
                        }
                        return [];
                    }""")
                except Exception:
                    articles = []

                if not articles:
                    try:
                        body_text = page.inner_text("body")
                        articles = [body_text] if body_text else []
                    except Exception:
                        articles = []

                new_count = 0
                for article in articles:
                    if not article or not article.strip():
                        continue
                    key = article[:200].strip()
                    if key not in seen_keys:
                        seen_keys.add(key)
                        all_parts.append(article)
                        new_count += 1

                if new_count == 0:
                    no_new_count += 1
                else:
                    no_new_count = 0
                if no_new_count >= 3:
                    break

                if i == max_scrolls // 2:
                    self._capture_screenshot(page, "Cuộn trang...")

                page.evaluate(f"window.scrollBy(0, {scroll_distance})")
                time.sleep(scroll_delay)

            self._capture_screenshot(page, "Đã tải xong nội dung")
            dom_text = "\n\n---\n\n".join(all_parts)
            dom_text = dom_text[:_MAX_PAGE_TEXT] if dom_text else ""

            if intercepted:
                logger.info(
                    "[INTERCEPT] Captured %d unique products from GraphQL",
                    len(intercepted),
                )

            return (dom_text, intercepted)
        finally:
            context.close()

    def _run_fetch_with_interception(
        self,
        url: str,
        max_scrolls: int = 8,
        scroll_delay: float = 2.5,
        scroll_distance: int = 800,
        max_response_size: int = 5_000_000,
    ) -> tuple:
        """Submit scroll-with-interception to Playwright worker thread.

        Returns (dom_text, intercepted_products).
        """
        cookies = self._get_cookies()
        timeout = self._get_timeout()
        adapter = self

        def _do_fetch(browser):
            return adapter._fetch_page_with_interception(
                url,
                timeout=timeout,
                cookies=cookies,
                _browser=browser,
                max_scrolls=max_scrolls,
                scroll_delay=scroll_delay,
                scroll_distance=scroll_distance,
                max_response_size=max_response_size,
            )

        worker_timeout = timeout + int(max_scrolls * (scroll_delay + 2)) + 15
        return _submit_to_pw_worker(_do_fetch, timeout=worker_timeout)

    def _map_intercepted_to_result(self, item: dict) -> ProductSearchResult:
        """Map intercepted GraphQL product dict to ProductSearchResult."""
        config = self.get_config()
        price_str = item.get("price", "")
        return ProductSearchResult(
            platform=config.display_name,
            title=item.get("title", ""),
            price=price_str,
            extracted_price=_parse_vnd_price(price_str) if price_str else None,
            link="",
            seller=item.get("seller", ""),
            image=item.get("image", ""),
            location=item.get("location", ""),
            source="graphql_intercept",
        )

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
        offload to a dedicated worker thread when called from async context.
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
        """Fetch page text via dedicated Playwright worker thread.

        Sprint 154: Read cookies via _get_cookies() BEFORE thread submission.
        ContextVar does NOT propagate to other threads.

        Sprint 154b: ALWAYS uses dedicated worker thread with persistent queue.
        The worker creates Playwright + browser in its own greenlet and reuses
        them across all tasks — no "Cannot switch to a different thread" errors.

        Note: LangChain tools run on sync thread pool threads (not the asyncio
        event loop thread), so checking asyncio.get_running_loop() is wrong —
        it would always fall through to the direct path in production.
        """
        # Read cookies in calling thread (ContextVar-safe)
        cookies = self._get_cookies()
        timeout = self._get_timeout()
        adapter = self

        def _do_fetch(browser):
            return adapter._fetch_page_text(
                url, timeout, cookies, _browser=browser,
            )

        # Always use worker — DO NOT fall back to direct _get_browser()
        # which creates a singleton bound to ONE greenlet.  If the worker
        # fails (timeout, crash), let the exception propagate so the adapter's
        # search_sync() can fall back to Serper instead of hitting a
        # greenlet mismatch on the legacy singleton.
        return _submit_to_pw_worker(_do_fetch, timeout=timeout + 15)

    def _get_timeout(self) -> int:
        """Get browser timeout from config."""
        try:
            from app.core.config import get_settings
            return get_settings().browser_scraping_timeout
        except Exception:
            return 15
