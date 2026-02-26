"""
International Search Tool — Sprint 196→199: "Cầu Nối Trung-Việt"

Searches for products on international markets using Serper.dev (Sprint 198)
+ Jina Reader for page content extraction. Converts prices to VND.
Falls back to DuckDuckGo if SERPER_API_KEY is not configured.

Sprint 199: Multi-region search (US + China + AliExpress) with
URL-based currency auto-detection, Chinese price patterns, and
configurable region filtering.

Gate: enable_international_search
"""

import json
import logging
import re
from typing import List, Optional
from urllib.parse import urlparse

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
    # Sprint 199: Chinese price patterns
    (re.compile(r'([\d,.]+)\s*元'), "CNY"),             # 12.50元 (yuan suffix)
    (re.compile(r'RMB\s?([\d,.]+)'), "CNY"),            # RMB 12.50
]

# Sprint 198b: Code-based price regex (e.g. "USD 450.00", "AED 5,820")
# Sprint 199: Added RMB code
_CODE_PRICE_REGEX = re.compile(
    r'(?:USD|EUR|GBP|CNY|JPY|KRW|SGD|THB|AED|CAD|AUD|TWD|RMB)\s?([\d,.\s]+)',
    re.IGNORECASE,
)

# Backward compat: keep _DEFAULT_RATES as alias
_DEFAULT_RATES = _EXCHANGE_RATES

# =============================================================================
# Sprint 199: Multi-Region Search Configuration
# =============================================================================

_SEARCH_REGIONS = [
    {
        "id": "global",
        "label": "Global (US/EU)",
        "gl": "us",
        "hl": "en",
        "default_currency": "USD",
        "queries": [
            "{product} price buy wholesale",
            "{product} supplier price",
        ],
    },
    {
        "id": "china_1688",
        "label": "1688.com (China B2B)",
        "gl": "cn",
        "hl": "zh",
        "default_currency": "CNY",
        "queries": ["site:1688.com {product}"],
    },
    {
        "id": "china_taobao",
        "label": "Taobao/Tmall",
        "gl": "cn",
        "hl": "zh",
        "default_currency": "CNY",
        "queries": ["site:taobao.com {product}", "site:tmall.com {product}"],
    },
    {
        "id": "aliexpress",
        "label": "AliExpress",
        "gl": "us",
        "hl": "en",
        "default_currency": "USD",
        "queries": ["site:aliexpress.com {product} price"],
    },
]

# Sprint 199: URL-based currency auto-detection
_DOMAIN_CURRENCY_MAP = {
    "1688.com": "CNY",
    "taobao.com": "CNY",
    "tmall.com": "CNY",
    "jd.com": "CNY",
    "aliexpress.com": "USD",
    "amazon.com": "USD",
    "amazon.co.uk": "GBP",
    "amazon.de": "EUR",
    "amazon.co.jp": "JPY",
    "ebay.com": "USD",
    "rakuten.co.jp": "JPY",
    "coupang.com": "KRW",
}


def _detect_currency_from_url(url: str) -> Optional[str]:
    """Detect likely currency based on the URL's domain.

    Sprint 199: Maps known e-commerce domains to their native currency.

    Returns:
        Currency code (e.g. "CNY") or None if domain not recognized.
    """
    if not url:
        return None
    try:
        hostname = urlparse(url).hostname or ""
        hostname = hostname.lower()
        # Try exact match first, then suffix match for subdomains
        for domain, currency in _DOMAIN_CURRENCY_MAP.items():
            if hostname == domain or hostname.endswith("." + domain):
                return currency
    except Exception:
        pass
    return None


def _get_active_regions(regions_filter: str = "") -> list:
    """Get active search regions based on filter and config.

    Args:
        regions_filter: Comma-separated region IDs (e.g. "global,china_1688").
                       Empty string = all regions based on config.

    Returns:
        List of region dicts from _SEARCH_REGIONS.
    """
    try:
        from app.core.config import get_settings
        settings = get_settings()
        chinese_enabled = getattr(settings, 'enable_chinese_platform_search', True)
    except Exception:
        chinese_enabled = True

    if regions_filter:
        requested = {r.strip() for r in regions_filter.split(",") if r.strip()}
        return [r for r in _SEARCH_REGIONS if r["id"] in requested]

    if not chinese_enabled:
        return [r for r in _SEARCH_REGIONS if r["id"] == "global"]

    return list(_SEARCH_REGIONS)


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

    # 4. Code regex (e.g. "USD 450.00", "AED 5,820", "RMB 12.50")
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


def _detect_result_currency(
    url: str,
    region: dict,
    user_currency: str,
) -> str:
    """Determine the best currency to use for price extraction.

    Sprint 199: 4-step fallback chain:
    1. URL-based detection (e.g. 1688.com → CNY)
    2. Region default currency (e.g. china_1688 → CNY)
    3. User-specified currency
    4. USD as ultimate fallback
    """
    # 1. URL-based auto-detection
    url_currency = _detect_currency_from_url(url)
    if url_currency:
        return url_currency
    # 2. Region default
    region_currency = region.get("default_currency")
    if region_currency:
        return region_currency
    # 3. User-specified
    if user_currency:
        return user_currency.upper()
    # 4. Ultimate fallback
    return "USD"


def _extract_source_platform(url: str) -> str:
    """Extract a human-readable platform name from URL.

    Sprint 199: Used for source_platform field in results.
    """
    if not url:
        return "unknown"
    try:
        hostname = urlparse(url).hostname or ""
        hostname = hostname.lower()
        # Known platform mappings
        platform_map = {
            "1688.com": "1688.com",
            "taobao.com": "Taobao",
            "tmall.com": "Tmall",
            "aliexpress.com": "AliExpress",
            "amazon.com": "Amazon US",
            "amazon.co.uk": "Amazon UK",
            "amazon.de": "Amazon DE",
            "amazon.co.jp": "Amazon JP",
            "ebay.com": "eBay",
            "jd.com": "JD.com",
            "rakuten.co.jp": "Rakuten",
        }
        for domain, name in platform_map.items():
            if hostname == domain or hostname.endswith("." + domain):
                return name
        # Fallback: use domain without www
        if hostname.startswith("www."):
            hostname = hostname[4:]
        return hostname
    except Exception:
        return "unknown"


def _region_label(region: dict) -> str:
    """Get a human-readable label for a search region."""
    return region.get("label", region.get("id", "unknown"))


def _search_international(
    product_name: str,
    currency: str = "USD",
    search_queries: Optional[list] = None,
    regions: str = "",
) -> dict:
    """Search international markets for product pricing.

    Sprint 198: Uses Serper.dev with gl=us, hl=en for international pricing.
    Sprint 199: Multi-region search (global + China + AliExpress).
    Falls back to DuckDuckGo if Serper is unavailable (global region only).

    Args:
        product_name: Product name to search
        currency: Primary currency to look for (USD, EUR, GBP, CNY)
        search_queries: Optional pre-optimized queries from Query Planner (Sprint 197).
                       When provided, used for global region only.
        regions: Optional comma-separated region filter (e.g. "global,china_1688")

    Returns:
        Dict with results list, count, exchange rate, and regions_searched.
    """
    from app.core.config import get_settings
    settings = get_settings()
    usd_vnd_rate = settings.usd_vnd_exchange_rate

    active_regions = _get_active_regions(regions)

    all_results: List[dict] = []
    seen_urls: set = set()
    regions_searched: List[str] = []

    from app.engine.tools.serper_web_search import is_serper_available, _serper_search

    serper_available = is_serper_available()

    for region in active_regions:
        region_id = region["id"]
        regions_searched.append(region_id)

        # Sprint 197: Use planner-optimized queries for global region if available
        if region_id == "global" and search_queries:
            queries = search_queries
        else:
            queries = [q.format(product=product_name) for q in region["queries"]]

        if serper_available:
            for query in queries:
                try:
                    results = _serper_search(
                        query, max_results=_DUCKDUCKGO_MAX_RESULTS,
                        gl=region["gl"], hl=region["hl"],
                        include_price_metadata=True,
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
                                "_region": region,
                            })
                except Exception as e:
                    logger.warning("[INTL_SEARCH] Serper query failed for %s: %s", region_id, e)
                    continue
        elif region_id == "global":
            # DuckDuckGo fallback (only for global — doesn't support gl=cn)
            ddgs_results = _search_international_ddgs(queries)
            for r in ddgs_results:
                r["_region"] = region
            all_results.extend(ddgs_results)

    if not all_results:
        return {
            "results": [],
            "count": 0,
            "exchange_rate": usd_vnd_rate,
            "currency": currency,
            "query": product_name,
            "regions_searched": regions_searched,
        }

    # Sprint 199: Fair quota per region — ensure Chinese results aren't eclipsed by global
    if len(active_regions) > 1:
        per_region = max(3, 12 // len(active_regions))
        region_buckets: dict = {}
        for result in all_results:
            rid = result.get("_region", {}).get("id", "global")
            region_buckets.setdefault(rid, []).append(result)
        fair_results = []
        for region_cfg in active_regions:
            bucket = region_buckets.get(region_cfg["id"], [])
            fair_results.extend(bucket[:per_region])
        # Fill remaining slots from any region
        seen_fair = {id(r) for r in fair_results}
        for result in all_results:
            if len(fair_results) >= 15:
                break
            if id(result) not in seen_fair:
                fair_results.append(result)
        candidate_results = fair_results
    else:
        candidate_results = all_results[:10]

    # Sprint 199: Enrich results with multi-currency price extraction
    enriched_results = []
    for result in candidate_results:
        url = result["url"]
        snippet = result.get("snippet", "")
        region = result.get("_region", active_regions[0] if active_regions else {"id": "global", "default_currency": "USD"})

        # Sprint 199: Detect currency per result
        result_currency = _detect_result_currency(url, region, currency)

        # Try Serper metadata first (no HTTP call needed)
        price_foreign = _extract_price_from_text(
            snippet, result_currency,
            serper_price=result.get("extracted_price"),
            serper_price_range=result.get("price_range"),
        )

        # Only fetch via Jina if no price from Serper metadata + snippet
        if price_foreign is None:
            markdown = _fetch_page_markdown(url)
            if markdown:
                price_foreign = _extract_price_from_text(markdown, result_currency)

        # Sprint 199: If still no price with detected currency, try USD fallback
        if price_foreign is None and result_currency != "USD":
            price_foreign = _extract_price_from_text(snippet, "USD")
            if price_foreign:
                result_currency = "USD"

        item = {
            "title": result["title"],
            "url": url,
            "snippet": snippet[:200],
            "price_foreign": None,
            "price_currency": result_currency,
            "price_vnd": None,
            "region": _region_label(region),
            "source_platform": _extract_source_platform(url),
        }

        if price_foreign and price_foreign > 0:
            item["price_foreign"] = price_foreign
            item["price_currency"] = result_currency
            item["price_vnd"] = round(_convert_to_vnd(price_foreign, result_currency, usd_vnd_rate))

        enriched_results.append(item)

    # Stable partition: items WITH price first, WITHOUT price last.
    # No price-direction sort — the LLM agent decides presentation
    # order (cheapest/expensive/grouped) based on user's question.
    enriched_results.sort(
        key=lambda x: (0 if x["price_vnd"] else 1)
    )

    return {
        "results": enriched_results,
        "count": len(enriched_results),
        "exchange_rate": usd_vnd_rate,
        "currency": currency,
        "query": product_name,
        "regions_searched": regions_searched,
    }


def tool_international_search_fn(
    product_name: str,
    currency: str = "USD",
    search_queries: str = "",
    regions: str = "",
) -> str:
    """Search international markets including Chinese platforms for product pricing.

    Finds global suppliers, distributors, and pricing for comparison
    with Vietnamese domestic prices. Includes 1688.com, Taobao, Tmall,
    AliExpress, Amazon, eBay. Converts CNY/USD/EUR to VND automatically.

    Args:
        product_name: Product name in English (e.g., "Zebra ZXP Series 7 printhead")
        currency: Price currency to look for (USD, EUR, GBP, CNY). Default: USD
        search_queries: Optional JSON array of pre-optimized search queries from Query Planner.
                       Example: '["Zebra ZXP7 printhead price wholesale", "ZXP Series 7 supplier"]'
                       If provided, uses these instead of auto-generated queries for global region.
        regions: Optional comma-separated region IDs to search.
                Choices: "global", "china_1688", "china_taobao", "aliexpress".
                Empty = all regions (default).

    Returns:
        JSON with international results including VND-converted prices and region info.
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
        result = _search_international(
            product_name, currency,
            search_queries=planned_queries,
            regions=regions,
        )
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
            "Tìm giá trên thị trường QUỐC TẾ bao gồm NỀN TẢNG TRUNG QUỐC "
            "(1688.com, Taobao, Tmall, AliExpress) và Mỹ/EU (Amazon, eBay). "
            "Tự động chuyển đổi CNY/USD/EUR sang VNĐ. "
            "Dùng khi cần so sánh giá nội địa vs quốc tế, "
            "hoặc tìm nguồn nhập khẩu cho sản phẩm chuyên dụng, linh kiện, thiết bị công nghiệp. "
            "Tham số search_queries (JSON array) cho phép truyền truy vấn tối ưu từ Query Planner."
        ),
    )
