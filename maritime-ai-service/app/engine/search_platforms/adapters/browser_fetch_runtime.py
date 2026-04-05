import json
import time
from typing import Any, Callable


def fetch_page_text_impl(
    adapter: Any,
    url: str,
    timeout: int = 15,
    cookies: list | None = None,
    _browser: Any = None,
    *,
    get_browser: Callable[[], Any],
    max_page_text: int,
) -> str:
    """Navigate to URL via headless Chromium, return visible page text."""
    from app.engine.search_platforms.utils import validate_url_for_scraping

    validate_url_for_scraping(url)

    adapter._last_screenshots = []
    browser = _browser if _browser is not None else get_browser()
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
        adapter._capture_screenshot(page, "Đang tải trang...")
        adapter._post_navigate(page)
        adapter._capture_screenshot(page, "Đã tải nội dung")
        text = page.inner_text("body")
        return text[:max_page_text] if text else ""
    finally:
        context.close()


def fetch_page_text_with_scroll_impl(
    adapter: Any,
    url: str,
    timeout: int = 15,
    cookies: list | None = None,
    _browser: Any = None,
    max_scrolls: int = 8,
    scroll_delay: float = 2.5,
    scroll_distance: int = 800,
    *,
    get_browser: Callable[[], Any],
    max_page_text: int,
    scroll_extract_js: str,
) -> str:
    """Navigate + scroll-and-extract for virtual scrolling pages."""
    from app.engine.search_platforms.utils import validate_url_for_scraping

    validate_url_for_scraping(url)

    adapter._last_screenshots = []
    browser = _browser if _browser is not None else get_browser()
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
        adapter._capture_screenshot(page, "Đang tải trang...")
        adapter._post_navigate(page)

        seen_keys: set[str] = set()
        all_parts: list[str] = []
        no_new_count = 0

        for i in range(max_scrolls):
            try:
                articles = page.evaluate(scroll_extract_js)
            except Exception:
                articles = []

            if not articles:
                try:
                    body_text = page.inner_text("body")
                    articles = [{"text": body_text, "link": "", "image": ""}] if body_text else []
                except Exception:
                    articles = []

            new_count = 0
            for article in articles:
                text_content = article.get("text", "") if isinstance(article, dict) else str(article)
                link = article.get("link", "") if isinstance(article, dict) else ""
                image = article.get("image", "") if isinstance(article, dict) else ""
                if not text_content or not text_content.strip():
                    continue
                key = text_content[:200].strip()
                if key not in seen_keys:
                    seen_keys.add(key)
                    prefix = ""
                    if link:
                        prefix += f"[POST_URL: {link}]\n"
                    if image:
                        prefix += f"[POST_IMAGE: {image}]\n"
                    all_parts.append(f"{prefix}{text_content}" if prefix else text_content)
                    new_count += 1

            if new_count == 0:
                no_new_count += 1
            else:
                no_new_count = 0
            if no_new_count >= 3:
                break

            if i == max_scrolls // 2:
                adapter._capture_screenshot(page, "Cuộn trang...")

            page.evaluate(f"window.scrollBy(0, {scroll_distance})")
            time.sleep(scroll_delay)

        adapter._capture_screenshot(page, "Đã tải xong nội dung")
        text = "\n\n---\n\n".join(all_parts)
        return text[:max_page_text] if text else ""
    finally:
        context.close()


def run_fetch_with_scroll_impl(
    adapter: Any,
    url: str,
    max_scrolls: int = 8,
    scroll_delay: float = 2.5,
    scroll_distance: int = 800,
    *,
    submit_to_pw_worker: Callable[..., Any],
) -> str:
    """Submit scroll-and-extract to Playwright worker thread."""
    cookies = adapter._get_cookies()
    timeout = adapter._get_timeout()

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

    worker_timeout = timeout + int(max_scrolls * (scroll_delay + 2)) + 15
    return submit_to_pw_worker(_do_fetch, timeout=worker_timeout)


def fetch_page_with_interception_impl(
    adapter: Any,
    url: str,
    timeout: int = 15,
    cookies: list | None = None,
    _browser: Any = None,
    max_scrolls: int = 8,
    scroll_delay: float = 2.5,
    scroll_distance: int = 800,
    max_response_size: int = 5_000_000,
    *,
    get_browser: Callable[[], Any],
    max_page_text: int,
    scroll_extract_js: str,
    graphql_endpoint: str,
    for_loop_prefix: str,
    scan_for_products: Callable[[Any], list],
    extract_product_from_node: Callable[[Any], dict | None],
    logger: Any,
) -> tuple[str, list]:
    """Navigate + scroll with GraphQL response interception."""
    from app.engine.search_platforms.utils import validate_url_for_scraping

    validate_url_for_scraping(url)

    adapter._last_screenshots = []
    browser = _browser if _browser is not None else get_browser()
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

    intercepted: list = []
    seen_titles: set[str] = set()

    def _on_response(response):
        try:
            req = response.request
            if req.method != "POST":
                return
            if graphql_endpoint not in response.url:
                return

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
            if text.startswith(for_loop_prefix):
                text = text[len(for_loop_prefix):]
            text = text.lstrip()
            if not text:
                return

            data = json.loads(text)
            nodes = scan_for_products(data)
            for node in nodes:
                product = extract_product_from_node(node)
                if product and product.get("title"):
                    dedup_key = product["title"][:100].lower()
                    if dedup_key not in seen_titles:
                        seen_titles.add(dedup_key)
                        intercepted.append(product)

        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
        except Exception as exc:
            logger.debug("[INTERCEPT] Response parse error: %s", exc)

    try:
        page.on("response", _on_response)
        page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
        adapter._capture_screenshot(page, "Đang tải trang...")
        adapter._post_navigate(page)

        seen_keys: set[str] = set()
        all_parts: list[str] = []
        no_new_count = 0

        for i in range(max_scrolls):
            try:
                articles = page.evaluate(scroll_extract_js)
            except Exception:
                articles = []

            if not articles:
                try:
                    body_text = page.inner_text("body")
                    articles = [{"text": body_text, "link": "", "image": ""}] if body_text else []
                except Exception:
                    articles = []

            new_count = 0
            for article in articles:
                text = article.get("text", "") if isinstance(article, dict) else str(article)
                link = article.get("link", "") if isinstance(article, dict) else ""
                image = article.get("image", "") if isinstance(article, dict) else ""
                if not text or not text.strip():
                    continue
                key = text[:200].strip()
                if key not in seen_keys:
                    seen_keys.add(key)
                    prefix = ""
                    if link:
                        prefix += f"[POST_URL: {link}]\n"
                    if image:
                        prefix += f"[POST_IMAGE: {image}]\n"
                    all_parts.append(f"{prefix}{text}" if prefix else text)
                    new_count += 1

            if new_count == 0:
                no_new_count += 1
            else:
                no_new_count = 0
            if no_new_count >= 3:
                break

            if i == max_scrolls // 2:
                adapter._capture_screenshot(page, "Cuộn trang...")

            page.evaluate(f"window.scrollBy(0, {scroll_distance})")
            time.sleep(scroll_delay)

        adapter._capture_screenshot(page, "Đã tải xong nội dung")
        dom_text = "\n\n---\n\n".join(all_parts)
        dom_text = dom_text[:max_page_text] if dom_text else ""

        if intercepted:
            logger.info(
                "[INTERCEPT] Captured %d unique products from GraphQL",
                len(intercepted),
            )

        return (dom_text, intercepted)
    finally:
        context.close()


def run_fetch_with_interception_impl(
    adapter: Any,
    url: str,
    max_scrolls: int = 8,
    scroll_delay: float = 2.5,
    scroll_distance: int = 800,
    max_response_size: int = 5_000_000,
    *,
    submit_to_pw_worker: Callable[..., Any],
) -> tuple[str, list]:
    """Submit scroll-with-interception to Playwright worker thread."""
    cookies = adapter._get_cookies()
    timeout = adapter._get_timeout()

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
    return submit_to_pw_worker(_do_fetch, timeout=worker_timeout)


def llm_extract_impl(
    adapter: Any,
    page_text: str,
    max_results: int,
    *,
    max_prompt_text: int,
    extract_json_array: Callable[[str], list],
) -> list:
    """Use light LLM to extract structured product data from page text."""
    from app.engine.llm_pool import get_llm_light
    from langchain_core.messages import HumanMessage

    prompt = adapter._get_extraction_prompt().format(
        text=page_text[:max_prompt_text],
        max_results=max_results,
    )

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

    products = extract_json_array(content)
    return [adapter._map_to_result(item) for item in products[:max_results] if isinstance(item, dict)]


def run_fetch_impl(
    adapter: Any,
    url: str,
    *,
    submit_to_pw_worker: Callable[..., Any],
) -> str:
    """Fetch page text via dedicated Playwright worker thread."""
    cookies = adapter._get_cookies()
    timeout = adapter._get_timeout()

    def _do_fetch(browser):
        return adapter._fetch_page_text(
            url,
            timeout,
            cookies,
            _browser=browser,
        )

    return submit_to_pw_worker(_do_fetch, timeout=timeout + 15)
