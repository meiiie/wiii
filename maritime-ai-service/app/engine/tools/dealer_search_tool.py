"""
Dealer Search Tool — Sprint 196: "Thợ Săn Chuyên Nghiệp"

Discovers dealers, distributors, and authorized resellers for niche/B2B products
using Serper.dev (Sprint 198) + Jina Reader for page content extraction.
Falls back to DuckDuckGo if SERPER_API_KEY is not configured.

Gate: enable_dealer_search
"""

import json
import logging
from typing import List, Optional

import httpx
from app.engine.tools.native_tool import StructuredTool

logger = logging.getLogger(__name__)

# Jina Reader endpoint (free, no API key needed)
_JINA_READER_URL = "https://r.jina.ai/"
_JINA_TIMEOUT = 25
_JINA_MAX_CHARS = 20000
_JINA_MAX_RETRIES = 1
_DUCKDUCKGO_MAX_RESULTS = 10


def _extract_contacts_from_text(text: str) -> dict:
    """Extract contact information from markdown text.

    Sprint 198b: Delegates to contact_extraction_tool._extract_all_contacts()
    for unified extraction (Viber, Facebook, intl phones, structural address).
    Wraps with dealer-specific limits for backward compatibility.
    """
    from app.engine.tools.contact_extraction_tool import _extract_all_contacts

    contacts = _extract_all_contacts(text)
    # Dealer-specific limits (backward compat)
    contacts["phones"] = contacts["phones"][:5]
    contacts["emails"] = contacts["emails"][:3]
    contacts["zalo"] = contacts["zalo"][:3]
    return contacts


def _fetch_page_markdown(url: str) -> str:
    """Fetch a page via Jina Reader and return markdown content.

    Sprint 198b: 25s timeout, 20k truncation, 1 retry on timeout/5xx.
    """
    for attempt in range(_JINA_MAX_RETRIES + 1):
        try:
            resp = httpx.get(
                f"{_JINA_READER_URL}{url}",
                timeout=_JINA_TIMEOUT,
                headers={"Accept": "text/markdown"},
                follow_redirects=True,
            )
            if resp.status_code == 200:
                return resp.text[:_JINA_MAX_CHARS]
            if resp.status_code >= 500 and attempt < _JINA_MAX_RETRIES:
                logger.debug("[DEALER_SEARCH] Jina Reader %d for %s, retrying", resp.status_code, url)
                continue
            logger.debug("[DEALER_SEARCH] Jina Reader returned %d for %s", resp.status_code, url)
            return ""
        except httpx.TimeoutException:
            if attempt < _JINA_MAX_RETRIES:
                logger.debug("[DEALER_SEARCH] Jina Reader timeout for %s, retrying", url)
                continue
            logger.debug("[DEALER_SEARCH] Jina Reader timeout for %s after %d attempts", url, attempt + 1)
            return ""
        except Exception as e:
            logger.debug("[DEALER_SEARCH] Jina Reader failed for %s: %s", url, e)
            return ""
    return ""


def _search_dealers_ddgs(queries: list) -> list:
    """DuckDuckGo fallback for dealer search (used when Serper unavailable)."""
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        return []

    all_results = []
    seen_urls = set()
    for query in queries:
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, region="vn-vi", max_results=_DUCKDUCKGO_MAX_RESULTS))
                for r in results:
                    url = r.get("href", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_results.append({
                            "url": url,
                            "title": r.get("title", ""),
                            "snippet": r.get("body", ""),
                        })
        except Exception as e:
            logger.warning("[DEALER_SEARCH] DuckDuckGo query failed: %s", e)
            continue
    return all_results


def _search_dealers(
    product_name: str,
    location: str = "Vietnam",
    search_queries: Optional[List[str]] = None,
) -> dict:
    """Search for dealers/distributors using Serper.dev + Jina Reader.

    Sprint 198: Uses Serper.dev (Google search API) for reliable Vietnamese search.
    Falls back to DuckDuckGo if Serper is unavailable.

    Args:
        product_name: Product name to search for dealers
        location: Market location (default: Vietnam)
        search_queries: Optional pre-optimized queries from Query Planner (Sprint 197).
                       If provided, uses these instead of hardcoded queries.

    Returns:
        Dict with dealers list, count, and query used.
    """
    # Sprint 197: Use planner-optimized queries if available
    if search_queries:
        queries = search_queries
    else:
        # Fallback: hardcoded queries (Sprint 196 original behavior)
        queries = [
            f'{product_name} đại lý phân phối Việt Nam',
            f'{product_name} mua ở đâu giá rẻ',
            f'{product_name} nhà cung cấp chính hãng',
            f'{product_name} price buy Vietnam dealer',
        ]
        if location.lower() != "vietnam":
            queries.append(f'{product_name} dealer distributor {location}')

    all_results = []
    seen_urls = set()

    # Sprint 198: Try Serper first, fall back to DuckDuckGo
    from app.engine.tools.serper_web_search import is_serper_available, _serper_search

    if is_serper_available():
        for query in queries:
            try:
                results = _serper_search(query, max_results=_DUCKDUCKGO_MAX_RESULTS, gl="vn", hl="vi")
                for r in results:
                    url = r.get("href", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_results.append({
                            "url": url,
                            "title": r.get("title", ""),
                            "snippet": r.get("body", ""),
                        })
            except Exception as e:
                logger.warning("[DEALER_SEARCH] Serper query failed: %s", e)
                continue
    else:
        # DuckDuckGo fallback
        all_results = _search_dealers_ddgs(queries)

    if not all_results:
        return {"dealers": [], "count": 0, "query": queries[0]}

    # Fetch top pages via Jina Reader and extract contacts
    dealers = []
    for result in all_results[:8]:  # limit to 8 pages for speed
        url = result["url"]
        markdown = _fetch_page_markdown(url)
        contacts = _extract_contacts_from_text(markdown or result.get("snippet", ""))

        # Only include if we found at least one contact method
        # Sprint 198b: Include new fields from consolidated extraction
        has_contact = (
            contacts["phones"]
            or contacts.get("international_phones")
            or contacts["emails"]
            or contacts["zalo"]
            or contacts.get("viber")
            or contacts.get("facebook")
            or contacts["address"]
        )

        dealer = {
            "name": result["title"],
            "url": url,
            "snippet": result["snippet"][:200],
            "contacts": contacts,
            "has_contact_info": has_contact,
        }
        dealers.append(dealer)

    # Sort: dealers with contacts first
    dealers.sort(key=lambda d: (not d["has_contact_info"], d["name"]))

    return {
        "dealers": dealers,
        "count": len(dealers),
        "query": queries[0],
        "total_pages_scanned": len(all_results),
    }


def tool_dealer_search_fn(
    product_name: str,
    location: str = "Vietnam",
    search_queries: str = "",
) -> str:
    """Search for dealers and distributors of a product in Vietnam.

    Finds authorized dealers, distributors, and resellers with contact info
    (phone, Zalo, email, address). Best for niche/B2B/industrial products.

    Args:
        product_name: Product name (e.g., "Zebra ZXP Series 7 printhead")
        location: Market to search (default: "Vietnam")
        search_queries: Optional JSON array of pre-optimized search queries from Query Planner.
                       Example: '["Zebra ZXP7 printhead dealer Vietnam", "Zebra ZXP7 dai ly phan phoi"]'
                       If provided, uses these instead of auto-generated queries.

    Returns:
        JSON with dealer list including contact information.
    """
    from app.core.config import get_settings
    settings = get_settings()
    if not settings.enable_dealer_search:
        return json.dumps(
            {"error": "Dealer search is not enabled", "dealers": [], "count": 0},
            ensure_ascii=False,
        )

    # Sprint 197: Parse planned queries
    planned_queries = None
    if search_queries:
        try:
            parsed = json.loads(search_queries)
            if isinstance(parsed, list) and parsed:
                planned_queries = [str(q) for q in parsed]
        except (json.JSONDecodeError, TypeError):
            logger.debug("[DEALER_SEARCH] Invalid search_queries JSON, using default")

    try:
        result = _search_dealers(product_name, location, search_queries=planned_queries)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.error("[DEALER_SEARCH] Failed: %s", e)
        return json.dumps(
            {"error": f"Dealer search failed: {str(e)[:200]}", "dealers": [], "count": 0},
            ensure_ascii=False,
        )


def get_dealer_search_tool() -> StructuredTool:
    """Create and return the dealer search StructuredTool."""
    return StructuredTool.from_function(
        func=tool_dealer_search_fn,
        name="tool_dealer_search",
        description=(
            "Tìm đại lý, nhà phân phối, đại diện chính hãng của sản phẩm tại Việt Nam. "
            "Trả về danh sách dealer kèm SĐT, Zalo, email, địa chỉ. "
            "Rất hiệu quả cho sản phẩm công nghiệp, B2B, thiết bị chuyên dụng, linh kiện. "
            "Tham số search_queries (JSON array) cho phép truyền truy vấn tối ưu từ Query Planner."
        ),
    )
