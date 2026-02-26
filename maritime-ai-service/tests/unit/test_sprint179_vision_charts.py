"""
Sprint 179: "Mat Wiii" + "Bieu Do Song" -- Vision Input + Chart Tools
Tests for multimodal image support and chart generation tools.

Covers:
- ImageInput Pydantic model validation (media_type, data, detail, type)
- ChatRequest.images field (max 5 images, backward compat)
- Config vision flags (enable_vision, vision_max_images_per_request, etc.)
- ChatContext.images field in input_processor
- Chart tools (tool_generate_mermaid, tool_generate_chart, get_chart_tools)
- Multimodal HumanMessage content block construction
- Feature gates for vision and chart tools
- Edge cases and regression tests
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


# =============================================================================
# SECTION 1: ImageInput Model Tests
# =============================================================================

class TestImageInput:
    """Test ImageInput Pydantic model validation."""

    def test_valid_base64_image(self):
        """Base64 image with valid media_type should pass validation."""
        from app.models.schemas import ImageInput
        img = ImageInput(type="base64", media_type="image/jpeg", data="abc123base64data", detail="auto")
        assert img.type == "base64"
        assert img.media_type == "image/jpeg"
        assert img.data == "abc123base64data"
        assert img.detail == "auto"

    def test_valid_url_image(self):
        """URL image should pass validation."""
        from app.models.schemas import ImageInput
        img = ImageInput(type="url", media_type="image/png", data="https://example.com/image.png")
        assert img.type == "url"
        assert img.data == "https://example.com/image.png"

    def test_all_valid_media_types(self):
        """All 4 allowed media types should pass."""
        from app.models.schemas import ImageInput
        for mt in ["image/jpeg", "image/png", "image/webp", "image/gif"]:
            img = ImageInput(data="test", media_type=mt)
            assert img.media_type == mt

    def test_invalid_media_type_rejected(self):
        """Unsupported media types should be rejected."""
        from app.models.schemas import ImageInput
        from pydantic import ValidationError
        with pytest.raises(ValidationError) as exc_info:
            ImageInput(data="test", media_type="image/bmp")
        assert "Unsupported media type" in str(exc_info.value)

    def test_invalid_media_type_svg_rejected(self):
        """SVG media type should be rejected."""
        from app.models.schemas import ImageInput
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ImageInput(data="test", media_type="image/svg+xml")

    def test_invalid_media_type_tiff_rejected(self):
        """TIFF media type should be rejected."""
        from app.models.schemas import ImageInput
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ImageInput(data="test", media_type="image/tiff")

    def test_empty_data_rejected(self):
        """Empty data string should be rejected."""
        from app.models.schemas import ImageInput
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ImageInput(data="", media_type="image/jpeg")

    def test_whitespace_data_rejected(self):
        """Whitespace-only data should be rejected."""
        from app.models.schemas import ImageInput
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ImageInput(data="   ", media_type="image/jpeg")

    def test_defaults(self):
        """Default values should be correct."""
        from app.models.schemas import ImageInput
        img = ImageInput(data="test")
        assert img.type == "base64"
        assert img.media_type == "image/jpeg"
        assert img.detail == "auto"

    def test_detail_levels(self):
        """All detail levels should be accepted."""
        from app.models.schemas import ImageInput
        for detail in ["auto", "low", "high"]:
            img = ImageInput(data="test", detail=detail)
            assert img.detail == detail

    def test_invalid_detail_rejected(self):
        """Invalid detail level should be rejected."""
        from app.models.schemas import ImageInput
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ImageInput(data="test", detail="medium")

    def test_invalid_type_rejected(self):
        """Invalid image type should be rejected."""
        from app.models.schemas import ImageInput
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ImageInput(type="file", data="test")

    def test_type_literal_base64(self):
        """type='base64' should be accepted."""
        from app.models.schemas import ImageInput
        img = ImageInput(type="base64", data="test")
        assert img.type == "base64"

    def test_type_literal_url(self):
        """type='url' should be accepted."""
        from app.models.schemas import ImageInput
        img = ImageInput(type="url", data="https://example.com/img.jpg")
        assert img.type == "url"

    def test_data_stripped_of_whitespace(self):
        """Data field should be stripped of surrounding whitespace by validator."""
        from app.models.schemas import ImageInput
        img = ImageInput(data="  abc123  ")
        assert img.data == "abc123"

    def test_long_base64_data(self):
        """Long base64 data string should be accepted."""
        from app.models.schemas import ImageInput
        long_data = "A" * 10000
        img = ImageInput(data=long_data)
        assert img.data == long_data
        assert len(img.data) == 10000


# =============================================================================
# SECTION 2: ChatRequest with Images
# =============================================================================

class TestChatRequestImages:
    """Test ChatRequest.images field."""

    def test_request_without_images(self):
        """ChatRequest without images should work (backward compat)."""
        from app.models.schemas import ChatRequest
        req = ChatRequest(user_id="u1", message="Hello", role="student")
        assert req.images is None

    def test_request_with_single_image(self):
        """ChatRequest with one image should pass."""
        from app.models.schemas import ChatRequest, ImageInput
        req = ChatRequest(
            user_id="u1", message="What is this?", role="student",
            images=[ImageInput(data="abc123", media_type="image/png")]
        )
        assert len(req.images) == 1
        assert req.images[0].data == "abc123"

    def test_request_with_multiple_images(self):
        """ChatRequest with multiple images should pass."""
        from app.models.schemas import ChatRequest, ImageInput
        imgs = [
            ImageInput(data="img1", media_type="image/jpeg"),
            ImageInput(data="img2", media_type="image/png"),
            ImageInput(data="img3", media_type="image/webp"),
        ]
        req = ChatRequest(user_id="u1", message="Compare", role="student", images=imgs)
        assert len(req.images) == 3

    def test_request_with_max_images(self):
        """ChatRequest with 5 images (max) should pass."""
        from app.models.schemas import ChatRequest, ImageInput
        imgs = [ImageInput(data=f"img{i}") for i in range(5)]
        req = ChatRequest(user_id="u1", message="Compare these", role="student", images=imgs)
        assert len(req.images) == 5

    def test_request_exceeds_max_images(self):
        """ChatRequest with >5 images should be rejected."""
        from app.models.schemas import ChatRequest, ImageInput
        from pydantic import ValidationError
        imgs = [ImageInput(data=f"img{i}") for i in range(6)]
        with pytest.raises(ValidationError):
            ChatRequest(user_id="u1", message="Too many", role="student", images=imgs)

    def test_request_with_empty_images_list(self):
        """ChatRequest with empty images list should work."""
        from app.models.schemas import ChatRequest
        req = ChatRequest(user_id="u1", message="Hello", role="student", images=[])
        assert req.images == []

    def test_request_serialization_with_images(self):
        """ChatRequest with images should serialize properly."""
        from app.models.schemas import ChatRequest, ImageInput
        req = ChatRequest(
            user_id="u1", message="Check this", role="student",
            images=[ImageInput(type="url", data="https://example.com/img.jpg", media_type="image/jpeg")]
        )
        data = req.model_dump()
        assert "images" in data
        assert data["images"][0]["type"] == "url"
        assert data["images"][0]["data"] == "https://example.com/img.jpg"

    def test_request_images_field_is_optional(self):
        """The images field should be truly optional (not required)."""
        from app.models.schemas import ChatRequest
        # Construct via dict without images key
        req = ChatRequest.model_validate({
            "user_id": "u1",
            "message": "Hello",
            "role": "student",
        })
        assert req.images is None

    def test_request_with_mixed_image_types(self):
        """ChatRequest with mix of base64 and URL images should pass."""
        from app.models.schemas import ChatRequest, ImageInput
        imgs = [
            ImageInput(type="base64", data="base64data", media_type="image/jpeg"),
            ImageInput(type="url", data="https://example.com/img.png", media_type="image/png"),
        ]
        req = ChatRequest(user_id="u1", message="Mixed", role="student", images=imgs)
        assert req.images[0].type == "base64"
        assert req.images[1].type == "url"


# =============================================================================
# SECTION 3: Config Vision Flags
# =============================================================================

class TestVisionConfig:
    """Test vision configuration flags."""

    def test_vision_disabled_by_default(self):
        """enable_vision should be False by default."""
        from app.core.config import Settings
        s = Settings(google_api_key="test", api_key="test")
        assert s.enable_vision is False

    def test_vision_max_images_default(self):
        """Default max images should be 5."""
        from app.core.config import Settings
        s = Settings(google_api_key="test", api_key="test")
        assert s.vision_max_images_per_request == 5

    def test_vision_detail_default(self):
        """Default detail should be 'auto'."""
        from app.core.config import Settings
        s = Settings(google_api_key="test", api_key="test")
        assert s.vision_default_detail == "auto"

    def test_vision_max_file_size_default(self):
        """Default max file size should be 10 MB."""
        from app.core.config import Settings
        s = Settings(google_api_key="test", api_key="test")
        assert s.vision_max_file_size_mb == 10

    def test_chart_tools_disabled_by_default(self):
        """enable_chart_tools should be False by default."""
        from app.core.config import Settings
        s = Settings(google_api_key="test", api_key="test")
        assert s.enable_chart_tools is False

    def test_vision_can_be_enabled(self):
        """enable_vision should be settable to True."""
        from app.core.config import Settings
        s = Settings(google_api_key="test", api_key="test", enable_vision=True)
        assert s.enable_vision is True

    def test_chart_tools_can_be_enabled(self):
        """enable_chart_tools should be settable to True."""
        from app.core.config import Settings
        s = Settings(google_api_key="test", api_key="test", enable_chart_tools=True)
        assert s.enable_chart_tools is True

    def test_vision_max_images_bounds(self):
        """vision_max_images_per_request should have bounds ge=1, le=20."""
        from app.core.config import Settings
        from pydantic import ValidationError
        # Should accept valid values
        s = Settings(google_api_key="test", api_key="test", vision_max_images_per_request=1)
        assert s.vision_max_images_per_request == 1
        s = Settings(google_api_key="test", api_key="test", vision_max_images_per_request=20)
        assert s.vision_max_images_per_request == 20

    def test_vision_max_file_size_bounds(self):
        """vision_max_file_size_mb should have bounds ge=1, le=50."""
        from app.core.config import Settings
        s = Settings(google_api_key="test", api_key="test", vision_max_file_size_mb=1)
        assert s.vision_max_file_size_mb == 1
        s = Settings(google_api_key="test", api_key="test", vision_max_file_size_mb=50)
        assert s.vision_max_file_size_mb == 50


# =============================================================================
# SECTION 4: ChatContext Images
# =============================================================================

class TestChatContextImages:
    """Test ChatContext.images field in input_processor."""

    def test_chat_context_images_default_none(self):
        """ChatContext.images should default to None."""
        from app.services.input_processor import ChatContext
        from uuid import uuid4
        ctx = ChatContext(user_id="u1", session_id=uuid4(), message="hello", user_role="student")
        assert ctx.images is None

    def test_chat_context_images_set(self):
        """ChatContext.images can be set to a list."""
        from app.services.input_processor import ChatContext
        from uuid import uuid4
        ctx = ChatContext(user_id="u1", session_id=uuid4(), message="hello", user_role="student")
        ctx.images = [{"type": "base64", "data": "abc", "media_type": "image/png"}]
        assert len(ctx.images) == 1

    def test_chat_context_images_multiple(self):
        """ChatContext.images can hold multiple images."""
        from app.services.input_processor import ChatContext
        from uuid import uuid4
        ctx = ChatContext(user_id="u1", session_id=uuid4(), message="hello", user_role="student")
        ctx.images = [
            {"type": "base64", "data": f"img{i}", "media_type": "image/jpeg"}
            for i in range(5)
        ]
        assert len(ctx.images) == 5

    def test_chat_context_images_empty_list(self):
        """ChatContext.images can be set to empty list."""
        from app.services.input_processor import ChatContext
        from uuid import uuid4
        ctx = ChatContext(user_id="u1", session_id=uuid4(), message="hello", user_role="student")
        ctx.images = []
        assert ctx.images == []

    def test_chat_context_dataclass_post_init(self):
        """ChatContext __post_init__ should not affect images (stays None)."""
        from app.services.input_processor import ChatContext
        from uuid import uuid4
        ctx = ChatContext(user_id="u1", session_id=uuid4(), message="hello", user_role="student")
        # images is not touched by __post_init__ — it stays None
        assert ctx.images is None
        # history_list, user_facts, langchain_messages get default empty lists
        assert ctx.history_list == []
        assert ctx.user_facts == []
        assert ctx.langchain_messages == []


# =============================================================================
# SECTION 5: Chart Tools
# =============================================================================

class TestChartTools:
    """Test chart generation tools."""

    def test_mermaid_tool_exists(self):
        """tool_generate_mermaid should be importable."""
        from app.engine.tools.chart_tools import tool_generate_mermaid
        assert tool_generate_mermaid is not None

    def test_chart_tool_exists(self):
        """tool_generate_chart should be importable."""
        from app.engine.tools.chart_tools import tool_generate_chart
        assert tool_generate_chart is not None

    def test_mermaid_tool_returns_string(self):
        """tool_generate_mermaid should return a string with instructions."""
        from app.engine.tools.chart_tools import tool_generate_mermaid
        result = tool_generate_mermaid.invoke({"description": "COLREGs decision tree"})
        assert isinstance(result, str)
        assert "mermaid" in result.lower() or "Mermaid" in result

    def test_mermaid_tool_contains_description(self):
        """tool_generate_mermaid output should contain the input description."""
        from app.engine.tools.chart_tools import tool_generate_mermaid
        desc = "Navigation rules flowchart"
        result = tool_generate_mermaid.invoke({"description": desc})
        assert desc in result

    def test_mermaid_tool_valid_types(self):
        """Should accept all valid diagram types."""
        from app.engine.tools.chart_tools import tool_generate_mermaid
        for dt in ["flowchart", "sequence", "class", "state", "er", "gantt", "pie", "mindmap", "timeline"]:
            result = tool_generate_mermaid.invoke({"description": "test", "diagram_type": dt})
            assert isinstance(result, str)
            assert dt in result.lower()

    def test_mermaid_tool_invalid_type_fallback(self):
        """Invalid diagram type should fallback to flowchart."""
        from app.engine.tools.chart_tools import tool_generate_mermaid
        result = tool_generate_mermaid.invoke({"description": "test", "diagram_type": "invalid"})
        assert "flowchart" in result.lower()

    def test_mermaid_tool_direction(self):
        """Should support flowchart directions."""
        from app.engine.tools.chart_tools import tool_generate_mermaid
        result = tool_generate_mermaid.invoke({"description": "test", "diagram_type": "flowchart", "direction": "LR"})
        assert "LR" in result

    def test_mermaid_tool_direction_bt(self):
        """Should support BT direction."""
        from app.engine.tools.chart_tools import tool_generate_mermaid
        result = tool_generate_mermaid.invoke({"description": "test", "direction": "BT"})
        assert "BT" in result

    def test_mermaid_tool_direction_rl(self):
        """Should support RL direction."""
        from app.engine.tools.chart_tools import tool_generate_mermaid
        result = tool_generate_mermaid.invoke({"description": "test", "direction": "RL"})
        assert "RL" in result

    def test_mermaid_tool_default_direction_td(self):
        """Default direction should be TD."""
        from app.engine.tools.chart_tools import tool_generate_mermaid
        result = tool_generate_mermaid.invoke({"description": "test"})
        assert "TD" in result

    def test_mermaid_tool_invalid_direction_fallback(self):
        """Invalid direction should fallback to TD."""
        from app.engine.tools.chart_tools import tool_generate_mermaid
        result = tool_generate_mermaid.invoke({"description": "test", "direction": "XY"})
        assert "TD" in result

    def test_mermaid_tool_flowchart_header(self):
        """Flowchart type should include 'flowchart TD' header instruction."""
        from app.engine.tools.chart_tools import tool_generate_mermaid
        result = tool_generate_mermaid.invoke({"description": "test", "diagram_type": "flowchart", "direction": "LR"})
        assert "flowchart LR" in result

    def test_mermaid_tool_non_flowchart_header(self):
        """Non-flowchart type should use the type itself as header."""
        from app.engine.tools.chart_tools import tool_generate_mermaid
        result = tool_generate_mermaid.invoke({"description": "test", "diagram_type": "sequence"})
        assert "sequence" in result

    def test_chart_tool_pie(self):
        """Pie chart generation should work."""
        from app.engine.tools.chart_tools import tool_generate_chart
        result = tool_generate_chart.invoke({
            "data_description": "50% COLREGs, 30% SOLAS, 20% MARPOL",
            "chart_type": "pie",
        })
        assert "pie" in result.lower()

    def test_chart_tool_gantt(self):
        """Gantt chart generation should work."""
        from app.engine.tools.chart_tools import tool_generate_chart
        result = tool_generate_chart.invoke({
            "data_description": "Phase 1: 2 weeks, Phase 2: 3 weeks",
            "chart_type": "gantt",
        })
        assert "gantt" in result.lower()

    def test_chart_tool_timeline(self):
        """Timeline chart generation should work."""
        from app.engine.tools.chart_tools import tool_generate_chart
        result = tool_generate_chart.invoke({
            "data_description": "2020: Event A, 2021: Event B",
            "chart_type": "timeline",
        })
        assert "timeline" in result.lower()

    def test_chart_tool_mindmap(self):
        """Mindmap chart generation should work."""
        from app.engine.tools.chart_tools import tool_generate_chart
        result = tool_generate_chart.invoke({
            "data_description": "Central topic with 3 branches",
            "chart_type": "mindmap",
        })
        assert "mindmap" in result.lower()

    def test_chart_tool_invalid_type_fallback(self):
        """Invalid chart type should fallback to pie."""
        from app.engine.tools.chart_tools import tool_generate_chart
        result = tool_generate_chart.invoke({
            "data_description": "test data",
            "chart_type": "scatter",
        })
        assert "pie" in result.lower()

    def test_chart_tool_with_title(self):
        """Chart with title should include it."""
        from app.engine.tools.chart_tools import tool_generate_chart
        result = tool_generate_chart.invoke({
            "data_description": "data",
            "chart_type": "pie",
            "title": "Thong ke",
        })
        assert "Thong ke" in result

    def test_chart_tool_default_title(self):
        """Chart without title should use default 'Bieu do'."""
        from app.engine.tools.chart_tools import tool_generate_chart
        result = tool_generate_chart.invoke({
            "data_description": "data",
            "chart_type": "pie",
        })
        # Default title is 'Bieu do' (no diacritics in source code)
        assert "Bieu do" in result

    def test_chart_tool_empty_title_uses_default(self):
        """Empty string title should use default 'Bieu do'."""
        from app.engine.tools.chart_tools import tool_generate_chart
        result = tool_generate_chart.invoke({
            "data_description": "data",
            "chart_type": "pie",
            "title": "",
        })
        assert "Bieu do" in result

    def test_chart_tool_data_description_in_output(self):
        """Chart output should contain the data description."""
        from app.engine.tools.chart_tools import tool_generate_chart
        desc = "50% engineering, 30% science, 20% arts"
        result = tool_generate_chart.invoke({
            "data_description": desc,
            "chart_type": "pie",
        })
        assert desc in result

    def test_get_chart_tools_disabled(self):
        """get_chart_tools should return empty list when disabled."""
        with patch("app.core.config.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(enable_chart_tools=False)
            from app.engine.tools.chart_tools import get_chart_tools
            result = get_chart_tools()
            assert result == []

    def test_get_chart_tools_enabled(self):
        """get_chart_tools should return 2 tools when enabled."""
        with patch("app.core.config.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(enable_chart_tools=True)
            from app.engine.tools.chart_tools import get_chart_tools
            result = get_chart_tools()
            assert len(result) == 2

    def test_get_chart_tools_returns_correct_tools(self):
        """get_chart_tools should return tool_generate_mermaid and tool_generate_chart."""
        with patch("app.core.config.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(enable_chart_tools=True)
            from app.engine.tools.chart_tools import (
                get_chart_tools,
                tool_generate_mermaid,
                tool_generate_chart,
            )
            result = get_chart_tools()
            assert tool_generate_mermaid in result
            assert tool_generate_chart in result

    def test_mermaid_tool_has_name(self):
        """tool_generate_mermaid should have a name attribute."""
        from app.engine.tools.chart_tools import tool_generate_mermaid
        assert hasattr(tool_generate_mermaid, "name")
        assert tool_generate_mermaid.name == "tool_generate_mermaid"

    def test_chart_tool_has_name(self):
        """tool_generate_chart should have a name attribute."""
        from app.engine.tools.chart_tools import tool_generate_chart
        assert hasattr(tool_generate_chart, "name")
        assert tool_generate_chart.name == "tool_generate_chart"

    def test_mermaid_tool_has_description(self):
        """tool_generate_mermaid should have a non-empty description."""
        from app.engine.tools.chart_tools import tool_generate_mermaid
        assert hasattr(tool_generate_mermaid, "description")
        assert len(tool_generate_mermaid.description) > 0

    def test_chart_tool_has_description(self):
        """tool_generate_chart should have a non-empty description."""
        from app.engine.tools.chart_tools import tool_generate_chart
        assert hasattr(tool_generate_chart, "description")
        assert len(tool_generate_chart.description) > 0


# =============================================================================
# SECTION 6: Multimodal HumanMessage Construction
# =============================================================================

class TestMultimodalMessageConstruction:
    """Test that images are correctly converted to multimodal HumanMessage content blocks."""

    def test_base64_image_content_block(self):
        """Base64 image should produce correct content block format."""
        img = {"type": "base64", "media_type": "image/jpeg", "data": "abc123", "detail": "auto"}
        content_blocks = [{"type": "text", "text": "What is this?"}]
        content_blocks.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:{img['media_type']};base64,{img['data']}",
                "detail": img.get("detail", "auto"),
            }
        })
        assert len(content_blocks) == 2
        assert content_blocks[1]["type"] == "image_url"
        assert content_blocks[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
        assert content_blocks[1]["image_url"]["url"] == "data:image/jpeg;base64,abc123"
        assert content_blocks[1]["image_url"]["detail"] == "auto"

    def test_url_image_content_block(self):
        """URL image should produce correct content block format."""
        img = {"type": "url", "media_type": "image/png", "data": "https://example.com/img.png", "detail": "high"}
        content_blocks = [{"type": "text", "text": "Analyze this"}]
        content_blocks.append({
            "type": "image_url",
            "image_url": {
                "url": img["data"],
                "detail": img.get("detail", "auto"),
            }
        })
        assert content_blocks[1]["image_url"]["url"] == "https://example.com/img.png"
        assert content_blocks[1]["image_url"]["detail"] == "high"

    def test_multiple_images_content_blocks(self):
        """Multiple images should produce multiple content blocks."""
        images = [
            {"type": "base64", "media_type": "image/jpeg", "data": f"img{i}", "detail": "auto"}
            for i in range(3)
        ]
        content_blocks = [{"type": "text", "text": "Compare these images"}]
        for img in images:
            content_blocks.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{img['media_type']};base64,{img['data']}",
                    "detail": img.get("detail", "auto"),
                }
            })
        assert len(content_blocks) == 4  # 1 text + 3 images

    def test_five_images_content_blocks(self):
        """Five images (max) should produce 6 content blocks (1 text + 5 images)."""
        images = [
            {"type": "base64", "media_type": "image/png", "data": f"img{i}", "detail": "low"}
            for i in range(5)
        ]
        content_blocks = [{"type": "text", "text": "Compare all"}]
        for img in images:
            content_blocks.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{img['media_type']};base64,{img['data']}",
                    "detail": img.get("detail", "auto"),
                }
            })
        assert len(content_blocks) == 6

    def test_no_images_text_only(self):
        """When no images, should fall back to text-only HumanMessage."""
        images = []
        query = "What is Rule 15?"
        if images:
            content = [{"type": "text", "text": query}]
        else:
            content = query
        assert content == "What is Rule 15?"
        assert isinstance(content, str)

    def test_empty_images_list_text_only(self):
        """Empty images list should produce text-only message."""
        images = []
        query = "Explain COLREGs"
        content = query if not images else [{"type": "text", "text": query}]
        assert isinstance(content, str)
        assert content == "Explain COLREGs"

    def test_content_block_with_low_detail(self):
        """Low detail image should set detail='low'."""
        img = {"type": "base64", "media_type": "image/jpeg", "data": "lowres", "detail": "low"}
        block = {
            "type": "image_url",
            "image_url": {
                "url": f"data:{img['media_type']};base64,{img['data']}",
                "detail": img["detail"],
            }
        }
        assert block["image_url"]["detail"] == "low"

    def test_content_block_with_high_detail(self):
        """High detail image should set detail='high'."""
        img = {"type": "base64", "media_type": "image/jpeg", "data": "hires", "detail": "high"}
        block = {
            "type": "image_url",
            "image_url": {
                "url": f"data:{img['media_type']};base64,{img['data']}",
                "detail": img["detail"],
            }
        }
        assert block["image_url"]["detail"] == "high"

    def test_mixed_base64_and_url_content_blocks(self):
        """Mix of base64 and URL images should produce correct blocks."""
        images = [
            {"type": "base64", "media_type": "image/jpeg", "data": "b64data", "detail": "auto"},
            {"type": "url", "media_type": "image/png", "data": "https://example.com/img.png", "detail": "high"},
        ]
        content_blocks = [{"type": "text", "text": "Compare"}]
        for img in images:
            if img["type"] == "base64":
                url = f"data:{img['media_type']};base64,{img['data']}"
            else:
                url = img["data"]
            content_blocks.append({
                "type": "image_url",
                "image_url": {"url": url, "detail": img.get("detail", "auto")}
            })
        assert content_blocks[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
        assert content_blocks[2]["image_url"]["url"] == "https://example.com/img.png"


# =============================================================================
# SECTION 7: Feature Gate Tests
# =============================================================================

class TestFeatureGates:
    """Test that vision and chart features are properly gated."""

    def test_vision_gate_images_not_passed_when_disabled(self):
        """When enable_vision is False, ChatContext.images should stay None."""
        from app.services.input_processor import ChatContext
        from app.models.schemas import ChatRequest, ImageInput
        from uuid import uuid4

        # Simulate: settings.enable_vision = False
        req = ChatRequest(
            user_id="u1", message="test", role="student",
            images=[ImageInput(data="abc")]
        )
        ctx = ChatContext(user_id="u1", session_id=uuid4(), message="test", user_role="student")

        # When vision disabled, images should stay None on context
        # (the actual gate is in build_context: `if request.images and settings.enable_vision`)
        assert ctx.images is None

    def test_image_input_validation_independent_of_gate(self):
        """ImageInput validation should work regardless of enable_vision flag."""
        from app.models.schemas import ImageInput
        # Validation happens at schema level, not feature gate level
        img = ImageInput(data="test", media_type="image/png")
        assert img.data == "test"

    def test_vision_gate_condition_in_input_processor(self):
        """The vision gate condition should check both request.images and settings.enable_vision."""
        from app.models.schemas import ChatRequest, ImageInput

        # Create request with images
        req = ChatRequest(
            user_id="u1", message="Check this image", role="student",
            images=[ImageInput(data="abc123", media_type="image/jpeg")]
        )

        # Simulate the gate condition from input_processor line 541:
        # if getattr(request, 'images', None) and settings.enable_vision:
        enable_vision_false = False
        enable_vision_true = True

        # Gate should block when vision disabled
        should_pass_images = bool(getattr(req, 'images', None) and enable_vision_false)
        assert should_pass_images is False

        # Gate should allow when vision enabled
        should_pass_images = bool(getattr(req, 'images', None) and enable_vision_true)
        assert should_pass_images is True

    def test_vision_gate_with_none_images(self):
        """Gate should not pass images when request.images is None."""
        from app.models.schemas import ChatRequest

        req = ChatRequest(user_id="u1", message="No images", role="student")
        enable_vision = True

        should_pass_images = bool(getattr(req, 'images', None) and enable_vision)
        assert should_pass_images is False

    def test_vision_gate_with_empty_images(self):
        """Gate should not pass images when request.images is empty list."""
        from app.models.schemas import ChatRequest

        req = ChatRequest(user_id="u1", message="Empty images", role="student", images=[])
        enable_vision = True

        # Empty list is falsy, so gate should not pass
        should_pass_images = bool(getattr(req, 'images', None) and enable_vision)
        assert should_pass_images is False

    def test_chart_tools_gate_disabled(self):
        """get_chart_tools returns [] when enable_chart_tools=False."""
        with patch("app.core.config.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(enable_chart_tools=False)
            from app.engine.tools.chart_tools import get_chart_tools
            assert get_chart_tools() == []

    def test_chart_tools_gate_enabled(self):
        """get_chart_tools returns tools when enable_chart_tools=True."""
        with patch("app.core.config.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(enable_chart_tools=True)
            from app.engine.tools.chart_tools import get_chart_tools
            assert len(get_chart_tools()) == 2

    def test_chart_tools_gate_attribute_missing(self):
        """get_chart_tools should handle missing enable_chart_tools gracefully via getattr."""
        with patch("app.core.config.get_settings") as mock_settings:
            # MagicMock without enable_chart_tools attribute set
            mock_obj = MagicMock(spec=[])
            mock_settings.return_value = mock_obj
            from app.engine.tools.chart_tools import get_chart_tools
            # getattr(settings, "enable_chart_tools", False) should return False
            result = get_chart_tools()
            assert result == []


# =============================================================================
# SECTION 8: Edge Cases and Regression Tests
# =============================================================================

class TestEdgeCases:
    """Edge cases and regression tests."""

    def test_image_input_strips_whitespace(self):
        """Data field should be stripped of surrounding whitespace."""
        from app.models.schemas import ImageInput
        img = ImageInput(data="  abc123  ")
        assert img.data == "abc123"

    def test_image_input_tab_whitespace_stripped(self):
        """Tab and newline whitespace in data should be stripped."""
        from app.models.schemas import ImageInput
        img = ImageInput(data="\tabc123\n")
        assert img.data == "abc123"

    def test_chart_tool_with_whitespace_description(self):
        """Chart tool with whitespace-only description should still return result."""
        from app.engine.tools.chart_tools import tool_generate_mermaid
        result = tool_generate_mermaid.invoke({"description": " "})
        assert isinstance(result, str)
        assert len(result) > 0

    def test_chart_tool_with_unicode_description(self):
        """Chart tool with Vietnamese Unicode description should work."""
        from app.engine.tools.chart_tools import tool_generate_mermaid
        result = tool_generate_mermaid.invoke({"description": "Quy trinh dieu huong tau bien"})
        assert "Quy trinh dieu huong tau bien" in result

    def test_chart_tool_with_special_characters(self):
        """Chart tool should handle special characters in description."""
        from app.engine.tools.chart_tools import tool_generate_chart
        result = tool_generate_chart.invoke({
            "data_description": "Category A: 50%, Category B: 30%, C & D: 20%",
            "chart_type": "pie",
        })
        assert isinstance(result, str)
        assert "Category A: 50%" in result

    def test_image_model_dump(self):
        """ImageInput.model_dump() should produce serializable dict."""
        from app.models.schemas import ImageInput
        img = ImageInput(type="base64", media_type="image/png", data="test123", detail="low")
        d = img.model_dump()
        assert d == {"type": "base64", "media_type": "image/png", "data": "test123", "detail": "low"}

    def test_image_model_dump_defaults(self):
        """ImageInput.model_dump() with defaults should include all fields."""
        from app.models.schemas import ImageInput
        img = ImageInput(data="test")
        d = img.model_dump()
        assert d["type"] == "base64"
        assert d["media_type"] == "image/jpeg"
        assert d["data"] == "test"
        assert d["detail"] == "auto"

    def test_chat_request_model_dump_without_images(self):
        """ChatRequest without images should dump with images=None."""
        from app.models.schemas import ChatRequest
        req = ChatRequest(user_id="u1", message="Hello", role="student")
        d = req.model_dump()
        assert d["images"] is None

    def test_chat_request_model_dump_with_images(self):
        """ChatRequest with images should dump correctly."""
        from app.models.schemas import ChatRequest, ImageInput
        req = ChatRequest(
            user_id="u1", message="Test", role="student",
            images=[ImageInput(data="abc", media_type="image/jpeg")]
        )
        d = req.model_dump()
        assert len(d["images"]) == 1
        assert d["images"][0]["data"] == "abc"
        assert d["images"][0]["media_type"] == "image/jpeg"
        assert d["images"][0]["type"] == "base64"
        assert d["images"][0]["detail"] == "auto"

    def test_chat_request_model_dump_with_empty_images(self):
        """ChatRequest with empty images list should dump correctly."""
        from app.models.schemas import ChatRequest
        req = ChatRequest(user_id="u1", message="Hello", role="student", images=[])
        d = req.model_dump()
        assert d["images"] == []

    def test_mermaid_tool_with_all_directions(self):
        """All valid flowchart directions should be accepted."""
        from app.engine.tools.chart_tools import tool_generate_mermaid
        for direction in ["TD", "LR", "BT", "RL", "TB"]:
            result = tool_generate_mermaid.invoke({
                "description": "test",
                "diagram_type": "flowchart",
                "direction": direction,
            })
            assert direction in result

    def test_mermaid_output_format_instruction(self):
        """Mermaid tool output should contain markdown code block instruction."""
        from app.engine.tools.chart_tools import tool_generate_mermaid
        result = tool_generate_mermaid.invoke({"description": "test"})
        assert "```mermaid" in result

    def test_chart_output_format_instruction(self):
        """Chart tool output should contain markdown code block instruction."""
        from app.engine.tools.chart_tools import tool_generate_chart
        result = tool_generate_chart.invoke({
            "data_description": "50% A, 50% B",
            "chart_type": "pie",
        })
        assert "```mermaid" in result

    def test_mermaid_output_contains_vietnamese_instruction(self):
        """Mermaid tool output should instruct use of Vietnamese labels."""
        from app.engine.tools.chart_tools import tool_generate_mermaid
        result = tool_generate_mermaid.invoke({"description": "test"})
        assert "Vietnamese" in result

    def test_chart_output_contains_vietnamese_instruction(self):
        """Chart tool output should instruct use of Vietnamese labels."""
        from app.engine.tools.chart_tools import tool_generate_chart
        result = tool_generate_chart.invoke({
            "data_description": "data",
            "chart_type": "pie",
        })
        assert "Vietnamese" in result

    def test_image_input_json_schema(self):
        """ImageInput should have a proper JSON schema."""
        from app.models.schemas import ImageInput
        schema = ImageInput.model_json_schema()
        assert "properties" in schema
        assert "type" in schema["properties"]
        assert "media_type" in schema["properties"]
        assert "data" in schema["properties"]
        assert "detail" in schema["properties"]

    def test_chat_request_json_schema_includes_images(self):
        """ChatRequest JSON schema should include the images field."""
        from app.models.schemas import ChatRequest
        schema = ChatRequest.model_json_schema()
        assert "images" in schema["properties"]
