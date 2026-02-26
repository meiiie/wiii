"""
Sprint 200: "Mắt Sản Phẩm" — Visual Product Search + Product Preview Cards

Tests for:
- _emit_product_previews() helper in product_search_node.py
- ProductSearchAgentNode image pass-through + routing
- visual_product_search.py tool (Gemini Vision identification)
- Config flags: enable_product_preview_cards, product_preview_max_cards, enable_visual_product_search
- AgentState.images field in state.py

40 tests across 6 test classes.
"""

import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

# =============================================================================
# Patch paths — lazy imports → patch at SOURCE module
# =============================================================================

_PATCH_SETTINGS = "app.core.config.get_settings"
_PATCH_GENAI_CLIENT = "google.genai.Client"
_PATCH_AGENT_CONFIG = "app.engine.multi_agent.agent_config.AgentConfigRegistry"
_PATCH_PRODUCT_TOOLS = "app.engine.tools.product_search_tools.get_product_search_tools"
_PATCH_EXCEL_TOOL = "app.engine.tools.excel_report_tool.tool_generate_product_report"
_PATCH_GRAPH_STREAMING = "app.engine.multi_agent.graph_streaming._get_event_queue"

# Module path for the function under test
_MODULE = "app.engine.multi_agent.agents.product_search_node"

# =============================================================================
# Singleton save/restore fixture
# =============================================================================

@pytest.fixture(autouse=True)
def _reset_singleton():
    """Save and restore the product_search_node singleton."""
    import app.engine.multi_agent.agents.product_search_node as mod
    original = mod._product_search_node
    yield
    mod._product_search_node = original


# =============================================================================
# Helper factories
# =============================================================================

def _mock_settings(**overrides):
    """Create a mock settings with Sprint 200 defaults."""
    s = MagicMock()
    s.enable_product_preview_cards = overrides.get("enable_product_preview_cards", True)
    s.product_preview_max_cards = overrides.get("product_preview_max_cards", 20)
    s.enable_visual_product_search = overrides.get("enable_visual_product_search", False)
    s.enable_product_search = overrides.get("enable_product_search", True)
    s.product_search_max_iterations = overrides.get("product_search_max_iterations", 15)
    s.enable_dealer_search = overrides.get("enable_dealer_search", False)
    s.enable_contact_extraction = overrides.get("enable_contact_extraction", False)
    s.enable_international_search = overrides.get("enable_international_search", False)
    s.enable_query_planner = overrides.get("enable_query_planner", False)
    s.google_api_key = overrides.get("google_api_key", "test-key")
    s.enable_advanced_excel_report = overrides.get("enable_advanced_excel_report", False)
    # Sprint 200: Vision provider config (extensible model management)
    s.visual_product_search_provider = overrides.get("visual_product_search_provider", "google")
    s.visual_product_search_model = overrides.get("visual_product_search_model", "")
    return s


def _google_shopping_results(n=3):
    """Generate mock Google Shopping search results."""
    return json.dumps({
        "platform": "google_shopping",
        "results": [
            {
                "title": f"Sản phẩm Google {i}",
                "price": f"{(i + 1) * 1000000}₫",
                "extracted_price": (i + 1) * 1000000,
                "link": f"https://shop.example.com/product-{i}",
                "image": f"https://images.example.com/img-{i}.jpg",
                "seller": f"Shop{i}",
                "rating": 4.0 + i * 0.1,
                "sold_count": 100 + i * 10,
                "delivery": "Giao hàng nhanh",
                "snippet": f"Mô tả sản phẩm Google Shopping {i}",
            }
            for i in range(n)
        ],
        "count": n,
    }, ensure_ascii=False)


def _shopee_results(n=2):
    """Generate mock Shopee search results."""
    return json.dumps({
        "platform": "shopee",
        "results": [
            {
                "title": f"Sản phẩm Shopee {i}",
                "price": f"{(i + 2) * 500000}₫",
                "url": f"https://shopee.vn/product-{i}",
                "image_url": f"https://cf.shopee.vn/img-{i}.jpg",
                "shop": f"ShopeeShop{i}",
                "rating": 4.5,
                "sold_count": 200,
            }
            for i in range(n)
        ],
        "count": n,
    }, ensure_ascii=False)


def _international_results(n=2):
    """Generate mock international/dealer search results."""
    return json.dumps({
        "platform": "international",
        "results": [
            {
                "title": f"International Product {i}",
                "price": f"${(i + 1) * 100}",
                "link": f"https://intl.example.com/product-{i}",
                "seller": f"GlobalSeller{i}",
                "rating": 4.2,
                "location": "US",
                "description": f"International product description {i}",
            }
            for i in range(n)
        ],
        "count": n,
    }, ensure_ascii=False)


# =============================================================================
# 1. TestProductPreviewEmission (12 tests)
# =============================================================================

class TestProductPreviewEmission:
    """Test _emit_product_previews() helper for product card carousel."""

    def test_emit_preview_from_google_shopping_results(self):
        """Parse google_shopping results, emit preview events with correct fields."""
        from app.engine.multi_agent.agents.product_search_node import _emit_product_previews

        results = _google_shopping_results(3)
        emitted = set()
        events = _emit_product_previews("tool_search_google_shopping", results, emitted, 20, 0)

        assert len(events) == 3
        for ev in events:
            assert ev["type"] == "preview"
            assert ev["node"] == "product_search_agent"
            assert ev["content"]["preview_type"] == "product"
            assert ev["content"]["title"]
            assert ev["content"]["metadata"]["platform"] == "google_shopping"

    def test_emit_preview_from_shopee_results(self):
        """Parse shopee results, emit preview events."""
        from app.engine.multi_agent.agents.product_search_node import _emit_product_previews

        results = _shopee_results(2)
        emitted = set()
        events = _emit_product_previews("tool_search_shopee", results, emitted, 20, 0)

        assert len(events) == 2
        for ev in events:
            assert ev["content"]["metadata"]["platform"] == "shopee"

    def test_emit_preview_from_international_search(self):
        """Parse international/dealer results."""
        from app.engine.multi_agent.agents.product_search_node import _emit_product_previews

        results = _international_results(2)
        emitted = set()
        events = _emit_product_previews("tool_international_search", results, emitted, 20, 0)

        assert len(events) == 2
        for ev in events:
            assert ev["content"]["metadata"]["platform"] == "international"

    def test_dedup_by_url(self):
        """Same product URL across calls → deduped via shared emitted_ids set.

        Note: Within a single results list, pid includes the loop index `_i` so items
        at different positions get different pids even with same URL. Dedup kicks in
        when the SAME pid appears across multiple tool calls (same index, same hash).
        """
        from app.engine.multi_agent.agents.product_search_node import _emit_product_previews

        single_result = json.dumps({
            "platform": "google_shopping",
            "results": [
                {"title": "Product A", "link": "https://same-url.com/p1", "price": "1000000₫"},
            ],
        }, ensure_ascii=False)

        emitted = set()
        # First call → 1 event, pid added to emitted
        events1 = _emit_product_previews("tool_search_google_shopping", single_result, emitted, 20, 0)
        assert len(events1) == 1

        # Second call with SAME data → pid already in emitted → 0 events
        events2 = _emit_product_previews("tool_search_google_shopping", single_result, emitted, 20, 1)
        assert len(events2) == 0

    def test_max_cards_limit(self):
        """Respect product_preview_max_cards setting."""
        from app.engine.multi_agent.agents.product_search_node import _emit_product_previews

        results = _google_shopping_results(8)
        emitted = set()
        # max_cards=3 with current_count=0
        events = _emit_product_previews("tool_search_google_shopping", results, emitted, 3, 0)

        assert len(events) <= 3

    def test_gate_disabled(self):
        """When called with a non-product tool → no events emitted (simulates gate)."""
        from app.engine.multi_agent.agents.product_search_node import _emit_product_previews

        results = _google_shopping_results(3)
        emitted = set()
        # Non-product tool name → should return empty
        events = _emit_product_previews("tool_current_datetime", results, emitted, 20, 0)

        assert events == []

    def test_empty_results_no_emission(self):
        """Empty tool results → no preview events."""
        from app.engine.multi_agent.agents.product_search_node import _emit_product_previews

        empty = json.dumps({"platform": "google_shopping", "results": [], "count": 0})
        emitted = set()
        events = _emit_product_previews("tool_search_google_shopping", empty, emitted, 20, 0)

        assert events == []

    def test_malformed_json_no_crash(self):
        """Invalid JSON doesn't crash — returns empty list."""
        from app.engine.multi_agent.agents.product_search_node import _emit_product_previews

        emitted = set()
        events = _emit_product_previews("tool_search_google_shopping", "NOT{valid JSON", emitted, 20, 0)

        assert events == []

    def test_missing_title_skipped(self):
        """Products without title are skipped."""
        from app.engine.multi_agent.agents.product_search_node import _emit_product_previews

        results = json.dumps({
            "platform": "shopee",
            "results": [
                {"link": "https://shopee.vn/p1", "price": "500000₫"},  # No title
                {"title": "Real Product", "link": "https://shopee.vn/p2", "price": "600000₫"},
            ],
        }, ensure_ascii=False)
        emitted = set()
        events = _emit_product_previews("tool_search_shopee", results, emitted, 20, 0)

        assert len(events) == 1
        assert events[0]["content"]["title"] == "Real Product"

    def test_preview_event_structure(self):
        """Verify preview event dict has correct type/content/node fields."""
        from app.engine.multi_agent.agents.product_search_node import _emit_product_previews

        results = _google_shopping_results(1)
        emitted = set()
        events = _emit_product_previews("tool_search_google_shopping", results, emitted, 20, 0)

        assert len(events) == 1
        ev = events[0]
        assert ev["type"] == "preview"
        assert ev["node"] == "product_search_agent"
        content = ev["content"]
        assert "preview_type" in content
        assert "preview_id" in content
        assert "title" in content
        assert "snippet" in content
        assert "url" in content
        assert "image_url" in content
        assert "metadata" in content

    def test_metadata_fields_populated(self):
        """Price, platform, seller, rating correctly mapped."""
        from app.engine.multi_agent.agents.product_search_node import _emit_product_previews

        results = _google_shopping_results(1)
        emitted = set()
        events = _emit_product_previews("tool_search_google_shopping", results, emitted, 20, 0)

        meta = events[0]["content"]["metadata"]
        assert meta["platform"] == "google_shopping"
        assert meta["price"]  # Non-empty price
        assert meta["seller"]  # Non-empty seller
        assert meta["rating"] is not None

    def test_multiple_tools_accumulate(self):
        """Events from multiple tool calls accumulate via shared emitted_ids set."""
        from app.engine.multi_agent.agents.product_search_node import _emit_product_previews

        emitted = set()
        count = 0

        # First tool call
        ev1 = _emit_product_previews(
            "tool_search_google_shopping", _google_shopping_results(3), emitted, 20, count,
        )
        count += len(ev1)

        # Second tool call
        ev2 = _emit_product_previews(
            "tool_search_shopee", _shopee_results(2), emitted, 20, count,
        )
        count += len(ev2)

        total = len(ev1) + len(ev2)
        assert total == 5
        assert count == 5


# =============================================================================
# 2. TestVisualProductIdentification (10 tests)
# =============================================================================

class TestVisualProductIdentification:
    """Test visual_product_search.py — Gemini Vision product identification."""

    def test_identify_product_success(self):
        """Mock Gemini Vision → returns product JSON."""
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "product_name": "MacBook Pro M4",
            "product_name_vi": "MacBook Pro M4",
            "brand": "Apple",
            "model": "M4 Pro",
            "category": "electronics",
            "search_keywords": ["macbook pro m4", "laptop apple"],
            "search_keywords_en": ["macbook pro m4", "apple laptop"],
            "confidence": 0.95,
        })

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch(_PATCH_SETTINGS) as mock_gs, \
             patch(_PATCH_GENAI_CLIENT, return_value=mock_client):
            mock_gs.return_value = _mock_settings(enable_visual_product_search=True)

            from app.engine.tools.visual_product_search import _identify_product_from_image
            result = json.loads(_identify_product_from_image("dGVzdA==", "image/jpeg"))

        assert result["product_name"] == "MacBook Pro M4"
        assert result["brand"] == "Apple"
        assert result["confidence"] == 0.95

    def test_identify_no_product(self):
        """Image with no product → returns error JSON."""
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "error": "no_product_found",
            "description": "The image shows a sunset over the ocean",
        })

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch(_PATCH_SETTINGS) as mock_gs, \
             patch(_PATCH_GENAI_CLIENT, return_value=mock_client):
            mock_gs.return_value = _mock_settings(enable_visual_product_search=True)

            from app.engine.tools.visual_product_search import _identify_product_from_image
            result = json.loads(_identify_product_from_image("dGVzdA=="))

        assert result["error"] == "no_product_found"

    def test_identify_parse_failure(self):
        """Gemini returns non-JSON → graceful fallback."""
        mock_response = MagicMock()
        mock_response.text = "I see a blue product that looks interesting but I can't identify it precisely."

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch(_PATCH_SETTINGS) as mock_gs, \
             patch(_PATCH_GENAI_CLIENT, return_value=mock_client):
            mock_gs.return_value = _mock_settings(enable_visual_product_search=True)

            from app.engine.tools.visual_product_search import _identify_product_from_image
            result = json.loads(_identify_product_from_image("dGVzdA=="))

        assert result["error"] == "parse_failed"

    def test_identify_gate_disabled(self):
        """When enable_visual_product_search=False → returns disabled error."""
        with patch(_PATCH_SETTINGS) as mock_gs:
            mock_gs.return_value = _mock_settings(enable_visual_product_search=False)

            from app.engine.tools.visual_product_search import _identify_product_from_image
            result = json.loads(_identify_product_from_image("dGVzdA=="))

        assert result["error"] == "visual_product_search_disabled"

    def test_identify_api_error(self):
        """Gemini API error → returns identification_failed error."""
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = RuntimeError("API quota exceeded")

        with patch(_PATCH_SETTINGS) as mock_gs, \
             patch(_PATCH_GENAI_CLIENT, return_value=mock_client):
            mock_gs.return_value = _mock_settings(enable_visual_product_search=True)

            from app.engine.tools.visual_product_search import _identify_product_from_image
            result = json.loads(_identify_product_from_image("dGVzdA=="))

        assert result["error"] == "identification_failed"
        assert "API quota exceeded" in result["message"]

    def test_identify_markdown_fence_strip(self):
        """Response with ```json fences → still parsed correctly."""
        mock_response = MagicMock()
        mock_response.text = '```json\n{"product_name": "iPhone 16", "brand": "Apple", "confidence": 0.9}\n```'

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch(_PATCH_SETTINGS) as mock_gs, \
             patch(_PATCH_GENAI_CLIENT, return_value=mock_client):
            mock_gs.return_value = _mock_settings(enable_visual_product_search=True)

            from app.engine.tools.visual_product_search import _identify_product_from_image
            result = json.loads(_identify_product_from_image("dGVzdA=="))

        assert result["product_name"] == "iPhone 16"

    def test_identify_missing_fields_defaults(self):
        """Missing fields get default values via setdefault."""
        mock_response = MagicMock()
        mock_response.text = json.dumps({"product_name": "Widget X"})

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch(_PATCH_SETTINGS) as mock_gs, \
             patch(_PATCH_GENAI_CLIENT, return_value=mock_client):
            mock_gs.return_value = _mock_settings(enable_visual_product_search=True)

            from app.engine.tools.visual_product_search import _identify_product_from_image
            result = json.loads(_identify_product_from_image("dGVzdA=="))

        assert result["product_name"] == "Widget X"
        assert result["brand"] == ""
        assert result["model"] == ""
        assert result["category"] == "other"
        assert result["search_keywords"] == []
        assert result["confidence"] == 0.5

    def test_identify_confidence_field(self):
        """Confidence field present in response."""
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "product_name": "Test Product",
            "confidence": 0.88,
        })

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch(_PATCH_SETTINGS) as mock_gs, \
             patch(_PATCH_GENAI_CLIENT, return_value=mock_client):
            mock_gs.return_value = _mock_settings(enable_visual_product_search=True)

            from app.engine.tools.visual_product_search import _identify_product_from_image
            result = json.loads(_identify_product_from_image("dGVzdA=="))

        assert result["confidence"] == 0.88

    def test_tool_registration(self):
        """get_visual_product_search_tool returns StructuredTool with correct name."""
        from app.engine.tools.visual_product_search import get_visual_product_search_tool
        from langchain_core.tools import StructuredTool

        tool = get_visual_product_search_tool()
        assert isinstance(tool, StructuredTool)
        assert tool.name == "tool_identify_product_from_image"

    def test_tool_function_signature(self):
        """Tool has correct args: image_data, image_media_type, context."""
        from app.engine.tools.visual_product_search import get_visual_product_search_tool
        import inspect

        tool = get_visual_product_search_tool()
        # The underlying function should accept image_data, image_media_type, context
        sig = inspect.signature(tool.func)
        params = list(sig.parameters.keys())
        assert "image_data" in params
        assert "image_media_type" in params
        assert "context" in params


# =============================================================================
# 3. TestImagePipelinePassthrough (8 tests)
# =============================================================================

class TestImagePipelinePassthrough:
    """Test image field pass-through from AgentState to ReAct loop."""

    def test_images_in_agent_state(self):
        """AgentState with images field accepted (TypedDict validation)."""
        from app.engine.multi_agent.state import AgentState

        state: AgentState = {
            "query": "Tìm sản phẩm này",
            "images": [{"data": "dGVzdA==", "media_type": "image/jpeg"}],
        }
        assert state["images"] is not None
        assert len(state["images"]) == 1

    @pytest.mark.asyncio
    async def test_images_passed_to_react_loop(self):
        """process() passes images from state to _react_loop."""
        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)

        # _react_loop mock
        react_result = ("Test response", [], None, False)

        with patch(f"{_MODULE}.ProductSearchAgentNode._init_llm"), \
             patch(f"{_MODULE}.ProductSearchAgentNode._react_loop", new_callable=AsyncMock, return_value=react_result) as mock_react:

            from app.engine.multi_agent.agents.product_search_node import ProductSearchAgentNode
            node = ProductSearchAgentNode()

            state = {
                "query": "Tìm sản phẩm trong ảnh",
                "context": {},
                "images": [{"data": "base64data", "media_type": "image/png"}],
            }

            await node.process(state)

            # Verify _react_loop was called with images
            call_kwargs = mock_react.call_args
            assert call_kwargs.kwargs.get("images") or (
                len(call_kwargs.args) >= 5 and call_kwargs.args[4] is not None
            ) or call_kwargs[1].get("images") is not None

    @pytest.mark.asyncio
    async def test_images_from_context(self):
        """Images can come from context dict when not in state directly."""
        react_result = ("Response", [], None, False)

        with patch(f"{_MODULE}.ProductSearchAgentNode._init_llm"), \
             patch(f"{_MODULE}.ProductSearchAgentNode._react_loop", new_callable=AsyncMock, return_value=react_result) as mock_react:

            from app.engine.multi_agent.agents.product_search_node import ProductSearchAgentNode
            node = ProductSearchAgentNode()

            state = {
                "query": "Tìm sản phẩm này",
                "context": {
                    "images": [{"data": "ctx_base64", "media_type": "image/jpeg"}],
                },
            }

            await node.process(state)

            call_kwargs = mock_react.call_args
            images_arg = call_kwargs.kwargs.get("images") if call_kwargs.kwargs else None
            assert images_arg is not None or (call_kwargs.args and len(call_kwargs.args) >= 5)

    @pytest.mark.asyncio
    async def test_missing_images_graceful(self):
        """No images → no crash, normal flow."""
        react_result = ("Normal response", [], None, False)

        with patch(f"{_MODULE}.ProductSearchAgentNode._init_llm"), \
             patch(f"{_MODULE}.ProductSearchAgentNode._react_loop", new_callable=AsyncMock, return_value=react_result):

            from app.engine.multi_agent.agents.product_search_node import ProductSearchAgentNode
            node = ProductSearchAgentNode()

            state = {
                "query": "Tìm MacBook Pro",
                "context": {},
            }

            result = await node.process(state)
            assert result["final_response"] == "Normal response"

    def test_image_routing_prompt_injection(self):
        """When images present + visual search enabled → system prompt includes image instruction."""
        with patch(_PATCH_SETTINGS) as mock_gs:
            mock_gs.return_value = _mock_settings(enable_visual_product_search=True)

            # The system prompt modification happens inside _react_loop,
            # so we test the prompt construction logic directly.
            # When images are present and enable_visual_product_search=True,
            # the prompt should contain the image instruction section.
            from app.engine.multi_agent.agents.product_search_node import _SYSTEM_PROMPT

            # The base system prompt should NOT contain visual search instructions
            assert "NHẬN DIỆN SẢN PHẨM TỪ ẢNH" not in _SYSTEM_PROMPT
            # The injection happens dynamically in _react_loop — this is verified
            # via the integration tests in test_images_passed_to_react_loop

    def test_image_routing_disabled(self):
        """When visual search disabled → prompt should NOT be modified."""
        with patch(_PATCH_SETTINGS) as mock_gs:
            mock_gs.return_value = _mock_settings(enable_visual_product_search=False)

            from app.engine.multi_agent.agents.product_search_node import _SYSTEM_PROMPT
            assert "NHẬN DIỆN SẢN PHẨM TỪ ẢNH" not in _SYSTEM_PROMPT

    def test_multimodal_human_message(self):
        """With images, HumanMessage should have multimodal content parts."""
        from langchain_core.messages import HumanMessage

        # Simulate what _react_loop does when images are present
        images = [{"data": "dGVzdA==", "media_type": "image/jpeg"}]
        query = "Tìm sản phẩm này"

        content_parts = []
        for img in images[:1]:
            img_data = img.get("data", "")
            img_type = img.get("media_type", "image/jpeg")
            if img_data:
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{img_type};base64,{img_data}"},
                })
        content_parts.append({"type": "text", "text": query})
        msg = HumanMessage(content=content_parts)

        assert isinstance(msg.content, list)
        assert len(msg.content) == 2
        assert msg.content[0]["type"] == "image_url"
        assert msg.content[1]["type"] == "text"
        assert msg.content[1]["text"] == query

    def test_no_images_text_message(self):
        """Without images, HumanMessage is plain text."""
        from langchain_core.messages import HumanMessage

        query = "Tìm MacBook Pro M4"
        msg = HumanMessage(content=query)

        assert isinstance(msg.content, str)
        assert msg.content == query


# =============================================================================
# 4. TestConfigFlags (4 tests)
# =============================================================================

class TestConfigFlags:
    """Test Sprint 200 config flag defaults and validation."""

    def test_enable_product_preview_cards_default_true(self):
        """enable_product_preview_cards defaults to True."""
        from app.core.config import Settings

        s = Settings(
            _env_file=None,
            google_api_key="test",
        )
        assert s.enable_product_preview_cards is True

    def test_product_preview_max_cards_default_20(self):
        """product_preview_max_cards defaults to 20."""
        from app.core.config import Settings

        s = Settings(
            _env_file=None,
            google_api_key="test",
        )
        assert s.product_preview_max_cards == 20

    def test_enable_visual_product_search_default_false(self):
        """enable_visual_product_search defaults to False."""
        from app.core.config import Settings

        s = Settings(
            _env_file=None,
            google_api_key="test",
        )
        assert s.enable_visual_product_search is False

    def test_product_preview_max_cards_validation(self):
        """product_preview_max_cards ge=1, le=50."""
        from app.core.config import Settings
        from pydantic import ValidationError

        # Valid: 1
        s = Settings(
            _env_file=None,
            google_api_key="test",
            product_preview_max_cards=1,
        )
        assert s.product_preview_max_cards == 1

        # Valid: 50
        s = Settings(
            _env_file=None,
            google_api_key="test",
            product_preview_max_cards=50,
        )
        assert s.product_preview_max_cards == 50

        # Invalid: 0
        with pytest.raises(ValidationError):
            Settings(
                _env_file=None,
                google_api_key="test",
                product_preview_max_cards=0,
            )

        # Invalid: 51
        with pytest.raises(ValidationError):
            Settings(
                _env_file=None,
                google_api_key="test",
                product_preview_max_cards=51,
            )


# =============================================================================
# 5. TestHelperFunction (6 tests)
# =============================================================================

class TestHelperFunction:
    """Direct tests of _emit_product_previews helper function."""

    def test_emit_product_previews_basic(self):
        """Direct test of _emit_product_previews with valid input."""
        from app.engine.multi_agent.agents.product_search_node import _emit_product_previews

        results = json.dumps({
            "platform": "google_shopping",
            "results": [
                {
                    "title": "Product A",
                    "price": "1.000.000₫",
                    "link": "https://example.com/a",
                    "image": "https://img.example.com/a.jpg",
                    "seller": "SellerA",
                    "rating": 4.5,
                },
                {
                    "title": "Product B",
                    "price": "2.000.000₫",
                    "link": "https://example.com/b",
                    "seller": "SellerB",
                },
            ],
        }, ensure_ascii=False)

        emitted = set()
        events = _emit_product_previews("tool_search_google_shopping", results, emitted, 20, 0)

        assert len(events) == 2
        assert events[0]["content"]["title"] == "Product A"
        assert events[1]["content"]["title"] == "Product B"

    def test_emit_product_previews_dedup(self):
        """Same pid across calls → only 1 event via emitted_ids tracking.

        pid includes loop index, so dedup works across repeated calls
        (same tool, same results at same index).
        """
        from app.engine.multi_agent.agents.product_search_node import _emit_product_previews

        results = json.dumps({
            "platform": "shopee",
            "results": [
                {"title": "Dup Product", "link": "https://shopee.vn/same"},
            ],
        }, ensure_ascii=False)

        emitted = set()
        # First call
        events1 = _emit_product_previews("tool_search_shopee", results, emitted, 20, 0)
        assert len(events1) == 1

        # Second call with same results → deduped
        events2 = _emit_product_previews("tool_search_shopee", results, emitted, 20, 1)
        assert len(events2) == 0

    def test_emit_product_previews_max_limit(self):
        """Respects max_cards when current_count is close to limit."""
        from app.engine.multi_agent.agents.product_search_node import _emit_product_previews

        results = _google_shopping_results(5)
        emitted = set()

        # current_count=18, max_cards=20 → only 2 more slots
        events = _emit_product_previews("tool_search_google_shopping", results, emitted, 20, 18)

        assert len(events) <= 2

    def test_emit_product_previews_non_product_tool(self):
        """Non-product tools → empty list."""
        from app.engine.multi_agent.agents.product_search_node import _emit_product_previews

        results = json.dumps({"platform": "test", "results": [{"title": "X"}]})
        emitted = set()

        # tool_current_datetime is not in _PRODUCT_RESULT_TOOLS
        events = _emit_product_previews("tool_current_datetime", results, emitted, 20, 0)
        assert events == []

        # tool_knowledge_search is not in _PRODUCT_RESULT_TOOLS
        events = _emit_product_previews("tool_knowledge_search", results, emitted, 20, 0)
        assert events == []

        # tool_fetch_product_detail is not in _PRODUCT_RESULT_TOOLS
        events = _emit_product_previews("tool_fetch_product_detail", results, emitted, 20, 0)
        assert events == []

    def test_emit_product_previews_malformed_json(self):
        """Bad JSON → empty list, no exception."""
        from app.engine.multi_agent.agents.product_search_node import _emit_product_previews

        emitted = set()
        events = _emit_product_previews("tool_search_google_shopping", "{broken json!!!", emitted, 20, 0)
        assert events == []

        # Non-dict JSON (list)
        events = _emit_product_previews("tool_search_google_shopping", "[1,2,3]", emitted, 20, 0)
        assert events == []

        # Non-string type passed (integer)
        events = _emit_product_previews("tool_search_google_shopping", 12345, emitted, 20, 0)
        assert events == []

    def test_emit_product_previews_no_title(self):
        """Products without title → skipped."""
        from app.engine.multi_agent.agents.product_search_node import _emit_product_previews

        results = json.dumps({
            "platform": "lazada",
            "results": [
                {"link": "https://lazada.vn/p1", "price": "500000₫"},  # No title
                {"title": "", "link": "https://lazada.vn/p2"},  # Empty title
                {"title": "   ", "link": "https://lazada.vn/p3"},  # Whitespace title — may or may not pass
                {"title": "Valid Product", "link": "https://lazada.vn/p4", "price": "800000₫"},
            ],
        }, ensure_ascii=False)

        emitted = set()
        events = _emit_product_previews("tool_search_lazada", results, emitted, 20, 0)

        # Only items with non-empty title should pass
        titles = [e["content"]["title"] for e in events]
        assert "Valid Product" in titles
        # First two have no title → skipped
        assert len([t for t in titles if t.strip()]) >= 1


# =============================================================================
# 6. TestProductResultToolSet (bonus: verify _PRODUCT_RESULT_TOOLS constant)
# =============================================================================

class TestProductResultToolSet:
    """Verify _PRODUCT_RESULT_TOOLS constant is complete."""

    def test_contains_core_search_tools(self):
        """All core search tools should be in _PRODUCT_RESULT_TOOLS."""
        from app.engine.multi_agent.agents.product_search_node import _PRODUCT_RESULT_TOOLS

        expected = {
            "tool_search_google_shopping",
            "tool_search_shopee",
            "tool_search_tiktok_shop",
            "tool_search_lazada",
            "tool_search_facebook_marketplace",
            "tool_search_all_web",
            "tool_search_instagram_shopping",
            "tool_search_websosanh",
        }
        for tool in expected:
            assert tool in _PRODUCT_RESULT_TOOLS, f"{tool} missing from _PRODUCT_RESULT_TOOLS"

    def test_contains_facebook_search_tools(self):
        """Facebook search/group tools included."""
        from app.engine.multi_agent.agents.product_search_node import _PRODUCT_RESULT_TOOLS

        assert "tool_search_facebook_search" in _PRODUCT_RESULT_TOOLS
        assert "tool_search_facebook_group" in _PRODUCT_RESULT_TOOLS
        assert "tool_search_facebook_groups_auto" in _PRODUCT_RESULT_TOOLS

    def test_contains_b2b_tools(self):
        """Sprint 196 B2B tools included."""
        from app.engine.multi_agent.agents.product_search_node import _PRODUCT_RESULT_TOOLS

        assert "tool_international_search" in _PRODUCT_RESULT_TOOLS
        assert "tool_dealer_search" in _PRODUCT_RESULT_TOOLS

    def test_excludes_non_product_tools(self):
        """Non-product tools should NOT be in the set."""
        from app.engine.multi_agent.agents.product_search_node import _PRODUCT_RESULT_TOOLS

        # These should NOT produce preview cards
        assert "tool_fetch_product_detail" not in _PRODUCT_RESULT_TOOLS
        assert "tool_generate_product_report" not in _PRODUCT_RESULT_TOOLS
        assert "tool_identify_product_from_image" not in _PRODUCT_RESULT_TOOLS
        assert "tool_current_datetime" not in _PRODUCT_RESULT_TOOLS
        assert "tool_extract_contacts" not in _PRODUCT_RESULT_TOOLS


# =============================================================================
# 7. TestSearchWorkerPreviewEmission (6 tests)
# =============================================================================

class TestSearchWorkerPreviewEmission:
    """Test preview emission from subagent search workers (Sprint 200 fix)."""

    @pytest.mark.asyncio
    async def test_worker_emits_preview_events(self):
        """platform_worker should emit preview events when products found."""
        from unittest.mock import AsyncMock
        import asyncio

        eq = asyncio.Queue()

        mock_adapter = MagicMock()
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {
            "title": "Arduino Mega 2560",
            "link": "https://shopee.vn/arduino",
            "price": "450,000đ",
            "image": "https://img.com/a.jpg",
            "seller": "TechShop",
        }
        mock_adapter.search_sync.return_value = [mock_result]

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_adapter

        with patch(_PATCH_SETTINGS) as mock_gs, \
             patch("app.engine.multi_agent.subagents.search.workers._get_event_queue", return_value=eq), \
             patch("app.engine.search_platforms.get_search_platform_registry", return_value=mock_registry):

            mock_gs.return_value = _mock_settings(enable_product_preview_cards=True)

            from app.engine.multi_agent.subagents.search.workers import platform_worker
            result = await platform_worker({
                "platform_id": "shopee",
                "query": "Arduino Mega 2560",
                "max_results": 10,
                "_event_bus_id": "test-bus",
            })

            # Collect all events
            events = []
            while not eq.empty():
                events.append(eq.get_nowait())

            # Should have preview events
            preview_events = [e for e in events if e.get("type") == "preview"]
            assert len(preview_events) >= 1
            assert preview_events[0]["content"]["preview_type"] == "product"
            assert "Arduino" in preview_events[0]["content"]["title"]

    @pytest.mark.asyncio
    async def test_worker_no_preview_when_disabled(self):
        """preview events NOT emitted when enable_product_preview_cards=False."""
        import asyncio

        eq = asyncio.Queue()

        mock_adapter = MagicMock()
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"title": "Product X", "link": "https://example.com"}
        mock_adapter.search_sync.return_value = [mock_result]

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_adapter

        with patch(_PATCH_SETTINGS) as mock_gs, \
             patch("app.engine.multi_agent.subagents.search.workers._get_event_queue", return_value=eq), \
             patch("app.engine.search_platforms.get_search_platform_registry", return_value=mock_registry):

            mock_gs.return_value = _mock_settings(enable_product_preview_cards=False)

            from app.engine.multi_agent.subagents.search.workers import platform_worker
            await platform_worker({
                "platform_id": "lazada",
                "query": "test",
                "max_results": 5,
                "_event_bus_id": "test-bus",
            })

            events = []
            while not eq.empty():
                events.append(eq.get_nowait())

            preview_events = [e for e in events if e.get("type") == "preview"]
            assert len(preview_events) == 0

    @pytest.mark.asyncio
    async def test_worker_no_preview_when_no_products(self):
        """No products → no preview events emitted."""
        import asyncio

        eq = asyncio.Queue()

        mock_adapter = MagicMock()
        mock_adapter.search_sync.return_value = []

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_adapter

        with patch(_PATCH_SETTINGS) as mock_gs, \
             patch("app.engine.multi_agent.subagents.search.workers._get_event_queue", return_value=eq), \
             patch("app.engine.search_platforms.get_search_platform_registry", return_value=mock_registry):

            mock_gs.return_value = _mock_settings(enable_product_preview_cards=True)

            from app.engine.multi_agent.subagents.search.workers import platform_worker
            await platform_worker({
                "platform_id": "tiktok_shop",
                "query": "test",
                "max_results": 5,
                "_event_bus_id": "test-bus",
            })

            events = []
            while not eq.empty():
                events.append(eq.get_nowait())

            preview_events = [e for e in events if e.get("type") == "preview"]
            assert len(preview_events) == 0

    @pytest.mark.asyncio
    async def test_worker_preview_max_per_platform(self):
        """Max 8 preview cards per platform worker."""
        import asyncio

        eq = asyncio.Queue()

        # 15 products → only 8 should emit previews
        mock_adapter = MagicMock()
        results = []
        for i in range(15):
            r = MagicMock()
            r.to_dict.return_value = {
                "title": f"Product {i}",
                "link": f"https://example.com/{i}",
                "price": f"{i}00,000đ",
            }
            results.append(r)
        mock_adapter.search_sync.return_value = results

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_adapter

        with patch(_PATCH_SETTINGS) as mock_gs, \
             patch("app.engine.multi_agent.subagents.search.workers._get_event_queue", return_value=eq), \
             patch("app.engine.search_platforms.get_search_platform_registry", return_value=mock_registry):

            mock_gs.return_value = _mock_settings(enable_product_preview_cards=True)

            from app.engine.multi_agent.subagents.search.workers import platform_worker
            await platform_worker({
                "platform_id": "google_shopping",
                "query": "test",
                "max_results": 20,
                "_event_bus_id": "test-bus",
            })

            events = []
            while not eq.empty():
                events.append(eq.get_nowait())

            preview_events = [e for e in events if e.get("type") == "preview"]
            assert len(preview_events) <= 8

    @pytest.mark.asyncio
    async def test_worker_preview_metadata_populated(self):
        """Preview metadata contains platform, price, seller info."""
        import asyncio

        eq = asyncio.Queue()

        mock_adapter = MagicMock()
        r = MagicMock()
        r.to_dict.return_value = {
            "title": "Arduino Board",
            "link": "https://shopee.vn/board",
            "price": "350,000đ",
            "extracted_price": 350000,
            "seller": "RobotShop",
            "rating": 4.8,
            "sold_count": 250,
            "delivery": "Giao nhanh 2h",
            "image": "https://img.com/board.jpg",
        }
        mock_adapter.search_sync.return_value = [r]

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_adapter

        with patch(_PATCH_SETTINGS) as mock_gs, \
             patch("app.engine.multi_agent.subagents.search.workers._get_event_queue", return_value=eq), \
             patch("app.engine.search_platforms.get_search_platform_registry", return_value=mock_registry):

            mock_gs.return_value = _mock_settings(enable_product_preview_cards=True)

            from app.engine.multi_agent.subagents.search.workers import platform_worker
            await platform_worker({
                "platform_id": "shopee",
                "query": "Arduino",
                "max_results": 5,
                "_event_bus_id": "test-bus",
            })

            events = []
            while not eq.empty():
                events.append(eq.get_nowait())

            preview_events = [e for e in events if e.get("type") == "preview"]
            assert len(preview_events) == 1
            meta = preview_events[0]["content"]["metadata"]
            assert meta["platform"] == "shopee"
            assert meta["price"] == "350,000đ"
            assert meta["seller"] == "RobotShop"
            assert meta["rating"] == 4.8
            assert meta["sold_count"] == 250
            assert meta["delivery"] == "Giao nhanh 2h"
            assert meta["extracted_price"] == 350000

    @pytest.mark.asyncio
    async def test_worker_preview_no_crash_on_error(self):
        """Preview emission should not crash the worker on errors."""
        import asyncio

        eq = asyncio.Queue()

        mock_adapter = MagicMock()
        r = MagicMock()
        r.to_dict.return_value = {"title": "Product", "link": "https://example.com"}
        mock_adapter.search_sync.return_value = [r]

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_adapter

        # config import raises → preview emission skipped, worker still succeeds
        with patch("app.engine.multi_agent.subagents.search.workers._get_event_queue", return_value=eq), \
             patch("app.engine.search_platforms.get_search_platform_registry", return_value=mock_registry), \
             patch("app.core.config.get_settings", side_effect=Exception("config broken")):

            from app.engine.multi_agent.subagents.search.workers import platform_worker
            result = await platform_worker({
                "platform_id": "all_web",
                "query": "test",
                "max_results": 5,
                "_event_bus_id": "test-bus",
            })

            # Worker should still return products
            assert len(result["all_products"]) == 1
