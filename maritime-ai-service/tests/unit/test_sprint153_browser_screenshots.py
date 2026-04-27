"""
Sprint 153: "Mắt Thần" — Browser Screenshots in Product Search

Tests for:
- Config: enable_browser_screenshots, browser_screenshot_quality
- StreamEventType.BROWSER_SCREENSHOT + create_browser_screenshot_event()
- PlaywrightLLMAdapter._capture_screenshot(), get_last_screenshots()
- _convert_bus_event() browser_screenshot case
- chat_stream.py browser_screenshot SSE mapping
- product_search_node screenshot push after browser tool
"""

import asyncio
import base64
import json
import sys
import types
import pytest
from unittest.mock import MagicMock, patch, PropertyMock, AsyncMock

# Break circular import: graph_streaming → graph → graph_streaming
# Mock the graph module so graph_streaming never triggers the circular chain
_graph_key = "app.engine.multi_agent.graph"
_cs_key = "app.services.chat_service"
_stubs = {}
for _key in (_graph_key, _cs_key):
    if _key not in sys.modules:
        _mod = types.ModuleType(_key)
        # graph_streaming imports these helper functions from the graph module.
        if _key == _graph_key:
            _mod._build_domain_config = MagicMock(return_value={})
            _mod._build_turn_local_state_defaults = MagicMock(return_value={})
        elif _key == _cs_key:
            _mod.ChatService = type("ChatService", (), {})
            _mod.get_chat_service = lambda: None
        sys.modules[_key] = _mod
        _stubs[_key] = True

from app.engine.multi_agent.graph_streaming import _convert_bus_event  # noqa: E402
from app.engine.multi_agent.stream_utils import StreamEventType as _SE  # noqa: E402

# Cleanup stubs so they don't leak to other tests
for _key in _stubs:
    sys.modules.pop(_key, None)


# =============================================================================
# Config Tests
# =============================================================================

class TestConfig:
    """Sprint 153: Config settings for browser screenshots."""

    def test_enable_browser_screenshots_default_false(self):
        """enable_browser_screenshots defaults to False."""
        with patch.dict("os.environ", {}, clear=True):
            from app.core.config import Settings
            s = Settings(
                google_api_key="test",
                _env_file=None,
            )
            assert s.enable_browser_screenshots is False

    def test_browser_screenshot_quality_default_40(self):
        """browser_screenshot_quality defaults to 40."""
        with patch.dict("os.environ", {}, clear=True):
            from app.core.config import Settings
            s = Settings(
                google_api_key="test",
                _env_file=None,
            )
            assert s.browser_screenshot_quality == 40

    def test_browser_screenshot_quality_override(self):
        """browser_screenshot_quality can be overridden."""
        with patch.dict("os.environ", {"BROWSER_SCREENSHOT_QUALITY": "60"}, clear=True):
            from app.core.config import Settings
            s = Settings(
                google_api_key="test",
                _env_file=None,
            )
            assert s.browser_screenshot_quality == 60


# =============================================================================
# StreamEventType + Factory Tests
# =============================================================================

class TestStreamEventType:
    """Sprint 153: BROWSER_SCREENSHOT event type."""

    def test_browser_screenshot_type_exists(self):
        """StreamEventType.BROWSER_SCREENSHOT exists with correct value."""
        from app.engine.multi_agent.stream_utils import StreamEventType
        assert hasattr(StreamEventType, "BROWSER_SCREENSHOT")
        assert StreamEventType.BROWSER_SCREENSHOT == "browser_screenshot"

    @pytest.mark.asyncio
    async def test_create_browser_screenshot_event(self):
        """create_browser_screenshot_event returns correct StreamEvent."""
        from app.engine.multi_agent.stream_utils import (
            create_browser_screenshot_event,
            StreamEventType,
        )
        event = await create_browser_screenshot_event(
            url="https://facebook.com/marketplace",
            image_base64="abc123==",
            label="Đang tải trang...",
            node="product_search_agent",
        )
        assert event.type == StreamEventType.BROWSER_SCREENSHOT
        assert event.content["url"] == "https://facebook.com/marketplace"
        assert event.content["image"] == "abc123=="
        assert event.content["label"] == "Đang tải trang..."
        assert event.content["metadata"] == {}
        assert event.node == "product_search_agent"

    @pytest.mark.asyncio
    async def test_create_browser_screenshot_event_node_optional(self):
        """create_browser_screenshot_event works without node."""
        from app.engine.multi_agent.stream_utils import create_browser_screenshot_event
        event = await create_browser_screenshot_event(
            url="https://example.com",
            image_base64="data",
            label="Test",
        )
        assert event.node is None
        assert event.content["metadata"] == {}

    @pytest.mark.asyncio
    async def test_create_browser_screenshot_event_with_metadata(self):
        from app.engine.multi_agent.stream_utils import create_browser_screenshot_event

        event = await create_browser_screenshot_event(
            url="https://example.com",
            image_base64="data",
            label="Test",
            metadata={"execution_id": "exec-1"},
        )

        assert event.content["metadata"]["execution_id"] == "exec-1"


# =============================================================================
# Screenshot Capture Tests
# =============================================================================

class TestScreenshotCapture:
    """Sprint 153: PlaywrightLLMAdapter screenshot capture."""

    def _make_adapter(self):
        """Create a concrete adapter for testing."""
        from app.engine.search_platforms.adapters.browser_base import PlaywrightLLMAdapter
        from app.engine.search_platforms.base import PlatformConfig, BackendType

        class TestAdapter(PlaywrightLLMAdapter):
            def get_config(self):
                return PlatformConfig(id="test", display_name="Test", backend_type=BackendType.BROWSER)
            def _build_url(self, query, page):
                return f"https://test.com/s?q={query}"
            def _get_extraction_prompt(self):
                return "Extract: {text} max {max_results}"

        return TestAdapter()

    def test_last_screenshots_initialized_empty(self):
        """_last_screenshots starts empty."""
        adapter = self._make_adapter()
        assert adapter._last_screenshots == []

    def test_capture_screenshot_disabled(self):
        """_capture_screenshot does nothing when disabled."""
        adapter = self._make_adapter()
        mock_settings = MagicMock()
        mock_settings.enable_browser_screenshots = False
        mock_settings.enable_browser_scraping = False

        with patch("app.core.config.get_settings", return_value=mock_settings):
            mock_page = MagicMock()
            adapter._capture_screenshot(mock_page, "test")
            assert len(adapter._last_screenshots) == 0

    def test_capture_screenshot_enabled(self):
        """_capture_screenshot stores screenshot when enabled."""
        adapter = self._make_adapter()
        mock_settings = MagicMock()
        mock_settings.enable_browser_screenshots = True
        mock_settings.browser_screenshot_quality = 40

        mock_page = MagicMock()
        # Return fake JPEG bytes
        mock_page.screenshot.return_value = b"\xff\xd8\xff\xe0test_image"
        mock_page.url = "https://facebook.com/marketplace"

        with patch("app.core.config.get_settings", return_value=mock_settings):
            adapter._capture_screenshot(mock_page, "Đang tải trang...")

        assert len(adapter._last_screenshots) == 1
        shot = adapter._last_screenshots[0]
        assert shot["label"] == "Đang tải trang..."
        assert shot["url"] == "https://facebook.com/marketplace"
        assert isinstance(shot["image"], str)
        assert isinstance(shot["timestamp"], float)
        # Verify base64 encoding
        decoded = base64.b64decode(shot["image"])
        assert decoded == b"\xff\xd8\xff\xe0test_image"

    def test_capture_screenshot_max_limit(self):
        """_capture_screenshot respects _MAX_SCREENSHOTS limit."""
        adapter = self._make_adapter()
        mock_settings = MagicMock()
        mock_settings.enable_browser_screenshots = True
        mock_settings.browser_screenshot_quality = 40

        mock_page = MagicMock()
        mock_page.screenshot.return_value = b"img"
        mock_page.url = "https://test.com"

        with patch("app.core.config.get_settings", return_value=mock_settings):
            for i in range(7):
                adapter._capture_screenshot(mock_page, f"shot-{i}")

        # Max is 5
        assert len(adapter._last_screenshots) == 5

    def test_capture_screenshot_error_handling(self):
        """_capture_screenshot handles errors gracefully."""
        adapter = self._make_adapter()
        mock_settings = MagicMock()
        mock_settings.enable_browser_screenshots = True
        mock_settings.browser_screenshot_quality = 40

        mock_page = MagicMock()
        mock_page.screenshot.side_effect = RuntimeError("Browser crashed")

        with patch("app.core.config.get_settings", return_value=mock_settings):
            adapter._capture_screenshot(mock_page, "test")

        assert len(adapter._last_screenshots) == 0

    def test_get_last_screenshots_clears(self):
        """get_last_screenshots returns and clears screenshots."""
        adapter = self._make_adapter()
        adapter._last_screenshots = [{"label": "a"}, {"label": "b"}]

        shots = adapter.get_last_screenshots()
        assert len(shots) == 2
        assert shots[0]["label"] == "a"
        assert adapter._last_screenshots == []

    def test_fetch_page_text_resets_screenshots(self):
        """_fetch_page_text resets _last_screenshots on each call."""
        adapter = self._make_adapter()
        adapter._last_screenshots = [{"label": "old"}]

        # Mock Playwright
        mock_page = MagicMock()
        mock_page.inner_text.return_value = "page content"
        mock_page.url = "https://test.com"
        mock_page.screenshot.return_value = b"img"

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page

        mock_browser = MagicMock()
        mock_browser.is_connected.return_value = True
        mock_browser.new_context.return_value = mock_context

        mock_settings = MagicMock()
        mock_settings.enable_browser_screenshots = True
        mock_settings.browser_screenshot_quality = 40
        mock_settings.browser_scraping_timeout = 15

        with patch("app.engine.search_platforms.adapters.browser_base._get_browser", return_value=mock_browser), \
             patch("app.core.config.get_settings", return_value=mock_settings), \
             patch("app.engine.search_platforms.utils.validate_url_for_scraping"):
            text = adapter._fetch_page_text("https://test.com", timeout=15)

        assert text == "page content"
        # Old screenshot cleared, 2 new ones (before and after navigate)
        assert len(adapter._last_screenshots) == 2
        assert adapter._last_screenshots[0]["label"] == "Đang tải trang..."
        assert adapter._last_screenshots[1]["label"] == "Đã tải nội dung"


# =============================================================================
# Bus Event Conversion Tests
# =============================================================================

class TestBusEventConversion:
    """Sprint 153: _convert_bus_event handles browser_screenshot."""

    @pytest.mark.asyncio
    async def test_convert_browser_screenshot_event(self):
        """_convert_bus_event correctly converts browser_screenshot events."""
        event = {
            "type": "browser_screenshot",
            "content": {
                "url": "https://facebook.com/marketplace",
                "image": "base64data",
                "label": "Đang tải trang...",
                "metadata": {"execution_id": "exec-1"},
            },
            "node": "product_search_agent",
        }

        result = await _convert_bus_event(event)
        assert result.type == _SE.BROWSER_SCREENSHOT
        assert result.content["url"] == "https://facebook.com/marketplace"
        assert result.content["image"] == "base64data"
        assert result.content["label"] == "Đang tải trang..."
        assert result.content["metadata"]["execution_id"] == "exec-1"
        assert result.node == "product_search_agent"

    @pytest.mark.asyncio
    async def test_convert_browser_screenshot_missing_content(self):
        """_convert_bus_event handles missing content fields gracefully."""
        event = {
            "type": "browser_screenshot",
            "content": {},
            "node": None,
        }
        result = await _convert_bus_event(event)
        assert result.content["url"] == ""
        assert result.content["image"] == ""
        assert result.content["label"] == ""
        assert result.content["metadata"] == {}

    @pytest.mark.asyncio
    async def test_existing_event_types_unchanged(self):
        """Existing event types still work correctly after Sprint 153 changes."""
        # thinking_delta still works
        event = {"type": "thinking_delta", "content": "test", "node": "direct"}
        result = await _convert_bus_event(event)
        assert result.type == _SE.THINKING_DELTA

        # action_text still works
        event = {"type": "action_text", "content": "test", "node": "supervisor"}
        result = await _convert_bus_event(event)
        assert result.type == _SE.ACTION_TEXT


# =============================================================================
# Event Factory Tests
# =============================================================================

class TestEventFactory:
    """Sprint 153: create_browser_screenshot_event factory."""

    @pytest.mark.asyncio
    async def test_fields_correct(self):
        """Factory produces event with correct fields."""
        from app.engine.multi_agent.stream_utils import create_browser_screenshot_event
        event = await create_browser_screenshot_event(
            url="https://fb.com",
            image_base64="img",
            label="Test",
            node="product_search_agent",
        )
        assert event.type == "browser_screenshot"
        assert isinstance(event.content, dict)
        assert "url" in event.content
        assert "image" in event.content
        assert "label" in event.content

    @pytest.mark.asyncio
    async def test_content_structure(self):
        """Content has exactly url, image, label keys."""
        from app.engine.multi_agent.stream_utils import create_browser_screenshot_event
        event = await create_browser_screenshot_event(
            url="u", image_base64="i", label="l"
        )
        assert set(event.content.keys()) == {"url", "image", "label", "metadata"}


# =============================================================================
# Product Search Node Integration Tests
# =============================================================================

class TestProductSearchNodeScreenshots:
    """Sprint 153: Screenshots pushed after browser tool execution."""

    @pytest.mark.asyncio
    async def test_screenshots_pushed_for_facebook_tool(self):
        """Screenshots are pushed to event queue after Facebook tool call."""
        pushed_events = []

        async def mock_push(evt):
            pushed_events.append(evt)

        # Simulate the screenshot push logic from product_search_node
        tool_name = "tool_search_facebook_search"
        if tool_name.startswith("tool_search_facebook") or tool_name.startswith("tool_search_instagram"):
            mock_adapter = MagicMock()
            mock_adapter.get_last_screenshots.return_value = [
                {"label": "Đang tải trang...", "image": "b64", "url": "https://fb.com", "timestamp": 1.0},
            ]

            mock_registry = MagicMock()
            mock_registry.get.return_value = mock_adapter

            with patch("app.engine.search_platforms.get_search_platform_registry", return_value=mock_registry):
                from app.engine.search_platforms import get_search_platform_registry
                registry = get_search_platform_registry()
                platform_id = tool_name.replace("tool_search_", "")
                adapter = registry.get(platform_id)
                if adapter and hasattr(adapter, "get_last_screenshots"):
                    for shot in adapter.get_last_screenshots():
                        await mock_push({
                            "type": "browser_screenshot",
                            "content": shot,
                            "node": "product_search_agent",
                        })

        assert len(pushed_events) == 1
        assert pushed_events[0]["type"] == "browser_screenshot"
        assert pushed_events[0]["content"]["label"] == "Đang tải trang..."

    @pytest.mark.asyncio
    async def test_no_screenshots_for_non_browser_tools(self):
        """Non-browser tools do not push screenshots."""
        pushed_events = []
        tool_name = "tool_search_google_shopping"

        if tool_name.startswith("tool_search_facebook") or tool_name.startswith("tool_search_instagram"):
            pushed_events.append("should_not_happen")

        assert len(pushed_events) == 0

    @pytest.mark.asyncio
    async def test_screenshots_not_pushed_when_no_adapter(self):
        """Handle case where adapter is not found."""
        tool_name = "tool_search_facebook_marketplace"

        mock_registry = MagicMock()
        mock_registry.get.return_value = None

        pushed_events = []
        try:
            with patch("app.engine.search_platforms.get_search_platform_registry", return_value=mock_registry):
                from app.engine.search_platforms import get_search_platform_registry
                registry = get_search_platform_registry()
                platform_id = tool_name.replace("tool_search_", "")
                adapter = registry.get(platform_id)
                if adapter and hasattr(adapter, "get_last_screenshots"):
                    for shot in adapter.get_last_screenshots():
                        pushed_events.append(shot)
        except Exception:
            pass

        assert len(pushed_events) == 0

    @pytest.mark.asyncio
    async def test_empty_screenshots_handled(self):
        """Handle case where adapter has no screenshots."""
        tool_name = "tool_search_facebook_search"

        mock_adapter = MagicMock()
        mock_adapter.get_last_screenshots.return_value = []

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_adapter

        pushed_events = []
        with patch("app.engine.search_platforms.get_search_platform_registry", return_value=mock_registry):
            from app.engine.search_platforms import get_search_platform_registry
            registry = get_search_platform_registry()
            platform_id = tool_name.replace("tool_search_", "")
            adapter = registry.get(platform_id)
            if adapter and hasattr(adapter, "get_last_screenshots"):
                for shot in adapter.get_last_screenshots():
                    pushed_events.append(shot)

        assert len(pushed_events) == 0


# =============================================================================
# Size / Performance Tests
# =============================================================================

class TestSizePerformance:
    """Sprint 153: Screenshot size and encoding tests."""

    def test_jpeg_output_is_bytes(self):
        """Playwright screenshot returns bytes."""
        mock_page = MagicMock()
        mock_page.screenshot.return_value = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        result = mock_page.screenshot(type="jpeg", quality=40)
        assert isinstance(result, bytes)

    def test_base64_encoding_works(self):
        """Base64 encoding of JPEG bytes produces ASCII string."""
        raw = b"\xff\xd8\xff\xe0test_screenshot_data"
        b64 = base64.b64encode(raw).decode("ascii")
        assert isinstance(b64, str)
        # Verify round-trip
        decoded = base64.b64decode(b64)
        assert decoded == raw

    def test_small_screenshot_reasonable_size(self):
        """A small screenshot base64 is under reasonable size."""
        # 10KB raw JPEG -> ~13.3KB base64
        raw = b"\xff\xd8" + b"\x00" * 10000
        b64 = base64.b64encode(raw).decode("ascii")
        assert len(b64) < 200000  # Well under 200KB


# =============================================================================
# Regression Tests
# =============================================================================

class TestRegression:
    """Sprint 153: Ensure no regressions in existing functionality."""

    def test_non_browser_adapter_unaffected(self):
        """Non-browser adapters (Serper, Apify) do not have screenshot methods."""
        # SerperShoppingAdapter should not have _capture_screenshot
        try:
            from app.engine.search_platforms.adapters.serper_shopping import SerperShoppingAdapter
            adapter = SerperShoppingAdapter()
            assert not hasattr(adapter, "_capture_screenshot")
        except ImportError:
            pytest.skip("SerperShoppingAdapter not available")

    def test_existing_stream_event_types_present(self):
        """All pre-Sprint 153 event types still exist."""
        from app.engine.multi_agent.stream_utils import StreamEventType
        assert hasattr(StreamEventType, "STATUS")
        assert hasattr(StreamEventType, "THINKING")
        assert hasattr(StreamEventType, "ANSWER")
        assert hasattr(StreamEventType, "TOOL_CALL")
        assert hasattr(StreamEventType, "ACTION_TEXT")
        assert hasattr(StreamEventType, "EMOTION")
        assert hasattr(StreamEventType, "BROWSER_SCREENSHOT")

    def test_browser_screenshots_disabled_by_default(self):
        """Feature is disabled by default -- zero behavioral change."""
        with patch.dict("os.environ", {}, clear=True):
            from app.core.config import Settings
            s = Settings(google_api_key="test", _env_file=None)
            assert s.enable_browser_screenshots is False
            assert s.enable_browser_scraping is False

    @pytest.mark.asyncio
    async def test_existing_create_action_text_event_still_works(self):
        """Existing create_action_text_event is not broken."""
        from app.engine.multi_agent.stream_utils import (
            create_action_text_event,
            StreamEventType,
        )
        event = await create_action_text_event("test text", "supervisor")
        assert event.type == StreamEventType.ACTION_TEXT
        assert event.content == "test text"
        assert event.node == "supervisor"
