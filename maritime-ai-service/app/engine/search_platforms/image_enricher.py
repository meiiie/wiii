"""
Product Image Enrichment — Sprint 201: "Ảnh Thật" + Sprint 201b: "Ảnh Thật v2"

Enriches product search results with Google-cached thumbnail images
via Serper /images API. Solves the problem of Serper site-filtered
results returning no images for Shopee/Lazada/TikTok/AllWeb.

Key insight: Serper /images returns `thumbnailUrl` from Google's cache
(encrypted-tbn0.gstatic.com) which has NO CORS restrictions — perfect
for product cards.

Sprint 201b hardening:
- Skip tiktok_shop (Serper site:tiktok.com returns garbage)
- Raise min_similarity 0.25→0.4 to reject wrong images
- Category mismatch rejection (Vietnamese product categories)
- Fix Instagram platform key mismatch

Usage:
    from app.engine.search_platforms.image_enricher import enrich_product_images

    products = enrich_product_images(products, query="Arduino Mega", platform_id="shopee")
"""

import logging
import os
from typing import Any, Dict, List, Set
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Platforms that already have good images — skip enrichment
_SKIP_ENRICHMENT_PLATFORMS = frozenset({
    "google_shopping",
    "websosanh",
    "facebook_groups_auto",
    "tiktok_shop",  # Sprint 201b: Serper site:tiktok.com returns unreliable results
})

# Map platform_id → site hint for Serper /images query
_SITE_HINTS: Dict[str, str] = {
    "shopee": "shopee.vn",
    "lazada": "lazada.vn",
    "all_web": "",
    "facebook_marketplace": "facebook.com",
    "instagram": "instagram.com",  # Sprint 201b: Fixed key to match serper_site.py adapter ID
}

# Sprint 201b: Vietnamese product category phrases for cross-category rejection.
# If image title contains a phrase from this set but the product title does NOT,
# the image is likely from a completely different product category → reject.
_REJECT_CATEGORIES = frozenset({
    "hộp cơm", "giữ nhiệt", "áo", "quần", "giày", "dép",
    "mỹ phẩm", "nước hoa", "son", "kem", "váy", "túi xách",
})


def should_enrich(platform_id: str, products: List[Dict[str, Any]]) -> bool:
    """Determine if products need image enrichment.

    Skip if:
    - Platform already provides images (google_shopping, websosanh, etc.)
    - >=50% of products already have images
    - No products to enrich
    """
    if not products:
        return False

    if platform_id in _SKIP_ENRICHMENT_PLATFORMS:
        return False

    # Check how many already have images
    with_images = sum(
        1 for p in products
        if p.get("image") or p.get("image_url") or p.get("thumbnail")
    )
    if with_images >= len(products) * 0.5:
        return False

    return True


def _extract_domain(url: str) -> str:
    """Extract root domain from URL.

    Examples:
        'https://cf.shopee.vn/img/abc.jpg' → 'shopee.vn'
        'https://www.lazada.vn/products/123' → 'lazada.vn'
        'https://tiktok.com/shop/item' → 'tiktok.com'
    """
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        # Remove www. prefix
        if host.startswith("www."):
            host = host[4:]
        # Extract root domain (last 2 parts)
        parts = host.split(".")
        if len(parts) >= 2:
            return ".".join(parts[-2:])
        return host
    except Exception:
        return ""


def _title_similarity(a: str, b: str) -> float:
    """Jaccard word overlap between two titles.

    Returns 0.0-1.0. Case-insensitive. Zero external deps.
    """
    if not a or not b:
        return 0.0
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def _has_category_mismatch(product_title: str, image_title: str) -> bool:
    """Sprint 201b: Reject images with unrelated Vietnamese category words.

    Returns True if image_title contains a category phrase NOT in product_title.
    This prevents e.g. "Hộp Cơm Giữ Nhiệt LocknLock" images matching to
    "Raspberry Pi 5" products via Jaccard title fallback.
    """
    if not product_title or not image_title:
        return False
    pt_lower = product_title.lower()
    it_lower = image_title.lower()
    for phrase in _REJECT_CATEGORIES:
        if phrase in it_lower and phrase not in pt_lower:
            return True
    return False


def _match_images_to_products(
    products: List[Dict[str, Any]],
    images: List[Dict[str, Any]],
    min_similarity: float = 0.4,
) -> int:
    """Match images to products in-place using thumbnailUrl.

    Strategy:
    1. Domain match (high confidence): product.link domain == image.link domain
    2. Title similarity fallback: Jaccard >= min_similarity + category check

    Sprint 201b: Added category mismatch rejection in title fallback pass.
    Each image consumed once (greedy). Existing images never overwritten.

    Returns:
        Number of products enriched.
    """
    if not products or not images:
        return 0

    enriched = 0
    used_images: Set[int] = set()  # indices of consumed images

    # Pass 1: Domain matching
    for product in products:
        # Skip if already has image
        if product.get("image") or product.get("image_url") or product.get("thumbnail"):
            continue

        product_link = product.get("link") or product.get("url", "")
        product_domain = _extract_domain(product_link)
        if not product_domain:
            continue

        for idx, img in enumerate(images):
            if idx in used_images:
                continue
            img_link = img.get("link", "")
            img_domain = _extract_domain(img_link)
            if product_domain == img_domain:
                thumb = img.get("thumbnailUrl", "")
                if thumb:
                    product["image"] = thumb
                    used_images.add(idx)
                    enriched += 1
                    break

    # Pass 2: Title similarity fallback (with category mismatch rejection)
    for product in products:
        if product.get("image") or product.get("image_url") or product.get("thumbnail"):
            continue

        product_title = product.get("title") or product.get("name", "")
        if not product_title:
            continue

        best_idx = -1
        best_sim = 0.0

        for idx, img in enumerate(images):
            if idx in used_images:
                continue
            img_title = img.get("title", "")

            # Sprint 201b: Reject cross-category images
            if _has_category_mismatch(product_title, img_title):
                continue

            sim = _title_similarity(product_title, img_title)
            if sim >= min_similarity and sim > best_sim:
                best_sim = sim
                best_idx = idx

        if best_idx >= 0:
            thumb = images[best_idx].get("thumbnailUrl", "")
            if thumb:
                product["image"] = thumb
                used_images.add(best_idx)
                enriched += 1

    return enriched


def _fetch_serper_images(
    query: str,
    site_hint: str = "",
    num: int = 10,
) -> List[Dict[str, Any]]:
    """Fetch image results from Serper /images API.

    Args:
        query: Search query (product name).
        site_hint: Optional site domain to scope search (e.g. 'shopee.vn').
        num: Number of results to request.

    Returns:
        List of image result dicts with keys: title, imageUrl, thumbnailUrl, link, etc.
        Returns [] on any error.
    """
    try:
        from app.core.config import get_settings
        settings = get_settings()
    except Exception:
        return []

    api_key = getattr(settings, "serper_api_key", "") or os.environ.get("SERPER_API_KEY", "")
    if not api_key:
        logger.debug("[IMAGE_ENRICHER] No Serper API key — skipping image fetch")
        return []

    timeout = getattr(settings, "image_enrichment_timeout", 8)

    # Build search query with site hint
    search_query = query
    if site_hint:
        search_query = f"{query} site:{site_hint}"

    try:
        import httpx

        resp = httpx.post(
            "https://google.serper.dev/images",
            json={"q": search_query, "num": num},
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("images", [])
    except Exception as exc:
        logger.debug("[IMAGE_ENRICHER] Serper /images failed: %s", exc)
        return []


def enrich_product_images(
    products: List[Dict[str, Any]],
    query: str,
    platform_id: str,
) -> List[Dict[str, Any]]:
    """Enrich products with Google-cached thumbnail images.

    Main entry point. Feature-gated by enable_product_image_enrichment.

    Args:
        products: List of product dicts (modified in-place).
        query: Original search query.
        platform_id: Platform identifier (e.g. 'shopee', 'lazada').

    Returns:
        The same products list (modified in-place with 'image' field populated).
    """
    if not should_enrich(platform_id, products):
        return products

    site_hint = _SITE_HINTS.get(platform_id, "")

    # Fetch image results from Serper
    images = _fetch_serper_images(query, site_hint=site_hint, num=min(len(products) + 5, 20))
    if not images:
        return products

    # Get min_similarity from config (Sprint 201b: default raised to 0.4)
    min_similarity = 0.4
    try:
        from app.core.config import get_settings
        min_similarity = get_settings().image_enrichment_min_similarity
    except Exception as _e:
        logger.debug("[IMAGE_ENRICHER] Config load failed, using default min_similarity: %s", _e)

    count = _match_images_to_products(products, images, min_similarity=min_similarity)
    if count > 0:
        logger.info(
            "[IMAGE_ENRICHER] Enriched %d/%d products for %s (query=%s)",
            count, len(products), platform_id, query[:50],
        )

    return products
