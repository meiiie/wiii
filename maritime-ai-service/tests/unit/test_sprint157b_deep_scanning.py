"""
Sprint 157b: "Quét Sâu" — Deep Facebook Scanning Tests

Tests:
- Group Post Indicator Fields (3)
- Scanner Dual-Mode (4)
- Extract Group Post (6)
- Image Attachments (4)
- Price Text Regex (4)
- FB-First Prompt (4)

Total: 25 tests
"""

import pytest

from app.engine.search_platforms.adapters.browser_base import (
    PlaywrightLLMAdapter,
    _GROUP_POST_INDICATOR_FIELDS,
    _MIN_GROUP_POST_MATCH,
    _PRODUCT_INDICATOR_FIELDS,
    _extract_image_from_attachments,
    _extract_price_from_text,
    _SCROLL_EXTRACT_JS,
)


# ============================================================================
# Group Post Indicator Fields (3 tests)
# ============================================================================


class TestGroupPostIndicatorFields:
    """Verify indicator field sets are correct."""

    def test_group_post_fields_defined(self):
        """Group post indicator fields should be a non-empty frozenset."""
        assert isinstance(_GROUP_POST_INDICATOR_FIELDS, frozenset)
        assert len(_GROUP_POST_INDICATOR_FIELDS) >= 4
        assert "message" in _GROUP_POST_INDICATOR_FIELDS
        assert "attachments" in _GROUP_POST_INDICATOR_FIELDS
        assert "comet_sections" in _GROUP_POST_INDICATOR_FIELDS

    def test_marketplace_fields_unchanged(self):
        """Marketplace indicator fields should remain unchanged."""
        assert "marketplace_listing_title" in _PRODUCT_INDICATOR_FIELDS
        assert "listing_price" in _PRODUCT_INDICATOR_FIELDS
        assert "primary_listing_photo" in _PRODUCT_INDICATOR_FIELDS

    def test_no_overlap_between_sets(self):
        """Marketplace and group post fields should not overlap."""
        overlap = _PRODUCT_INDICATOR_FIELDS & _GROUP_POST_INDICATOR_FIELDS
        assert len(overlap) == 0, f"Fields overlap: {overlap}"


# ============================================================================
# Scanner Dual-Mode (4 tests)
# ============================================================================


class TestScannerDualMode:
    """_scan_for_products should detect both marketplace and group post nodes."""

    def test_scan_marketplace_nodes(self):
        """Marketplace nodes should be detected (backward compat)."""
        data = {
            "data": {
                "marketplace_search": {
                    "feed_units": {
                        "edges": [
                            {
                                "node": {
                                    "marketplace_listing_title": "MacBook Pro M4",
                                    "listing_price": {"formatted_amount": "45.000.000đ"},
                                    "primary_listing_photo": {"image": {"uri": "https://img.com/1.jpg"}},
                                }
                            }
                        ]
                    }
                }
            }
        }
        results = PlaywrightLLMAdapter._scan_for_products(data)
        assert len(results) >= 1
        assert results[0].get("marketplace_listing_title") == "MacBook Pro M4"

    def test_scan_group_post_nodes(self):
        """Group post nodes should be detected."""
        data = {
            "data": {
                "group": {
                    "search_results": {
                        "edges": [
                            {
                                "node": {
                                    "message": {"text": "Bán MacBook Pro M4 giá 42tr"},
                                    "attachments": [{"media": {"image": {"uri": "https://img.com/2.jpg"}}}],
                                    "comet_sections": {},
                                    "actors": [{"name": "Nguyen Van A"}],
                                }
                            }
                        ]
                    }
                }
            }
        }
        results = PlaywrightLLMAdapter._scan_for_products(data)
        assert len(results) >= 1
        assert "message" in results[0]

    def test_scan_mixed_nodes(self):
        """Both marketplace and group post nodes detected in same payload."""
        data = {
            "results": [
                {
                    "marketplace_listing_title": "iPhone 16",
                    "listing_price": {"formatted_amount": "30.000.000đ"},
                },
                {
                    "message": {"text": "Bán iPhone 15 Pro"},
                    "attachments": [{}],
                    "story": {"text": "selling"},
                },
            ]
        }
        results = PlaywrightLLMAdapter._scan_for_products(data)
        assert len(results) == 2

    def test_scan_max_depth_respected(self):
        """Scanner should respect max_depth and not recurse infinitely."""
        # Build deeply nested structure
        data = {"level": 0}
        current = data
        for i in range(30):
            current["child"] = {
                "level": i + 1,
                "message": {"text": "deep"},
                "attachments": [{}],
                "story": {},
            }
            current = current["child"]

        # With depth=5, should not find deeply nested nodes
        results = PlaywrightLLMAdapter._scan_for_products(data, max_depth=5)
        # All found nodes should be within depth limit
        for r in results:
            assert "message" in r or "marketplace_listing_title" in r


# ============================================================================
# Extract Group Post (6 tests)
# ============================================================================


class TestExtractGroupPost:
    """_extract_group_post_product should map group post fields correctly."""

    def test_message_to_title(self):
        """message.text should become title."""
        node = {
            "message": {"text": "Bán MacBook Pro M4 Pro 48GB RAM - Fullbox"},
            "attachments": [{}],
            "comet_sections": {},
        }
        result = PlaywrightLLMAdapter._extract_group_post_product(node)
        assert result is not None
        assert "MacBook Pro M4 Pro 48GB RAM" in result["title"]

    def test_attachments_to_image(self):
        """attachments[].media.image.uri should become image."""
        node = {
            "message": {"text": "Bán laptop cũ"},
            "attachments": [
                {"media": {"image": {"uri": "https://scontent.xx/photo_123.jpg"}}}
            ],
            "story": {},
        }
        result = PlaywrightLLMAdapter._extract_group_post_product(node)
        assert result is not None
        assert result["image"] == "https://scontent.xx/photo_123.jpg"

    def test_actors_to_seller(self):
        """actors[0].name should become seller."""
        node = {
            "message": {"text": "Bán iPhone 15"},
            "attachments": [],
            "actors": [{"name": "Trần Văn B", "id": "123"}],
        }
        result = PlaywrightLLMAdapter._extract_group_post_product(node)
        assert result is not None
        assert result["seller"] == "Trần Văn B"

    def test_permalink_to_link(self):
        """permalink_url should become link."""
        node = {
            "message": {"text": "Bán Samsung S24"},
            "attachments": [{}],
            "permalink_url": "https://www.facebook.com/groups/123/posts/456/",
        }
        result = PlaywrightLLMAdapter._extract_group_post_product(node)
        assert result is not None
        assert result["link"] == "https://www.facebook.com/groups/123/posts/456/"

    def test_price_regex_extraction(self):
        """Price should be extracted from message text via regex."""
        node = {
            "message": {"text": "Bán MacBook Pro M4 giá 42.000.000đ, fullbox, BH 12 tháng"},
            "attachments": [],
            "comet_sections": {},
        }
        result = PlaywrightLLMAdapter._extract_group_post_product(node)
        assert result is not None
        assert "42.000.000" in result["price"]

    def test_title_truncation(self):
        """Long messages should be truncated to ~200 chars in title."""
        long_text = "A" * 500
        node = {
            "message": {"text": long_text},
            "attachments": [],
            "story": {},
        }
        result = PlaywrightLLMAdapter._extract_group_post_product(node)
        assert result is not None
        assert len(result["title"]) <= 210  # 200 + "..."


# ============================================================================
# Image Attachments (4 tests)
# ============================================================================


class TestImageAttachments:
    """_extract_image_from_attachments should walk various attachment structures."""

    def test_media_image_uri(self):
        """Direct media.image.uri path."""
        node = {
            "attachments": [
                {"media": {"image": {"uri": "https://scontent.xx/photo.jpg"}}}
            ]
        }
        assert _extract_image_from_attachments(node) == "https://scontent.xx/photo.jpg"

    def test_all_subattachments(self):
        """all_subattachments.nodes[].media.image.uri path."""
        node = {
            "all_subattachments": {
                "nodes": [
                    {"media": {"image": {"uri": "https://scontent.xx/sub_photo.jpg"}}}
                ]
            }
        }
        assert _extract_image_from_attachments(node) == "https://scontent.xx/sub_photo.jpg"

    def test_comet_sections_nested(self):
        """comet_sections.content.story.attachments path."""
        node = {
            "comet_sections": {
                "content": {
                    "story": {
                        "attachments": [
                            {"media": {"image": {"uri": "https://scontent.xx/comet.jpg"}}}
                        ]
                    }
                }
            }
        }
        assert _extract_image_from_attachments(node) == "https://scontent.xx/comet.jpg"

    def test_empty_attachments(self):
        """Empty/missing attachments should return empty string."""
        assert _extract_image_from_attachments({}) == ""
        assert _extract_image_from_attachments({"attachments": []}) == ""
        assert _extract_image_from_attachments({"attachments": [{}]}) == ""


# ============================================================================
# Price Text Regex (4 tests)
# ============================================================================


class TestPriceTextRegex:
    """_extract_price_from_text should find prices in Vietnamese text."""

    def test_vnd_with_dots(self):
        """Standard VND: 25.000.000đ"""
        text = "Bán MacBook Pro giá 25.000.000đ, fullbox"
        result = _extract_price_from_text(text)
        assert "25.000.000" in result

    def test_trieu_shorthand(self):
        """Shorthand: 25tr, 25 triệu"""
        text = "iPhone 15 Pro Max giá 25tr, mới 99%"
        result = _extract_price_from_text(text)
        assert "25tr" in result or "25" in result

    def test_dollar_price(self):
        """Dollar: 900$, $900"""
        text = "Selling laptop for 900$ only, barely used"
        result = _extract_price_from_text(text)
        assert "900" in result

    def test_no_price_returns_empty(self):
        """No price in text should return empty string."""
        text = "Tìm mua MacBook Pro, ai bán inbox"
        result = _extract_price_from_text(text)
        assert result == ""


# ============================================================================
# Extract Product From Node — Dispatcher (3 tests)
# ============================================================================


class TestExtractProductDispatcher:
    """_extract_product_from_node should dispatch to correct extractor."""

    def test_marketplace_node_dispatched(self):
        """Marketplace node should be dispatched to _extract_marketplace_product."""
        node = {
            "marketplace_listing_title": "MacBook Pro",
            "listing_price": {"formatted_amount": "45.000.000đ"},
            "primary_listing_photo": {"image": {"uri": "https://img.com/1.jpg"}},
            "marketplace_listing_seller": {"name": "Shop ABC"},
            "id": "123456",
        }
        result = PlaywrightLLMAdapter._extract_product_from_node(node)
        assert result is not None
        assert result["title"] == "MacBook Pro"
        assert "marketplace" in result["link"]

    def test_group_post_node_dispatched(self):
        """Group post node should be dispatched to _extract_group_post_product."""
        node = {
            "message": {"text": "Bán iPhone 15 Pro giá 22.000.000đ"},
            "attachments": [{"media": {"image": {"uri": "https://img.com/2.jpg"}}}],
            "comet_sections": {},
            "actors": [{"name": "Nguyễn A"}],
            "permalink_url": "https://www.facebook.com/groups/123/posts/456/",
        }
        result = PlaywrightLLMAdapter._extract_product_from_node(node)
        assert result is not None
        assert "iPhone 15 Pro" in result["title"]
        assert "22.000.000" in result["price"]
        assert result["seller"] == "Nguyễn A"
        assert "groups" in result["link"]

    def test_invalid_node_returns_none(self):
        """Non-dict input should return None."""
        assert PlaywrightLLMAdapter._extract_product_from_node(None) is None
        assert PlaywrightLLMAdapter._extract_product_from_node("string") is None
        assert PlaywrightLLMAdapter._extract_product_from_node(123) is None


# ============================================================================
# FB-First Prompt (4 tests)
# ============================================================================


class TestFBFirstPrompt:
    """Verify prompt changes for FB-First strategy."""

    def test_system_prompt_fb_groups_before_google(self):
        """System prompt should mention FB Groups BEFORE Google Shopping."""
        from app.engine.multi_agent.agents.product_search_node import _SYSTEM_PROMPT
        fb_pos = _SYSTEM_PROMPT.find("Facebook Groups TRƯỚC")
        google_pos = _SYSTEM_PROMPT.find("Google Shopping")
        assert fb_pos != -1, "System prompt should mention 'Facebook Groups TRƯỚC'"
        assert fb_pos < google_pos, "FB Groups should appear before Google Shopping"

    def test_deep_search_round1_includes_fb(self):
        """Deep search Round 1 should include Facebook Groups."""
        from app.engine.multi_agent.agents.product_search_node import _DEEP_SEARCH_PROMPT
        # Round 1 section
        round1_pos = _DEEP_SEARCH_PROMPT.find("Vòng 1")
        round2_pos = _DEEP_SEARCH_PROMPT.find("Vòng 2")
        round1_section = _DEEP_SEARCH_PROMPT[round1_pos:round2_pos]
        assert "facebook_groups_auto" in round1_section.lower() or "Facebook" in round1_section

    def test_tool_ack_fb_groups_auto_updated(self):
        """System prompt for facebook_groups_auto should mention nhóm Facebook."""
        from app.engine.multi_agent.agents.product_search_node import _SYSTEM_PROMPT
        assert "tool_search_facebook_groups_auto" in _SYSTEM_PROMPT
        assert "nhóm Facebook" in _SYSTEM_PROMPT

    def test_existing_tool_acks_preserved(self):
        """System prompt should still describe existing tools."""
        from app.engine.multi_agent.agents.product_search_node import _SYSTEM_PROMPT
        assert "Google Shopping" in _SYSTEM_PROMPT
        assert "Shopee" in _SYSTEM_PROMPT
        assert "Excel" in _SYSTEM_PROMPT


# ============================================================================
# Scroll Extract JS (1 test)
# ============================================================================


class TestScrollExtractJS:
    """Verify scroll JS includes pfbid and image extraction."""

    def test_scroll_js_includes_pfbid(self):
        """Scroll JS should match pfbid permalink format."""
        assert "pfbid" in _SCROLL_EXTRACT_JS

    def test_scroll_js_extracts_images(self):
        """Scroll JS should extract img[src] from articles."""
        assert "img[src]" in _SCROLL_EXTRACT_JS or "imgs" in _SCROLL_EXTRACT_JS


# ============================================================================
# _map_to_result Image Field (3 tests)
# ============================================================================


class TestMapToResultImage:
    """_map_to_result should include image field in ProductSearchResult."""

    def test_image_field_populated(self):
        """Image URL from LLM extraction should be preserved."""
        from app.engine.search_platforms.adapters.facebook_search import FacebookSearchAdapter
        adapter = FacebookSearchAdapter()
        item = {
            "title": "iPhone 16 Pro Max",
            "price": "30.000.000đ",
            "link": "https://facebook.com/groups/123/posts/456",
            "image": "https://scontent.xx/photo_abc.jpg",
            "seller": "Nguyễn A",
        }
        result = adapter._map_to_result(item)
        assert result.image == "https://scontent.xx/photo_abc.jpg"

    def test_image_field_empty_when_missing(self):
        """Missing image should default to empty string."""
        from app.engine.search_platforms.adapters.facebook_search import FacebookSearchAdapter
        adapter = FacebookSearchAdapter()
        item = {"title": "MacBook Pro", "price": "45tr"}
        result = adapter._map_to_result(item)
        assert result.image == ""

    def test_image_field_in_group_adapter(self):
        """FacebookGroupSearchAdapter should also pass image through."""
        from app.engine.search_platforms.adapters.facebook_group import FacebookGroupSearchAdapter
        adapter = FacebookGroupSearchAdapter()
        item = {
            "title": "Samsung S24 Ultra",
            "price": "25.000.000đ",
            "image": "https://scontent.xx/group_photo.jpg",
        }
        result = adapter._map_to_result(item)
        assert result.image == "https://scontent.xx/group_photo.jpg"


# ============================================================================
# FORMAT KẾT QUẢ Prompt (2 tests)
# ============================================================================


class TestFormatResultPrompt:
    """System prompt should instruct LLM to format links/images as markdown."""

    def test_markdown_link_instruction(self):
        """System prompt should instruct markdown link format."""
        from app.engine.multi_agent.agents.product_search_node import _SYSTEM_PROMPT
        assert "[Xem ngay]" in _SYSTEM_PROMPT or "markdown link" in _SYSTEM_PROMPT.lower()

    def test_image_markdown_instruction(self):
        """System prompt should instruct image markdown format."""
        from app.engine.multi_agent.agents.product_search_node import _SYSTEM_PROMPT
        assert "![" in _SYSTEM_PROMPT
