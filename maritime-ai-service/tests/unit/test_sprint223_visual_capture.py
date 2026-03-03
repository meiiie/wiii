"""Sprint 223: On-demand visual page capture tool."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import base64


class TestVisualCaptureTool:
    """Test tool_request_page_visual generation and behavior."""

    def test_tool_created_when_gate_enabled(self):
        from app.engine.context.visual_capture import create_visual_capture_tool
        mock_settings = MagicMock()
        mock_settings.enable_visual_page_capture = True
        with patch("app.engine.context.visual_capture.get_settings", return_value=mock_settings):
            tool = create_visual_capture_tool(event_bus_id="bus-123")
            assert tool is not None
            assert tool.name == "request_page_visual"

    def test_tool_not_created_when_gate_disabled(self):
        from app.engine.context.visual_capture import create_visual_capture_tool
        mock_settings = MagicMock()
        mock_settings.enable_visual_page_capture = False
        with patch("app.engine.context.visual_capture.get_settings", return_value=mock_settings):
            tool = create_visual_capture_tool(event_bus_id="bus-123")
            assert tool is None

    def test_tool_description_mentions_screenshot(self):
        from app.engine.context.visual_capture import create_visual_capture_tool
        mock_settings = MagicMock()
        mock_settings.enable_visual_page_capture = True
        with patch("app.engine.context.visual_capture.get_settings", return_value=mock_settings):
            tool = create_visual_capture_tool(event_bus_id="bus-123")
            assert "screenshot" in tool.description.lower() or "visual" in tool.description.lower()


class TestAnalyzeScreenshot:
    """Test Gemini Vision integration for screenshot analysis."""

    @pytest.mark.asyncio
    async def test_analyze_returns_description(self):
        from app.engine.context.visual_capture import analyze_screenshot
        fake_image = base64.b64encode(b"fake-image-data").decode()
        with patch("app.engine.context.visual_capture._call_gemini_vision", new_callable=AsyncMock, return_value="Trang hiển thị bảng điểm với 3 khóa học"):
            result = await analyze_screenshot(fake_image)
            assert "bảng điểm" in result.lower() or len(result) > 0

    @pytest.mark.asyncio
    async def test_analyze_timeout_returns_fallback(self):
        from app.engine.context.visual_capture import analyze_screenshot
        fake_image = base64.b64encode(b"fake").decode()
        with patch("app.engine.context.visual_capture._call_gemini_vision", new_callable=AsyncMock, side_effect=TimeoutError("timeout")):
            result = await analyze_screenshot(fake_image)
            assert "không thể" in result.lower() or "timeout" in result.lower()

    @pytest.mark.asyncio
    async def test_analyze_rejects_oversized_image(self):
        from app.engine.context.visual_capture import analyze_screenshot
        huge_image = base64.b64encode(b"x" * 2_000_000).decode()
        result = await analyze_screenshot(huge_image, max_size=1_000_000)
        assert "quá lớn" in result.lower() or "too large" in result.lower()


class TestValidateScreenshotData:
    """Test screenshot data validation."""

    def test_valid_jpeg_base64(self):
        from app.engine.context.visual_capture import validate_screenshot_data
        data = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff").decode()
        assert validate_screenshot_data(data) is True

    def test_valid_png_base64(self):
        from app.engine.context.visual_capture import validate_screenshot_data
        data = "data:image/png;base64," + base64.b64encode(b"\x89PNG").decode()
        assert validate_screenshot_data(data) is True

    def test_invalid_format_rejected(self):
        from app.engine.context.visual_capture import validate_screenshot_data
        assert validate_screenshot_data("not-an-image") is False

    def test_empty_data_rejected(self):
        from app.engine.context.visual_capture import validate_screenshot_data
        assert validate_screenshot_data("") is False
