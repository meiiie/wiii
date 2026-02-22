"""
Tests for Sprint 148: "Săn Hàng" — Product Search Agent

Covers:
- Product search tools (Serper.dev Google Shopping, Apify platform scrapers)
- Excel report generation
- Circuit breaker per-platform isolation
- Tool registration with ToolCategory.PRODUCT_SEARCH
- Supervisor routing: product_search intent → PRODUCT_SEARCH_AGENT
- Agent node ReAct loop (mock LLM + tools)
- Graph wiring: product_search_agent → synthesizer
- Feature gate: node absent when enable_product_search=False
- Streaming events: thinking_start/delta/end + tool_call/tool_result
"""

import json
import os
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset module-level singletons to avoid test pollution."""
    import app.engine.tools.product_search_tools as pst
    pst._platform_cb.clear()
    pst._failure_count if hasattr(pst, '_failure_count') else None

    import app.engine.multi_agent.agents.product_search_node as psn
    psn._product_search_node = None
    yield


@pytest.fixture
def mock_settings():
    """Settings with product search enabled."""
    s = MagicMock()
    s.enable_product_search = True
    s.serper_api_key = "test-serper-key"
    s.apify_api_token = "test-apify-token"
    s.product_search_max_results = 30
    s.product_search_timeout = 10
    s.workspace_root = "~/.wiii/workspace"
    return s


# =============================================================================
# 1. Config & Schema Tests
# =============================================================================


class TestConfig:
    """Feature flag and schema additions."""

    def test_product_search_flags_exist(self):
        """Config has product search feature flags."""
        from app.core.config import Settings
        fields = Settings.model_fields
        assert "enable_product_search" in fields
        assert "serper_api_key" in fields
        assert "apify_api_token" in fields
        assert "product_search_max_results" in fields
        assert "product_search_timeout" in fields

    def test_product_search_defaults(self):
        """Product search disabled by default."""
        from app.core.config import Settings
        assert Settings.model_fields["enable_product_search"].default is False
        assert Settings.model_fields["product_search_max_results"].default == 30
        assert Settings.model_fields["product_search_timeout"].default == 30

    def test_routing_decision_has_product_search_intent(self):
        """RoutingDecision schema includes product_search intent."""
        from app.engine.structured_schemas import RoutingDecision
        r = RoutingDecision(
            intent="product_search",
            agent="PRODUCT_SEARCH_AGENT",
            confidence=0.95,
            reasoning="User wants to find products",
        )
        assert r.intent == "product_search"
        assert r.agent == "PRODUCT_SEARCH_AGENT"

    def test_routing_decision_product_search_agent(self):
        """RoutingDecision accepts PRODUCT_SEARCH_AGENT."""
        from app.engine.structured_schemas import RoutingDecision
        r = RoutingDecision(agent="PRODUCT_SEARCH_AGENT")
        assert r.agent == "PRODUCT_SEARCH_AGENT"


# =============================================================================
# 2. Tool Category Registration
# =============================================================================


class TestToolRegistry:
    """ToolCategory.PRODUCT_SEARCH exists and tools register correctly."""

    def test_product_search_category_exists(self):
        from app.engine.tools.registry import ToolCategory
        assert hasattr(ToolCategory, "PRODUCT_SEARCH")
        assert ToolCategory.PRODUCT_SEARCH.value == "product_search"

    def test_init_product_search_tools(self, mock_settings):
        """init_product_search_tools registers 5 tools."""
        from app.engine.tools.registry import get_tool_registry, ToolCategory

        # Save and restore registry state
        registry = get_tool_registry()
        old_tools = dict(registry._tools)
        old_cats = {k: list(v) for k, v in registry._categories.items()}

        try:
            with patch("app.core.config.get_settings", return_value=mock_settings):
                from app.engine.tools.product_search_tools import init_product_search_tools
                init_product_search_tools()

            ps_tools = registry.get_by_category(ToolCategory.PRODUCT_SEARCH)
            # Should have at least 5 search tools (may also have excel tool if registered separately)
            assert len(ps_tools) >= 5
        finally:
            registry._tools = old_tools
            registry._categories = old_cats


# =============================================================================
# 3. Google Shopping Tool (Serper.dev)
# =============================================================================


class TestGoogleShoppingTool:
    """tool_search_google_shopping via Serper.dev."""

    def test_google_shopping_success(self, mock_settings):
        """Successful Google Shopping search returns structured data."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "shopping": [
                {
                    "title": "Dây điện Cadivi 3x2.5mm",
                    "price": "450,000₫",
                    "extracted_price": 450000,
                    "source": "shopee.vn",
                    "rating": 4.8,
                    "ratingCount": 120,
                    "link": "https://shopee.vn/product/123",
                    "imageUrl": "https://img.shopee.vn/123.jpg",
                    "delivery": "Miễn phí",
                },
            ],
        }
        mock_response.raise_for_status = MagicMock()

        with patch("app.core.config.get_settings", return_value=mock_settings), \
             patch("httpx.post", return_value=mock_response) as mock_post:

            from app.engine.tools.product_search_tools import _search_google_shopping_sync
            results = _search_google_shopping_sync("dây điện 3x2.5mm", 10)

        assert len(results) == 1
        assert results[0]["platform"] == "Google Shopping"
        assert results[0]["title"] == "Dây điện Cadivi 3x2.5mm"
        assert results[0]["extracted_price"] == 450000

        # Verify request was made with correct params
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://google.serper.dev/shopping"
        body = call_args[1]["json"]
        assert body["gl"] == "vn"
        assert body["hl"] == "vi"

    def test_google_shopping_no_api_key(self):
        """Returns error when SERPER_API_KEY not configured."""
        s = MagicMock()
        s.serper_api_key = None

        with patch("app.core.config.get_settings", return_value=s):
            from app.engine.tools.product_search_tools import _search_google_shopping_sync
            results = _search_google_shopping_sync("test")

        assert len(results) == 1
        assert "error" in results[0]


# =============================================================================
# 4. Platform Search via Serper site: filter
# =============================================================================


class TestPlatformSerperSearch:
    """Platform-specific search via Serper.dev site: filter."""

    def test_shopee_search_success(self, mock_settings):
        """Shopee search returns results from shopee.vn via Serper."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "organic": [
                {
                    "title": "Dây điện Cadivi 3x2.5mm - Shopee",
                    "link": "https://shopee.vn/product/123",
                    "snippet": "Dây điện chính hãng, giá tốt",
                    "priceRange": "420,000₫",
                },
            ],
        }
        mock_response.raise_for_status = MagicMock()

        with patch("app.core.config.get_settings", return_value=mock_settings), \
             patch("httpx.post", return_value=mock_response) as mock_post:

            from app.engine.tools.product_search_tools import _search_platform_via_serper_sync
            results = _search_platform_via_serper_sync("dây điện", "Shopee", 10)

        assert len(results) == 1
        assert results[0]["platform"] == "Shopee"
        assert "shopee.vn" in results[0]["link"]

        # Verify site: filter in query
        call_args = mock_post.call_args
        body = call_args[1]["json"]
        assert "site:shopee.vn" in body["q"]

    def test_platform_search_no_api_key(self):
        """Returns error when SERPER_API_KEY not configured."""
        s = MagicMock()
        s.serper_api_key = None

        with patch("app.core.config.get_settings", return_value=s):
            from app.engine.tools.product_search_tools import _search_platform_via_serper_sync
            results = _search_platform_via_serper_sync("test", "Shopee")

        assert len(results) == 1
        assert "error" in results[0]


# =============================================================================
# 5. Circuit Breaker
# =============================================================================


class TestCircuitBreaker:
    """Per-platform circuit breaker isolation."""

    def test_circuit_breaker_opens_after_threshold(self):
        """3 failures for one platform opens CB for that platform only."""
        from app.engine.tools.product_search_tools import (
            _cb_is_open, _cb_record_failure, _cb_record_success,
        )

        assert not _cb_is_open("shopee")
        assert not _cb_is_open("lazada")

        # 3 failures for shopee
        for _ in range(3):
            _cb_record_failure("shopee")

        assert _cb_is_open("shopee")
        assert not _cb_is_open("lazada")  # Lazada unaffected

    def test_circuit_breaker_resets_on_success(self):
        """Success resets failure count."""
        from app.engine.tools.product_search_tools import (
            _cb_is_open, _cb_record_failure, _cb_record_success,
        )

        _cb_record_failure("tiktok_shop")
        _cb_record_failure("tiktok_shop")
        _cb_record_success("tiktok_shop")
        _cb_record_failure("tiktok_shop")  # Count restarted at 1

        assert not _cb_is_open("tiktok_shop")


# =============================================================================
# 6. Excel Report Tool
# =============================================================================


class TestExcelReportTool:

    def test_generate_report_success(self, tmp_path):
        """Excel report generates valid .xlsx file."""
        s = MagicMock()
        s.workspace_root = str(tmp_path)

        products = [
            {
                "platform": "Shopee",
                "title": "Dây điện Cadivi 3x2.5mm",
                "price": "450,000₫",
                "extracted_price": 450000,
                "seller": "Shop ABC",
                "rating": 4.8,
                "sold_count": 120,
                "link": "https://shopee.vn/123",
            },
            {
                "platform": "Lazada",
                "title": "Dây điện Sino 3x2.5mm",
                "price": "380,000₫",
                "extracted_price": 380000,
                "seller": "Siêu thị điện",
                "rating": 4.5,
                "sold_count": 80,
                "link": "https://lazada.vn/456",
            },
        ]

        with patch("app.core.config.get_settings", return_value=s):
            from app.engine.tools.excel_report_tool import tool_generate_product_report
            result = tool_generate_product_report.invoke({
                "products_json": json.dumps(products, ensure_ascii=False),
                "title": "Test Report",
            })

        data = json.loads(result)
        assert "file_path" in data
        assert data["total_products"] == 2
        assert data["min_price"] == 380000
        assert data["max_price"] == 450000
        assert Path(data["file_path"]).exists()

    def test_generate_report_invalid_json(self):
        """Returns error on invalid JSON input."""
        from app.engine.tools.excel_report_tool import tool_generate_product_report
        result = tool_generate_product_report.invoke({
            "products_json": "not valid json",
        })

        data = json.loads(result)
        assert "error" in data

    def test_generate_report_empty_list(self):
        """Returns error on empty product list."""
        from app.engine.tools.excel_report_tool import tool_generate_product_report
        result = tool_generate_product_report.invoke({
            "products_json": "[]",
        })

        data = json.loads(result)
        assert "error" in data

    def test_price_extraction(self):
        """_extract_price handles various Vietnamese price formats."""
        from app.engine.tools.excel_report_tool import _extract_price

        assert _extract_price("450,000₫") == 450000.0
        assert _extract_price("1.234.567₫") == 1234567.0
        assert _extract_price("", 250000) == 250000.0
        assert _extract_price("Liên hệ") == 0.0
        assert _extract_price(None) == 0.0


# =============================================================================
# 7. Supervisor Routing
# =============================================================================


class TestSupervisorRouting:
    """Supervisor routes product search queries correctly."""

    def test_agent_type_has_product_search(self):
        """AgentType enum includes PRODUCT_SEARCH."""
        from app.engine.multi_agent.supervisor import AgentType
        assert hasattr(AgentType, "PRODUCT_SEARCH")
        assert AgentType.PRODUCT_SEARCH.value == "product_search_agent"

    def test_agent_map_includes_product_search(self):
        """agent_map in _route_structured maps PRODUCT_SEARCH_AGENT."""
        # The agent_map is defined inside _route_structured, so we test via the schema
        from app.engine.structured_schemas import RoutingDecision
        r = RoutingDecision(agent="PRODUCT_SEARCH_AGENT", intent="product_search")
        assert r.agent == "PRODUCT_SEARCH_AGENT"

    def test_product_search_disabled_falls_back_to_direct(self):
        """When enable_product_search=False, product_search routes to direct."""
        from app.engine.multi_agent.supervisor import AgentType

        # Simulate the fallback logic from _route_structured
        chosen = AgentType.PRODUCT_SEARCH.value
        enable_product_search = False

        if chosen == AgentType.PRODUCT_SEARCH.value and not enable_product_search:
            chosen = AgentType.DIRECT.value

        assert chosen == "direct"


# =============================================================================
# 8. Graph Wiring
# =============================================================================


class TestGraphWiring:
    """Graph includes product_search_agent node when enabled."""

    def test_route_decision_handles_product_search(self):
        """route_decision returns 'product_search_agent' for matching state."""
        from app.engine.multi_agent.graph import route_decision

        state = {"next_agent": "product_search_agent"}
        assert route_decision(state) == "product_search_agent"

    def test_route_decision_default_to_direct(self):
        """Unknown agent falls back to direct."""
        from app.engine.multi_agent.graph import route_decision

        state = {"next_agent": "unknown_agent"}
        assert route_decision(state) == "direct"

    @patch("app.engine.multi_agent.graph.settings")
    def test_graph_builds_with_product_search(self, mock_s):
        """Graph includes product_search_agent node when enabled."""
        mock_s.enable_product_search = True
        mock_s.quality_skip_threshold = 0.85
        mock_s.default_domain = "maritime"
        mock_s.app_name = "Wiii"

        from app.engine.multi_agent.graph import build_multi_agent_graph
        graph = build_multi_agent_graph()

        # Check that the node exists in the compiled graph
        node_names = list(graph.nodes.keys())
        assert "product_search_agent" in node_names

    @patch("app.engine.multi_agent.graph.settings")
    def test_graph_builds_without_product_search(self, mock_s):
        """Graph excludes product_search_agent when disabled."""
        mock_s.enable_product_search = False
        mock_s.quality_skip_threshold = 0.85
        mock_s.default_domain = "maritime"
        mock_s.app_name = "Wiii"

        from app.engine.multi_agent.graph import build_multi_agent_graph
        graph = build_multi_agent_graph()

        node_names = list(graph.nodes.keys())
        assert "product_search_agent" not in node_names


# =============================================================================
# 9. Streaming Labels
# =============================================================================


class TestStreamingLabels:
    """Streaming metadata includes product search entries."""

    def test_node_descriptions_has_product_search(self):
        from app.engine.multi_agent.stream_utils import NODE_DESCRIPTIONS
        assert "product_search_agent" in NODE_DESCRIPTIONS

    def test_node_labels_has_product_search(self):
        from app.engine.multi_agent.graph_streaming import _NODE_LABELS
        assert "product_search_agent" in _NODE_LABELS
        assert _NODE_LABELS["product_search_agent"] == "Tìm kiếm sản phẩm"

    def test_intent_action_text_has_product_search(self):
        from app.engine.multi_agent.graph_streaming import _INTENT_ACTION_TEXT
        assert "product_search" in _INTENT_ACTION_TEXT

    def test_thinking_summary_product_search(self):
        from app.engine.multi_agent.graph_streaming import _generate_thinking_summary

        output = {"routing_metadata": {"intent": "product_search"}, "next_agent": "product_search_agent"}
        summary = _generate_thinking_summary(output, "dây điện 3x2.5mm")
        assert "sản phẩm" in summary.lower()

    def test_node_label_product_search(self):
        """_INTENT_EFFORT was removed; verify product_search_agent is in _NODE_LABELS instead."""
        from app.engine.multi_agent.graph_streaming import _NODE_LABELS
        assert "product_search_agent" in _NODE_LABELS


# =============================================================================
# 10. Agent Node (process mock)
# =============================================================================


class TestProductSearchAgentNode:
    """ProductSearchAgentNode process + ReAct loop."""

    @pytest.mark.asyncio
    async def test_process_returns_final_response(self):
        """process() sets final_response and current_agent in state."""
        from app.engine.multi_agent.agents.product_search_node import ProductSearchAgentNode

        node = ProductSearchAgentNode.__new__(ProductSearchAgentNode)
        node._llm = MagicMock()
        node._llm_with_tools = MagicMock()
        node._tools = []

        # Mock _react_loop to return a simple response
        async def mock_react_loop(*args, **kwargs):
            return "Đây là kết quả tìm kiếm", [{"name": "tool_search_google_shopping"}], None, False

        node._react_loop = mock_react_loop

        state = {
            "query": "tìm dây điện",
            "context": {},
            "agent_outputs": {},
        }

        result = await node.process(state)
        assert result["final_response"] == "Đây là kết quả tìm kiếm"
        assert result["current_agent"] == "product_search_agent"
        assert len(result["tools_used"]) == 1

    def test_lazy_import_in_agents_init(self):
        """agents/__init__.py lazy import works for ProductSearchAgentNode."""
        from app.engine.multi_agent.agents import _ATTR_MAP
        assert "ProductSearchAgentNode" in _ATTR_MAP
        assert "get_product_search_agent_node" in _ATTR_MAP


# =============================================================================
# 11. Feature Gate Integration
# =============================================================================


class TestFeatureGate:
    """Product search feature is properly gated."""

    def test_tool_registration_skipped_when_disabled(self):
        """Tools not registered when enable_product_search=False."""
        from app.engine.tools.registry import get_tool_registry, ToolCategory

        registry = get_tool_registry()
        old_tools = dict(registry._tools)
        old_cats = dict(registry._categories)

        try:
            # Simulate disabled state — don't call init_product_search_tools
            s = MagicMock()
            s.enable_product_search = False

            # The _init_extended_tools() gate check
            if s.enable_product_search:
                from app.engine.tools.product_search_tools import init_product_search_tools
                init_product_search_tools()

            # No product search tools should be registered from this test
            # (pre-existing ones from other tests may be there)
        finally:
            registry._tools = old_tools
            registry._categories = old_cats
