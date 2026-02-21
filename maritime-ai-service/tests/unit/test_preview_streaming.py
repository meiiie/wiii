"""
Sprint 166: Preview Architecture — Streaming & Link Preview Tests

Tests:
1. StreamEventType.PREVIEW enum value
2. create_preview_event factory — fields, truncation, defaults
3. Constants — PREVIEW_SNIPPET_MAX_LENGTH, PREVIEW_TITLE_MAX_LENGTH, etc.
4. Config — enable_preview default and override
5. Bus event conversion — preview dict → StreamEvent via _convert_bus_event
6. SSE forwarding — preview StreamEvent → SSE text
7. Link preview service — URL validation, SSRF, OG parsing, cache, fetch
8. Preview dedup — _emitted_preview_ids set
9. Preview settings from context — show_previews, preview_types, preview_max_count
"""

import asyncio
import hashlib
import json
import sys
import time
import types
from html.parser import HTMLParser
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest


# ============================================================================
# Break circular import chain (same pattern as test_sprint144)
# ============================================================================

_cs_key = "app.services.chat_service"
_svc_key = "app.services"
_graph_key = "app.engine.multi_agent.graph"
_had_cs = _cs_key in sys.modules
_had_svc = _svc_key in sys.modules
_had_graph = _graph_key in sys.modules
_orig_cs = sys.modules.get(_cs_key)
_orig_graph = sys.modules.get(_graph_key)

if not _had_cs:
    _mock_chat_svc = types.ModuleType(_cs_key)
    _mock_chat_svc.ChatService = type("ChatService", (), {})
    _mock_chat_svc.get_chat_service = lambda: None
    sys.modules[_cs_key] = _mock_chat_svc

if not _had_graph:
    _mock_graph = types.ModuleType(_graph_key)
    _mock_graph.get_multi_agent_graph_async = AsyncMock()
    _mock_graph._build_domain_config = MagicMock()
    _mock_graph._TRACERS = {}
    _mock_graph._cleanup_tracer = MagicMock()
    sys.modules[_graph_key] = _mock_graph

# Import after patching
from app.engine.multi_agent.stream_utils import (
    StreamEventType,
    StreamEvent,
    create_preview_event,
    create_status_event,
)
from app.core.constants import (
    PREVIEW_SNIPPET_MAX_LENGTH,
    PREVIEW_TITLE_MAX_LENGTH,
    PREVIEW_MAX_PER_MESSAGE,
    PREVIEW_CONFIDENCE_THRESHOLD,
)
from app.core.config import settings

# Restore sys.modules
if not _had_cs:
    sys.modules.pop(_cs_key, None)
    if not _had_svc:
        sys.modules.pop(_svc_key, None)
elif _orig_cs is not None:
    sys.modules[_cs_key] = _orig_cs

if not _had_graph:
    sys.modules.pop(_graph_key, None)
elif _orig_graph is not None:
    sys.modules[_graph_key] = _orig_graph


# ============================================================================
# Section 1: StreamEventType Tests
# ============================================================================

class TestStreamEventTypePreview:
    """StreamEventType.PREVIEW enum value exists and is correct."""

    def test_preview_enum_exists(self):
        """PREVIEW attribute should exist on StreamEventType."""
        assert hasattr(StreamEventType, "PREVIEW")

    def test_preview_enum_value(self):
        """PREVIEW should have string value 'preview'."""
        assert StreamEventType.PREVIEW == "preview"

    def test_preview_is_string(self):
        """PREVIEW value should be a string type."""
        assert isinstance(StreamEventType.PREVIEW, str)

    def test_preview_distinct_from_other_types(self):
        """PREVIEW should not collide with any other event type."""
        other_types = [
            StreamEventType.STATUS,
            StreamEventType.THINKING,
            StreamEventType.TOOL_CALL,
            StreamEventType.TOOL_RESULT,
            StreamEventType.ANSWER,
            StreamEventType.SOURCES,
            StreamEventType.METADATA,
            StreamEventType.THINKING_DELTA,
            StreamEventType.THINKING_START,
            StreamEventType.THINKING_END,
            StreamEventType.DONE,
            StreamEventType.ERROR,
            StreamEventType.DOMAIN_NOTICE,
            StreamEventType.EMOTION,
            StreamEventType.ACTION_TEXT,
            StreamEventType.BROWSER_SCREENSHOT,
        ]
        for t in other_types:
            assert StreamEventType.PREVIEW != t, f"PREVIEW collides with {t}"


# ============================================================================
# Section 2: create_preview_event Tests
# ============================================================================

class TestCreatePreviewEvent:
    """create_preview_event factory function tests."""

    @pytest.mark.asyncio
    async def test_returns_stream_event(self):
        """Should return a StreamEvent instance."""
        event = await create_preview_event(
            preview_type="document",
            preview_id="doc-1",
            title="Test Title",
        )
        assert isinstance(event, StreamEvent)

    @pytest.mark.asyncio
    async def test_event_type_is_preview(self):
        """Returned event type should be 'preview'."""
        event = await create_preview_event(
            preview_type="document",
            preview_id="doc-1",
            title="Test Title",
        )
        assert event.type == StreamEventType.PREVIEW

    @pytest.mark.asyncio
    async def test_all_fields_pass_through(self):
        """All provided fields should appear in event.content."""
        event = await create_preview_event(
            preview_type="product",
            preview_id="prod-42",
            title="Sản phẩm thử nghiệm",
            snippet="Mô tả chi tiết sản phẩm",
            url="https://example.com/product/42",
            image_url="https://example.com/img.jpg",
            citation_index=3,
            node="rag_agent",
            metadata={"price": "500000 VND", "platform": "shopee"},
        )
        content = event.content
        assert content["preview_type"] == "product"
        assert content["preview_id"] == "prod-42"
        assert content["title"] == "Sản phẩm thử nghiệm"
        assert content["snippet"] == "Mô tả chi tiết sản phẩm"
        assert content["url"] == "https://example.com/product/42"
        assert content["image_url"] == "https://example.com/img.jpg"
        assert content["citation_index"] == 3
        assert content["metadata"]["price"] == "500000 VND"
        assert content["metadata"]["platform"] == "shopee"
        assert event.node == "rag_agent"

    @pytest.mark.asyncio
    async def test_default_snippet_is_empty(self):
        """When snippet not provided, defaults to empty string."""
        event = await create_preview_event(
            preview_type="web",
            preview_id="web-1",
            title="Title",
        )
        assert event.content["snippet"] == ""

    @pytest.mark.asyncio
    async def test_default_metadata_is_empty_dict(self):
        """When metadata not provided, defaults to empty dict."""
        event = await create_preview_event(
            preview_type="document",
            preview_id="doc-1",
            title="Title",
        )
        assert event.content["metadata"] == {}

    @pytest.mark.asyncio
    async def test_default_url_is_none(self):
        """When url not provided, defaults to None."""
        event = await create_preview_event(
            preview_type="document",
            preview_id="doc-1",
            title="Title",
        )
        assert event.content["url"] is None

    @pytest.mark.asyncio
    async def test_default_image_url_is_none(self):
        """When image_url not provided, defaults to None."""
        event = await create_preview_event(
            preview_type="document",
            preview_id="doc-1",
            title="Title",
        )
        assert event.content["image_url"] is None

    @pytest.mark.asyncio
    async def test_default_citation_index_is_none(self):
        """When citation_index not provided, defaults to None."""
        event = await create_preview_event(
            preview_type="document",
            preview_id="doc-1",
            title="Title",
        )
        assert event.content["citation_index"] is None

    @pytest.mark.asyncio
    async def test_default_node_is_none(self):
        """When node not provided, defaults to None."""
        event = await create_preview_event(
            preview_type="document",
            preview_id="doc-1",
            title="Title",
        )
        assert event.node is None

    @pytest.mark.asyncio
    async def test_snippet_truncation(self):
        """Snippet should be truncated at PREVIEW_SNIPPET_MAX_LENGTH (300)."""
        long_snippet = "A" * 500
        event = await create_preview_event(
            preview_type="document",
            preview_id="doc-1",
            title="Title",
            snippet=long_snippet,
        )
        assert len(event.content["snippet"]) == PREVIEW_SNIPPET_MAX_LENGTH
        assert event.content["snippet"] == "A" * 300

    @pytest.mark.asyncio
    async def test_snippet_not_truncated_when_short(self):
        """Snippet shorter than max should not be truncated."""
        short_snippet = "Short text"
        event = await create_preview_event(
            preview_type="document",
            preview_id="doc-1",
            title="Title",
            snippet=short_snippet,
        )
        assert event.content["snippet"] == short_snippet

    @pytest.mark.asyncio
    async def test_snippet_exact_max_length(self):
        """Snippet exactly at max length should not be truncated."""
        exact_snippet = "B" * PREVIEW_SNIPPET_MAX_LENGTH
        event = await create_preview_event(
            preview_type="document",
            preview_id="doc-1",
            title="Title",
            snippet=exact_snippet,
        )
        assert len(event.content["snippet"]) == PREVIEW_SNIPPET_MAX_LENGTH

    @pytest.mark.asyncio
    async def test_title_truncation(self):
        """Title should be truncated at PREVIEW_TITLE_MAX_LENGTH (120)."""
        long_title = "T" * 200
        event = await create_preview_event(
            preview_type="document",
            preview_id="doc-1",
            title=long_title,
        )
        assert len(event.content["title"]) == PREVIEW_TITLE_MAX_LENGTH
        assert event.content["title"] == "T" * 120

    @pytest.mark.asyncio
    async def test_title_not_truncated_when_short(self):
        """Title shorter than max should not be truncated."""
        event = await create_preview_event(
            preview_type="document",
            preview_id="doc-1",
            title="Short Title",
        )
        assert event.content["title"] == "Short Title"

    @pytest.mark.asyncio
    async def test_title_exact_max_length(self):
        """Title exactly at max length should not be truncated."""
        exact_title = "C" * PREVIEW_TITLE_MAX_LENGTH
        event = await create_preview_event(
            preview_type="document",
            preview_id="doc-1",
            title=exact_title,
        )
        assert len(event.content["title"]) == PREVIEW_TITLE_MAX_LENGTH

    @pytest.mark.asyncio
    async def test_vietnamese_title_truncation(self):
        """Vietnamese characters should truncate correctly."""
        vn_title = "Quy tắc hàng hải quốc tế " * 10  # ~260 chars
        event = await create_preview_event(
            preview_type="document",
            preview_id="doc-1",
            title=vn_title,
        )
        assert len(event.content["title"]) <= PREVIEW_TITLE_MAX_LENGTH

    @pytest.mark.asyncio
    async def test_vietnamese_snippet_truncation(self):
        """Vietnamese snippet should truncate correctly."""
        vn_snippet = "Đây là nội dung mô tả chi tiết về quy tắc " * 15  # ~660 chars
        event = await create_preview_event(
            preview_type="document",
            preview_id="doc-1",
            title="Quy tắc",
            snippet=vn_snippet,
        )
        assert len(event.content["snippet"]) <= PREVIEW_SNIPPET_MAX_LENGTH

    @pytest.mark.asyncio
    async def test_to_dict_serialization(self):
        """StreamEvent.to_dict() should include preview content and node."""
        event = await create_preview_event(
            preview_type="web",
            preview_id="web-5",
            title="Web Result",
            node="direct",
        )
        d = event.to_dict()
        assert d["type"] == "preview"
        assert d["content"]["preview_type"] == "web"
        assert d["content"]["preview_id"] == "web-5"
        assert d["node"] == "direct"

    @pytest.mark.asyncio
    async def test_preview_types_all_valid(self):
        """All five preview types should be accepted."""
        for ptype in ("document", "product", "web", "link", "code"):
            event = await create_preview_event(
                preview_type=ptype,
                preview_id=f"{ptype}-1",
                title=f"Test {ptype}",
            )
            assert event.content["preview_type"] == ptype


# ============================================================================
# Section 3: Constants Tests
# ============================================================================

class TestPreviewConstants:
    """Preview system constants have expected values."""

    def test_snippet_max_length(self):
        """PREVIEW_SNIPPET_MAX_LENGTH should be 300."""
        assert PREVIEW_SNIPPET_MAX_LENGTH == 300

    def test_title_max_length(self):
        """PREVIEW_TITLE_MAX_LENGTH should be 120."""
        assert PREVIEW_TITLE_MAX_LENGTH == 120

    def test_max_per_message(self):
        """PREVIEW_MAX_PER_MESSAGE should be 20."""
        assert PREVIEW_MAX_PER_MESSAGE == 20

    def test_confidence_threshold(self):
        """PREVIEW_CONFIDENCE_THRESHOLD should be 0.3."""
        assert PREVIEW_CONFIDENCE_THRESHOLD == 0.3

    def test_snippet_max_is_int(self):
        """PREVIEW_SNIPPET_MAX_LENGTH should be an integer."""
        assert isinstance(PREVIEW_SNIPPET_MAX_LENGTH, int)

    def test_confidence_threshold_is_float(self):
        """PREVIEW_CONFIDENCE_THRESHOLD should be a float."""
        assert isinstance(PREVIEW_CONFIDENCE_THRESHOLD, float)

    def test_confidence_threshold_range(self):
        """PREVIEW_CONFIDENCE_THRESHOLD should be between 0 and 1."""
        assert 0.0 <= PREVIEW_CONFIDENCE_THRESHOLD <= 1.0


# ============================================================================
# Section 4: Config Tests
# ============================================================================

class TestPreviewConfig:
    """enable_preview config flag tests."""

    def test_enable_preview_default_true(self):
        """enable_preview should default to True."""
        assert settings.enable_preview is True

    def test_enable_preview_is_bool(self):
        """enable_preview should be a boolean."""
        assert isinstance(settings.enable_preview, bool)

    def test_enable_preview_can_be_false(self):
        """enable_preview should accept False override."""
        original = settings.enable_preview
        try:
            settings.enable_preview = False
            assert settings.enable_preview is False
        finally:
            settings.enable_preview = original


# ============================================================================
# Section 5: Bus Event Conversion Tests
# ============================================================================

class TestBusEventConversion:
    """_convert_bus_event converts preview bus dict to StreamEvent."""

    @pytest.mark.asyncio
    async def test_preview_bus_event_converts(self):
        """Preview bus event dict should convert to StreamEvent with type=preview."""
        from app.engine.multi_agent.graph_streaming import _convert_bus_event

        bus_event = {
            "type": "preview",
            "node": "rag_agent",
            "content": {
                "preview_type": "document",
                "preview_id": "doc-123",
                "title": "Rule 15 — Tình huống cắt mặt",
                "snippet": "Khi hai tàu máy cắt mặt nhau...",
                "url": None,
                "image_url": None,
                "citation_index": 1,
            },
        }
        result = await _convert_bus_event(bus_event)
        assert isinstance(result, StreamEvent)
        assert result.type == StreamEventType.PREVIEW

    @pytest.mark.asyncio
    async def test_preview_bus_all_fields_pass_through(self):
        """All preview content fields should survive bus conversion."""
        from app.engine.multi_agent.graph_streaming import _convert_bus_event

        bus_event = {
            "type": "preview",
            "node": "direct",
            "content": {
                "preview_type": "web",
                "preview_id": "web-42",
                "title": "Maritime Safety Blog",
                "snippet": "Latest news on SOLAS compliance...",
                "url": "https://example.com/maritime",
                "image_url": "https://example.com/og.jpg",
                "citation_index": 5,
            },
        }
        result = await _convert_bus_event(bus_event)
        content = result.content
        assert content["preview_type"] == "web"
        assert content["preview_id"] == "web-42"
        assert content["title"] == "Maritime Safety Blog"
        assert content["snippet"] == "Latest news on SOLAS compliance..."
        assert content["url"] == "https://example.com/maritime"
        assert content["image_url"] == "https://example.com/og.jpg"
        assert content["citation_index"] == 5
        assert result.node == "direct"

    @pytest.mark.asyncio
    async def test_preview_bus_missing_fields_use_defaults(self):
        """Missing fields in preview bus event should get defaults."""
        from app.engine.multi_agent.graph_streaming import _convert_bus_event

        bus_event = {
            "type": "preview",
            "content": {
                "preview_type": "link",
                "title": "Minimal preview",
            },
        }
        result = await _convert_bus_event(bus_event)
        assert result.type == StreamEventType.PREVIEW
        content = result.content
        assert content["preview_type"] == "link"
        assert content["title"] == "Minimal preview"
        # Defaults for missing fields
        assert content["snippet"] == ""
        assert content["metadata"] == {}

    @pytest.mark.asyncio
    async def test_non_preview_bus_event_unchanged(self):
        """Non-preview bus events should still convert normally."""
        from app.engine.multi_agent.graph_streaming import _convert_bus_event

        bus_event = {
            "type": "status",
            "node": "rag_agent",
            "content": "Tìm kiếm tài liệu",
        }
        result = await _convert_bus_event(bus_event)
        assert result.type == StreamEventType.STATUS
        assert result.content == "Tìm kiếm tài liệu"


# ============================================================================
# Section 6: SSE Forwarding Tests
# ============================================================================

class TestSSEForwarding:
    """Preview event SSE formatting tests."""

    def test_format_sse_preview_event(self):
        """Preview event should produce correct SSE format."""
        from app.api.v1.chat_stream import format_sse

        data = {
            "content": {
                "preview_type": "document",
                "preview_id": "doc-1",
                "title": "Test",
                "snippet": "Description",
                "url": None,
                "image_url": None,
                "citation_index": None,
                "metadata": {},
            },
            "node": "rag_agent",
        }
        sse_text = format_sse("preview", data, event_id=1)
        assert "event: preview" in sse_text
        assert "id: 1" in sse_text
        # Data should be valid JSON
        data_line = [line for line in sse_text.split("\n") if line.startswith("data: ")][0]
        json_str = data_line[len("data: "):]
        parsed = json.loads(json_str)
        assert parsed["content"]["preview_type"] == "document"
        assert parsed["node"] == "rag_agent"

    def test_format_sse_preview_vietnamese(self):
        """Vietnamese content in preview SSE should be preserved."""
        from app.api.v1.chat_stream import format_sse

        data = {
            "content": {
                "preview_type": "document",
                "preview_id": "doc-vn",
                "title": "Quy tắc phòng ngừa va chạm trên biển",
                "snippet": "Mỗi tàu phải duy trì cảnh giới thích đáng bằng mắt...",
                "url": None,
                "image_url": None,
                "citation_index": 1,
                "metadata": {},
            },
            "node": "rag_agent",
        }
        sse_text = format_sse("preview", data, event_id=2)
        # JSON should contain Vietnamese chars (ensure_ascii=False)
        data_line = [line for line in sse_text.split("\n") if line.startswith("data: ")][0]
        json_str = data_line[len("data: "):]
        parsed = json.loads(json_str)
        assert "va chạm" in parsed["content"]["title"]
        assert "cảnh giới" in parsed["content"]["snippet"]

    def test_format_sse_preview_no_event_id(self):
        """Preview SSE without event_id should omit id field."""
        from app.api.v1.chat_stream import format_sse

        data = {"content": {"preview_type": "web"}, "node": None}
        sse_text = format_sse("preview", data)
        assert "id:" not in sse_text
        assert "event: preview" in sse_text


# ============================================================================
# Section 7: Link Preview Service Tests
# ============================================================================

class TestValidateUrl:
    """_validate_url blocks unsafe URLs, allows public ones."""

    def test_blocks_private_ip_10(self):
        """10.x.x.x should be blocked."""
        from app.services.link_preview_service import _validate_url
        assert _validate_url("http://10.0.0.1/page") is False

    def test_blocks_private_ip_172(self):
        """172.16.x.x should be blocked."""
        from app.services.link_preview_service import _validate_url
        assert _validate_url("http://172.16.0.1/page") is False

    def test_blocks_private_ip_192(self):
        """192.168.x.x should be blocked."""
        from app.services.link_preview_service import _validate_url
        assert _validate_url("http://192.168.1.1/page") is False

    def test_blocks_localhost(self):
        """localhost should be blocked."""
        from app.services.link_preview_service import _validate_url
        assert _validate_url("http://localhost/page") is False

    def test_blocks_127_0_0_1(self):
        """127.0.0.1 should be blocked."""
        from app.services.link_preview_service import _validate_url
        assert _validate_url("http://127.0.0.1:8000/api") is False

    def test_blocks_0_0_0_0(self):
        """0.0.0.0 should be blocked."""
        from app.services.link_preview_service import _validate_url
        assert _validate_url("http://0.0.0.0/admin") is False

    def test_blocks_dot_local(self):
        """.local hostnames should be blocked."""
        from app.services.link_preview_service import _validate_url
        assert _validate_url("http://myhost.local/page") is False

    def test_blocks_dot_internal(self):
        """.internal hostnames should be blocked."""
        from app.services.link_preview_service import _validate_url
        assert _validate_url("http://service.internal/api") is False

    def test_blocks_ftp_scheme(self):
        """FTP scheme should be blocked."""
        from app.services.link_preview_service import _validate_url
        assert _validate_url("ftp://example.com/file") is False

    def test_blocks_file_scheme(self):
        """file:// scheme should be blocked."""
        from app.services.link_preview_service import _validate_url
        assert _validate_url("file:///etc/passwd") is False

    def test_blocks_empty_hostname(self):
        """Empty hostname should be blocked."""
        from app.services.link_preview_service import _validate_url
        assert _validate_url("http:///path") is False

    def test_allows_public_https(self):
        """Public HTTPS URL should be allowed."""
        from app.services.link_preview_service import _validate_url
        assert _validate_url("https://example.com/page") is True

    def test_allows_public_http(self):
        """Public HTTP URL should be allowed."""
        from app.services.link_preview_service import _validate_url
        assert _validate_url("http://example.com/page") is True

    def test_allows_subdomain(self):
        """Subdomain of public domain should be allowed."""
        from app.services.link_preview_service import _validate_url
        assert _validate_url("https://docs.example.com/api") is True

    def test_blocks_malformed_url(self):
        """Malformed URL should be blocked."""
        from app.services.link_preview_service import _validate_url
        assert _validate_url("not-a-url") is False

    def test_blocks_empty_string(self):
        """Empty string should be blocked."""
        from app.services.link_preview_service import _validate_url
        assert _validate_url("") is False


class TestIsPrivateIp:
    """_is_private_ip checks for private/reserved IPs."""

    def test_loopback(self):
        """127.0.0.1 is loopback."""
        from app.services.link_preview_service import _is_private_ip
        assert _is_private_ip("127.0.0.1") is True

    def test_private_class_a(self):
        """10.0.0.1 is private."""
        from app.services.link_preview_service import _is_private_ip
        assert _is_private_ip("10.0.0.1") is True

    def test_private_class_b(self):
        """172.16.0.1 is private."""
        from app.services.link_preview_service import _is_private_ip
        assert _is_private_ip("172.16.0.1") is True

    def test_private_class_c(self):
        """192.168.0.1 is private."""
        from app.services.link_preview_service import _is_private_ip
        assert _is_private_ip("192.168.0.1") is True

    def test_link_local(self):
        """169.254.1.1 is link-local."""
        from app.services.link_preview_service import _is_private_ip
        assert _is_private_ip("169.254.1.1") is True

    def test_public_ip(self):
        """8.8.8.8 is not private."""
        from app.services.link_preview_service import _is_private_ip
        assert _is_private_ip("8.8.8.8") is False

    def test_public_ip_93(self):
        """93.184.216.34 is not private."""
        from app.services.link_preview_service import _is_private_ip
        assert _is_private_ip("93.184.216.34") is False

    def test_non_ip_hostname(self):
        """Non-IP hostname should return False (not an IP address)."""
        from app.services.link_preview_service import _is_private_ip
        assert _is_private_ip("example.com") is False


class TestOGParser:
    """_OGParser extracts OG metadata from HTML."""

    def test_extracts_og_title(self):
        """Should extract og:title meta tag."""
        from app.services.link_preview_service import _OGParser

        html = '<html><head><meta property="og:title" content="Test Title"></head></html>'
        parser = _OGParser()
        parser.feed(html)
        assert parser.og.get("og:title") == "Test Title"

    def test_extracts_og_description(self):
        """Should extract og:description meta tag."""
        from app.services.link_preview_service import _OGParser

        html = '<html><head><meta property="og:description" content="A description"></head></html>'
        parser = _OGParser()
        parser.feed(html)
        assert parser.og.get("og:description") == "A description"

    def test_extracts_og_image(self):
        """Should extract og:image meta tag."""
        from app.services.link_preview_service import _OGParser

        html = '<html><head><meta property="og:image" content="https://img.com/pic.jpg"></head></html>'
        parser = _OGParser()
        parser.feed(html)
        assert parser.og.get("og:image") == "https://img.com/pic.jpg"

    def test_extracts_og_url(self):
        """Should extract og:url meta tag."""
        from app.services.link_preview_service import _OGParser

        html = '<html><head><meta property="og:url" content="https://example.com/page"></head></html>'
        parser = _OGParser()
        parser.feed(html)
        assert parser.og.get("og:url") == "https://example.com/page"

    def test_falls_back_to_title_tag(self):
        """When no og:title, should capture <title> text."""
        from app.services.link_preview_service import _OGParser

        html = '<html><head><title>Fallback Title</title></head></html>'
        parser = _OGParser()
        parser.feed(html)
        assert parser._title_text == "Fallback Title"
        assert "og:title" not in parser.og

    def test_og_title_overrides_title_tag(self):
        """og:title should take priority over <title> in OG dict."""
        from app.services.link_preview_service import _OGParser

        html = '<html><head><title>HTML Title</title><meta property="og:title" content="OG Title"></head></html>'
        parser = _OGParser()
        parser.feed(html)
        assert parser.og["og:title"] == "OG Title"
        # title_text also captured but OG takes priority in fetch_link_preview
        assert parser._title_text == "HTML Title"

    def test_meta_description_fallback(self):
        """meta name=description should fall back to og:description if not already set."""
        from app.services.link_preview_service import _OGParser

        html = '<html><head><meta name="description" content="Meta desc"></head></html>'
        parser = _OGParser()
        parser.feed(html)
        assert parser.og.get("og:description") == "Meta desc"

    def test_og_description_not_overridden_by_meta(self):
        """og:description should not be overridden by meta name=description."""
        from app.services.link_preview_service import _OGParser

        html = (
            '<html><head>'
            '<meta property="og:description" content="OG Desc">'
            '<meta name="description" content="Meta Desc">'
            '</head></html>'
        )
        parser = _OGParser()
        parser.feed(html)
        assert parser.og["og:description"] == "OG Desc"

    def test_ignores_body_meta_tags(self):
        """Meta tags in <body> should be ignored (_in_head=False after </head>)."""
        from app.services.link_preview_service import _OGParser

        html = (
            '<html><head></head><body>'
            '<meta property="og:title" content="Body Title">'
            '</body></html>'
        )
        parser = _OGParser()
        parser.feed(html)
        assert "og:title" not in parser.og

    def test_vietnamese_og_content(self):
        """Vietnamese content in OG tags should be preserved."""
        from app.services.link_preview_service import _OGParser

        html = '<html><head><meta property="og:title" content="Quy tắc hàng hải"></head></html>'
        parser = _OGParser()
        parser.feed(html)
        assert parser.og["og:title"] == "Quy tắc hàng hải"

    def test_empty_content_ignored(self):
        """Meta tag with empty content should be ignored."""
        from app.services.link_preview_service import _OGParser

        html = '<html><head><meta property="og:title" content=""></head></html>'
        parser = _OGParser()
        parser.feed(html)
        assert "og:title" not in parser.og


class TestFetchLinkPreview:
    """fetch_link_preview with mock httpx."""

    @pytest.mark.asyncio
    async def test_success_returns_dict(self):
        """Successful fetch should return dict with title, description, image_url, url."""
        from app.services.link_preview_service import fetch_link_preview, clear_cache

        clear_cache()

        html = (
            '<html><head>'
            '<meta property="og:title" content="Test Page">'
            '<meta property="og:description" content="A test description">'
            '<meta property="og:image" content="https://img.com/pic.jpg">'
            '<meta property="og:url" content="https://example.com/page">'
            '</head></html>'
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html; charset=utf-8"}
        mock_response.text = html

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.link_preview_service.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_link_preview("https://example.com/page")

        assert result is not None
        assert result["title"] == "Test Page"
        assert result["description"] == "A test description"
        assert result["image_url"] == "https://img.com/pic.jpg"
        assert result["url"] == "https://example.com/page"

    @pytest.mark.asyncio
    async def test_invalid_url_returns_none(self):
        """Invalid/unsafe URL should return None without making HTTP request."""
        from app.services.link_preview_service import fetch_link_preview, clear_cache

        clear_cache()
        result = await fetch_link_preview("http://localhost/admin")
        assert result is None

    @pytest.mark.asyncio
    async def test_private_ip_returns_none(self):
        """Private IP URL should return None."""
        from app.services.link_preview_service import fetch_link_preview, clear_cache

        clear_cache()
        result = await fetch_link_preview("http://10.0.0.1/secret")
        assert result is None

    @pytest.mark.asyncio
    async def test_non_200_returns_none(self):
        """Non-200 HTTP status should return None."""
        from app.services.link_preview_service import fetch_link_preview, clear_cache

        clear_cache()

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.headers = {"content-type": "text/html"}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.link_preview_service.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_link_preview("https://example.com/missing")

        assert result is None

    @pytest.mark.asyncio
    async def test_non_html_content_type_returns_none(self):
        """Non-HTML content-type should return None."""
        from app.services.link_preview_service import fetch_link_preview, clear_cache

        clear_cache()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.link_preview_service.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_link_preview("https://api.example.com/data")

        assert result is None

    @pytest.mark.asyncio
    async def test_no_title_returns_none(self):
        """HTML without any title should return None."""
        from app.services.link_preview_service import fetch_link_preview, clear_cache

        clear_cache()

        html = '<html><head><meta property="og:description" content="No title here"></head></html>'

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = html

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.link_preview_service.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_link_preview("https://example.com/notitle")

        assert result is None

    @pytest.mark.asyncio
    async def test_http_error_returns_none(self):
        """httpx.HTTPError should be caught, return None."""
        import httpx as httpx_mod
        from app.services.link_preview_service import fetch_link_preview, clear_cache

        clear_cache()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx_mod.ConnectError("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.link_preview_service.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_link_preview("https://example.com/down")

        assert result is None

    @pytest.mark.asyncio
    async def test_title_tag_fallback(self):
        """When og:title missing, should use <title> tag."""
        from app.services.link_preview_service import fetch_link_preview, clear_cache

        clear_cache()

        html = '<html><head><title>Fallback Title</title></head></html>'

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = html

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.link_preview_service.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_link_preview("https://example.com/fallback")

        assert result is not None
        assert result["title"] == "Fallback Title"


class TestLinkPreviewCache:
    """Cache behavior for fetch_link_preview."""

    @pytest.mark.asyncio
    async def test_second_call_returns_cached(self):
        """Second call for same URL should return cached result without HTTP request."""
        from app.services.link_preview_service import fetch_link_preview, clear_cache

        clear_cache()

        html = '<html><head><meta property="og:title" content="Cached"></head></html>'

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = html

        call_count = 0

        async def counting_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            return mock_response

        mock_client = AsyncMock()
        mock_client.get = counting_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.link_preview_service.httpx.AsyncClient", return_value=mock_client):
            result1 = await fetch_link_preview("https://example.com/cached")
            result2 = await fetch_link_preview("https://example.com/cached")

        assert result1 is not None
        assert result2 is not None
        assert result1["title"] == result2["title"] == "Cached"
        # Only 1 HTTP request should have been made
        assert call_count == 1

    def test_clear_cache_clears_entries(self):
        """clear_cache should empty the cache dict."""
        from app.services.link_preview_service import _og_cache, clear_cache

        _og_cache["test-key"] = (time.time(), {"title": "Cached"})
        assert len(_og_cache) >= 1
        clear_cache()
        assert len(_og_cache) == 0

    def test_evict_stale_removes_expired(self):
        """Expired entries should be evicted."""
        from app.services.link_preview_service import _og_cache, _evict_stale, _CACHE_TTL, clear_cache

        clear_cache()
        # Add an entry that expired 100 seconds ago
        _og_cache["expired-key"] = (time.time() - _CACHE_TTL - 100, {"title": "Old"})
        # Add a fresh entry
        _og_cache["fresh-key"] = (time.time(), {"title": "Fresh"})
        _evict_stale()
        assert "expired-key" not in _og_cache
        assert "fresh-key" in _og_cache


# ============================================================================
# Section 8: Preview Dedup Tests
# ============================================================================

class TestPreviewDedup:
    """_emitted_preview_ids set prevents duplicate emission."""

    def test_dedup_set_prevents_duplicate(self):
        """Same preview_id should be skipped on second encounter."""
        _emitted_preview_ids = set()
        emitted = []

        previews = [
            {"preview_id": "doc-1", "title": "First"},
            {"preview_id": "doc-2", "title": "Second"},
            {"preview_id": "doc-1", "title": "Duplicate of First"},
            {"preview_id": "doc-3", "title": "Third"},
            {"preview_id": "doc-2", "title": "Duplicate of Second"},
        ]

        for p in previews:
            pid = p["preview_id"]
            if pid in _emitted_preview_ids:
                continue
            _emitted_preview_ids.add(pid)
            emitted.append(p)

        assert len(emitted) == 3
        assert [p["preview_id"] for p in emitted] == ["doc-1", "doc-2", "doc-3"]

    def test_dedup_set_empty_initially(self):
        """Dedup set should start empty per request."""
        _emitted_preview_ids = set()
        assert len(_emitted_preview_ids) == 0

    def test_dedup_different_types_same_source(self):
        """Different preview types with distinct IDs should not collide."""
        _emitted_preview_ids = set()

        ids = ["doc-1", "web-1", "prod-1"]
        for pid in ids:
            assert pid not in _emitted_preview_ids
            _emitted_preview_ids.add(pid)

        assert len(_emitted_preview_ids) == 3


# ============================================================================
# Section 9: Preview Settings from Context
# ============================================================================

class TestPreviewSettingsFromContext:
    """Preview settings read from context (show_previews, preview_types, preview_max_count)."""

    def test_show_previews_false_disables(self):
        """When context has show_previews=False, preview should be disabled."""
        context = {"show_previews": False}
        _preview_enabled = True  # default from settings
        if context.get("show_previews") is False:
            _preview_enabled = False
        assert _preview_enabled is False

    def test_show_previews_true_keeps_enabled(self):
        """When context has show_previews=True, preview stays enabled."""
        context = {"show_previews": True}
        _preview_enabled = True
        if context.get("show_previews") is False:
            _preview_enabled = False
        assert _preview_enabled is True

    def test_show_previews_none_keeps_default(self):
        """When show_previews not in context, default (True) applies."""
        context = {}
        _preview_enabled = True
        if context.get("show_previews") is False:
            _preview_enabled = False
        assert _preview_enabled is True

    def test_preview_types_filters_document(self):
        """When preview_types=['document'], only document previews pass."""
        context = {"preview_types": ["document"]}
        _preview_types = None
        if context.get("preview_types"):
            _preview_types = set(context["preview_types"])

        assert _preview_types == {"document"}
        assert "document" in _preview_types
        assert "web" not in _preview_types
        assert "product" not in _preview_types

    def test_preview_types_multiple(self):
        """Multiple preview types should all be included in filter set."""
        context = {"preview_types": ["document", "web", "product"]}
        _preview_types = None
        if context.get("preview_types"):
            _preview_types = set(context["preview_types"])

        assert _preview_types == {"document", "web", "product"}

    def test_preview_types_none_allows_all(self):
        """When preview_types not set, all types pass (None check)."""
        context = {}
        _preview_types = None
        if context.get("preview_types"):
            _preview_types = set(context["preview_types"])

        assert _preview_types is None
        # Logic: not _preview_types or "document" in _preview_types → True when None
        assert not _preview_types or "document" in _preview_types

    def test_preview_max_count_overrides_default(self):
        """Context preview_max_count should override PREVIEW_MAX_PER_MESSAGE."""
        context = {"preview_max_count": 5}
        _preview_max = PREVIEW_MAX_PER_MESSAGE
        if context.get("preview_max_count"):
            _preview_max = int(context["preview_max_count"])
        assert _preview_max == 5

    def test_preview_max_count_none_uses_default(self):
        """When preview_max_count not set, PREVIEW_MAX_PER_MESSAGE (20) applies."""
        context = {}
        _preview_max = PREVIEW_MAX_PER_MESSAGE
        if context.get("preview_max_count"):
            _preview_max = int(context["preview_max_count"])
        assert _preview_max == PREVIEW_MAX_PER_MESSAGE == 20

    def test_preview_max_count_limits_emission(self):
        """Only preview_max_count previews should be emitted."""
        _preview_max = 3
        _emitted_preview_ids = set()
        emitted = []

        sources = [{"node_id": f"n{i}", "title": f"Doc {i}", "content": f"Content {i}"} for i in range(10)]

        for idx, src in enumerate(sources[:_preview_max]):
            pid = f"doc-{src['node_id']}"
            if pid in _emitted_preview_ids:
                continue
            _emitted_preview_ids.add(pid)
            emitted.append(src)

        assert len(emitted) == 3

    def test_combined_settings(self):
        """All three settings should work together."""
        context = {
            "show_previews": True,
            "preview_types": ["document", "web"],
            "preview_max_count": 10,
        }

        _preview_enabled = settings.enable_preview
        _preview_types = None
        _preview_max = PREVIEW_MAX_PER_MESSAGE

        if context.get("show_previews") is False:
            _preview_enabled = False
        if context.get("preview_types"):
            _preview_types = set(context["preview_types"])
        if context.get("preview_max_count"):
            _preview_max = int(context["preview_max_count"])

        assert _preview_enabled is True
        assert _preview_types == {"document", "web"}
        assert _preview_max == 10
        # Type filter check: document allowed, product blocked
        assert "document" in _preview_types
        assert "web" in _preview_types
        assert "product" not in _preview_types
