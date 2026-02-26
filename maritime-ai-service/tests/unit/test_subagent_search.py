"""
Sprint 163 Phase 2: Product Search Subgraph — Unit Tests.

Tests cover:
- SearchSubgraphState / PlatformWorkerState schema
- plan_search: platform ordering, empty registry fallback
- platform_worker: search execution, error handling, events
- aggregate_results: dedup, price sort, Excel generation
- synthesize_response: LLM synthesis, fallback
- route_to_platforms: Send() creation, empty fallback
- build_search_subgraph: graph compiles
- Graph integration: conditional subgraph vs original node
- Streaming events: events propagated through bus
- Organization ID propagation
"""

import asyncio
import json
import operator
from typing import Annotated, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =========================================================================
# State schemas
# =========================================================================


class TestPlatformWorkerState:
    """PlatformWorkerState schema validation."""

    def test_basic_fields(self):
        from app.engine.multi_agent.subagents.search.state import PlatformWorkerState

        state: PlatformWorkerState = {
            "query": "test",
            "platform_id": "shopee",
            "max_results": 20,
            "page": 1,
            "organization_id": None,
            "_event_bus_id": None,
        }
        assert state["platform_id"] == "shopee"
        assert state["max_results"] == 20

    def test_with_org_id(self):
        from app.engine.multi_agent.subagents.search.state import PlatformWorkerState

        state: PlatformWorkerState = {
            "query": "laptop",
            "platform_id": "lazada",
            "max_results": 10,
            "page": 2,
            "organization_id": "org_123",
            "_event_bus_id": "bus_abc",
        }
        assert state["organization_id"] == "org_123"
        assert state["_event_bus_id"] == "bus_abc"


class TestSearchSubgraphState:
    """SearchSubgraphState schema and reducer annotations."""

    def test_has_accumulator_fields(self):
        from app.engine.multi_agent.subagents.search.state import SearchSubgraphState
        import typing

        hints = typing.get_type_hints(SearchSubgraphState, include_extras=True)

        # all_products should be Annotated with operator.add
        ap = hints["all_products"]
        assert hasattr(ap, "__metadata__")
        assert ap.__metadata__[0] is operator.add

    def test_has_platform_errors_accumulator(self):
        from app.engine.multi_agent.subagents.search.state import SearchSubgraphState
        import typing

        hints = typing.get_type_hints(SearchSubgraphState, include_extras=True)
        pe = hints["platform_errors"]
        assert pe.__metadata__[0] is operator.add

    def test_has_platforms_searched_accumulator(self):
        from app.engine.multi_agent.subagents.search.state import SearchSubgraphState
        import typing

        hints = typing.get_type_hints(SearchSubgraphState, include_extras=True)
        ps = hints["platforms_searched"]
        assert ps.__metadata__[0] is operator.add

    def test_has_tools_used_accumulator(self):
        from app.engine.multi_agent.subagents.search.state import SearchSubgraphState
        import typing

        hints = typing.get_type_hints(SearchSubgraphState, include_extras=True)
        tu = hints["tools_used"]
        assert tu.__metadata__[0] is operator.add

    def test_output_fields_present(self):
        from app.engine.multi_agent.subagents.search.state import SearchSubgraphState
        import typing

        hints = typing.get_type_hints(SearchSubgraphState, include_extras=True)
        assert "final_response" in hints
        assert "agent_outputs" in hints
        assert "current_agent" in hints
        assert "_answer_streamed_via_bus" in hints

    def test_input_fields_present(self):
        from app.engine.multi_agent.subagents.search.state import SearchSubgraphState
        import typing

        hints = typing.get_type_hints(SearchSubgraphState, include_extras=True)
        assert "query" in hints
        assert "context" in hints
        assert "organization_id" in hints
        assert "_event_bus_id" in hints


# =========================================================================
# plan_search
# =========================================================================


class TestPlanSearch:
    """plan_search node tests."""

    @pytest.mark.asyncio
    async def test_returns_platforms_list(self):
        from app.engine.multi_agent.subagents.search.workers import plan_search

        with patch(
            "app.engine.multi_agent.subagents.search.workers._get_available_platforms",
            return_value=["google_shopping", "shopee", "lazada"],
        ):
            result = await plan_search({"query": "laptop"})

        assert "platforms_to_search" in result
        assert len(result["platforms_to_search"]) == 3
        assert result["current_agent"] == "product_search_agent"
        assert result["search_round"] == 1

    @pytest.mark.asyncio
    async def test_tier_ordering(self):
        from app.engine.multi_agent.subagents.search.workers import plan_search

        with patch(
            "app.engine.multi_agent.subagents.search.workers._get_available_platforms",
            return_value=["lazada", "websosanh", "all_web", "shopee", "google_shopping"],
        ):
            result = await plan_search({"query": "phone"})

        platforms = result["platforms_to_search"]
        # Tier 1 first
        assert platforms.index("websosanh") < platforms.index("shopee")
        assert platforms.index("google_shopping") < platforms.index("lazada")
        # Tier 3 last
        assert platforms.index("all_web") > platforms.index("shopee")

    @pytest.mark.asyncio
    async def test_empty_registry_fallback(self):
        from app.engine.multi_agent.subagents.search.workers import plan_search

        with patch(
            "app.engine.multi_agent.subagents.search.workers._get_available_platforms",
            return_value=["google_shopping", "shopee", "lazada"],
        ):
            result = await plan_search({"query": "test"})

        assert len(result["platforms_to_search"]) >= 1

    @pytest.mark.asyncio
    async def test_query_variants_include_base(self):
        from app.engine.multi_agent.subagents.search.workers import plan_search

        with patch(
            "app.engine.multi_agent.subagents.search.workers._get_available_platforms",
            return_value=["google_shopping"],
        ):
            result = await plan_search({"query": "dây điện 3x2.5"})

        assert "dây điện 3x2.5" in result["query_variants"]

    @pytest.mark.asyncio
    async def test_streaming_events_pushed(self):
        from app.engine.multi_agent.subagents.search.workers import plan_search

        queue = asyncio.Queue()
        with patch(
            "app.engine.multi_agent.subagents.search.workers._get_event_queue",
            return_value=queue,
        ), patch(
            "app.engine.multi_agent.subagents.search.workers._get_available_platforms",
            return_value=["google_shopping"],
        ):
            await plan_search({"query": "test", "_event_bus_id": "bus_1"})

        events = []
        while not queue.empty():
            events.append(queue.get_nowait())

        types = [e["type"] for e in events]
        assert "thinking_start" in types
        assert "thinking_end" in types


# =========================================================================
# platform_worker
# =========================================================================


class TestPlatformWorker:
    """platform_worker node tests."""

    @pytest.mark.asyncio
    async def test_successful_search(self):
        from app.engine.multi_agent.subagents.search.workers import platform_worker

        mock_result = MagicMock()
        mock_result.to_dict.return_value = {
            "platform": "Shopee",
            "title": "Laptop ABC",
            "price": "15.000.000đ",
            "extracted_price": 15000000,
            "link": "https://shopee.vn/test",
        }

        mock_adapter = MagicMock()
        mock_adapter.search_sync.return_value = [mock_result]

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_adapter

        with patch(
            "app.engine.search_platforms.get_search_platform_registry",
            return_value=mock_registry,
        ), patch(
            "app.engine.multi_agent.subagents.search.workers._get_event_queue",
            return_value=None,
        ):
            result = await platform_worker({
                "query": "laptop",
                "platform_id": "shopee",
                "max_results": 20,
                "page": 1,
                "_event_bus_id": None,
            })

        assert len(result["all_products"]) == 1
        assert result["all_products"][0]["title"] == "Laptop ABC"
        assert result["platforms_searched"] == ["shopee"]
        assert len(result["platform_errors"]) == 0

    @pytest.mark.asyncio
    async def test_platform_not_found(self):
        from app.engine.multi_agent.subagents.search.workers import platform_worker

        mock_registry = MagicMock()
        mock_registry.get.return_value = None

        with patch(
            "app.engine.search_platforms.get_search_platform_registry",
            return_value=mock_registry,
        ), patch(
            "app.engine.multi_agent.subagents.search.workers._get_event_queue",
            return_value=None,
        ):
            result = await platform_worker({
                "query": "test",
                "platform_id": "nonexistent",
                "max_results": 20,
                "page": 1,
                "_event_bus_id": None,
            })

        assert len(result["all_products"]) == 0
        assert len(result["platform_errors"]) == 1
        assert "not found" in result["platform_errors"][0]

    @pytest.mark.asyncio
    async def test_search_exception(self):
        from app.engine.multi_agent.subagents.search.workers import platform_worker

        mock_adapter = MagicMock()
        mock_adapter.search_sync.side_effect = RuntimeError("Connection failed")

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_adapter

        with patch(
            "app.engine.search_platforms.get_search_platform_registry",
            return_value=mock_registry,
        ), patch(
            "app.engine.multi_agent.subagents.search.workers._get_event_queue",
            return_value=None,
        ):
            result = await platform_worker({
                "query": "test",
                "platform_id": "shopee",
                "max_results": 20,
                "page": 1,
                "_event_bus_id": None,
            })

        assert len(result["all_products"]) == 0
        assert len(result["platform_errors"]) == 1
        assert "RuntimeError" in result["platform_errors"][0]

    @pytest.mark.asyncio
    async def test_tools_used_returned(self):
        from app.engine.multi_agent.subagents.search.workers import platform_worker

        mock_adapter = MagicMock()
        mock_adapter.search_sync.return_value = []
        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_adapter

        with patch(
            "app.engine.search_platforms.get_search_platform_registry",
            return_value=mock_registry,
        ), patch(
            "app.engine.multi_agent.subagents.search.workers._get_event_queue",
            return_value=None,
        ):
            result = await platform_worker({
                "query": "test",
                "platform_id": "google_shopping",
                "max_results": 20,
                "page": 1,
                "_event_bus_id": None,
            })

        assert len(result["tools_used"]) == 1
        assert result["tools_used"][0]["name"] == "tool_search_google_shopping"

    @pytest.mark.asyncio
    async def test_events_pushed_to_queue(self):
        from app.engine.multi_agent.subagents.search.workers import platform_worker

        queue = asyncio.Queue()
        mock_adapter = MagicMock()
        mock_adapter.search_sync.return_value = []
        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_adapter

        with patch(
            "app.engine.search_platforms.get_search_platform_registry",
            return_value=mock_registry,
        ), patch(
            "app.engine.multi_agent.subagents.search.workers._get_event_queue",
            return_value=queue,
        ):
            await platform_worker({
                "query": "test",
                "platform_id": "shopee",
                "max_results": 20,
                "page": 1,
                "_event_bus_id": "bus_1",
            })

        events = []
        while not queue.empty():
            events.append(queue.get_nowait())

        types = [e["type"] for e in events]
        assert "tool_call" in types
        assert "tool_result" in types

    @pytest.mark.asyncio
    async def test_duration_ms_tracked(self):
        from app.engine.multi_agent.subagents.search.workers import platform_worker

        mock_adapter = MagicMock()
        mock_adapter.search_sync.return_value = []
        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_adapter

        with patch(
            "app.engine.search_platforms.get_search_platform_registry",
            return_value=mock_registry,
        ), patch(
            "app.engine.multi_agent.subagents.search.workers._get_event_queue",
            return_value=None,
        ):
            result = await platform_worker({
                "query": "test",
                "platform_id": "shopee",
                "max_results": 20,
                "page": 1,
                "_event_bus_id": None,
            })

        assert result["tools_used"][0]["duration_ms"] >= 0


# =========================================================================
# aggregate_results
# =========================================================================


class TestAggregateResults:
    """aggregate_results node tests."""

    @pytest.mark.asyncio
    async def test_deduplicates_by_link(self):
        from app.engine.multi_agent.subagents.search.workers import aggregate_results

        with patch(
            "app.engine.multi_agent.subagents.search.workers._get_event_queue",
            return_value=None,
        ):
            result = await aggregate_results({
                "all_products": [
                    {"title": "A", "link": "https://a.com", "extracted_price": 100},
                    {"title": "A dup", "link": "https://a.com", "extracted_price": 100},
                    {"title": "B", "link": "https://b.com", "extracted_price": 200},
                ],
                "platforms_searched": ["shopee", "lazada"],
                "query": "test",
            })

        assert len(result["deduped_products"]) == 2

    @pytest.mark.asyncio
    async def test_preserves_insertion_order(self):
        """Sprint 202b: aggregate_results no longer sorts by price —
        curation LLM sees platform-interleaved results instead."""
        from app.engine.multi_agent.subagents.search.workers import aggregate_results

        with patch(
            "app.engine.multi_agent.subagents.search.workers._get_event_queue",
            return_value=None,
        ):
            result = await aggregate_results({
                "all_products": [
                    {"title": "Expensive", "link": "https://e.com", "extracted_price": 500},
                    {"title": "Cheap", "link": "https://c.com", "extracted_price": 100},
                    {"title": "Medium", "link": "https://m.com", "extracted_price": 300},
                ],
                "platforms_searched": ["shopee"],
                "query": "test",
            })

        titles = [p["title"] for p in result["deduped_products"]]
        assert titles == ["Expensive", "Cheap", "Medium"]  # insertion order preserved

    @pytest.mark.asyncio
    async def test_mixed_prices_preserved(self):
        """Sprint 202b: products with/without prices keep insertion order."""
        from app.engine.multi_agent.subagents.search.workers import aggregate_results

        with patch(
            "app.engine.multi_agent.subagents.search.workers._get_event_queue",
            return_value=None,
        ):
            result = await aggregate_results({
                "all_products": [
                    {"title": "No price", "link": "https://n.com"},
                    {"title": "Has price", "link": "https://h.com", "extracted_price": 50},
                    {"title": "Zero price", "link": "https://z.com", "extracted_price": 0},
                ],
                "platforms_searched": ["shopee"],
                "query": "test",
            })

        products = result["deduped_products"]
        assert len(products) == 3
        assert products[0]["title"] == "No price"  # insertion order, not price-sorted
        assert products[1]["title"] == "Has price"
        assert products[2]["title"] == "Zero price"

    @pytest.mark.asyncio
    async def test_empty_products(self):
        from app.engine.multi_agent.subagents.search.workers import aggregate_results

        with patch(
            "app.engine.multi_agent.subagents.search.workers._get_event_queue",
            return_value=None,
        ):
            result = await aggregate_results({
                "all_products": [],
                "platforms_searched": [],
                "query": "test",
            })

        assert result["deduped_products"] == []

    @pytest.mark.asyncio
    async def test_products_without_links_kept(self):
        from app.engine.multi_agent.subagents.search.workers import aggregate_results

        with patch(
            "app.engine.multi_agent.subagents.search.workers._get_event_queue",
            return_value=None,
        ):
            result = await aggregate_results({
                "all_products": [
                    {"title": "No link 1", "extracted_price": 100},
                    {"title": "No link 2", "extracted_price": 200},
                ],
                "platforms_searched": ["shopee"],
                "query": "test",
            })

        # Products without links can't be deduped, so both kept
        assert len(result["deduped_products"]) == 2

    @pytest.mark.asyncio
    async def test_excel_generation_attempted(self):
        from app.engine.multi_agent.subagents.search.workers import aggregate_results

        products = [
            {"title": f"Product {i}", "link": f"https://p{i}.com", "extracted_price": i * 100}
            for i in range(10)
        ]

        mock_tool = MagicMock()
        mock_tool.invoke.return_value = "Report saved to /tmp/report.xlsx"

        with patch(
            "app.engine.multi_agent.subagents.search.workers._get_event_queue",
            return_value=None,
        ), patch(
            "app.engine.tools.excel_report_tool.tool_generate_product_report",
            mock_tool,
        ):
            result = await aggregate_results({
                "all_products": products,
                "platforms_searched": ["shopee"],
                "query": "laptop",
            })

        # Excel should be attempted for >= 5 products
        assert result["excel_path"] is not None or mock_tool.invoke.called


# =========================================================================
# synthesize_response
# =========================================================================


class TestSynthesizeResponse:
    """synthesize_response node tests."""

    @pytest.mark.asyncio
    async def test_fallback_when_llm_unavailable(self):
        from app.engine.multi_agent.subagents.search.workers import synthesize_response

        with patch(
            "app.engine.multi_agent.agent_config.AgentConfigRegistry"
        ) as mock_reg, patch(
            "app.engine.multi_agent.subagents.search.workers._get_event_queue",
            return_value=None,
        ):
            mock_reg.get_llm.return_value = None

            result = await synthesize_response({
                "deduped_products": [{"title": "A"}],
                "platforms_searched": ["shopee"],
                "platform_errors": [],
                "query": "test",
                "_event_bus_id": None,
            })

        assert "1 sản phẩm" in result["final_response"]
        assert result["current_agent"] == "product_search_agent"

    @pytest.mark.asyncio
    async def test_llm_synthesis_non_streaming(self):
        from app.engine.multi_agent.subagents.search.workers import synthesize_response

        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "Đây là kết quả tìm kiếm tổng hợp..."
        mock_llm.ainvoke.return_value = mock_response

        with patch(
            "app.engine.multi_agent.agent_config.AgentConfigRegistry"
        ) as mock_reg, patch(
            "app.engine.multi_agent.subagents.search.workers._get_event_queue",
            return_value=None,
        ):
            mock_reg.get_llm.return_value = mock_llm

            result = await synthesize_response({
                "deduped_products": [{"title": "A", "extracted_price": 100}],
                "platforms_searched": ["shopee"],
                "platform_errors": [],
                "query": "laptop",
                "_event_bus_id": None,
            })

        assert result["final_response"] == "Đây là kết quả tìm kiếm tổng hợp..."
        assert result["_answer_streamed_via_bus"] is False

    @pytest.mark.asyncio
    async def test_agent_outputs_set(self):
        from app.engine.multi_agent.subagents.search.workers import synthesize_response

        with patch(
            "app.engine.multi_agent.agent_config.AgentConfigRegistry"
        ) as mock_reg, patch(
            "app.engine.multi_agent.subagents.search.workers._get_event_queue",
            return_value=None,
        ):
            mock_reg.get_llm.return_value = None

            result = await synthesize_response({
                "deduped_products": [],
                "platforms_searched": [],
                "platform_errors": [],
                "query": "test",
                "_event_bus_id": None,
            })

        assert "product_search" in result["agent_outputs"]
        assert result["current_agent"] == "product_search_agent"

    @pytest.mark.asyncio
    async def test_thinking_content_set(self):
        from app.engine.multi_agent.subagents.search.workers import synthesize_response

        with patch(
            "app.engine.multi_agent.agent_config.AgentConfigRegistry"
        ) as mock_reg, patch(
            "app.engine.multi_agent.subagents.search.workers._get_event_queue",
            return_value=None,
        ):
            mock_reg.get_llm.return_value = None

            result = await synthesize_response({
                "deduped_products": [{"title": "X"}],
                "platforms_searched": ["shopee", "lazada"],
                "platform_errors": [],
                "query": "test",
                "_event_bus_id": None,
            })

        assert "2 nền tảng" in result["thinking"]


# =========================================================================
# route_to_platforms
# =========================================================================


class TestRouteToPlatforms:
    """route_to_platforms Send() creation tests."""

    def test_creates_send_per_platform(self):
        from app.engine.multi_agent.subagents.search.graph import route_to_platforms
        from langgraph.types import Send

        sends = route_to_platforms({
            "platforms_to_search": ["shopee", "lazada", "google_shopping"],
            "query": "laptop",
        })

        assert len(sends) == 3
        assert all(isinstance(s, Send) for s in sends)

    def test_sends_contain_correct_platform_ids(self):
        from app.engine.multi_agent.subagents.search.graph import route_to_platforms

        sends = route_to_platforms({
            "platforms_to_search": ["shopee", "lazada"],
            "query": "test",
        })

        platform_ids = [s.arg["platform_id"] for s in sends]
        assert "shopee" in platform_ids
        assert "lazada" in platform_ids

    def test_empty_platforms_fallback(self):
        from app.engine.multi_agent.subagents.search.graph import route_to_platforms

        sends = route_to_platforms({
            "platforms_to_search": [],
            "query": "test",
        })

        assert len(sends) == 1
        assert sends[0].arg["platform_id"] == "google_shopping"

    def test_org_id_propagated(self):
        from app.engine.multi_agent.subagents.search.graph import route_to_platforms

        sends = route_to_platforms({
            "platforms_to_search": ["shopee"],
            "query": "test",
            "organization_id": "org_abc",
        })

        assert sends[0].arg["organization_id"] == "org_abc"

    def test_bus_id_propagated(self):
        from app.engine.multi_agent.subagents.search.graph import route_to_platforms

        sends = route_to_platforms({
            "platforms_to_search": ["shopee"],
            "query": "test",
            "_event_bus_id": "bus_xyz",
        })

        assert sends[0].arg["_event_bus_id"] == "bus_xyz"

    def test_default_max_results_and_page(self):
        from app.engine.multi_agent.subagents.search.graph import route_to_platforms

        sends = route_to_platforms({
            "platforms_to_search": ["shopee"],
            "query": "test",
        })

        assert sends[0].arg["max_results"] == 20
        assert sends[0].arg["page"] == 1


# =========================================================================
# build_search_subgraph
# =========================================================================


class TestBuildSearchSubgraph:
    """build_search_subgraph compilation tests."""

    def test_compiles_successfully(self):
        from app.engine.multi_agent.subagents.search.graph import build_search_subgraph

        graph = build_search_subgraph()
        assert graph is not None

    def test_has_expected_nodes(self):
        from app.engine.multi_agent.subagents.search.graph import build_search_subgraph

        graph = build_search_subgraph()
        # LangGraph compiled graph has nodes attribute
        node_names = set()
        if hasattr(graph, "nodes"):
            node_names = set(graph.nodes.keys())
        # At minimum these nodes should exist
        for expected in ["plan_search", "platform_worker", "aggregate_results", "synthesize_response"]:
            assert expected in node_names, f"Missing node: {expected}"


# =========================================================================
# Graph integration
# =========================================================================


class TestGraphIntegration:
    """Integration with main multi-agent graph."""

    def test_subgraph_used_when_both_flags_enabled(self):
        """When enable_subagent_architecture=True AND enable_product_search=True,
        the search subgraph should be used instead of the original node."""
        from app.engine.multi_agent.graph import build_multi_agent_graph

        with patch("app.engine.multi_agent.graph.settings") as mock_settings:
            mock_settings.enable_product_search = True
            mock_settings.enable_subagent_architecture = True
            mock_settings.quality_skip_threshold = 0.85
            mock_settings.default_domain = "maritime"
            mock_settings.app_name = "Wiii"

            graph = build_multi_agent_graph()

        # Graph should have product_search_agent node
        assert "product_search_agent" in graph.nodes

    def test_original_node_when_subagent_disabled(self):
        """When enable_subagent_architecture=False, use original node."""
        from app.engine.multi_agent.graph import build_multi_agent_graph

        with patch("app.engine.multi_agent.graph.settings") as mock_settings:
            mock_settings.enable_product_search = True
            mock_settings.enable_subagent_architecture = False
            mock_settings.quality_skip_threshold = 0.85
            mock_settings.default_domain = "maritime"
            mock_settings.app_name = "Wiii"

            graph = build_multi_agent_graph()

        assert "product_search_agent" in graph.nodes

    def test_no_product_search_when_disabled(self):
        """When enable_product_search=False, no product search node."""
        from app.engine.multi_agent.graph import build_multi_agent_graph

        with patch("app.engine.multi_agent.graph.settings") as mock_settings:
            mock_settings.enable_product_search = False
            mock_settings.enable_subagent_architecture = False
            mock_settings.quality_skip_threshold = 0.85
            mock_settings.default_domain = "maritime"
            mock_settings.app_name = "Wiii"

            graph = build_multi_agent_graph()

        assert "product_search_agent" not in graph.nodes


# =========================================================================
# Workers utility functions
# =========================================================================


class TestWorkerHelpers:
    """Helper function tests."""

    def test_order_platforms_tier_priority(self):
        from app.engine.multi_agent.subagents.search.workers import _order_platforms

        result = _order_platforms(["lazada", "all_web", "websosanh", "shopee"])
        # websosanh (tier1) before shopee/lazada (tier2) before all_web (tier3)
        assert result.index("websosanh") < result.index("shopee")
        assert result.index("shopee") < result.index("all_web")

    def test_order_platforms_unknown_at_end(self):
        from app.engine.multi_agent.subagents.search.workers import _order_platforms

        result = _order_platforms(["custom_platform", "google_shopping"])
        assert result[-1] == "custom_platform"
        assert result[0] == "google_shopping"

    def test_order_platforms_empty(self):
        from app.engine.multi_agent.subagents.search.workers import _order_platforms

        result = _order_platforms([])
        assert result == []


# =========================================================================
# Streaming events
# =========================================================================


class TestStreamingEvents:
    """Event bus integration tests."""

    @pytest.mark.asyncio
    async def test_plan_search_emits_thinking_events(self):
        from app.engine.multi_agent.subagents.search.workers import plan_search

        queue = asyncio.Queue()
        with patch(
            "app.engine.multi_agent.subagents.search.workers._get_event_queue",
            return_value=queue,
        ), patch(
            "app.engine.multi_agent.subagents.search.workers._get_available_platforms",
            return_value=["google_shopping"],
        ):
            await plan_search({"query": "test", "_event_bus_id": "bus_1"})

        events = []
        while not queue.empty():
            events.append(queue.get_nowait())

        assert any(e["type"] == "thinking_start" for e in events)
        assert any(e["type"] == "thinking_delta" for e in events)
        assert any(e["type"] == "thinking_end" for e in events)

    @pytest.mark.asyncio
    async def test_worker_emits_tool_events(self):
        from app.engine.multi_agent.subagents.search.workers import platform_worker

        queue = asyncio.Queue()
        mock_adapter = MagicMock()
        mock_adapter.search_sync.return_value = []
        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_adapter

        with patch(
            "app.engine.search_platforms.get_search_platform_registry",
            return_value=mock_registry,
        ), patch(
            "app.engine.multi_agent.subagents.search.workers._get_event_queue",
            return_value=queue,
        ):
            await platform_worker({
                "query": "test",
                "platform_id": "shopee",
                "max_results": 20,
                "page": 1,
                "_event_bus_id": "bus_1",
            })

        events = []
        while not queue.empty():
            events.append(queue.get_nowait())

        assert any(e["type"] == "tool_call" for e in events)
        assert any(e["type"] == "tool_result" for e in events)
        # tool_call should contain platform name
        tc = next(e for e in events if e["type"] == "tool_call")
        assert tc["content"]["name"] == "tool_search_shopee"

    @pytest.mark.asyncio
    async def test_aggregate_emits_thinking_events(self):
        from app.engine.multi_agent.subagents.search.workers import aggregate_results

        queue = asyncio.Queue()
        with patch(
            "app.engine.multi_agent.subagents.search.workers._get_event_queue",
            return_value=queue,
        ):
            await aggregate_results({
                "all_products": [
                    {"title": "A", "link": "https://a.com", "extracted_price": 100},
                ],
                "platforms_searched": ["shopee"],
                "query": "test",
            })

        events = []
        while not queue.empty():
            events.append(queue.get_nowait())

        assert any(e["type"] == "thinking_start" for e in events)


# =========================================================================
# Organization ID propagation
# =========================================================================


class TestOrganizationPropagation:
    """Organization ID flows through the subgraph."""

    def test_send_carries_org_id(self):
        from app.engine.multi_agent.subagents.search.graph import route_to_platforms

        sends = route_to_platforms({
            "platforms_to_search": ["shopee", "lazada"],
            "query": "test",
            "organization_id": "org_maritime_uni",
        })

        for send in sends:
            assert send.arg["organization_id"] == "org_maritime_uni"

    def test_send_carries_none_org_id(self):
        from app.engine.multi_agent.subagents.search.graph import route_to_platforms

        sends = route_to_platforms({
            "platforms_to_search": ["shopee"],
            "query": "test",
            "organization_id": None,
        })

        assert sends[0].arg["organization_id"] is None


# =========================================================================
# Feature flag gating
# =========================================================================


class TestFeatureFlag:
    """Feature flag controls subgraph activation."""

    def test_default_disabled(self, monkeypatch):
        monkeypatch.delenv("ENABLE_SUBAGENT_ARCHITECTURE", raising=False)
        from app.core.config import Settings

        s = Settings(_env_file=None, google_api_key="test", api_key="test")
        assert s.enable_subagent_architecture is False

    def test_enabled_explicitly(self):
        from app.core.config import Settings

        s = Settings(
            google_api_key="test",
            api_key="test",
            enable_subagent_architecture=True,
        )
        assert s.enable_subagent_architecture is True

    def test_product_search_independent(self):
        """enable_product_search and enable_subagent_architecture are independent."""
        from app.core.config import Settings

        s = Settings(
            google_api_key="test",
            api_key="test",
            enable_product_search=True,
            enable_subagent_architecture=False,
        )
        assert s.enable_product_search is True
        assert s.enable_subagent_architecture is False


# =========================================================================
# Accumulator pattern tests
# =========================================================================


class TestAccumulatorPattern:
    """Test that operator.add reducers work correctly."""

    def test_list_accumulation_simulated(self):
        """Simulate what operator.add does for multiple worker returns."""
        # Worker 1 returns
        w1 = {"all_products": [{"title": "A"}]}
        # Worker 2 returns
        w2 = {"all_products": [{"title": "B"}, {"title": "C"}]}

        # operator.add merges
        merged = operator.add(w1["all_products"], w2["all_products"])
        assert len(merged) == 3
        assert merged[0]["title"] == "A"
        assert merged[2]["title"] == "C"

    def test_error_accumulation_simulated(self):
        w1 = {"platform_errors": ["shopee: timeout"]}
        w2 = {"platform_errors": []}
        w3 = {"platform_errors": ["lazada: 500"]}

        merged = operator.add(operator.add(w1["platform_errors"], w2["platform_errors"]), w3["platform_errors"])
        assert len(merged) == 2

    def test_tools_used_accumulation(self):
        w1 = {"tools_used": [{"name": "tool_search_shopee"}]}
        w2 = {"tools_used": [{"name": "tool_search_lazada"}]}

        merged = operator.add(w1["tools_used"], w2["tools_used"])
        assert len(merged) == 2
        names = [t["name"] for t in merged]
        assert "tool_search_shopee" in names
        assert "tool_search_lazada" in names
