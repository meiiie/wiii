"""
Web Search Tools - Serper.dev (Sprint 198) + DuckDuckGo fallback for AI agents.

SOTA 2026: Agents need web search with resilience (circuit breaker + timeout).
Sprint 198: Primary backend is Serper.dev (Google search API) for reliable
Vietnamese search. Falls back to DuckDuckGo when Serper unavailable.

Sprint 102: Enhanced Vietnamese search — news (RSS + Serper News),
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
# SOTA relevance filter — align with Perplexity / Gemini Deep Research
# =============================================================================

# Vietnamese + English function words that should not count as content matches.
# Without this filter, queries like "giá dầu hôm nay" match every trending
# article that contains "hôm nay" — producing noise instead of relevance.
_VI_EN_STOPWORDS = frozenset({
    # Vietnamese common fillers
    "là", "của", "và", "cho", "với", "các", "những", "một", "tôi", "bạn", "mình",
    "hôm", "nay", "qua", "mai", "đang", "sẽ", "có", "không", "được", "rồi",
    "thì", "mà", "như", "để", "từ", "trong", "ngoài", "ở", "đến", "theo",
    "hay", "hoặc", "nhưng", "này", "kia", "đó", "ai", "gì", "sao", "nào",
    "mới", "cũ", "lại", "đã", "chỉ", "cũng", "thêm", "nữa", "ra", "vào",
    "về", "trên", "dưới", "trước", "sau", "giữa", "bên", "lúc", "khi",
    "tại", "bởi", "do", "nên", "vì", "nếu", "thì",
    # English
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "what", "when", "where", "who", "how", "why", "i", "you", "we", "they",
    "today", "now", "current", "latest", "today's",
})


def _content_words(query: str) -> list[str]:
    """Tokenize a query into content-carrying lowercase words (≥2 chars, non-stopword)."""
    raw = [w.strip(".,!?;:\"'()[]{}").lower() for w in (query or "").split()]
    return [w for w in raw if len(w) >= 2 and w not in _VI_EN_STOPWORDS]


def _relevance_score(query: str, result: dict) -> float:
    """Fraction of query content words found in result title+body. 0.0 to 1.0."""
    words = _content_words(query)
    if not words:
        return 1.0
    title = str(result.get("title", ""))
    body = str(result.get("body") or result.get("snippet") or result.get("summary") or "")
    text = f"{title} {body}".lower()
    matches = sum(1 for w in words if w in text)
    return matches / len(words)


def _filter_by_relevance(query: str, results: list, *, threshold: float = 0.5) -> list:
    """Keep results whose content-word overlap with query is ≥ threshold.

    SOTA research agents (Perplexity, Gemini Deep Research) always post-filter
    retrieval — blindly forwarding search output to the LLM pollutes grounding.
    We require ≥50% of content words to appear in title+body by default.
    """
    if not results:
        return results
    scored = [(r, _relevance_score(query, r)) for r in results]
    kept = [r for (r, s) in scored if s >= threshold]
    if not kept:
        # Fallback: keep top-N by score even if all below threshold, so the
        # agent still has something to work from rather than an empty set.
        scored.sort(key=lambda pair: pair[1], reverse=True)
        kept = [r for (r, s) in scored[: min(3, len(scored))] if s > 0]
    return kept


# Finance-specific site list for price/market queries.
_FINANCE_SITES = [
    "tradingview.com", "investing.com", "bloomberg.com",
    "reuters.com", "cnbc.com", "ft.com",
    "vietstock.vn", "cafef.vn", "vneconomy.vn", "ndh.vn",
]

_FINANCE_KEYWORDS = (
    "giá dầu", "giá vàng", "giá xăng", "chứng khoán", "cổ phiếu", "tỷ giá",
    "lãi suất", "trái phiếu", "chỉ số", "vn-index", "vnindex",
    "bitcoin", "ethereum", "crypto", "tiền ảo",
    "brent", "wti", "gold", "oil price", "stock", "forex",
    "usd/vnd", "eur/vnd", "jpy/vnd",
)


def _is_finance_query(query: str) -> bool:
    q = (query or "").lower()
    return any(kw in q for kw in _FINANCE_KEYWORDS)


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
    SOTA filter: require ≥60% of content words to match; reject stopword-only
    matches (e.g. "hôm nay" matching every trending article).
    """
    try:
        import feedparser
    except ImportError:
        return []

    content_query_words = _content_words(query)
    if not content_query_words:
        return []

    results = []
    for source, url in _NEWS_RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:15]:
                title = (entry.get("title") or "")
                summary = (entry.get("summary") or "")
                text = f"{title} {summary}".lower()
                matches = sum(1 for w in content_query_words if w in text)
                if matches / max(len(content_query_words), 1) >= 0.6:
                    results.append({
                        "title": title,
                        "body": summary[:300],
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
    """Search the web for current information. Uses Serper.dev (Sprint 198) with DuckDuckGo fallback."""
    _CB_NAME = "web_search"
    if _cb_is_open(_CB_NAME):
        logger.warning("[WEB_SEARCH] Circuit breaker OPEN — skipping search")
        return "Tìm kiếm web tạm thời không khả dụng. Vui lòng thử lại sau."

    try:
        # Sprint 198: Try Serper first
        from app.engine.tools.serper_web_search import is_serper_available, _serper_search

        if is_serper_available():
            # SOTA finance routing: for price/market queries, restrict to
            # dedicated financial sites first (TradingView, Bloomberg, Reuters,
            # VietStock, CafeF) — generic Google returns noise for real-time prices.
            if _is_finance_query(query):
                site_filter = " OR ".join(f"site:{s}" for s in _FINANCE_SITES)
                finance_q = f"({site_filter}) {query}"
                finance_results = _serper_search(finance_q, max_results=5)
                finance_results = _filter_by_relevance(query, finance_results, threshold=0.4)
                if finance_results:
                    _cb_record_success(_CB_NAME)
                    logger.info("[WEB_SEARCH] Finance-site branch returned %d results", len(finance_results))
                    return _format_results(finance_results, "WEB_SEARCH")

            results = _serper_search(query, max_results=8)
            results = _filter_by_relevance(query, results, threshold=0.5)
            if results:
                _cb_record_success(_CB_NAME)
                return _format_results(results[:5], "WEB_SEARCH")
            # Serper returned empty — fall through to DuckDuckGo

        # DuckDuckGo fallback
        import concurrent.futures

        future = _executor.submit(_search_sync, query)
        results = future.result(timeout=WEB_SEARCH_TIMEOUT)
        results = _filter_by_relevance(query, results or [], threshold=0.5)

        if not results:
            return "Không tìm thấy kết quả trên web."

        _cb_record_success(_CB_NAME)
        return _format_results(results[:5], "WEB_SEARCH")

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

# Sprint 204: Neutral description — guidance is in system prompt, not tool metadata
@tool(description=(
    "Tìm kiếm TIN TỨC Việt Nam — tin tức, thời sự, sự kiện, bản tin, báo chí. "
    "Nguồn: VnExpress, Tuổi Trẻ, Thanh Niên, Dân Trí + RSS feeds."
))
def tool_search_news(query: str) -> str:
    """Search Vietnamese news using Serper.dev News (Sprint 198) + RSS feeds."""
    _CB_NAME = "search_news"
    if _cb_is_open(_CB_NAME):
        logger.warning("[NEWS_SEARCH] Circuit breaker OPEN — skipping search")
        return "Tìm kiếm tin tức tạm thời không khả dụng. Vui lòng thử lại sau."

    try:
        import concurrent.futures

        # Sprint 198: Try Serper news + RSS in parallel
        from app.engine.tools.serper_web_search import is_serper_available, _serper_news_search

        serper_results = []
        rss_results = []

        if is_serper_available():
            serper_results = _serper_news_search(query, max_results=5, gl="vn", hl="vi")
        else:
            # DuckDuckGo News fallback
            news_future = _executor.submit(_news_search_sync, query, 5)
            try:
                serper_results = news_future.result(timeout=WEB_SEARCH_TIMEOUT)
            except concurrent.futures.TimeoutError:
                logger.warning("[NEWS_SEARCH] DuckDuckGo news timeout")

        # RSS always runs (independent source)
        rss_future = _executor.submit(_rss_fetch_sync, query, 5)
        try:
            rss_results = rss_future.result(timeout=WEB_SEARCH_TIMEOUT)
        except concurrent.futures.TimeoutError:
            logger.warning("[NEWS_SEARCH] RSS fetch timeout")

        # Merge and deduplicate by URL
        all_results = []
        seen_urls = set()
        for r in serper_results + rss_results:
            url = r.get("href", r.get("url", r.get("link", "")))
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_results.append(r)

        # SOTA relevance gate: reject articles whose title+body doesn't
        # actually cover the query content words. Without this, RSS and Serper
        # feed trending noise (e.g. vnexpress trending articles for "giá dầu").
        all_results = _filter_by_relevance(query, all_results, threshold=0.5)

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

# Sprint 204: Neutral description — guidance is in system prompt, not tool metadata
@tool(description=(
    "Tìm kiếm VĂN BẢN PHÁP LUẬT Việt Nam — luật, nghị định, thông tư, quy định, mức phạt, bộ luật. "
    "Nguồn: Thư viện Pháp luật, Cổng TTĐT Chính phủ, Luật Việt Nam, Công báo."
))
def tool_search_legal(query: str) -> str:
    """Search Vietnamese legal documents using site-restricted Serper.dev (Sprint 198)."""
    _CB_NAME = "search_legal"
    if _cb_is_open(_CB_NAME):
        logger.warning("[LEGAL_SEARCH] Circuit breaker OPEN — skipping search")
        return "Tìm kiếm pháp luật tạm thời không khả dụng. Vui lòng thử lại sau."

    try:
        # Sprint 198: Serper supports site: natively via Google
        from app.engine.tools.serper_web_search import is_serper_available, _serper_search

        if is_serper_available():
            site_filter = " OR ".join(f"site:{s}" for s in _LEGAL_SITES)
            restricted_query = f"({site_filter}) {query}"
            results = _serper_search(restricted_query, max_results=7, gl="vn", hl="vi")
            if results:
                _cb_record_success(_CB_NAME)
                return _format_results(results, "LEGAL_SEARCH")
            # Serper returned empty — try without site restriction
            results = _serper_search(query, max_results=7, gl="vn", hl="vi")
            if results:
                _cb_record_success(_CB_NAME)
                return _format_results(results, "LEGAL_SEARCH")

        # DuckDuckGo fallback
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
    """Search international maritime information using site-restricted Serper.dev (Sprint 198)."""
    _CB_NAME = "search_maritime"
    if _cb_is_open(_CB_NAME):
        logger.warning("[MARITIME_SEARCH] Circuit breaker OPEN — skipping search")
        return "Tìm kiếm hàng hải tạm thời không khả dụng. Vui lòng thử lại sau."

    try:
        # Sprint 198: Serper supports site: natively via Google
        from app.engine.tools.serper_web_search import is_serper_available, _serper_search

        if is_serper_available():
            site_filter = " OR ".join(f"site:{s}" for s in _MARITIME_SITES)
            restricted_query = f"({site_filter}) {query}"
            results = _serper_search(restricted_query, max_results=7, gl="vn", hl="vi")
            if results:
                _cb_record_success(_CB_NAME)
                return _format_results(results, "MARITIME_SEARCH")
            # Serper returned empty — try without site restriction
            results = _serper_search(query, max_results=7, gl="vn", hl="vi")
            if results:
                _cb_record_success(_CB_NAME)
                return _format_results(results, "MARITIME_SEARCH")

        # DuckDuckGo fallback
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
        (tool_web_search, "Web search via Serper.dev (DuckDuckGo fallback)"),
        (tool_search_news, "Vietnamese news search (Serper News + RSS)"),
        (tool_search_legal, "Vietnamese legal document search (site-restricted Serper)"),
        (tool_search_maritime, "Maritime international search (site-restricted Serper)"),
    ]:
        registry.register(
            tool_fn,
            category=ToolCategory.UTILITY,
            access=ToolAccess.READ,
            description=desc,
        )

    logger.info("Web search tools registered: web_search, search_news, search_legal, search_maritime")
