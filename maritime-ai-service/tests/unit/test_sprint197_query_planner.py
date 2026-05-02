"""
Sprint 197: LLM Query Planner Tests — "Thông Minh Tìm Kiếm"

Tests for:
- app/engine/tools/query_planner.py (models, planner, format)
- product_search_node.py integration (plan injection via _react_loop)
- subagents/search/workers.py integration (plan injection via subagent flow)
- dealer_search_tool.py search_queries param
- international_search_tool.py search_queries param
- config flag

70 tests total.

GOTCHA: All modules use lazy imports (inside function bodies), so
patch at SOURCE module: app.core.config.get_settings, app.engine.llm_pool.get_llm_light
"""

import json
import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


@pytest.fixture(autouse=True)
def _structured_invoke_uses_test_llm_mock(monkeypatch):
    """Keep planner tests on the mocked LLM seam, not the real failover pool."""

    async def _ainvoke(*, llm, schema, payload, **kwargs):
        structured_llm = llm.with_structured_output(schema)
        return await structured_llm.ainvoke(payload)

    monkeypatch.setattr(
        "app.services.structured_invoke_service.StructuredInvokeService.ainvoke",
        _ainvoke,
    )


# =============================================================================
# 1. Pydantic Model Tests (12 tests)
# =============================================================================

class TestSearchIntent:
    """Test SearchIntent enum."""

    def test_b2c_consumer_value(self):
        from app.engine.tools.query_planner import SearchIntent
        assert SearchIntent.B2C_CONSUMER == "B2C_CONSUMER"

    def test_b2b_sourcing_value(self):
        from app.engine.tools.query_planner import SearchIntent
        assert SearchIntent.B2B_SOURCING == "B2B_SOURCING"

    def test_price_comparison_value(self):
        from app.engine.tools.query_planner import SearchIntent
        assert SearchIntent.PRICE_COMPARISON == "PRICE_COMPARISON"

    def test_international_value(self):
        from app.engine.tools.query_planner import SearchIntent
        assert SearchIntent.INTERNATIONAL == "INTERNATIONAL"


class TestSearchStrategy:
    """Test SearchStrategy enum."""

    def test_ecommerce_first(self):
        from app.engine.tools.query_planner import SearchStrategy
        assert SearchStrategy.ECOMMERCE_FIRST == "ECOMMERCE_FIRST"

    def test_b2b_first(self):
        from app.engine.tools.query_planner import SearchStrategy
        assert SearchStrategy.B2B_FIRST == "B2B_FIRST"

    def test_comparison_first(self):
        from app.engine.tools.query_planner import SearchStrategy
        assert SearchStrategy.COMPARISON_FIRST == "COMPARISON_FIRST"


class TestSubQuery:
    """Test SubQuery model."""

    def test_basic_creation(self):
        from app.engine.tools.query_planner import SubQuery
        sq = SubQuery(platform="dealer", query="Zebra ZXP7 dealer Vietnam", language="en", priority=1)
        assert sq.platform == "dealer"
        assert sq.query == "Zebra ZXP7 dealer Vietnam"
        assert sq.language == "en"
        assert sq.priority == 1

    def test_defaults(self):
        from app.engine.tools.query_planner import SubQuery
        sq = SubQuery(platform="shopee", query="đầu in Zebra")
        assert sq.language == "vi"
        assert sq.priority == 1

    def test_priority_bounds(self):
        from app.engine.tools.query_planner import SubQuery
        sq = SubQuery(platform="dealer", query="test", priority=3)
        assert sq.priority == 3
        with pytest.raises(Exception):
            SubQuery(platform="dealer", query="test", priority=0)
        with pytest.raises(Exception):
            SubQuery(platform="dealer", query="test", priority=4)


class TestQueryPlan:
    """Test QueryPlan model."""

    def test_full_creation(self):
        from app.engine.tools.query_planner import QueryPlan, SearchIntent, SearchStrategy, SubQuery
        plan = QueryPlan(
            product_name_en="Zebra ZXP Series 7 Printhead",
            product_name_vi="đầu in máy in thẻ Zebra ZXP7",
            brand="Zebra",
            model_number="ZXP Series 7",
            intent=SearchIntent.B2B_SOURCING,
            search_strategy=SearchStrategy.B2B_FIRST,
            sub_queries=[
                SubQuery(platform="dealer", query="Zebra ZXP7 printhead dealer Vietnam", language="en", priority=1),
                SubQuery(platform="international", query="Zebra ZXP7 printhead price", language="en", priority=1),
            ],
            synonyms=["printhead", "đầu in", "đầu in nhiệt"],
            reasoning="B2B product, dealer search first",
        )
        assert plan.intent == SearchIntent.B2B_SOURCING
        assert len(plan.sub_queries) == 2
        assert len(plan.synonyms) == 3

    def test_defaults(self):
        from app.engine.tools.query_planner import QueryPlan, SearchIntent, SearchStrategy
        plan = QueryPlan(
            product_name_en="iPhone 16",
            product_name_vi="iPhone 16",
        )
        assert plan.intent == SearchIntent.B2C_CONSUMER
        assert plan.search_strategy == SearchStrategy.ECOMMERCE_FIRST
        assert plan.brand == ""
        assert plan.sub_queries == []
        assert plan.synonyms == []

    def test_unicode_names(self):
        from app.engine.tools.query_planner import QueryPlan
        plan = QueryPlan(
            product_name_en="Printhead",
            product_name_vi="đầu in máy in thẻ Zebra ZXP7 — chính hãng",
        )
        assert "đầu in" in plan.product_name_vi
        assert "chính hãng" in plan.product_name_vi


# =============================================================================
# 2. format_plan_for_prompt Tests (11 tests)
# =============================================================================

class TestFormatPlanForPrompt:
    """Test format_plan_for_prompt()."""

    def _make_plan(self, **overrides):
        from app.engine.tools.query_planner import QueryPlan, SearchIntent, SearchStrategy, SubQuery
        defaults = dict(
            product_name_en="Zebra ZXP7 Printhead",
            product_name_vi="đầu in Zebra ZXP7",
            brand="Zebra",
            model_number="ZXP7",
            intent=SearchIntent.B2B_SOURCING,
            search_strategy=SearchStrategy.B2B_FIRST,
            sub_queries=[
                SubQuery(platform="dealer", query="Zebra ZXP7 printhead dealer Vietnam", language="en", priority=1),
                SubQuery(platform="international", query="Zebra ZXP7 printhead price USD", language="en", priority=2),
            ],
            synonyms=["printhead", "đầu in", "đầu in nhiệt"],
            reasoning="B2B industrial product",
        )
        defaults.update(overrides)
        return QueryPlan(**defaults)

    def _fn(self, plan):
        from app.engine.tools.query_planner import format_plan_for_prompt
        return format_plan_for_prompt(plan)

    def test_contains_product_name_en(self):
        result = self._fn(self._make_plan())
        assert "Zebra ZXP7 Printhead" in result

    def test_contains_product_name_vi(self):
        result = self._fn(self._make_plan())
        assert "đầu in Zebra ZXP7" in result

    def test_contains_brand(self):
        result = self._fn(self._make_plan())
        assert "Zebra" in result

    def test_contains_model_number(self):
        result = self._fn(self._make_plan())
        assert "ZXP7" in result

    def test_contains_intent(self):
        result = self._fn(self._make_plan())
        assert "B2B_SOURCING" in result

    def test_contains_strategy(self):
        result = self._fn(self._make_plan())
        assert "B2B_FIRST" in result

    def test_contains_sub_queries(self):
        result = self._fn(self._make_plan())
        assert "Zebra ZXP7 printhead dealer Vietnam" in result
        assert "Zebra ZXP7 printhead price USD" in result

    def test_contains_synonyms(self):
        result = self._fn(self._make_plan())
        assert "printhead" in result
        assert "đầu in nhiệt" in result

    def test_priority_grouping(self):
        from app.engine.tools.query_planner import SubQuery
        plan = self._make_plan(sub_queries=[
            SubQuery(platform="dealer", query="q1", priority=1),
            SubQuery(platform="shopee", query="q2", priority=2),
            SubQuery(platform="websosanh", query="q3", priority=3),
        ])
        result = self._fn(plan)
        p1_pos = result.find("Vòng 1")
        p2_pos = result.find("Vòng 2")
        p3_pos = result.find("Vòng 3")
        assert p1_pos < p2_pos < p3_pos

    def test_no_brand_no_model(self):
        result = self._fn(self._make_plan(brand="", model_number=""))
        assert "Thương hiệu" not in result
        assert "Model/Mã SP" not in result

    def test_no_reasoning(self):
        result = self._fn(self._make_plan(reasoning=""))
        assert "Lý do" not in result


# =============================================================================
# 3. plan_search_queries Tests (15 tests)
# =============================================================================

class TestPlanSearchQueries:
    """Test plan_search_queries().

    GOTCHA: get_settings and get_llm_light are lazy imports in function body.
    Patch at SOURCE: app.core.config.get_settings, app.engine.llm_pool.get_llm_light
    """

    def _mock_settings(self, enabled=True):
        s = MagicMock()
        s.enable_query_planner = enabled
        return s

    def _mock_llm(self, return_value):
        mock_structured_llm = AsyncMock()
        mock_structured_llm.ainvoke = AsyncMock(return_value=return_value)
        mock_llm = MagicMock()
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured_llm)
        return mock_llm, mock_structured_llm

    @pytest.mark.asyncio
    async def test_gate_disabled_returns_none(self):
        with patch("app.core.config.get_settings", return_value=self._mock_settings(enabled=False)):
            from app.engine.tools.query_planner import plan_search_queries
            result = await plan_search_queries("test query")
        assert result is None

    @pytest.mark.asyncio
    async def test_gate_enabled_calls_llm(self):
        from app.engine.tools.query_planner import QueryPlan, SearchIntent, SearchStrategy, SubQuery
        mock_plan = QueryPlan(
            product_name_en="Zebra ZXP7 Printhead",
            product_name_vi="đầu in Zebra ZXP7",
            intent=SearchIntent.B2B_SOURCING,
            search_strategy=SearchStrategy.B2B_FIRST,
            sub_queries=[SubQuery(platform="dealer", query="test query")],
        )
        mock_llm, _ = self._mock_llm(mock_plan)

        with patch("app.core.config.get_settings", return_value=self._mock_settings()), \
             patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm):
            from app.engine.tools.query_planner import plan_search_queries
            result = await plan_search_queries("tìm đầu in Zebra ZXP7")

        assert result is not None
        assert result.intent == SearchIntent.B2B_SOURCING
        assert len(result.sub_queries) == 1

    @pytest.mark.asyncio
    async def test_llm_failure_returns_none(self):
        mock_structured_llm = AsyncMock()
        mock_structured_llm.ainvoke = AsyncMock(side_effect=Exception("LLM timeout"))
        mock_llm = MagicMock()
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured_llm)

        with patch("app.core.config.get_settings", return_value=self._mock_settings()), \
             patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm):
            from app.engine.tools.query_planner import plan_search_queries
            result = await plan_search_queries("test")
        assert result is None

    @pytest.mark.asyncio
    async def test_llm_init_failure_returns_none(self):
        with patch("app.core.config.get_settings", return_value=self._mock_settings()), \
             patch("app.engine.llm_pool.get_llm_light", side_effect=ImportError("no pool")):
            from app.engine.tools.query_planner import plan_search_queries
            result = await plan_search_queries("test")
        assert result is None

    @pytest.mark.asyncio
    async def test_settings_import_failure_returns_none(self):
        with patch("app.core.config.get_settings", side_effect=Exception("config broken")):
            from app.engine.tools.query_planner import plan_search_queries
            result = await plan_search_queries("test")
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_sub_queries_discarded(self):
        from app.engine.tools.query_planner import QueryPlan
        mock_plan = QueryPlan(product_name_en="test", product_name_vi="test", sub_queries=[])
        mock_llm, _ = self._mock_llm(mock_plan)

        with patch("app.core.config.get_settings", return_value=self._mock_settings()), \
             patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm):
            from app.engine.tools.query_planner import plan_search_queries
            result = await plan_search_queries("test")
        assert result is None

    @pytest.mark.asyncio
    async def test_sub_queries_capped_at_10(self):
        from app.engine.tools.query_planner import QueryPlan, SubQuery
        mock_plan = QueryPlan(
            product_name_en="test", product_name_vi="test",
            sub_queries=[SubQuery(platform=f"p{i}", query=f"q{i}") for i in range(15)],
        )
        mock_llm, _ = self._mock_llm(mock_plan)

        with patch("app.core.config.get_settings", return_value=self._mock_settings()), \
             patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm):
            from app.engine.tools.query_planner import plan_search_queries
            result = await plan_search_queries("test")

        assert result is not None
        assert len(result.sub_queries) == 10

    @pytest.mark.asyncio
    async def test_synonyms_capped_at_10(self):
        from app.engine.tools.query_planner import QueryPlan, SubQuery
        mock_plan = QueryPlan(
            product_name_en="test", product_name_vi="test",
            sub_queries=[SubQuery(platform="dealer", query="test")],
            synonyms=[f"synonym_{i}" for i in range(15)],
        )
        mock_llm, _ = self._mock_llm(mock_plan)

        with patch("app.core.config.get_settings", return_value=self._mock_settings()), \
             patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm):
            from app.engine.tools.query_planner import plan_search_queries
            result = await plan_search_queries("test")

        assert result is not None
        assert len(result.synonyms) == 10

    @pytest.mark.asyncio
    async def test_context_passed_to_prompt(self):
        from app.engine.tools.query_planner import QueryPlan, SubQuery
        mock_plan = QueryPlan(
            product_name_en="test", product_name_vi="test",
            sub_queries=[SubQuery(platform="dealer", query="test")],
        )
        mock_llm, mock_struct = self._mock_llm(mock_plan)

        with patch("app.core.config.get_settings", return_value=self._mock_settings()), \
             patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm):
            from app.engine.tools.query_planner import plan_search_queries
            await plan_search_queries(
                "tìm đầu in",
                context={"conversation_summary": "User is looking for printer parts"},
            )

        call_args = mock_struct.ainvoke.call_args
        prompt_text = call_args[0][0]
        assert "User is looking for printer parts" in prompt_text

    @pytest.mark.asyncio
    async def test_context_none_handled(self):
        from app.engine.tools.query_planner import QueryPlan, SubQuery
        mock_plan = QueryPlan(
            product_name_en="test", product_name_vi="test",
            sub_queries=[SubQuery(platform="dealer", query="test")],
        )
        mock_llm, _ = self._mock_llm(mock_plan)

        with patch("app.core.config.get_settings", return_value=self._mock_settings()), \
             patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm):
            from app.engine.tools.query_planner import plan_search_queries
            result = await plan_search_queries("test", context=None)
        assert result is not None

    @pytest.mark.asyncio
    async def test_llm_returns_non_queryplan(self):
        mock_llm, _ = self._mock_llm("not a QueryPlan")

        with patch("app.core.config.get_settings", return_value=self._mock_settings()), \
             patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm):
            from app.engine.tools.query_planner import plan_search_queries
            result = await plan_search_queries("test")
        assert result is None

    @pytest.mark.asyncio
    async def test_llm_returns_none(self):
        mock_llm, _ = self._mock_llm(None)

        with patch("app.core.config.get_settings", return_value=self._mock_settings()), \
             patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm):
            from app.engine.tools.query_planner import plan_search_queries
            result = await plan_search_queries("test")
        assert result is None

    @pytest.mark.asyncio
    async def test_prompt_contains_query(self):
        from app.engine.tools.query_planner import QueryPlan, SubQuery
        mock_plan = QueryPlan(
            product_name_en="test", product_name_vi="test",
            sub_queries=[SubQuery(platform="dealer", query="test")],
        )
        mock_llm, mock_struct = self._mock_llm(mock_plan)

        with patch("app.core.config.get_settings", return_value=self._mock_settings()), \
             patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm):
            from app.engine.tools.query_planner import plan_search_queries
            await plan_search_queries("đầu in Zebra ZXP7 giá rẻ nhất")

        call_args = mock_struct.ainvoke.call_args
        prompt_text = call_args[0][0]
        assert "đầu in Zebra ZXP7 giá rẻ nhất" in prompt_text

    @pytest.mark.asyncio
    async def test_with_structured_output_called_with_queryplan(self):
        from app.engine.tools.query_planner import QueryPlan, SubQuery
        mock_plan = QueryPlan(
            product_name_en="test", product_name_vi="test",
            sub_queries=[SubQuery(platform="dealer", query="test")],
        )
        mock_llm, _ = self._mock_llm(mock_plan)

        with patch("app.core.config.get_settings", return_value=self._mock_settings()), \
             patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm):
            from app.engine.tools.query_planner import plan_search_queries
            await plan_search_queries("test")

        mock_llm.with_structured_output.assert_called_once_with(QueryPlan)

    @pytest.mark.asyncio
    async def test_empty_context_dict_handled(self):
        from app.engine.tools.query_planner import QueryPlan, SubQuery
        mock_plan = QueryPlan(
            product_name_en="test", product_name_vi="test",
            sub_queries=[SubQuery(platform="dealer", query="test")],
        )
        mock_llm, _ = self._mock_llm(mock_plan)

        with patch("app.core.config.get_settings", return_value=self._mock_settings()), \
             patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm):
            from app.engine.tools.query_planner import plan_search_queries
            result = await plan_search_queries("test", context={})
        assert result is not None


# =============================================================================
# 4. Product Search Node Integration Tests (5 tests)
# =============================================================================

class TestProductSearchNodePlannerIntegration:
    """Test planner integration in product_search_node._react_loop().

    These are integration-style tests that verify the planner is called
    and its output is injected into the system prompt.
    """

    def _make_mock_node(self):
        """Create a minimal ProductSearchAgentNode with mocked LLM."""
        from app.engine.multi_agent.agents.product_search_node import ProductSearchAgentNode

        node = ProductSearchAgentNode.__new__(ProductSearchAgentNode)
        node._tools = []
        node._llm = MagicMock()
        node._llm_with_tools = MagicMock()

        mock_response = MagicMock()
        mock_response.content = "Kết quả tìm kiếm"
        mock_response.tool_calls = []

        node._llm_with_tools.ainvoke = AsyncMock(return_value=mock_response)
        node._llm.ainvoke = AsyncMock(return_value=mock_response)

        return node

    @pytest.mark.asyncio
    async def test_planner_disabled_no_plan_in_prompt(self):
        node = self._make_mock_node()
        mock_settings = MagicMock()
        mock_settings.enable_query_planner = False
        mock_settings.product_search_max_iterations = 3

        with patch("app.core.config.get_settings", return_value=mock_settings):
            response, tools, thinking, streamed = await node._react_loop(
                query="test", context={},
            )

        assert response
        call_args = node._llm_with_tools.ainvoke.call_args
        messages = call_args[0][0]
        system_msg = messages[0].content
        assert "KẾ HOẠCH TÌM KIẾM TỐI ƯU" not in system_msg

    @pytest.mark.asyncio
    async def test_planner_enabled_plan_injected(self):
        from app.engine.tools.query_planner import QueryPlan, SearchIntent, SearchStrategy, SubQuery

        node = self._make_mock_node()
        mock_settings = MagicMock()
        mock_settings.enable_query_planner = True
        mock_settings.product_search_max_iterations = 3

        mock_plan = QueryPlan(
            product_name_en="Zebra ZXP7",
            product_name_vi="đầu in Zebra ZXP7",
            intent=SearchIntent.B2B_SOURCING,
            search_strategy=SearchStrategy.B2B_FIRST,
            sub_queries=[SubQuery(platform="dealer", query="Zebra ZXP7 dealer Vietnam")],
        )

        mock_structured_llm = AsyncMock()
        mock_structured_llm.ainvoke = AsyncMock(return_value=mock_plan)
        mock_llm = MagicMock()
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured_llm)

        with patch("app.core.config.get_settings", return_value=mock_settings), \
             patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm):
            response, tools, thinking, streamed = await node._react_loop(
                query="tìm đầu in Zebra ZXP7", context={},
            )

        call_args = node._llm_with_tools.ainvoke.call_args
        messages = call_args[0][0]
        system_msg = messages[0].content
        assert "KẾ HOẠCH TÌM KIẾM TỐI ƯU" in system_msg
        assert "Zebra ZXP7 dealer Vietnam" in system_msg

    @pytest.mark.asyncio
    async def test_planner_failure_graceful_degradation(self):
        node = self._make_mock_node()
        mock_settings = MagicMock()
        mock_settings.enable_query_planner = True
        mock_settings.product_search_max_iterations = 3

        mock_llm = MagicMock()
        mock_llm.with_structured_output = MagicMock(side_effect=Exception("planner crash"))

        with patch("app.core.config.get_settings", return_value=mock_settings), \
             patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm):
            response, tools, thinking, streamed = await node._react_loop(
                query="test", context={},
            )

        assert response is not None

    @pytest.mark.asyncio
    async def test_planner_returns_none_no_plan_injected(self):
        node = self._make_mock_node()
        mock_settings = MagicMock()
        mock_settings.enable_query_planner = True
        mock_settings.product_search_max_iterations = 3

        mock_structured_llm = AsyncMock()
        mock_structured_llm.ainvoke = AsyncMock(return_value=None)
        mock_llm = MagicMock()
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured_llm)

        with patch("app.core.config.get_settings", return_value=mock_settings), \
             patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm):
            response, tools, thinking, streamed = await node._react_loop(
                query="test", context={},
            )

        call_args = node._llm_with_tools.ainvoke.call_args
        messages = call_args[0][0]
        system_msg = messages[0].content
        assert "KẾ HOẠCH TÌM KIẾM TỐI ƯU" not in system_msg

    @pytest.mark.asyncio
    async def test_streaming_events_with_planner(self):
        from app.engine.tools.query_planner import QueryPlan, SearchIntent, SearchStrategy, SubQuery
        import queue as stdlib_queue

        node = self._make_mock_node()
        event_queue = stdlib_queue.Queue()

        mock_settings = MagicMock()
        mock_settings.enable_query_planner = True
        mock_settings.product_search_max_iterations = 3

        mock_plan = QueryPlan(
            product_name_en="test", product_name_vi="test",
            intent=SearchIntent.B2C_CONSUMER,
            search_strategy=SearchStrategy.ECOMMERCE_FIRST,
            sub_queries=[SubQuery(platform="shopee", query="test")],
        )

        mock_structured_llm = AsyncMock()
        mock_structured_llm.ainvoke = AsyncMock(return_value=mock_plan)
        mock_llm = MagicMock()
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured_llm)

        with patch("app.core.config.get_settings", return_value=mock_settings), \
             patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm):
            response, tools, thinking, streamed = await node._react_loop(
                query="test", context={}, event_queue=event_queue,
            )

        events = []
        while not event_queue.empty():
            events.append(event_queue.get_nowait())

        event_types = [e.get("type") for e in events]
        assert "thinking_start" in event_types


# =============================================================================
# 5. Dealer Search search_queries Param Tests (8 tests)
# =============================================================================

class TestDealerSearchSearchQueries:
    """Test dealer_search_tool with search_queries parameter."""

    def test_search_queries_used_when_provided(self):
        from app.engine.tools.dealer_search_tool import _search_dealers

        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        mock_ddgs_instance.__exit__ = MagicMock(return_value=False)
        mock_ddgs_instance.text = MagicMock(return_value=[
            {"href": "https://dealer.vn", "title": "Dealer VN", "body": "Contact us"},
        ])

        with patch("duckduckgo_search.DDGS", return_value=mock_ddgs_instance), \
             patch("app.engine.tools.dealer_search_tool._fetch_page_markdown", return_value=""), \
             patch("app.engine.tools.serper_web_search.is_serper_available", return_value=False):
            result = _search_dealers(
                "Zebra ZXP7",
                search_queries=["Zebra ZXP7 printhead dealer Vietnam"],
            )

        assert mock_ddgs_instance.text.call_count == 1
        call_query = mock_ddgs_instance.text.call_args[0][0]
        assert call_query == "Zebra ZXP7 printhead dealer Vietnam"

    def test_fallback_when_no_search_queries(self):
        from app.engine.tools.dealer_search_tool import _search_dealers

        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        mock_ddgs_instance.__exit__ = MagicMock(return_value=False)
        mock_ddgs_instance.text = MagicMock(return_value=[])

        with patch("duckduckgo_search.DDGS", return_value=mock_ddgs_instance), \
             patch("app.engine.tools.dealer_search_tool._fetch_page_markdown", return_value=""), \
             patch("app.engine.tools.serper_web_search.is_serper_available", return_value=False):
            result = _search_dealers("Zebra ZXP7", search_queries=None)

        assert mock_ddgs_instance.text.call_count == 4

    def test_tool_fn_parses_json_search_queries(self):
        mock_settings = MagicMock()
        mock_settings.enable_dealer_search = True

        with patch("app.core.config.get_settings", return_value=mock_settings), \
             patch("app.engine.tools.dealer_search_tool._search_dealers") as mock_search:
            mock_search.return_value = {"dealers": [], "count": 0, "query": "test"}

            from app.engine.tools.dealer_search_tool import tool_dealer_search_fn
            tool_dealer_search_fn(
                product_name="Zebra ZXP7",
                search_queries='["query1", "query2"]',
            )

        mock_search.assert_called_once_with("Zebra ZXP7", "Vietnam", search_queries=["query1", "query2"])

    def test_tool_fn_invalid_json_uses_default(self):
        mock_settings = MagicMock()
        mock_settings.enable_dealer_search = True

        with patch("app.core.config.get_settings", return_value=mock_settings), \
             patch("app.engine.tools.dealer_search_tool._search_dealers") as mock_search:
            mock_search.return_value = {"dealers": [], "count": 0, "query": "test"}

            from app.engine.tools.dealer_search_tool import tool_dealer_search_fn
            tool_dealer_search_fn(product_name="Zebra ZXP7", search_queries="not valid json")

        mock_search.assert_called_once_with("Zebra ZXP7", "Vietnam", search_queries=None)

    def test_tool_fn_empty_string_uses_default(self):
        mock_settings = MagicMock()
        mock_settings.enable_dealer_search = True

        with patch("app.core.config.get_settings", return_value=mock_settings), \
             patch("app.engine.tools.dealer_search_tool._search_dealers") as mock_search:
            mock_search.return_value = {"dealers": [], "count": 0, "query": "test"}

            from app.engine.tools.dealer_search_tool import tool_dealer_search_fn
            tool_dealer_search_fn(product_name="test", search_queries="")

        mock_search.assert_called_once_with("test", "Vietnam", search_queries=None)

    def test_tool_fn_empty_json_array_uses_default(self):
        mock_settings = MagicMock()
        mock_settings.enable_dealer_search = True

        with patch("app.core.config.get_settings", return_value=mock_settings), \
             patch("app.engine.tools.dealer_search_tool._search_dealers") as mock_search:
            mock_search.return_value = {"dealers": [], "count": 0, "query": "test"}

            from app.engine.tools.dealer_search_tool import tool_dealer_search_fn
            tool_dealer_search_fn(product_name="test", search_queries="[]")

        mock_search.assert_called_once_with("test", "Vietnam", search_queries=None)

    def test_backward_compat_no_search_queries(self):
        mock_settings = MagicMock()
        mock_settings.enable_dealer_search = True

        with patch("app.core.config.get_settings", return_value=mock_settings), \
             patch("app.engine.tools.dealer_search_tool._search_dealers") as mock_search:
            mock_search.return_value = {"dealers": [], "count": 0, "query": "test"}

            from app.engine.tools.dealer_search_tool import tool_dealer_search_fn
            tool_dealer_search_fn(product_name="Zebra ZXP7")

        mock_search.assert_called_once_with("Zebra ZXP7", "Vietnam", search_queries=None)

    def test_structured_tool_creation(self):
        from app.engine.tools.dealer_search_tool import get_dealer_search_tool
        tool = get_dealer_search_tool()
        assert tool.name == "tool_dealer_search"
        assert "Query Planner" in tool.description


# =============================================================================
# 6. International Search search_queries Param Tests (5 tests)
# =============================================================================

class TestInternationalSearchSearchQueries:
    """Test international_search_tool with search_queries parameter."""

    def test_search_queries_used_when_provided(self):
        from app.engine.tools.international_search_tool import _search_international

        mock_settings = MagicMock()
        mock_settings.usd_vnd_exchange_rate = 25500.0

        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        mock_ddgs_instance.__exit__ = MagicMock(return_value=False)
        mock_ddgs_instance.text = MagicMock(return_value=[
            {"href": "https://example.com", "title": "Product", "body": "$150.00"},
        ])

        with patch("duckduckgo_search.DDGS", return_value=mock_ddgs_instance), \
             patch("app.core.config.get_settings", return_value=mock_settings), \
             patch("app.engine.tools.international_search_tool._fetch_page_markdown", return_value=""), \
             patch("app.engine.tools.serper_web_search.is_serper_available", return_value=False):
            result = _search_international(
                "Zebra ZXP7",
                search_queries=["Zebra ZXP7 printhead price wholesale"],
            )

        assert mock_ddgs_instance.text.call_count == 1
        call_query = mock_ddgs_instance.text.call_args[0][0]
        assert call_query == "Zebra ZXP7 printhead price wholesale"

    def test_fallback_when_no_search_queries(self):
        from app.engine.tools.international_search_tool import _search_international

        mock_settings = MagicMock()
        mock_settings.usd_vnd_exchange_rate = 25500.0

        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        mock_ddgs_instance.__exit__ = MagicMock(return_value=False)
        mock_ddgs_instance.text = MagicMock(return_value=[])

        with patch("duckduckgo_search.DDGS", return_value=mock_ddgs_instance), \
             patch("app.core.config.get_settings", return_value=mock_settings), \
             patch("app.engine.tools.serper_web_search.is_serper_available", return_value=False):
            result = _search_international("Zebra ZXP7", search_queries=None)

        assert mock_ddgs_instance.text.call_count == 2

    def test_tool_fn_parses_json_search_queries(self):
        mock_settings = MagicMock()
        mock_settings.enable_international_search = True
        mock_settings.usd_vnd_exchange_rate = 25500.0

        with patch("app.core.config.get_settings", return_value=mock_settings), \
             patch("app.engine.tools.international_search_tool._search_international") as mock_search:
            mock_search.return_value = {"results": [], "count": 0, "exchange_rate": 25500.0}

            from app.engine.tools.international_search_tool import tool_international_search_fn
            tool_international_search_fn(
                product_name="Zebra ZXP7",
                search_queries='["q1 price", "q2 wholesale"]',
            )

        # Sprint 199: regions kwarg added
        mock_search.assert_called_once_with(
            "Zebra ZXP7", "USD",
            search_queries=["q1 price", "q2 wholesale"],
            regions="",
        )

    def test_tool_fn_invalid_json_uses_default(self):
        mock_settings = MagicMock()
        mock_settings.enable_international_search = True

        with patch("app.core.config.get_settings", return_value=mock_settings), \
             patch("app.engine.tools.international_search_tool._search_international") as mock_search:
            mock_search.return_value = {"results": [], "count": 0, "exchange_rate": 25500.0}

            from app.engine.tools.international_search_tool import tool_international_search_fn
            tool_international_search_fn(product_name="test", search_queries="broken json{")

        # Sprint 199: regions kwarg added
        mock_search.assert_called_once_with("test", "USD", search_queries=None, regions="")

    def test_structured_tool_creation(self):
        from app.engine.tools.international_search_tool import get_international_search_tool
        tool = get_international_search_tool()
        assert tool.name == "tool_international_search"
        assert "Query Planner" in tool.description


# =============================================================================
# 7. Config Flag Tests (3 tests)
# =============================================================================

class TestConfigFlag:
    """Test enable_query_planner config flag."""

    def test_default_is_false(self):
        from app.core.config import Settings
        s = Settings(google_api_key="test", _env_file=None)
        assert s.enable_query_planner is False

    def test_can_enable(self):
        from app.core.config import Settings
        s = Settings(google_api_key="test", enable_query_planner=True, _env_file=None)
        assert s.enable_query_planner is True

    def test_env_override(self):
        import os
        with patch.dict(os.environ, {"ENABLE_QUERY_PLANNER": "true"}):
            from app.core.config import Settings
            s = Settings(google_api_key="test", _env_file=None)
            assert s.enable_query_planner is True


# =============================================================================
# 8. Subagent Architecture Integration Tests (10 tests)
# =============================================================================

class TestSubagentPlanSearchIntegration:
    """Test planner integration in subagents/search/workers.plan_search().

    When enable_subagent_architecture=True, the product search uses the
    subgraph flow (plan_search→platform_worker→aggregate→synthesize)
    instead of _react_loop(). The planner must work in both paths.
    """

    def _mock_settings(self, planner=True):
        s = MagicMock()
        s.enable_query_planner = planner
        s.enable_product_search = True
        s.product_search_platforms = ["google_shopping", "shopee"]
        return s

    @pytest.mark.asyncio
    async def test_plan_search_planner_disabled(self):
        """When planner disabled, plan_search returns normally without _query_plan_text."""
        mock_settings = self._mock_settings(planner=False)

        with patch("app.core.config.get_settings", return_value=mock_settings), \
             patch("app.engine.multi_agent.subagents.search.workers._get_available_platforms",
                   return_value=["google_shopping"]), \
             patch("app.engine.multi_agent.subagents.search.workers._get_event_queue",
                   return_value=None):
            from app.engine.multi_agent.subagents.search.workers import plan_search
            result = await plan_search({"query": "test product", "context": {}})

        assert "platforms_to_search" in result
        assert "_query_plan_text" not in result

    @pytest.mark.asyncio
    async def test_plan_search_planner_enabled_injects_plan(self):
        """When planner enabled, plan_search stores _query_plan_text in result."""
        from app.engine.tools.query_planner import QueryPlan, SubQuery

        mock_plan = QueryPlan(
            product_name_en="Test Product",
            product_name_vi="Sản phẩm thử",
            sub_queries=[SubQuery(platform="dealer", query="test dealer query")],
        )

        mock_structured = AsyncMock()
        mock_structured.ainvoke = AsyncMock(return_value=mock_plan)
        mock_llm = MagicMock()
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured)

        mock_settings = self._mock_settings(planner=True)

        with patch("app.core.config.get_settings", return_value=mock_settings), \
             patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm), \
             patch("app.engine.multi_agent.subagents.search.workers._get_available_platforms",
                   return_value=["google_shopping"]), \
             patch("app.engine.multi_agent.subagents.search.workers._get_event_queue",
                   return_value=None):
            from app.engine.multi_agent.subagents.search.workers import plan_search
            result = await plan_search({"query": "tìm sản phẩm", "context": {}})

        assert "_query_plan_text" in result
        assert "KẾ HOẠCH TÌM KIẾM TỐI ƯU" in result["_query_plan_text"]
        assert "Test Product" in result["_query_plan_text"]

    @pytest.mark.asyncio
    async def test_plan_search_planner_failure_graceful(self):
        """Planner failure in plan_search doesn't crash — continues normally."""
        mock_settings = self._mock_settings(planner=True)
        mock_llm = MagicMock()
        mock_llm.with_structured_output = MagicMock(side_effect=Exception("planner crash"))

        with patch("app.core.config.get_settings", return_value=mock_settings), \
             patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm), \
             patch("app.engine.multi_agent.subagents.search.workers._get_available_platforms",
                   return_value=["google_shopping"]), \
             patch("app.engine.multi_agent.subagents.search.workers._get_event_queue",
                   return_value=None):
            from app.engine.multi_agent.subagents.search.workers import plan_search
            result = await plan_search({"query": "test", "context": {}})

        assert "platforms_to_search" in result
        assert "_query_plan_text" not in result

    @pytest.mark.asyncio
    async def test_plan_search_planner_none_result(self):
        """Planner returns None — no _query_plan_text stored."""
        mock_settings = self._mock_settings(planner=True)
        mock_structured = AsyncMock()
        mock_structured.ainvoke = AsyncMock(return_value=None)
        mock_llm = MagicMock()
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured)

        with patch("app.core.config.get_settings", return_value=mock_settings), \
             patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm), \
             patch("app.engine.multi_agent.subagents.search.workers._get_available_platforms",
                   return_value=["google_shopping"]), \
             patch("app.engine.multi_agent.subagents.search.workers._get_event_queue",
                   return_value=None):
            from app.engine.multi_agent.subagents.search.workers import plan_search
            result = await plan_search({"query": "test", "context": {}})

        assert "_query_plan_text" not in result

    @pytest.mark.asyncio
    async def test_plan_search_emits_thinking_events(self):
        """Planner emits thinking_start/delta/end events via event queue."""
        from app.engine.tools.query_planner import QueryPlan, SubQuery

        mock_plan = QueryPlan(
            product_name_en="Test", product_name_vi="Test",
            sub_queries=[SubQuery(platform="dealer", query="test")],
        )
        mock_structured = AsyncMock()
        mock_structured.ainvoke = AsyncMock(return_value=mock_plan)
        mock_llm = MagicMock()
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured)
        mock_settings = self._mock_settings(planner=True)

        eq = asyncio.Queue()

        with patch("app.core.config.get_settings", return_value=mock_settings), \
             patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm), \
             patch("app.engine.multi_agent.subagents.search.workers._get_available_platforms",
                   return_value=["google_shopping"]), \
             patch("app.engine.multi_agent.subagents.search.workers._get_event_queue",
                   return_value=eq):
            from app.engine.multi_agent.subagents.search.workers import plan_search
            await plan_search({"query": "test", "context": {}, "_event_bus_id": "bus1"})

        # Collect all events
        events = []
        while not eq.empty():
            events.append(eq.get_nowait())

        thinking_starts = [
            e for e in events
            if isinstance(e, dict) and e.get("type") == "thinking_start"
        ]
        thinking_deltas = [
            e for e in events
            if isinstance(e, dict) and e.get("type") == "thinking_delta"
        ]
        thinking_ends = [
            e for e in events
            if isinstance(e, dict) and e.get("type") == "thinking_end"
        ]

        assert len(thinking_starts) >= 2, (
            "Expected query-planner + platform-plan thinking_start events, got: "
            f"{[e.get('content', '')[:40] for e in events]}"
        )
        assert thinking_deltas, "Expected planner path to emit thinking_delta chunks"
        assert len(thinking_ends) >= 1

    @pytest.mark.asyncio
    async def test_synthesize_response_uses_plan_text(self):
        """synthesize_response includes _query_plan_text in system prompt."""
        mock_llm_response = MagicMock()
        mock_llm_response.content = "Test response"

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)

        from app.engine.multi_agent.subagents.search.workers import synthesize_response

        with patch("app.engine.multi_agent.agent_config.AgentConfigRegistry.get_llm",
                   return_value=mock_llm):
            result = await synthesize_response({
                "deduped_products": [{"name": "Product A", "price": 100000}],
                "platforms_searched": ["google_shopping"],
                "platform_errors": [],
                "query": "test query",
                "_query_plan_text": "## KẾ HOẠCH TÌM KIẾM TỐI ƯU\n**Sản phẩm**: Test Product",
            })

        # Verify system message includes plan text
        call_args = mock_llm.ainvoke.call_args[0][0]
        system_msg = call_args[0]["content"] if isinstance(call_args[0], dict) else call_args[0].content
        assert "KẾ HOẠCH TÌM KIẾM TỐI ƯU" in system_msg
        assert "Test Product" in system_msg

    @pytest.mark.asyncio
    async def test_synthesize_response_without_plan_text(self):
        """synthesize_response works normally when no plan text."""
        mock_llm_response = MagicMock()
        mock_llm_response.content = "Test response"

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)

        from app.engine.multi_agent.subagents.search.workers import synthesize_response

        with patch("app.engine.multi_agent.agent_config.AgentConfigRegistry.get_llm",
                   return_value=mock_llm):
            result = await synthesize_response({
                "deduped_products": [],
                "platforms_searched": ["shopee"],
                "platform_errors": [],
                "query": "test",
            })

        call_args = mock_llm.ainvoke.call_args[0][0]
        system_msg = call_args[0]["content"] if isinstance(call_args[0], dict) else call_args[0].content
        assert "KẾ HOẠCH TÌM KIẾM TỐI ƯU" not in system_msg
        assert "Wiii" in system_msg  # Base prompt still present

    def test_state_schema_has_query_plan_text_field(self):
        """SearchSubgraphState includes _query_plan_text field."""
        from app.engine.multi_agent.subagents.search.state import SearchSubgraphState
        import typing
        hints = typing.get_type_hints(SearchSubgraphState)
        assert "_query_plan_text" in hints

    @pytest.mark.asyncio
    async def test_plan_search_preserves_platforms(self):
        """Planner integration doesn't break platform selection."""
        from app.engine.tools.query_planner import QueryPlan, SubQuery

        mock_plan = QueryPlan(
            product_name_en="Test", product_name_vi="Test",
            sub_queries=[SubQuery(platform="dealer", query="test")],
        )
        mock_structured = AsyncMock()
        mock_structured.ainvoke = AsyncMock(return_value=mock_plan)
        mock_llm = MagicMock()
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured)
        mock_settings = self._mock_settings(planner=True)

        with patch("app.core.config.get_settings", return_value=mock_settings), \
             patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm), \
             patch("app.engine.multi_agent.subagents.search.workers._get_available_platforms",
                   return_value=["google_shopping", "shopee"]), \
             patch("app.engine.multi_agent.subagents.search.workers._get_event_queue",
                   return_value=None):
            from app.engine.multi_agent.subagents.search.workers import plan_search
            result = await plan_search({"query": "test", "context": {}})

        assert "google_shopping" in result["platforms_to_search"]
        assert "shopee" in result["platforms_to_search"]

    @pytest.mark.asyncio
    async def test_plan_search_backward_compat_no_event_bus(self):
        """plan_search works without event bus (no streaming)."""
        mock_settings = self._mock_settings(planner=True)
        mock_structured = AsyncMock()
        mock_structured.ainvoke = AsyncMock(return_value=None)
        mock_llm = MagicMock()
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured)

        with patch("app.core.config.get_settings", return_value=mock_settings), \
             patch("app.engine.llm_pool.get_llm_light", return_value=mock_llm), \
             patch("app.engine.multi_agent.subagents.search.workers._get_available_platforms",
                   return_value=["google_shopping"]), \
             patch("app.engine.multi_agent.subagents.search.workers._get_event_queue",
                   return_value=None):
            from app.engine.multi_agent.subagents.search.workers import plan_search
            result = await plan_search({"query": "test"})

        assert "platforms_to_search" in result
