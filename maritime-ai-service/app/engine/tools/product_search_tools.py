"""
Product Search Tools — Sprint 149: "Cắm & Chạy" (Plugin Architecture)

Refactored from Sprint 148 monolithic file to delegate to SearchPlatformAdapter plugins.
Tools are auto-generated from the SearchPlatformRegistry — adding a new platform
requires only a new adapter + config line, no changes here.

Backward compatible: tool names, output format, and get_product_search_tools() API
remain identical to Sprint 148.
"""

import json
import logging
from typing import List

from langchain_core.tools import tool, StructuredTool

from app.engine.tools.registry import (
    ToolCategory,
    ToolAccess,
    get_tool_registry,
)

logger = logging.getLogger(__name__)

# Timeout and limits — overridden by config at init
_SEARCH_TIMEOUT = 30
_MAX_RESULTS = 30

# Module-level circuit breaker instance (created at init)
_circuit_breaker = None

# Auto-generated tools list (populated at init)
_generated_tools: List = []

# Legacy circuit breaker API (for backward compatibility with Sprint 148 tests)
_platform_cb = {}


def _cb_is_open(platform: str) -> bool:
    """Legacy CB check — delegates to PerPlatformCircuitBreaker."""
    if _circuit_breaker:
        return _circuit_breaker.is_open(platform)
    return False


def _cb_record_failure(platform: str):
    """Legacy CB record failure."""
    if _circuit_breaker:
        _circuit_breaker.record_failure(platform)


def _cb_record_success(platform: str):
    """Legacy CB record success."""
    if _circuit_breaker:
        _circuit_breaker.record_success(platform)


# =============================================================================
# Legacy sync functions (kept for backward compat with Sprint 148 tests)
# =============================================================================

def _search_google_shopping_sync(query: str, max_results: int = 20, page: int = 1) -> list:
    """Sync call to Serper.dev /shopping endpoint (delegates to adapter)."""
    from app.engine.search_platforms import get_search_platform_registry
    registry = get_search_platform_registry()
    adapter = registry.get("google_shopping")
    if adapter is None:
        # Fallback: direct implementation for when registry not initialized
        from app.core.config import get_settings
        settings = get_settings()
        api_key = settings.serper_api_key
        if not api_key:
            return [{"error": "SERPER_API_KEY not configured"}]
        import httpx
        resp = httpx.post(
            "https://google.serper.dev/shopping",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query, "gl": "vn", "hl": "vi", "num": min(max_results, 100), "page": page},
            timeout=_SEARCH_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get("shopping", [])[:max_results]:
            results.append({
                "platform": "Google Shopping",
                "title": item.get("title", ""),
                "price": item.get("price", ""),
                "extracted_price": item.get("extracted_price"),
                "source": item.get("source", ""),
                "rating": item.get("rating"),
                "reviews": item.get("ratingCount"),
                "link": item.get("link", ""),
                "image": item.get("imageUrl", ""),
                "delivery": item.get("delivery", ""),
            })
        return results

    results = adapter.search_sync(query, max_results, page=page)
    return [r.to_dict() for r in results]


def _search_platform_via_serper_sync(
    query: str,
    platform_name: str,
    max_results: int = 20,
    page: int = 1,
) -> list:
    """Search a specific platform using Serper.dev (delegates to adapter)."""
    from app.engine.search_platforms import get_search_platform_registry

    # Map display name to platform ID
    _NAME_TO_ID = {
        "Shopee": "shopee",
        "TikTok Shop": "tiktok_shop",
        "Lazada": "lazada",
        "Facebook Marketplace": "facebook_marketplace",
        "Instagram": "instagram",
    }

    registry = get_search_platform_registry()
    platform_id = _NAME_TO_ID.get(platform_name, platform_name.lower().replace(" ", "_"))
    adapter = registry.get(platform_id)

    if adapter is None:
        # Fallback: direct Serper call
        from app.core.config import get_settings
        settings = get_settings()
        api_key = settings.serper_api_key
        if not api_key:
            return [{"error": "SERPER_API_KEY not configured"}]

        _PLATFORM_SITE_FILTERS = {
            "Shopee": "site:shopee.vn",
            "TikTok Shop": "site:tiktok.com/shop",
            "Lazada": "site:lazada.vn",
            "Facebook Marketplace": "site:facebook.com/marketplace",
            "Instagram": "site:instagram.com",
        }
        site_filter = _PLATFORM_SITE_FILTERS.get(platform_name, "")
        full_query = f"{site_filter} {query}" if site_filter else query

        import httpx
        resp = httpx.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": full_query, "gl": "vn", "hl": "vi", "num": min(max_results, 100), "page": page},
            timeout=_SEARCH_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get("organic", [])[:max_results]:
            results.append({
                "platform": platform_name,
                "title": item.get("title", ""),
                "price": item.get("priceRange", ""),
                "link": item.get("link", ""),
                "snippet": item.get("snippet", ""),
                "source": item.get("source", ""),
            })
        return results

    results = adapter.search_sync(query, max_results, page=page)
    return [r.to_dict() for r in results]


# =============================================================================
# Auto-generated tool builder
# =============================================================================

def _build_platform_tool(adapter, circuit_breaker):
    """
    Auto-generate a LangChain StructuredTool from a SearchPlatformAdapter.

    Tool name = adapter.get_tool_name() (e.g. "tool_search_shopee")
    Output format = {"platform": ..., "results": [...], "count": N} (backward compat)
    """
    config = adapter.get_config()
    platform_id = config.id
    display_name = config.display_name
    tool_name = adapter.get_tool_name()
    tool_desc = adapter.get_tool_description()
    default_max = config.max_results_default

    def platform_tool(query: str, max_results: int = default_max, page: int = 1) -> str:
        if circuit_breaker.is_open(platform_id):
            return json.dumps(
                {"error": f"{display_name} tạm thời không khả dụng, thử lại sau"},
                ensure_ascii=False,
            )
        try:
            results = adapter.search_sync(query, min(max_results, _MAX_RESULTS), page=page)
            circuit_breaker.record_success(platform_id)
            return json.dumps(
                {
                    "platform": display_name,
                    "results": [r.to_dict() for r in results],
                    "count": len(results),
                },
                ensure_ascii=False,
            )
        except Exception as e:
            circuit_breaker.record_failure(platform_id)
            return json.dumps(
                {"error": f"Lỗi tìm kiếm {display_name}: {str(e)[:200]}"},
                ensure_ascii=False,
            )

    return StructuredTool.from_function(
        func=platform_tool,
        name=tool_name,
        description=tool_desc,
    )


def _build_auto_group_search_tool(circuit_breaker):
    """Build composite tool that auto-discovers and searches Facebook groups.

    Sprint 157: Searches 2-3 popular groups based on product category,
    without requiring the user to name specific groups.
    """

    def facebook_groups_auto_tool(query: str, max_groups: int = 3) -> str:
        """Auto-discover and search relevant Facebook Groups for a product.

        Args:
            query: Product search query (e.g., "MacBook M4 Pro 24GB")
            max_groups: Maximum groups to search (default 3, max 5)
        """
        max_groups = max(1, min(max_groups, 5))

        # 1. Get groups from catalog
        from app.engine.search_platforms.facebook_group_catalog import (
            get_groups_for_query,
            discover_groups_via_serper,
        )
        groups = get_groups_for_query(query, max_groups)

        # 2. Fallback: Serper discovery if catalog misses
        if not groups:
            groups = discover_groups_via_serper(query, max_groups)

        if not groups:
            return json.dumps(
                {"error": "Không tìm thấy nhóm Facebook phù hợp", "platform": "Facebook Groups (auto)"},
                ensure_ascii=False,
            )

        # 3. Get facebook_group adapter from registry
        from app.engine.search_platforms import get_search_platform_registry
        adapter = get_search_platform_registry().get("facebook_group")
        if not adapter:
            return json.dumps(
                {"error": "Facebook Group adapter not available", "platform": "Facebook Groups (auto)"},
                ensure_ascii=False,
            )

        # 4. Search each group sequentially (Playwright single-threaded)
        all_results = []
        groups_searched = []
        for g in groups:
            if circuit_breaker.is_open("facebook_group"):
                logger.info("[AUTO_GROUP] Circuit breaker open — stopping group search")
                break
            try:
                group_ref = g.get("url") or g["name"]
                results = adapter.search_group_sync(group_ref, query, max_results=10)
                circuit_breaker.record_success("facebook_group")
                groups_searched.append(g["name"])
                all_results.extend([r.to_dict() for r in results])
                logger.info(
                    "[AUTO_GROUP] Found %d results in '%s'",
                    len(results), g["name"],
                )
            except Exception as e:
                circuit_breaker.record_failure("facebook_group")
                logger.warning("[AUTO_GROUP] Failed to search '%s': %s", g["name"], e)

        logger.info(
            "[AUTO_GROUP] Searched %d groups for '%s', total %d results",
            len(groups_searched), query[:50], len(all_results),
        )

        return json.dumps(
            {
                "platform": "Facebook Groups (auto)",
                "groups_searched": groups_searched,
                "results": all_results,
                "count": len(all_results),
            },
            ensure_ascii=False,
        )

    return StructuredTool.from_function(
        func=facebook_groups_auto_tool,
        name="tool_search_facebook_groups_auto",
        description=(
            "Tu dong tim san pham trong cac nhom Facebook pho bien. "
            "Khong can biet ten nhom — tool se tu xac dinh nhom phu hop voi loai san pham. "
            "Rat tot cho hang cu, second-hand, deal tot. YEU CAU cookie dang nhap Facebook."
        ),
    )


def _build_group_search_tool(adapter, circuit_breaker):
    """Build custom tool for Facebook Group search with different signature.

    Sprint 155: Group search needs (group_name_or_url, query, max_results)
    instead of the standard (query, max_results, page) signature.
    """
    config = adapter.get_config()
    platform_id = config.id
    display_name = config.display_name
    tool_desc = adapter.get_tool_description()

    def facebook_group_tool(group_name_or_url: str, query: str, max_results: int = 20) -> str:
        """Search for products WITHIN a specific Facebook Group.

        Args:
            group_name_or_url: Group name (e.g., 'Vua 2nd') or full Facebook group URL
            query: Product search query (e.g., 'MacBook M4 Pro')
            max_results: Maximum number of results (default 20)
        """
        if circuit_breaker.is_open(platform_id):
            return json.dumps(
                {"error": f"{display_name} tam thoi khong kha dung, thu lai sau"},
                ensure_ascii=False,
            )
        try:
            results = adapter.search_group_sync(
                group_name_or_url, query, min(max_results, _MAX_RESULTS),
            )
            circuit_breaker.record_success(platform_id)
            return json.dumps(
                {
                    "platform": display_name,
                    "group": group_name_or_url,
                    "results": [r.to_dict() for r in results],
                    "count": len(results),
                },
                ensure_ascii=False,
            )
        except Exception as e:
            circuit_breaker.record_failure(platform_id)
            return json.dumps(
                {"error": f"Loi tim kiem {display_name}: {str(e)[:200]}"},
                ensure_ascii=False,
            )

    return StructuredTool.from_function(
        func=facebook_group_tool,
        name="tool_search_facebook_group",
        description=tool_desc,
    )


# =============================================================================
# Static tool definitions (backward compat — used when registry not yet init'd)
# These are replaced by auto-generated tools after init_product_search_tools()
# =============================================================================

@tool
def tool_search_google_shopping(query: str, max_results: int = 20, page: int = 1) -> str:
    """Search Google Shopping for products in Vietnam. Returns structured product data including prices, ratings, and links.
    Use this for the fastest, most structured results across many Vietnamese e-commerce platforms.

    Args:
        query: Product search query (e.g., "cuộn dây điện 3 ruột 2.5mm²")
        max_results: Maximum number of results (default 20, max 100)
        page: Page number for pagination (default 1). Use page=2, 3... to get more results.
    """
    if _cb_is_open("google_shopping"):
        return json.dumps({"error": "Google Shopping tạm thời không khả dụng, thử lại sau"}, ensure_ascii=False)
    try:
        results = _search_google_shopping_sync(query, min(max_results, _MAX_RESULTS), page=page)
        _cb_record_success("google_shopping")
        return json.dumps({"platform": "Google Shopping", "results": results, "count": len(results)}, ensure_ascii=False)
    except Exception as e:
        _cb_record_failure("google_shopping")
        return json.dumps({"error": f"Lỗi tìm kiếm Google Shopping: {str(e)[:200]}"}, ensure_ascii=False)


@tool
def tool_search_shopee(query: str, max_results: int = 20, page: int = 1) -> str:
    """Search Shopee Vietnam for products. Returns product listings from shopee.vn with titles, prices, and links.

    Args:
        query: Product search query (e.g., "dây điện Cadivi 2.5mm")
        max_results: Maximum number of results (default 20)
        page: Page number for pagination (default 1). Use page=2, 3... to get more results.
    """
    if _cb_is_open("shopee"):
        return json.dumps({"error": "Shopee tạm thời không khả dụng, thử lại sau"}, ensure_ascii=False)
    try:
        results = _search_platform_via_serper_sync(query, "Shopee", min(max_results, _MAX_RESULTS), page=page)
        _cb_record_success("shopee")
        return json.dumps({"platform": "Shopee", "results": results, "count": len(results)}, ensure_ascii=False)
    except Exception as e:
        _cb_record_failure("shopee")
        return json.dumps({"error": f"Lỗi tìm kiếm Shopee: {str(e)[:200]}"}, ensure_ascii=False)


@tool
def tool_search_tiktok_shop(query: str, max_results: int = 20, page: int = 1) -> str:
    """Search TikTok Shop Vietnam for products. Returns product listings with titles, prices, and links.

    Args:
        query: Product search query (e.g., "dây điện 3x2.5mm")
        max_results: Maximum number of results (default 20)
        page: Page number for pagination (default 1). Use page=2, 3... to get more results.
    """
    if _cb_is_open("tiktok_shop"):
        return json.dumps({"error": "TikTok Shop tạm thời không khả dụng, thử lại sau"}, ensure_ascii=False)
    try:
        results = _search_platform_via_serper_sync(query, "TikTok Shop", min(max_results, _MAX_RESULTS), page=page)
        _cb_record_success("tiktok_shop")
        return json.dumps({"platform": "TikTok Shop", "results": results, "count": len(results)}, ensure_ascii=False)
    except Exception as e:
        _cb_record_failure("tiktok_shop")
        return json.dumps({"error": f"Lỗi tìm kiếm TikTok Shop: {str(e)[:200]}"}, ensure_ascii=False)


@tool
def tool_search_lazada(query: str, max_results: int = 20, page: int = 1) -> str:
    """Search Lazada Vietnam for products. Returns product listings with titles, prices, and links.

    Args:
        query: Product search query (e.g., "dây cáp điện 2.5mm")
        max_results: Maximum number of results (default 20)
        page: Page number for pagination (default 1). Use page=2, 3... to get more results.
    """
    if _cb_is_open("lazada"):
        return json.dumps({"error": "Lazada tạm thời không khả dụng, thử lại sau"}, ensure_ascii=False)
    try:
        results = _search_platform_via_serper_sync(query, "Lazada", min(max_results, _MAX_RESULTS), page=page)
        _cb_record_success("lazada")
        return json.dumps({"platform": "Lazada", "results": results, "count": len(results)}, ensure_ascii=False)
    except Exception as e:
        _cb_record_failure("lazada")
        return json.dumps({"error": f"Lỗi tìm kiếm Lazada: {str(e)[:200]}"}, ensure_ascii=False)


@tool
def tool_search_facebook_marketplace(query: str, max_results: int = 20, page: int = 1) -> str:
    """Search Facebook Marketplace for products in Vietnam. Returns products with titles, prices, and links.

    Args:
        query: Product search query (e.g., "cuộn dây điện")
        max_results: Maximum number of results (default 20)
        page: Page number for pagination (default 1). Use page=2, 3... to get more results.
    """
    if _cb_is_open("facebook_marketplace"):
        return json.dumps({"error": "Facebook Marketplace tạm thời không khả dụng, thử lại sau"}, ensure_ascii=False)
    try:
        results = _search_platform_via_serper_sync(query, "Facebook Marketplace", min(max_results, _MAX_RESULTS), page=page)
        _cb_record_success("facebook_marketplace")
        return json.dumps({"platform": "Facebook Marketplace", "results": results, "count": len(results)}, ensure_ascii=False)
    except Exception as e:
        _cb_record_failure("facebook_marketplace")
        return json.dumps({"error": f"Lỗi tìm kiếm Facebook Marketplace: {str(e)[:200]}"}, ensure_ascii=False)


@tool
def tool_search_all_web(query: str, max_results: int = 20, page: int = 1) -> str:
    """Search ALL websites for product prices — not just major platforms.
    This finds small/independent Vietnamese shops, B2B suppliers, wholesale distributors, and niche stores
    that often have better prices than Shopee/Lazada. Uses Google web search with Vietnamese locale.

    Args:
        query: Product search query with "giá" or "mua" for best results (e.g., "giá dây điện 3 ruột 2.5mm mua ở đâu")
        max_results: Maximum number of results (default 20)
        page: Page number for pagination (default 1). Use page=2, 3... to get more results.
    """
    if _cb_is_open("all_web"):
        return json.dumps({"error": "Web search tạm thời không khả dụng, thử lại sau"}, ensure_ascii=False)

    from app.engine.search_platforms import get_search_platform_registry
    registry = get_search_platform_registry()
    adapter = registry.get("all_web")

    if adapter:
        try:
            results = adapter.search_sync(query, min(max_results, _MAX_RESULTS))
            _cb_record_success("all_web")
            return json.dumps(
                {"platform": "Web (all)", "results": [r.to_dict() for r in results], "count": len(results)},
                ensure_ascii=False,
            )
        except Exception as e:
            _cb_record_failure("all_web")
            return json.dumps({"error": f"Lỗi tìm kiếm web: {str(e)[:200]}"}, ensure_ascii=False)

    # Fallback: direct Serper call
    from app.core.config import get_settings
    settings = get_settings()
    api_key = settings.serper_api_key
    if not api_key:
        return json.dumps({"error": "SERPER_API_KEY not configured"}, ensure_ascii=False)
    import httpx
    try:
        search_query = f"{query} giá bán -site:shopee.vn -site:lazada.vn -site:tiki.vn"
        resp = httpx.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": search_query, "gl": "vn", "hl": "vi", "num": min(max_results, 100), "page": page},
            timeout=_SEARCH_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get("organic", [])[:max_results]:
            results.append({
                "platform": "Web",
                "title": item.get("title", ""),
                "price": item.get("priceRange", ""),
                "link": item.get("link", ""),
                "snippet": item.get("snippet", ""),
                "source": item.get("source", ""),
            })
        _cb_record_success("all_web")
        return json.dumps({"platform": "Web (all)", "results": results, "count": len(results)}, ensure_ascii=False)
    except Exception as e:
        _cb_record_failure("all_web")
        return json.dumps({"error": f"Lỗi tìm kiếm web: {str(e)[:200]}"}, ensure_ascii=False)


@tool
def tool_search_instagram_shopping(query: str, max_results: int = 20, page: int = 1) -> str:
    """Search Instagram for product posts in Vietnam. Finds public shopping posts, reels, and store pages.
    Note: Only finds publicly indexed content — private groups require separate auth.

    Args:
        query: Product search query (e.g., "dây điện 2.5mm")
        max_results: Maximum number of results (default 20)
        page: Page number for pagination (default 1). Use page=2, 3... to get more results.
    """
    if _cb_is_open("instagram"):
        return json.dumps({"error": "Instagram search tạm thời không khả dụng, thử lại sau"}, ensure_ascii=False)
    try:
        results = _search_platform_via_serper_sync(query, "Instagram", min(max_results, _MAX_RESULTS), page=page)
        _cb_record_success("instagram")
        return json.dumps({"platform": "Instagram", "results": results, "count": len(results)}, ensure_ascii=False)
    except Exception as e:
        _cb_record_failure("instagram")
        return json.dumps({"error": f"Lỗi tìm kiếm Instagram: {str(e)[:200]}"}, ensure_ascii=False)


# =============================================================================
# Tool Registration
# =============================================================================

_ALL_PRODUCT_SEARCH_TOOLS = [
    tool_search_google_shopping,
    tool_search_shopee,
    tool_search_tiktok_shop,
    tool_search_lazada,
    tool_search_facebook_marketplace,
    tool_search_all_web,
    tool_search_instagram_shopping,
]


def get_product_search_tools() -> list:
    """Get all product search tools (for binding to agent LLM).

    Returns auto-generated tools if registry is initialized,
    otherwise returns static tool definitions (backward compat).
    """
    if _generated_tools:
        return list(_generated_tools)
    return list(_ALL_PRODUCT_SEARCH_TOOLS)


def init_product_search_tools():
    """
    Register all product search tools with the global registry.

    Sprint 149: Initializes SearchPlatformRegistry, then auto-generates tools
    from registered adapters. Falls back to static tools if registry init fails.
    """
    from app.core.config import get_settings
    settings = get_settings()

    global _SEARCH_TIMEOUT, _MAX_RESULTS, _circuit_breaker, _generated_tools
    _SEARCH_TIMEOUT = settings.product_search_timeout
    _MAX_RESULTS = settings.product_search_max_results

    # Initialize circuit breaker
    from app.engine.search_platforms.circuit_breaker import PerPlatformCircuitBreaker
    _circuit_breaker = PerPlatformCircuitBreaker()

    # Initialize search platform registry
    try:
        from app.engine.search_platforms import init_search_platforms
        registry = init_search_platforms()

        # Auto-generate tools from registered adapters
        _generated_tools.clear()
        for adapter in registry.get_all_enabled():
            config = adapter.get_config()
            # Sprint 155: Facebook Group uses custom tool builder (different signature)
            if config.id == "facebook_group":
                t = _build_group_search_tool(adapter, _circuit_breaker)
            else:
                t = _build_platform_tool(adapter, _circuit_breaker)
            _generated_tools.append(t)

        # Sprint 157: Auto group discovery tool
        enabled = set(settings.product_search_platforms)
        if settings.enable_auto_group_discovery and "facebook_group" in enabled:
            auto_tool = _build_auto_group_search_tool(_circuit_breaker)
            _generated_tools.append(auto_tool)
            logger.info("Auto group discovery tool registered")

        if _generated_tools:
            logger.info(
                "Auto-generated %d product search tools from registry",
                len(_generated_tools),
            )
    except Exception as e:
        logger.warning("Search platform registry init failed, using static tools: %s", e)
        _generated_tools.clear()

    # Register tools with the tool registry
    tool_registry = get_tool_registry()
    tools_to_register = _generated_tools if _generated_tools else _ALL_PRODUCT_SEARCH_TOOLS
    for t in tools_to_register:
        tool_registry.register(t, ToolCategory.PRODUCT_SEARCH, ToolAccess.READ)

    logger.info("Product search tools registered (%d tools)", len(tools_to_register))
