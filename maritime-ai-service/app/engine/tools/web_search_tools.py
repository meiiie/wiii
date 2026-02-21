"""
Web Search Tools - DuckDuckGo integration for AI agents.

SOTA 2026: Agents need web search with resilience (circuit breaker + timeout).
Uses duckduckgo-search (free, no API key required).

Sprint 102: Enhanced Vietnamese search — news (RSS + DuckDuckGo News),
legal (site-restricted), maritime (site-restricted).
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from langchain_core.tools import tool

from app.engine.tools.registry import (
    ToolCategory,
    ToolAccess,
    get_tool_registry,
)

logger = logging.getLogger(__name__)

# Timeout for DuckDuckGo calls (seconds)
WEB_SEARCH_TIMEOUT = 10.0

# Thread pool for running sync DuckDuckGo in background
_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="web_search")

# Per-tool circuit breaker state (avoids importing resilience.py which is async)
# Sprint audit: Changed from single global CB to per-tool isolation
# to prevent one tool's failures from blocking unrelated tools.
_CB_THRESHOLD = 3
_CB_RECOVERY_SECONDS = 120
_cb_lock = threading.Lock()
_cb_states: dict = {}  # {tool_name: {"failures": int, "last_failure": float}}


# =============================================================================
# Sprint 102: Site restriction constants
# =============================================================================

_LEGAL_SITES = [
    "thuvienphapluat.vn", "vanban.chinhphu.vn",
    "luatvietnam.vn", "congbao.chinhphu.vn",
]

_NEWS_SITES = [
    "vnexpress.net", "tuoitre.vn",
    "thanhnien.vn", "dantri.com.vn",
]

_MARITIME_SITES = [
    "imo.org", "safety4sea.com", "maritime-executive.com",
    "splash247.com", "vinamarine.gov.vn", "mt.gov.vn",
]

_NEWS_RSS_FEEDS = {
    "vnexpress": "https://vnexpress.net/rss/tin-moi-nhat.rss",
    "tuoitre": "https://tuoitre.vn/rss/tin-moi-nhat.rss",
    "thanhnien": "https://thanhnien.vn/rss/home.rss",
    "dantri": "https://dantri.com.vn/rss/home.rss",
}


# =============================================================================
# Circuit breaker helpers
# =============================================================================

def _cb_is_open(tool_name: str = "default") -> bool:
    """Check if circuit breaker is open for a specific tool."""
    with _cb_lock:
        state = _cb_states.get(tool_name)
        if not state:
            return False
        if state["failures"] >= _CB_THRESHOLD:
            if time.time() - state["last_failure"] < _CB_RECOVERY_SECONDS:
                return True
            # Recovery period passed — reset
            state["failures"] = 0
        return False


def _cb_record_failure(tool_name: str = "default"):
    """Record a failure for a specific tool's circuit breaker."""
    with _cb_lock:
        if tool_name not in _cb_states:
            _cb_states[tool_name] = {"failures": 0, "last_failure": 0.0}
        _cb_states[tool_name]["failures"] += 1
        _cb_states[tool_name]["last_failure"] = time.time()


def _cb_record_success(tool_name: str = "default"):
    """Record success — reset failure count for a specific tool."""
    with _cb_lock:
        if tool_name in _cb_states:
            _cb_states[tool_name]["failures"] = 0


# =============================================================================
# Sync search helpers (run in ThreadPoolExecutor)
# =============================================================================

def _get_ddgs():
    """Import DDGS with fallback."""
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS
    return DDGS


def _search_sync(query: str, max_results: int = 5) -> list:
    """Synchronous DuckDuckGo search with fallback."""
    DDGS = _get_ddgs()

    # Try vn-vi first, fallback to wt-wt if empty
    for region in ("vn-vi", "wt-wt"):
        results = DDGS().text(
            query,
            region=region,
            safesearch="moderate",
            max_results=max_results,
            backend="auto",
        )
        if results:
            return results
    return []


def _search_site_restricted_sync(query: str, sites: list, max_results: int = 5) -> list:
    """Search DuckDuckGo with site: restriction.

    Sprint 102: Builds "site:a OR site:b" query prefix for domain-specific search.
    Falls back to general search if site-restricted returns nothing.
    """
    DDGS = _get_ddgs()

    site_filter = " OR ".join(f"site:{s}" for s in sites)
    restricted_query = f"({site_filter}) {query}"

    results = DDGS().text(
        restricted_query,
        region="vn-vi",
        safesearch="moderate",
        max_results=max_results,
        backend="auto",
    )
    if results:
        return results

    # Fallback: general search without site restriction
    return DDGS().text(
        query,
        region="vn-vi",
        safesearch="moderate",
        max_results=max_results,
        backend="auto",
    ) or []


def _news_search_sync(query: str, max_results: int = 5) -> list:
    """Search DuckDuckGo News with Vietnamese region.

    Sprint 102: Uses DDGS().news() for news-specific results.
    """
    DDGS = _get_ddgs()
    return DDGS().news(
        query,
        region="vn-vi",
        safesearch="moderate",
        max_results=max_results,
    ) or []


def _rss_fetch_sync(query: str, max_results: int = 5) -> list:
    """Fetch Vietnamese news from RSS feeds, filtered by query keywords.

    Sprint 102: Uses feedparser for RSS aggregation. Graceful on ImportError.
    """
    try:
        import feedparser
    except ImportError:
        return []

    query_words = [w.lower() for w in query.split() if len(w) >= 2]
    if not query_words:
        return []

    results = []
    for source, url in _NEWS_RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]:
                title = (entry.get("title") or "").lower()
                summary = (entry.get("summary") or "").lower()
                text = f"{title} {summary}"
                if any(w in text for w in query_words):
                    results.append({
                        "title": entry.get("title", ""),
                        "body": entry.get("summary", "")[:300],
                        "href": entry.get("link", ""),
                        "source": source,
                        "date": entry.get("published", ""),
                    })
        except Exception as e:
            logger.debug("[RSS] Failed to parse %s: %s", source, e)

    # Deduplicate by URL
    seen = set()
    deduped = []
    for r in results:
        if r["href"] not in seen:
            seen.add(r["href"])
            deduped.append(r)

    return deduped[:max_results]


# =============================================================================
# Format helpers
# =============================================================================

def _format_results(results: list, tag: str = "WEB_SEARCH") -> str:
    """Format search results into readable text."""
    formatted = []
    for r in results:
        title = r.get("title", "Không có tiêu đề")
        body = r.get("body", r.get("summary", ""))
        href = r.get("href", r.get("url", r.get("link", "")))
        date = r.get("date", r.get("published", ""))
        source = r.get("source", "")
        line = f"**{title}**"
        if date:
            line += f" ({date})"
        if source:
            line += f" [{source}]"
        line += f"\n{body}"
        if href:
            line += f"\nURL: {href}"
        formatted.append(line)

    logger.info("[%s] Found %d results", tag, len(results))
    return "\n\n---\n\n".join(formatted)


# =============================================================================
# Tool: General web search (existing)
# =============================================================================

@tool(description="Tìm kiếm thông tin trên web. Hữu ích khi cần thông tin mới nhất, tin tức, hoặc kiến thức không có trong cơ sở dữ liệu nội bộ.")
def tool_web_search(query: str) -> str:
    """Search the web for current information using DuckDuckGo."""
    _CB_NAME = "web_search"
    if _cb_is_open(_CB_NAME):
        logger.warning("[WEB_SEARCH] Circuit breaker OPEN — skipping search")
        return "Tìm kiếm web tạm thời không khả dụng. Vui lòng thử lại sau."

    try:
        import concurrent.futures

        future = _executor.submit(_search_sync, query)
        results = future.result(timeout=WEB_SEARCH_TIMEOUT)

        if not results:
            return "Không tìm thấy kết quả trên web."

        _cb_record_success(_CB_NAME)
        return _format_results(results, "WEB_SEARCH")

    except concurrent.futures.TimeoutError:
        _cb_record_failure(_CB_NAME)
        logger.warning("[WEB_SEARCH] Timeout (%ss) for: %s", WEB_SEARCH_TIMEOUT, query[:50])
        return "Tìm kiếm web quá thời gian chờ. Vui lòng thử lại."

    except ImportError:
        return "Lỗi: Chưa cài đặt duckduckgo-search. Chạy: pip install duckduckgo-search"

    except Exception as e:
        _cb_record_failure(_CB_NAME)
        logger.warning("[WEB_SEARCH] Failed: %s", e)
        return f"Lỗi tìm kiếm: {e}"


# =============================================================================
# Sprint 102: Tool — Vietnamese news search
# =============================================================================

@tool(description=(
    "Tìm kiếm TIN TỨC Việt Nam. BẮT BUỘC dùng khi user hỏi về tin tức, thời sự, "
    "sự kiện, bản tin, báo chí. Nguồn: VnExpress, Tuổi Trẻ, Thanh Niên, Dân Trí + RSS feeds."
))
def tool_search_news(query: str) -> str:
    """Search Vietnamese news using DuckDuckGo News + RSS feeds."""
    _CB_NAME = "search_news"
    if _cb_is_open(_CB_NAME):
        logger.warning("[NEWS_SEARCH] Circuit breaker OPEN — skipping search")
        return "Tìm kiếm tin tức tạm thời không khả dụng. Vui lòng thử lại sau."

    try:
        import concurrent.futures

        # Run DuckDuckGo news + RSS in parallel
        news_future = _executor.submit(_news_search_sync, query, 5)
        rss_future = _executor.submit(_rss_fetch_sync, query, 5)

        ddg_results = []
        rss_results = []
        try:
            ddg_results = news_future.result(timeout=WEB_SEARCH_TIMEOUT)
        except concurrent.futures.TimeoutError:
            logger.warning("[NEWS_SEARCH] DuckDuckGo news timeout")
        try:
            rss_results = rss_future.result(timeout=WEB_SEARCH_TIMEOUT)
        except concurrent.futures.TimeoutError:
            logger.warning("[NEWS_SEARCH] RSS fetch timeout")

        # Merge and deduplicate by URL
        all_results = []
        seen_urls = set()
        for r in ddg_results + rss_results:
            url = r.get("href", r.get("url", r.get("link", "")))
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_results.append(r)

        if not all_results:
            return "Không tìm thấy tin tức liên quan."

        _cb_record_success(_CB_NAME)
        return _format_results(all_results[:8], "NEWS_SEARCH")

    except ImportError:
        return "Lỗi: Chưa cài đặt duckduckgo-search. Chạy: pip install duckduckgo-search"

    except Exception as e:
        _cb_record_failure(_CB_NAME)
        logger.warning("[NEWS_SEARCH] Failed: %s", e)
        return f"Lỗi tìm kiếm tin tức: {e}"


# =============================================================================
# Sprint 102: Tool — Vietnamese legal search
# =============================================================================

@tool(description=(
    "Tìm kiếm VĂN BẢN PHÁP LUẬT Việt Nam. BẮT BUỘC dùng khi user hỏi về luật, nghị định, "
    "thông tư, quy định pháp luật, mức phạt, bộ luật. "
    "Nguồn: Thư viện Pháp luật, Cổng TTĐT Chính phủ, Luật Việt Nam, Công báo."
))
def tool_search_legal(query: str) -> str:
    """Search Vietnamese legal documents using site-restricted DuckDuckGo."""
    _CB_NAME = "search_legal"
    if _cb_is_open(_CB_NAME):
        logger.warning("[LEGAL_SEARCH] Circuit breaker OPEN — skipping search")
        return "Tìm kiếm pháp luật tạm thời không khả dụng. Vui lòng thử lại sau."

    try:
        import concurrent.futures

        future = _executor.submit(
            _search_site_restricted_sync, query, _LEGAL_SITES, 7
        )
        results = future.result(timeout=WEB_SEARCH_TIMEOUT)

        if not results:
            return "Không tìm thấy văn bản pháp luật liên quan."

        _cb_record_success(_CB_NAME)
        return _format_results(results, "LEGAL_SEARCH")

    except concurrent.futures.TimeoutError:
        _cb_record_failure(_CB_NAME)
        logger.warning("[LEGAL_SEARCH] Timeout for: %s", query[:50])
        return "Tìm kiếm pháp luật quá thời gian chờ. Vui lòng thử lại."

    except ImportError:
        return "Lỗi: Chưa cài đặt duckduckgo-search. Chạy: pip install duckduckgo-search"

    except Exception as e:
        _cb_record_failure(_CB_NAME)
        logger.warning("[LEGAL_SEARCH] Failed: %s", e)
        return f"Lỗi tìm kiếm pháp luật: {e}"


# =============================================================================
# Sprint 102: Tool — International maritime search
# =============================================================================

@tool(description=(
    "Tìm kiếm thông tin HÀNG HẢI quốc tế trên web. Dùng khi user hỏi về IMO, "
    "quy định hàng hải quốc tế, tin tức shipping, DNV, classification societies, "
    "hoặc thông tin từ Cục Hàng hải Việt Nam. "
    "Nguồn: IMO, Safety4Sea, Maritime Executive, VINAMARINE."
))
def tool_search_maritime(query: str) -> str:
    """Search international maritime information using site-restricted DuckDuckGo."""
    _CB_NAME = "search_maritime"
    if _cb_is_open(_CB_NAME):
        logger.warning("[MARITIME_SEARCH] Circuit breaker OPEN — skipping search")
        return "Tìm kiếm hàng hải tạm thời không khả dụng. Vui lòng thử lại sau."

    try:
        import concurrent.futures

        future = _executor.submit(
            _search_site_restricted_sync, query, _MARITIME_SITES, 7
        )
        results = future.result(timeout=WEB_SEARCH_TIMEOUT)

        if not results:
            return "Không tìm thấy thông tin hàng hải liên quan."

        _cb_record_success(_CB_NAME)
        return _format_results(results, "MARITIME_SEARCH")

    except concurrent.futures.TimeoutError:
        _cb_record_failure(_CB_NAME)
        logger.warning("[MARITIME_SEARCH] Timeout for: %s", query[:50])
        return "Tìm kiếm hàng hải quá thời gian chờ. Vui lòng thử lại."

    except ImportError:
        return "Lỗi: Chưa cài đặt duckduckgo-search. Chạy: pip install duckduckgo-search"

    except Exception as e:
        _cb_record_failure(_CB_NAME)
        logger.warning("[MARITIME_SEARCH] Failed: %s", e)
        return f"Lỗi tìm kiếm hàng hải: {e}"


# =============================================================================
# Registration
# =============================================================================

def init_web_search_tools() -> None:
    """Register web search tools with the global registry."""
    registry = get_tool_registry()

    for tool_fn, desc in [
        (tool_web_search, "Web search via DuckDuckGo"),
        (tool_search_news, "Vietnamese news search (DuckDuckGo News + RSS)"),
        (tool_search_legal, "Vietnamese legal document search (site-restricted)"),
        (tool_search_maritime, "Maritime international search (site-restricted)"),
    ]:
        registry.register(
            tool_fn,
            category=ToolCategory.UTILITY,
            access=ToolAccess.READ,
            description=desc,
        )

    logger.info("Web search tools registered: web_search, search_news, search_legal, search_maritime")
