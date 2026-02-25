"""
Shared Serper.dev Web Search Utility — Sprint 198: "Nâng Cấp Serper"

Provides _serper_search() and _serper_news_search() functions used by:
- dealer_search_tool.py (B2B dealer discovery, gl=vn)
- international_search_tool.py (global pricing, gl=us)
- web_search_tools.py (general web/news/legal/maritime search)

Replaces DuckDuckGo which fails on Vietnamese diacritics, site: operators,
and gets IP-banned. Serper.dev uses Google's index — reliable and Vietnamese-aware.

Gate: enable_serper_web_search (default True, requires SERPER_API_KEY)
"""

import logging
from typing import List, Optional

import httpx

logger = logging.getLogger(__name__)

_SERPER_BASE_URL = "https://google.serper.dev"
_SERPER_TIMEOUT = 10  # seconds


def _serper_search(
    query: str,
    max_results: int = 10,
    gl: str = "vn",
    hl: str = "vi",
    search_type: str = "search",
    include_price_metadata: bool = False,
) -> List[dict]:
    """Search via Serper.dev and return normalized results.

    Args:
        query: Search query (supports site: operator natively)
        max_results: Maximum results to return
        gl: Google country code (vn=Vietnam, us=USA, gb=UK, etc.)
        hl: Language code (vi=Vietnamese, en=English)
        search_type: "search" for web, "news" for news

    Returns:
        List of dicts with keys: title, body, href, date, source
        (compatible with DuckDuckGo result format for _format_results())
    """
    from app.core.config import get_settings
    settings = get_settings()

    api_key = settings.serper_api_key
    if not api_key:
        logger.warning("[SERPER_WEB] No SERPER_API_KEY configured")
        return []

    endpoint = f"{_SERPER_BASE_URL}/{search_type}"
    payload = {
        "q": query,
        "gl": gl,
        "hl": hl,
        "num": min(max_results, 100),
    }
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }

    try:
        resp = httpx.post(
            endpoint,
            headers=headers,
            json=payload,
            timeout=_SERPER_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except httpx.TimeoutException:
        logger.warning("[SERPER_WEB] Timeout for query: %s", query[:80])
        return []
    except httpx.HTTPStatusError as e:
        logger.warning("[SERPER_WEB] HTTP %d for query: %s", e.response.status_code, query[:80])
        return []
    except Exception as e:
        logger.warning("[SERPER_WEB] Failed: %s", e)
        return []

    # Normalize results to DuckDuckGo-compatible format
    results = []

    if search_type == "news":
        items = data.get("news", [])
    else:
        items = data.get("organic", [])

    for item in items[:max_results]:
        result = {
            "title": item.get("title", ""),
            "body": item.get("snippet", ""),
            "href": item.get("link", ""),
        }
        # News items may have extra fields
        if item.get("date"):
            result["date"] = item["date"]
        if item.get("source"):
            result["source"] = item["source"]
        # Sprint 198b: Pass Serper price metadata for international search
        if include_price_metadata:
            if item.get("price"):
                result["extracted_price"] = item["price"]
            if item.get("priceRange"):
                result["price_range"] = item["priceRange"]
        results.append(result)

    logger.info("[SERPER_WEB] %s query '%s' (gl=%s) → %d results",
                search_type, query[:60], gl, len(results))
    return results


def _serper_news_search(
    query: str,
    max_results: int = 5,
    gl: str = "vn",
    hl: str = "vi",
) -> List[dict]:
    """Convenience wrapper for Serper.dev news search.

    Returns results in same format as _serper_search() but from /news endpoint.
    """
    return _serper_search(
        query=query,
        max_results=max_results,
        gl=gl,
        hl=hl,
        search_type="news",
    )


def is_serper_available() -> bool:
    """Check if Serper.dev is configured and enabled."""
    try:
        from app.core.config import get_settings
        settings = get_settings()
        return bool(
            getattr(settings, 'enable_serper_web_search', True)
            and settings.serper_api_key
        )
    except Exception:
        return False
