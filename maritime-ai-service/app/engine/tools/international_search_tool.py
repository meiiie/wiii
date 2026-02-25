"""
International Search Tool — Sprint 196: "Thợ Săn Chuyên Nghiệp"

Searches for products on international markets using Serper.dev (Sprint 198)
+ Jina Reader for page content extraction. Converts prices to VND.
Falls back to DuckDuckGo if SERPER_API_KEY is not configured.

Gate: enable_international_search
"""

import json
import logging
import re
from typing import Optional

import httpx
from langchain_core.tools import StructuredTool

logger = logging.getLogger(__name__)

# Jina Reader endpoint
_JINA_READER_URL = "https://r.jina.ai/"
_JINA_TIMEOUT = 25
_JINA_MAX_CHARS = 20000
_JINA_MAX_RETRIES = 1
_DUCKDUCKGO_MAX_RESULTS = 8

# Sprint 198b: 12 currencies — to-USD conversion factors
_EXCHANGE_RATES = {
    "USD": 1.0,
    "EUR": 1.08,    # EUR → USD
    "GBP": 1.27,    # GBP → USD
    "CNY": 0.14,    # Chinese Yuan
    "JPY": 0.0067,  # Japanese Yen
    "KRW": 0.00075, # Korean Won
    "SGD": 0.74,    # Singapore Dollar
    "THB": 0.028,   # Thai Baht
    "AED": 0.27,    # UAE Dirham
    "CAD": 0.74,    # Canadian Dollar
    "AUD": 0.65,    # Australian Dollar
    "TWD": 0.031,   # Taiwan Dollar
}

# Sprint 198b: Symbol-to-currency mapping (order matters: specific before generic)
_SYMBOL_PATTERNS = [
    (re.compile(r'S\$\s?([\d,.\s]+)'), "SGD"),        # S$
    (re.compile(r'C\$\s?([\d,.\s]+)'), "CAD"),        # C$
    (re.compile(r'A\$\s?([\d,.\s]+)'), "AUD"),        # A$
    (re.compile(r'NT\$\s?([\d,.\s]+)'), "TWD"),       # NT$
    (re.compile(r'\$\s?([\d,.\s]+)'), "USD"),          # $ (generic, last)
    (re.compile(r'€\s?([\d,.\s]+)'), "EUR"),           # €
    (re.compile(r'£\s?([\d,.\s]+)'), "GBP"),           # £
    (re.compile(r'¥\s?([\d,.\s]+)'), "CNY"),           # ¥ (default to CNY)
    (re.compile(r'₩\s?([\d,.\s]+)'), "KRW"),           # ₩
    (re.compile(r'฿\s?([\d,.\s]+)'), "THB"),           # ฿
]

# Sprint 198b: Code-based price regex (e.g. "USD 450.00", "AED 5,820")
_CODE_PRICE_REGEX = re.compile(
    r'(?:USD|EUR|GBP|CNY|JPY|KRW|SGD|THB|AED|CAD|AUD|TWD)\s?([\d,.\s]+)',
    re.IGNORECASE,
)

# Backward compat: keep _DEFAULT_RATES as alias
_DEFAULT_RATES = _EXCHANGE_RATES


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
                logger.debug("[INTL_SEARCH] Jina Reader %d for %s, retrying", resp.status_code, url)
                continue
            return ""
        except httpx.TimeoutException:
            if attempt < _JINA_MAX_RETRIES:
                logger.debug("[INTL_SEARCH] Jina Reader timeout for %s, retrying", url)
                continue
            logger.debug("[INTL_SEARCH] Jina Reader timeout for %s after %d attempts", url, attempt + 1)
            return ""
        except Exception as e:
            logger.debug("[INTL_SEARCH] Jina Reader failed for %s: %s", url, e)
            return ""
    return ""


def _parse_price_amount(raw: str) -> Optional[float]:
    """Parse a price string handling European (1.234,50) and Anglo (1,234.50) formats.

    Sprint 198b: Last-separator heuristic to fix EUR/GBP decimal handling.
    - Comma AFTER dot → European: 1.234,50 → 1234.50
    - Dot AFTER comma → Anglo: 1,234.50 → 1234.50
    - Only comma with ≤2 digits after → decimal: 1,50 → 1.50
    - Only dot → check if decimal or thousands
    """
    if not raw:
        return None
    # Remove spaces and strip trailing non-numeric chars (sentence dots, etc.)
    s = raw.strip().replace(' ', '')
    s = s.rstrip('.,;:!?)')
    if not s:
        return None

    has_dot = '.' in s
    has_comma = ',' in s

    if has_dot and has_comma:
        last_dot = s.rfind('.')
        last_comma = s.rfind(',')
        if last_comma > last_dot:
            # European: 1.234,50 — dot is thousands, comma is decimal
            s = s.replace('.', '').replace(',', '.')
        else:
            # Anglo: 1,234.50 — comma is thousands, dot is decimal
            s = s.replace(',', '')
    elif has_comma and not has_dot:
        # Check if comma is decimal separator: "1,50" (≤2 digits after last comma)
        parts = s.rsplit(',', 1)
        if len(parts) == 2 and len(parts[1]) <= 2:
            s = s.replace(',', '.')
        else:
            # Thousands separator: "1,234" or "1,234,567"
            s = s.replace(',', '')
    # Only dot: already correct for float() (both "1.50" and "1234.50" work)

    try:
        val = float(s)
        return val if val > 0 else None
    except ValueError:
        return None


def _get_exchange_rates() -> dict:
    """Get exchange rates, merging config overrides over defaults."""
    try:
        from app.core.config import get_settings
        settings = get_settings()
        overrides = getattr(settings, 'exchange_rate_overrides', {})
        if overrides:
            merged = dict(_EXCHANGE_RATES)
            merged.update({k.upper(): v for k, v in overrides.items()})
            return merged
    except Exception:
        pass
    return _EXCHANGE_RATES


def _extract_price_from_text(
    text: str,
    target_currency: str = "USD",
    *,
    serper_price: object = None,
    serper_price_range: object = None,
) -> Optional[float]:
    """Extract the first price from text matching the target currency.

    Sprint 198b: Priority chain:
    1. serper_price (float/str from Serper metadata) — most reliable
    2. serper_price_range (string like "$100-$200") — take midpoint
    3. Symbol regex matching target_currency
    4. Code regex (e.g. "USD 450.00")
    """
    # 1. Serper price metadata (highest priority)
    if serper_price is not None:
        try:
            val = float(str(serper_price).replace(',', '').replace('$', '').replace('€', '').replace('£', ''))
            if val > 0:
                return val
        except (ValueError, TypeError):
            pass

    # 2. Serper price range — take first value
    if serper_price_range is not None:
        range_str = str(serper_price_range)
        # Extract first number from range like "$100 - $200" or "100-200"
        nums = re.findall(r'[\d,]+(?:\.\d+)?', range_str)
        if nums:
            parsed = _parse_price_amount(nums[0])
            if parsed and parsed > 0:
                return parsed

    if not text:
        return None

    target = target_currency.upper()

    # 3. Symbol regex — find matching currency symbol
    for pattern, currency in _SYMBOL_PATTERNS:
        if currency == target:
            match = pattern.search(text)
            if match:
                parsed = _parse_price_amount(match.group(1))
                if parsed:
                    return parsed

    # 4. Code regex (e.g. "USD 450.00", "AED 5,820")
    code_pattern = re.compile(
        rf'{re.escape(target)}\s?([\d,.\s]+)',
        re.IGNORECASE,
    )
    code_match = code_pattern.search(text)
    if code_match:
        parsed = _parse_price_amount(code_match.group(1))
        if parsed:
            return parsed

    return None


def _convert_to_vnd(price: float, currency: str, usd_vnd_rate: float) -> float:
    """Convert a foreign currency price to VND."""
    rates = _get_exchange_rates()
    # First convert to USD
    to_usd_rate = rates.get(currency.upper(), 1.0)
    price_usd = price * to_usd_rate
    # Then convert USD to VND
    return price_usd * usd_vnd_rate


def _search_international_ddgs(queries: list) -> list:
    """DuckDuckGo fallback for international search (used when Serper unavailable)."""
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        return []

    all_results = []
    seen_urls = set()
    for query in queries:
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, region="wt-wt", max_results=_DUCKDUCKGO_MAX_RESULTS))
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
            logger.warning("[INTL_SEARCH] DuckDuckGo query failed: %s", e)
            continue
    return all_results


def _search_international(
    product_name: str,
    currency: str = "USD",
    search_queries: Optional[list] = None,
) -> dict:
    """Search international markets for product pricing.

    Sprint 198: Uses Serper.dev with gl=us, hl=en for international pricing.
    Falls back to DuckDuckGo if Serper is unavailable.

    Args:
        product_name: Product name to search
        currency: Primary currency to look for (USD, EUR, GBP)
        search_queries: Optional pre-optimized queries from Query Planner (Sprint 197)

    Returns:
        Dict with results list, count, and exchange rate.
    """
    from app.core.config import get_settings
    settings = get_settings()
    usd_vnd_rate = settings.usd_vnd_exchange_rate

    # Sprint 197: Use planner-optimized queries if available
    if search_queries:
        queries = search_queries
    else:
        # Fallback: hardcoded queries (Sprint 196, quotes removed Sprint 198b for broader results)
        queries = [
            f'{product_name} price buy {currency}',
            f'{product_name} wholesale supplier price',
        ]

    all_results = []
    seen_urls = set()

    # Sprint 198: Try Serper first (gl=us for international pricing), fall back to DuckDuckGo
    # Sprint 198b: include_price_metadata=True to get Serper price data
    from app.engine.tools.serper_web_search import is_serper_available, _serper_search

    if is_serper_available():
        for query in queries:
            try:
                results = _serper_search(
                    query, max_results=_DUCKDUCKGO_MAX_RESULTS,
                    gl="us", hl="en", include_price_metadata=True,
                )
                for r in results:
                    url = r.get("href", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_results.append({
                            "url": url,
                            "title": r.get("title", ""),
                            "snippet": r.get("body", ""),
                            "extracted_price": r.get("extracted_price"),
                            "price_range": r.get("price_range"),
                        })
            except Exception as e:
                logger.warning("[INTL_SEARCH] Serper query failed: %s", e)
                continue
    else:
        # DuckDuckGo fallback
        all_results = _search_international_ddgs(queries)

    if not all_results:
        return {
            "results": [],
            "count": 0,
            "exchange_rate": usd_vnd_rate,
            "query": queries[0],
        }

    # Sprint 198b: Try Serper price metadata BEFORE Jina fetch
    enriched_results = []
    for result in all_results[:5]:  # top 5 for speed
        url = result["url"]
        snippet = result.get("snippet", "")

        # Try Serper metadata first (no HTTP call needed)
        price_foreign = _extract_price_from_text(
            snippet, currency,
            serper_price=result.get("extracted_price"),
            serper_price_range=result.get("price_range"),
        )

        # Only fetch via Jina if no price from Serper metadata + snippet
        if price_foreign is None:
            markdown = _fetch_page_markdown(url)
            if markdown:
                price_foreign = _extract_price_from_text(markdown, currency)

        item = {
            "title": result["title"],
            "url": url,
            "snippet": snippet[:200],
            "price_foreign": None,
            "price_currency": currency,
            "price_vnd": None,
        }

        if price_foreign and price_foreign > 0:
            item["price_foreign"] = price_foreign
            item["price_vnd"] = round(_convert_to_vnd(price_foreign, currency, usd_vnd_rate))

        enriched_results.append(item)

    # Sort by VND price (items with price first)
    enriched_results.sort(
        key=lambda x: x["price_vnd"] if x["price_vnd"] else float('inf')
    )

    return {
        "results": enriched_results,
        "count": len(enriched_results),
        "exchange_rate": usd_vnd_rate,
        "currency": currency,
        "query": queries[0],
    }


def tool_international_search_fn(
    product_name: str,
    currency: str = "USD",
    search_queries: str = "",
) -> str:
    """Search international markets for product pricing and availability.

    Finds global suppliers, distributors, and pricing for comparison
    with Vietnamese domestic prices. Converts to VND automatically.

    Args:
        product_name: Product name in English (e.g., "Zebra ZXP Series 7 printhead")
        currency: Price currency to look for (USD, EUR, GBP). Default: USD
        search_queries: Optional JSON array of pre-optimized search queries from Query Planner.
                       Example: '["Zebra ZXP7 printhead price wholesale", "ZXP Series 7 supplier"]'
                       If provided, uses these instead of auto-generated queries.

    Returns:
        JSON with international results including VND-converted prices.
    """
    from app.core.config import get_settings
    settings = get_settings()
    if not settings.enable_international_search:
        return json.dumps(
            {"error": "International search is not enabled", "results": [], "count": 0},
            ensure_ascii=False,
        )

    currency = currency.upper()
    if currency not in _EXCHANGE_RATES:
        currency = "USD"

    # Sprint 197: Parse planned queries
    planned_queries = None
    if search_queries:
        try:
            parsed = json.loads(search_queries)
            if isinstance(parsed, list) and parsed:
                planned_queries = [str(q) for q in parsed]
        except (json.JSONDecodeError, TypeError):
            logger.debug("[INTL_SEARCH] Invalid search_queries JSON, using default")

    try:
        result = _search_international(product_name, currency, search_queries=planned_queries)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.error("[INTL_SEARCH] Failed: %s", e)
        return json.dumps(
            {"error": f"International search failed: {str(e)[:200]}", "results": [], "count": 0},
            ensure_ascii=False,
        )


def get_international_search_tool() -> StructuredTool:
    """Create and return the international search StructuredTool."""
    return StructuredTool.from_function(
        func=tool_international_search_fn,
        name="tool_international_search",
        description=(
            "Tìm giá sản phẩm trên thị trường QUỐC TẾ (Mỹ, EU, Trung Quốc...) "
            "và tự động chuyển đổi sang VNĐ. Dùng khi cần so sánh giá nội địa vs quốc tế, "
            "hoặc tìm nguồn nhập khẩu cho sản phẩm chuyên dụng, linh kiện, thiết bị công nghiệp. "
            "Tham số search_queries (JSON array) cho phép truyền truy vấn tối ưu từ Query Planner."
        ),
    )
