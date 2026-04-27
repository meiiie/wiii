"""
Product Search Agent Node — Sprint 148→150→200: "Săn Hàng" → "Tìm Sâu" → "Mắt Sản Phẩm"

Specialized WiiiRunner node for multi-platform e-commerce product search.
Uses ReAct loop (LLM→tools→observe→decide) pattern from tutor_node.py.

Sprint 150 enhancements:
- Configurable max iterations (default 15, was hardcoded 5)
- Enhanced deep search system prompt with multi-round strategy
- Context-aware iteration labels
- Page scraper tool integration (tool_fetch_product_detail)
- Pagination support (page parameter on all search tools)

Sprint 200 enhancements:
- Real-time preview card emission during ReAct loop (product carousel)
- Visual product search (image → product identification via Gemini Vision)
- Image pass-through from AgentState for visual search routing
"""

import logging
import threading
from typing import Dict, List, Optional, Tuple

from app.engine.multi_agent.state import AgentState
from app.engine.multi_agent.agents.product_search_surface import (
    _DEEP_SEARCH_PROMPT,
    _SYSTEM_PROMPT,
    _iteration_label,
    emit_product_previews_impl,
)
from app.engine.multi_agent.agents.product_search_runtime import (
    init_llm_impl,
    react_loop_impl,
)
from app.engine.tools.runtime_context import (
    build_tool_runtime_context,
)

logger = logging.getLogger(__name__)

# Max ReAct iterations — read from config at runtime, fallback to default
_MAX_ITERATIONS_DEFAULT = 15

# Chunk streaming config (matches tutor_node.py)
_CHUNK_SIZE = 40
_CHUNK_DELAY = 0.008  # 8ms

# Sprint 200: Tool names that produce product search results
_PRODUCT_RESULT_TOOLS = {
    "tool_search_google_shopping", "tool_search_shopee", "tool_search_tiktok_shop",
    "tool_search_lazada", "tool_search_facebook_marketplace", "tool_search_all_web",
    "tool_search_instagram_shopping", "tool_search_websosanh",
    "tool_search_facebook_search", "tool_search_facebook_group",
    "tool_search_facebook_groups_auto",
    "tool_international_search", "tool_dealer_search",
}

_PLAN_PLATFORM_TO_TOOL = {
    "google_shopping": "tool_search_google_shopping",
    "shopee": "tool_search_shopee",
    "lazada": "tool_search_lazada",
    "tiktok_shop": "tool_search_tiktok_shop",
    "facebook": "tool_search_facebook_search",
    "websosanh": "tool_search_websosanh",
    "all_web": "tool_search_all_web",
    "dealer": "tool_dealer_search",
    "international": "tool_international_search",
}


def _emit_product_previews(
    tool_name: str,
    result_str: str,
    emitted_ids: set,
    max_cards: int = 5,
    current_count: int = 0,
) -> list:
    """Compatibility wrapper for legacy tests/import sites."""
    return emit_product_previews_impl(
        tool_name=tool_name,
        result_str=result_str,
        emitted_ids=emitted_ids,
        max_cards=max_cards,
        current_count=current_count,
        product_result_tools=_PRODUCT_RESULT_TOOLS,
    )


def _product_search_required_tools(query: str, context: Optional[dict], query_plan=None) -> list[str]:
    """Choose must-have product-search tools from query intent + planner output."""
    normalized_query = (query or "").lower()
    required = {
        "tool_fetch_product_detail",
        "tool_generate_product_report",
    }

    if (context or {}).get("images"):
        required.add("tool_identify_product_from_image")

    plan_intent = getattr(getattr(query_plan, "intent", None), "value", "") or str(getattr(query_plan, "intent", "") or "")
    plan_strategy = getattr(getattr(query_plan, "search_strategy", None), "value", "") or str(getattr(query_plan, "search_strategy", "") or "")

    if (
        plan_intent == "PRICE_COMPARISON"
        or plan_strategy == "COMPARISON_FIRST"
        or any(keyword in normalized_query for keyword in ("rẻ", "re nhat", "cheap", "cheapest", "so sánh", "compare", "top"))
    ):
        required.update({
            "tool_search_websosanh",
            "tool_search_google_shopping",
            "tool_search_all_web",
        })

    if (
        plan_intent in {"B2B_SOURCING", "INTERNATIONAL", "CHINESE_SOURCING"}
        or plan_strategy in {"B2B_FIRST", "CHINA_FIRST"}
        or any(
            keyword in normalized_query
            for keyword in ("đại lý", "nha phan phoi", "giá sỉ", "1688", "taobao", "aliexpress", "nguồn hàng", "import")
        )
    ):
        required.update({
            "tool_dealer_search",
            "tool_international_search",
            "tool_search_all_web",
        })

    for sub_query in getattr(query_plan, "sub_queries", []) or []:
        tool_name = _PLAN_PLATFORM_TO_TOOL.get(str(getattr(sub_query, "platform", "")).strip().lower())
        if tool_name:
            required.add(tool_name)

    return list(required)


class ProductSearchAgentNode:
    """Agent node for multi-platform product search via ReAct loop."""

    def __init__(self):
        self._llm = None
        self._llm_with_tools = None
        self._tools = []
        self._init_llm()

    def _init_llm(self):
        """Initialize LLM and bind product search tools."""
        init_llm_impl(self)

    async def process(self, state: AgentState) -> AgentState:
        """Main entry point from WiiiRunner."""
        query = state.get("query", "")
        context = state.get("context", {})

        # Get event queue for streaming
        event_queue = None
        bus_id = state.get("_event_bus_id")
        if bus_id:
            from app.engine.multi_agent.graph_event_bus import _get_event_queue
            event_queue = _get_event_queue(bus_id)

        # Sprint 200: Pass images for visual product search
        images = state.get("images") or (context.get("images") if context else None)
        runtime_context_base = build_tool_runtime_context(
            event_bus_id=bus_id,
            request_id=bus_id or state.get("session_id"),
            session_id=state.get("session_id"),
            organization_id=state.get("organization_id"),
            user_id=state.get("user_id"),
            user_role=(context or {}).get("user_role", "student"),
            node="product_search_agent",
            source="agentic_loop",
        )

        # Run ReAct loop
        response, tools_used, thinking, answer_streamed = await self._react_loop(
            query=query,
            context=context,
            state=state,
            event_queue=event_queue,
            thinking_effort=state.get("thinking_effort"),
            images=images,
            runtime_context_base=runtime_context_base,
        )

        if answer_streamed:
            state["_answer_streamed_via_bus"] = True

        state["final_response"] = response
        state["agent_outputs"] = state.get("agent_outputs", {})
        state["agent_outputs"]["product_search"] = response
        state["current_agent"] = "product_search_agent"
        state["tools_used"] = tools_used

        if thinking:
            state["thinking"] = thinking

        return state

    async def _react_loop(
        self,
        query: str,
        context: dict,
        state: Optional[AgentState] = None,
        event_queue=None,
        thinking_effort: str = None,
        images: list = None,
        runtime_context_base=None,
    ) -> Tuple[str, List[Dict], Optional[str], bool]:
        """ReAct loop for product search."""
        return await react_loop_impl(
            self,
            query=query,
            context=context,
            state=state,
            event_queue=event_queue,
            thinking_effort=thinking_effort,
            images=images,
            runtime_context_base=runtime_context_base,
            max_iterations_default=_MAX_ITERATIONS_DEFAULT,
            chunk_size=_CHUNK_SIZE,
            chunk_delay=_CHUNK_DELAY,
            product_result_tools=_PRODUCT_RESULT_TOOLS,
            product_search_required_tools=_product_search_required_tools,
        )

    @staticmethod
    def _extract_text(content) -> str:
        """Extract text from LLM response content (handles Gemini block format)."""
        if isinstance(content, str):
            # Strip thinking tags if present
            from app.services.output_processor import extract_thinking_from_response
            text, _ = extract_thinking_from_response(content)
            return text.strip()
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
                elif isinstance(block, str):
                    parts.append(block)
            return " ".join(parts).strip()
        return str(content).strip()

    @staticmethod
    def _extract_thinking(content) -> str:
        """Extract thinking content from LLM response."""
        if isinstance(content, str):
            from app.services.output_processor import extract_thinking_from_response
            _, thinking = extract_thinking_from_response(content)
            return thinking or ""
        return ""


# =============================================================================
# Singleton
# =============================================================================

_product_search_node: Optional[ProductSearchAgentNode] = None
_node_lock = threading.Lock()


def get_product_search_agent_node() -> ProductSearchAgentNode:
    """Get or create ProductSearchAgentNode singleton (thread-safe)."""
    global _product_search_node
    if _product_search_node is None:
        with _node_lock:
            if _product_search_node is None:
                _product_search_node = ProductSearchAgentNode()
    return _product_search_node
