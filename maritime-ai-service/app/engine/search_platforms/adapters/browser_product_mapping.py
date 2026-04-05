import json
import re
from typing import Optional

from app.engine.search_platforms.base import ProductSearchResult

_PRODUCT_INDICATOR_FIELDS = frozenset(
    {
        "marketplace_listing_title",
        "listing_price",
        "primary_listing_photo",
        "marketplace_listing_seller",
    }
)
_MIN_INDICATOR_MATCH = 2

_GROUP_POST_INDICATOR_FIELDS = frozenset(
    {
        "message",
        "story",
        "comet_sections",
        "attached_story",
        "attachments",
    }
)
_MIN_GROUP_POST_MATCH = 2

_PRICE_PATTERNS = [
    re.compile(
        r"(\d{1,3}(?:\.\d{3})+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(\d+[.,]?\d*)\s*(?:tr\b|trieu\b|tri\S{0,8}\b)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:\$\s*(\d[\d,.]*)|(\d[\d,.]*)\s*(?:\$|USD|usd))",
        re.IGNORECASE,
    ),
    re.compile(
        r"(\d{6,})\s*(?:dong|vnd)",
        re.IGNORECASE,
    ),
]


def extract_json_array(text: str) -> list:
    """Extract the first JSON array from a model response."""
    if not text:
        return []

    text = text.strip()
    if text.startswith("["):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    fence_match = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", text)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    arr_match = re.search(r"\[[\s\S]*\]", text)
    if arr_match:
        try:
            return json.loads(arr_match.group(0))
        except json.JSONDecodeError:
            pass

    return []


def parse_vnd_price(price_str: str) -> Optional[float]:
    """Parse a VND price string via the shared search utility."""
    from app.engine.search_platforms.utils import parse_vnd_price as _parse

    return _parse(price_str)


def extract_price_from_text(text: str) -> str:
    """Extract the first free-text price mention from a post body."""
    if not text:
        return ""
    for pattern in _PRICE_PATTERNS:
        match = pattern.search(text)
        if match:
            return (match.group(1) or match.group(0)).strip()
    return ""


def dig_image_uri(attachment: dict) -> str:
    """Dig into an attachment payload for a usable image URI."""
    if not isinstance(attachment, dict):
        return ""
    media = attachment.get("media")
    if not isinstance(media, dict):
        return ""

    image = media.get("image")
    if isinstance(image, dict):
        uri = image.get("uri", "")
        if uri:
            return uri

    photo = media.get("photo")
    if isinstance(photo, dict):
        photo_image = photo.get("image")
        if isinstance(photo_image, dict):
            uri = photo_image.get("uri", "")
            if uri:
                return uri

    uri = media.get("uri", "")
    return uri or ""


def extract_image_from_attachments(node: dict) -> str:
    """Walk Facebook group-post attachment layouts for the first image URI."""
    if not isinstance(node, dict):
        return ""

    attachments = node.get("attachments")
    if isinstance(attachments, list):
        for attachment in attachments:
            uri = dig_image_uri(attachment)
            if uri:
                return uri

    subattachments = node.get("all_subattachments")
    if isinstance(subattachments, dict):
        nodes = subattachments.get("nodes", [])
        if isinstance(nodes, list):
            for subnode in nodes:
                uri = dig_image_uri(subnode)
                if uri:
                    return uri

    comet_sections = node.get("comet_sections")
    if isinstance(comet_sections, dict):
        content = comet_sections.get("content")
        if isinstance(content, dict):
            story = content.get("story")
            if isinstance(story, dict):
                inner_attachments = story.get("attachments")
                if isinstance(inner_attachments, list):
                    for attachment in inner_attachments:
                        uri = dig_image_uri(attachment)
                        if uri:
                            return uri

    return ""


def scan_for_products(data, max_depth: int = 20) -> list:
    """Recursively scan JSON for marketplace or group-post product nodes."""
    results = []

    def _walk(obj, depth: int) -> None:
        if depth <= 0:
            return
        if isinstance(obj, dict):
            marketplace_match = sum(1 for key in obj if key in _PRODUCT_INDICATOR_FIELDS)
            group_match = sum(1 for key in obj if key in _GROUP_POST_INDICATOR_FIELDS)
            if (
                marketplace_match >= _MIN_INDICATOR_MATCH
                or group_match >= _MIN_GROUP_POST_MATCH
            ):
                results.append(obj)
            for value in obj.values():
                if isinstance(value, (dict, list)):
                    _walk(value, depth - 1)
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, (dict, list)):
                    _walk(item, depth - 1)

    _walk(data, max_depth)
    return results


def extract_marketplace_product(node: dict) -> Optional[dict]:
    """Map a marketplace GraphQL node to a normalized product dict."""
    title = (
        node.get("marketplace_listing_title")
        or node.get("name")
        or node.get("title")
    )
    if not title:
        return None

    price = ""
    price_obj = node.get("listing_price")
    if isinstance(price_obj, dict):
        price = price_obj.get("formatted_amount", "")
        if not price:
            amount = price_obj.get("amount")
            currency = price_obj.get("currency", "")
            if amount is not None:
                price = f"{amount} {currency}".strip()

    image = ""
    photo = node.get("primary_listing_photo")
    if isinstance(photo, dict):
        image_obj = photo.get("image")
        if isinstance(image_obj, dict):
            image = image_obj.get("uri", "")
        elif isinstance(photo.get("uri"), str):
            image = photo["uri"]

    seller = ""
    seller_obj = node.get("marketplace_listing_seller")
    if isinstance(seller_obj, dict):
        seller = seller_obj.get("name", "")

    location = ""
    location_obj = node.get("location")
    if isinstance(location_obj, dict):
        geocode = location_obj.get("reverse_geocode")
        if isinstance(geocode, dict):
            city_page = geocode.get("city_page")
            if isinstance(city_page, dict):
                location = city_page.get("name", "")
            elif isinstance(geocode.get("city"), str):
                location = geocode["city"]

    link = ""
    listing_id = (
        node.get("id")
        or node.get("listing_id")
        or node.get("marketplace_listing_id")
    )
    if listing_id:
        link = f"https://www.facebook.com/marketplace/item/{listing_id}/"

    return {
        "title": str(title),
        "price": str(price),
        "image": str(image),
        "seller": str(seller),
        "location": str(location),
        "link": str(link),
    }


def extract_group_post_product(node: dict) -> Optional[dict]:
    """Map a Facebook group-post GraphQL node to a normalized product dict."""
    title = ""
    message = node.get("message")
    if isinstance(message, dict):
        title = message.get("text", "")
    elif isinstance(message, str):
        title = message

    if not title:
        story = node.get("story")
        if isinstance(story, dict):
            title = story.get("text", "")
        elif isinstance(story, str):
            title = story

    if not title:
        return None

    full_text = title
    if len(title) > 200:
        title = title[:200] + "..."

    seller = ""
    actors = node.get("actors")
    if isinstance(actors, list) and actors:
        first_actor = actors[0]
        if isinstance(first_actor, dict):
            seller = first_actor.get("name", "")
    actor = node.get("actor")
    if not seller and isinstance(actor, dict):
        seller = actor.get("name", "")

    link = ""
    for field in ("permalink_url", "url"):
        value = node.get(field)
        if isinstance(value, str) and value:
            link = value
            break
    if not link:
        story = node.get("story")
        if isinstance(story, dict):
            link = story.get("url", "")

    return {
        "title": str(title),
        "price": str(extract_price_from_text(full_text)),
        "image": str(extract_image_from_attachments(node)),
        "seller": str(seller),
        "location": "",
        "link": str(link),
    }


def extract_product_from_node(node: dict) -> Optional[dict]:
    """Dispatch to the marketplace or group-post extractor."""
    if not isinstance(node, dict):
        return None

    marketplace_match = sum(1 for key in node if key in _PRODUCT_INDICATOR_FIELDS)
    group_match = sum(1 for key in node if key in _GROUP_POST_INDICATOR_FIELDS)

    if marketplace_match >= _MIN_INDICATOR_MATCH:
        return extract_marketplace_product(node)
    if group_match >= _MIN_GROUP_POST_MATCH:
        return extract_group_post_product(node)
    return extract_marketplace_product(node)


def map_intercepted_to_result(platform_name: str, item: dict) -> ProductSearchResult:
    """Map an intercepted GraphQL product dict to a search result."""
    price_str = item.get("price", "")
    return ProductSearchResult(
        platform=platform_name,
        title=item.get("title", ""),
        price=price_str,
        extracted_price=parse_vnd_price(price_str) if price_str else None,
        link=item.get("link", ""),
        seller=item.get("seller", ""),
        image=item.get("image", ""),
        location=item.get("location", ""),
        source="graphql_intercept",
    )


def map_llm_item_to_result(platform_name: str, item: dict) -> ProductSearchResult:
    """Map an LLM-extracted dict to a search result."""
    price_str = str(item.get("price", ""))
    return ProductSearchResult(
        platform=platform_name,
        title=str(item.get("title", "")),
        price=price_str,
        extracted_price=parse_vnd_price(price_str),
        link=str(item.get("link", "")),
        image=str(item.get("image", "")),
        seller=str(item.get("seller", "")),
        location=str(item.get("location", "")),
        snippet=str(item.get("description", "")),
    )
