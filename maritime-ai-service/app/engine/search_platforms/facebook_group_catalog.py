"""
Facebook Group Catalog — Sprint 157: "Săn Nhóm"

Static catalog of popular Vietnamese Facebook groups organized by product category.
Enables auto-discovery of relevant groups for a product search query.

Usage:
    from app.engine.search_platforms.facebook_group_catalog import get_groups_for_query

    groups = get_groups_for_query("MacBook M4 Pro", max_groups=3)
    # [{"name": "Vựa 2nd", "url": "https://www.facebook.com/groups/vua2nd", "priority": 1}, ...]
"""

import logging
import re
import unicodedata
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Category → Groups mapping
# ---------------------------------------------------------------------------

CATEGORY_GROUPS: Dict[str, dict] = {
    "electronics_laptop": {
        "keywords": [
            "laptop", "macbook", "thinkpad", "dell", "hp", "asus", "acer",
            "máy tính xách tay", "may tinh xach tay", "notebook", "surface",
            "lenovo", "msi", "razer", "chromebook",
        ],
        "groups": [
            # Verified 2026-02-20: Vựa 2nd PUBLIC (153K members, 20+ posts/day)
            {"name": "Vựa 2nd", "url": "https://www.facebook.com/groups/1779682299414133", "priority": 1},
            # Verified: Chợ Laptop Cũ (active trading group)
            {"name": "Chợ Laptop Cũ", "url": "https://www.facebook.com/groups/344287045137154", "priority": 2},
            # Verified: Hội Mua Bán Macbook Việt Nam — returned 7 results in live test
            {"name": "Hội Mua Bán Macbook VN", "url": "https://www.facebook.com/groups/muabanmacbookvn", "priority": 3},
            # Verified: Mua Bán Macbook Cũ ✅
            {"name": "Mua Bán Macbook Cũ", "url": "https://www.facebook.com/groups/muabanmacbookcu", "priority": 4},
        ],
    },
    "electronics_phone": {
        "keywords": [
            "iphone", "samsung", "điện thoại", "dien thoai", "phone",
            "galaxy", "pixel", "oppo", "xiaomi", "redmi", "realme",
            "vivo", "huawei", "oneplus",
        ],
        "groups": [
            # Verified: Vựa 2nd PUBLIC (153K, general electronics)
            {"name": "Vựa 2nd", "url": "https://www.facebook.com/groups/1779682299414133", "priority": 1},
            # Verified: Hội iPhone Hà Nội (Mua Bán Điện Thoại Cũ Mới)
            {"name": "Hội iPhone Hà Nội", "url": "https://www.facebook.com/groups/2549665671997956", "priority": 2},
            # Verified: Cộng Đồng iPhone Việt Nam
            {"name": "Cộng Đồng iPhone VN", "url": "https://www.facebook.com/groups/696924561239780", "priority": 3},
        ],
    },
    "electronics_general": {
        "keywords": [
            "tai nghe", "loa", "camera", "máy ảnh", "may anh", "console",
            "ps5", "ps4", "nintendo", "switch", "xbox", "airpods",
            "apple watch", "đồng hồ thông minh", "smartwatch", "tablet",
            "ipad", "máy tính bảng", "may tinh bang",
        ],
        "groups": [
            # Verified: Vựa 2nd PUBLIC (153K, general electronics)
            {"name": "Vựa 2nd", "url": "https://www.facebook.com/groups/1779682299414133", "priority": 1},
            # Verified: Vựa 2nd (543K, second largest)
            {"name": "Vựa 2nd (543K)", "url": "https://www.facebook.com/groups/vua2ndd", "priority": 2},
        ],
    },
    "vehicles_motorbike": {
        "keywords": [
            "xe máy", "xe may", "honda", "yamaha", "suzuki", "vespa",
            "piaggio", "sym", "wave", "air blade", "exciter", "winner",
            "sh", "lead", "vision", "xe ga", "xe số",
        ],
        "groups": [
            # Use name-based resolution (no verified URL yet)
            {"name": "Hội Mua Bán Xe Máy Cũ TPHCM", "url": None, "priority": 1},
            {"name": "Chợ Xe Máy Cũ", "url": None, "priority": 2},
        ],
    },
    "vehicles_car": {
        "keywords": [
            "ô tô", "o to", "xe hơi", "xe hoi", "toyota", "hyundai",
            "kia", "mazda", "ford", "vinfast", "mercedes", "bmw",
            "audi", "honda crv", "vios", "camry",
        ],
        "groups": [
            {"name": "Hội Mua Bán Ô Tô Cũ", "url": None, "priority": 1},
        ],
    },
    "fashion": {
        "keywords": [
            "quần áo", "quan ao", "giày", "giay", "túi xách", "tui xach",
            "đồng hồ", "dong ho", "thời trang", "thoi trang",
            "áo khoác", "ao khoac", "váy", "vay", "sneaker", "nike",
            "adidas", "balenciaga", "gucci", "louis vuitton",
        ],
        "groups": [
            {"name": "Hội Mua Bán Quần Áo 2nd Hand", "url": None, "priority": 1},
            {"name": "Thời Trang Second Hand VN", "url": None, "priority": 2},
        ],
    },
    "furniture": {
        "keywords": [
            "nội thất", "noi that", "bàn", "ban", "ghế", "ghe",
            "tủ", "tu", "giường", "giuong", "sofa", "kệ", "ke",
            "bàn làm việc", "bàn học",
        ],
        "groups": [
            {"name": "Hội Mua Bán Nội Thất Cũ", "url": None, "priority": 1},
        ],
    },
    "appliances": {
        "keywords": [
            "máy giặt", "may giat", "tủ lạnh", "tu lanh", "điều hòa",
            "dieu hoa", "máy lọc", "may loc", "máy rửa", "may rua",
            "quạt", "quat", "nồi chiên", "noi chien", "lò vi sóng",
        ],
        "groups": [
            {"name": "Hội Mua Bán Đồ Gia Dụng Cũ", "url": None, "priority": 1},
        ],
    },
}


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Normalize Vietnamese text: lowercase, strip diacritics for matching."""
    text = text.lower().strip()
    # NFD decompose then strip combining marks
    nfd = unicodedata.normalize("NFD", text)
    stripped = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return stripped


def _query_tokens(query: str) -> List[str]:
    """Tokenize query into lowercase normalized words."""
    return _normalize(query).split()


# ---------------------------------------------------------------------------
# Category matching
# ---------------------------------------------------------------------------

def _word_boundary_match(keyword: str, text: str) -> bool:
    """Check if keyword appears in text with word boundary awareness.

    Short keywords (<=3 chars) require word boundaries to avoid
    false positives like 'tủ' matching 'quantum'.
    """
    if len(keyword) <= 3:
        # Use regex word boundary for short keywords
        pattern = r'\b' + re.escape(keyword) + r'\b'
        return bool(re.search(pattern, text))
    return keyword in text


def match_categories(query: str) -> List[str]:
    """Match query against category keywords.

    Returns list of category IDs sorted by number of keyword matches (descending).
    """
    query_norm = _normalize(query)
    query_lower = query.lower()

    scores: Dict[str, int] = {}
    for cat_id, cat_data in CATEGORY_GROUPS.items():
        count = 0
        for kw in cat_data["keywords"]:
            # Check both original (with diacritics) and normalized
            kw_lower = kw.lower()
            kw_norm = _normalize(kw)
            if _word_boundary_match(kw_lower, query_lower) or _word_boundary_match(kw_norm, query_norm):
                count += 1
        if count > 0:
            scores[cat_id] = count

    # Sort by match count descending
    return sorted(scores.keys(), key=lambda c: scores[c], reverse=True)


def get_groups_for_query(query: str, max_groups: int = 3) -> List[dict]:
    """Get top N groups relevant to the query from the static catalog.

    Returns deduplicated groups sorted by priority.

    Args:
        query: Product search query
        max_groups: Maximum groups to return (1-5)

    Returns:
        List of {"name": str, "url": str|None, "priority": int}
    """
    max_groups = max(1, min(max_groups, 5))
    categories = match_categories(query)

    if not categories:
        return []

    # Collect groups from all matching categories
    seen_names: set = set()
    groups: List[dict] = []

    for cat_id in categories:
        for g in CATEGORY_GROUPS[cat_id]["groups"]:
            name = g["name"]
            if name not in seen_names:
                seen_names.add(name)
                groups.append(dict(g))  # shallow copy

    # Sort by priority (lower = better)
    groups.sort(key=lambda g: g["priority"])

    return groups[:max_groups]


# ---------------------------------------------------------------------------
# Serper fallback discovery
# ---------------------------------------------------------------------------

# Module-level cache: query_key → list of groups
_discovery_cache: Dict[str, List[dict]] = {}


def _make_cache_key(query: str) -> str:
    """Stable cache key from query."""
    return _normalize(query).strip()


def discover_groups_via_serper(query: str, max_groups: int = 3) -> List[dict]:
    """Discover Facebook groups via Serper search (fallback when catalog misses).

    Searches: site:facebook.com/groups "{query}" mua bán

    Args:
        query: Product search query
        max_groups: Maximum groups to return

    Returns:
        List of {"name": str, "url": str, "priority": int}
    """
    cache_key = _make_cache_key(query)
    if cache_key in _discovery_cache:
        return _discovery_cache[cache_key][:max_groups]

    from app.core.config import get_settings
    settings = get_settings()
    api_key = settings.serper_api_key
    if not api_key:
        logger.warning("[GROUP_CATALOG] No SERPER_API_KEY — cannot discover groups")
        return []

    search_query = f'site:facebook.com/groups "{query}" mua bán'

    try:
        import httpx
        resp = httpx.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": search_query, "gl": "vn", "hl": "vi", "num": 10},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning("[GROUP_CATALOG] Serper discovery failed: %s", e)
        return []

    groups: List[dict] = []
    seen_urls: set = set()
    fb_group_pattern = re.compile(r"https?://(?:www\.)?facebook\.com/groups/[^/?\s]+")

    for item in data.get("organic", []):
        link = item.get("link", "")
        match = fb_group_pattern.search(link)
        if not match:
            continue
        group_url = match.group(0)
        if group_url in seen_urls:
            continue
        seen_urls.add(group_url)

        title = item.get("title", "")
        # Clean title: remove " | Facebook" suffix, etc.
        name = re.sub(r"\s*\|?\s*Facebook\s*$", "", title).strip()
        if not name:
            name = group_url.rstrip("/").split("/")[-1]

        groups.append({
            "name": name,
            "url": group_url,
            "priority": len(groups) + 1,
        })

        if len(groups) >= max_groups:
            break

    # Cache the result
    _discovery_cache[cache_key] = groups
    logger.info("[GROUP_CATALOG] Serper discovered %d groups for '%s'", len(groups), query[:50])

    return groups[:max_groups]


def clear_discovery_cache():
    """Clear the Serper discovery cache (for testing)."""
    _discovery_cache.clear()
