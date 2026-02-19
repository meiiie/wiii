"""
Product Search Agent Node — Sprint 148: "Săn Hàng"

Specialized LangGraph node for multi-platform e-commerce product search.
Uses ReAct loop (LLM→tools→observe→decide) pattern from tutor_node.py.

Flow:
1. LLM analyzes query → understands specs/brand/quantity
2. LLM calls tool_search_google_shopping first (fastest, structured)
3. LLM decides which additional platforms to search (Shopee, TikTok, Lazada, FB)
4. LLM synthesizes, compares, ranks products
5. If user requests Excel → calls tool_generate_product_report
6. Max 5 iterations, early exit when data is sufficient
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Tuple

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from app.engine.multi_agent.state import AgentState

logger = logging.getLogger(__name__)

# Max ReAct iterations — product search needs more rounds (multi-platform)
_MAX_ITERATIONS = 5

# Chunk streaming config (matches tutor_node.py)
_CHUNK_SIZE = 40
_CHUNK_DELAY = 0.008  # 8ms

# Post-tool acknowledgment templates
_TOOL_ACK = {
    "tool_search_google_shopping": "Tìm được từ Google Shopping! Đang phân tích...",
    "tool_search_shopee": "Đã tìm trên Shopee! Đang xem kết quả...",
    "tool_search_tiktok_shop": "Đã tìm trên TikTok Shop! Đang so sánh...",
    "tool_search_lazada": "Đã tìm trên Lazada! Đang tổng hợp...",
    "tool_search_facebook_marketplace": "Đã tìm trên Facebook Marketplace!",
    "tool_search_all_web": "Đã quét web cửa hàng nhỏ! Đang xem giá...",
    "tool_search_instagram_shopping": "Đã tìm trên Instagram!",
    "tool_generate_product_report": "Báo cáo Excel đã được tạo!",
}

# Vietnamese system prompt for product search agent
_SYSTEM_PROMPT = """Bạn là Wiii — trợ lý tìm kiếm sản phẩm thông minh. Nhiệm vụ:

## NĂNG LỰC
- Phân tích yêu cầu tìm kiếm → hiểu thông số kỹ thuật, thương hiệu, số lượng
- Tìm kiếm sản phẩm trên nhiều sàn TMĐT Việt Nam
- So sánh giá, seller, đánh giá, lượt bán
- Tạo báo cáo Excel nếu user yêu cầu

## QUY TRÌNH
1. **Phân tích query**: Xác định loại SP, thông số, thương hiệu, ngân sách
2. **Tìm Google Shopping TRƯỚC** (nhanh nhất, dữ liệu cấu trúc tốt)
3. **Tìm thêm sàn khác** nếu cần: Shopee, Lazada, TikTok Shop, web cửa hàng nhỏ
4. **So sánh & xếp hạng**: Giá, uy tín seller, đánh giá, lượt bán
5. **Tạo Excel** nếu user yêu cầu "báo cáo", "excel", "xuất file"

## CÔNG CỤ
- tool_search_google_shopping: Tìm Google Shopping VN (nhanh nhất, dữ liệu cấu trúc)
- tool_search_shopee: Tìm Shopee VN
- tool_search_tiktok_shop: Tìm TikTok Shop VN
- tool_search_lazada: Tìm Lazada VN
- tool_search_facebook_marketplace: Tìm Facebook Marketplace VN
- tool_search_all_web: Quét TẤT CẢ web cửa hàng nhỏ, nhà phân phối, B2B (thường rẻ hơn sàn TMĐT!)
- tool_search_instagram_shopping: Tìm bài bán hàng trên Instagram VN
- tool_generate_product_report: Tạo file Excel so sánh

## QUY TẮC
- LUÔN gọi tool tìm kiếm — KHÔNG tự bịa giá, SP, link
- Tạo search variants phù hợp (VD: "dây điện 3x2.5" → thử "dây cáp Cadivi 3x2.5mm", "cuộn dây điện 3 ruột 2.5mm²")
- Trả lời bằng tiếng Việt, format bảng Markdown khi so sánh
- Ghi rõ nguồn (sàn nào, web nào), giá VNĐ, link sản phẩm
- Nếu một sàn lỗi → bỏ qua, tìm sàn khác
- ƯU TIÊN gọi tool_search_all_web khi user hỏi "web nào rẻ nhất" hoặc muốn so sánh giá toàn diện
- KHÔNG cần tìm TẤT CẢ sàn — chỉ tìm đủ để so sánh có ý nghĩa (2-4 nguồn)
"""


def _iteration_label(iteration: int, tools_used: list) -> str:
    """Context-aware thinking block label for product search."""
    if iteration == 0:
        return "Phân tích yêu cầu tìm kiếm"
    if tools_used:
        return "So sánh và tổng hợp kết quả"
    return f"Tìm kiếm thêm (vòng {iteration + 1})"


class ProductSearchAgentNode:
    """Agent node for multi-platform product search via ReAct loop."""

    def __init__(self):
        self._llm = None
        self._llm_with_tools = None
        self._tools = []
        self._init_llm()

    def _init_llm(self):
        """Initialize LLM and bind product search tools."""
        try:
            from app.engine.multi_agent.agent_config import AgentConfigRegistry
            self._llm = AgentConfigRegistry.get_llm("product_search")
            if not self._llm:
                # Fallback to direct node config
                self._llm = AgentConfigRegistry.get_llm("direct")
        except Exception as e:
            logger.warning("[PRODUCT_SEARCH] LLM init failed: %s", e)

        # Load tools
        try:
            from app.engine.tools.product_search_tools import get_product_search_tools
            from app.engine.tools.excel_report_tool import tool_generate_product_report
            self._tools = get_product_search_tools() + [tool_generate_product_report]
        except Exception as e:
            logger.warning("[PRODUCT_SEARCH] Tools init failed: %s", e)

        if self._llm and self._tools:
            self._llm_with_tools = self._llm.bind_tools(self._tools)
        elif self._llm:
            self._llm_with_tools = self._llm

    async def process(self, state: AgentState) -> AgentState:
        """Main entry point from LangGraph."""
        query = state.get("query", "")
        context = state.get("context", {})

        # Get event queue for streaming
        event_queue = None
        bus_id = state.get("_event_bus_id")
        if bus_id:
            from app.engine.multi_agent.graph_streaming import _get_event_queue
            event_queue = _get_event_queue(bus_id)

        # Run ReAct loop
        response, tools_used, thinking, answer_streamed = await self._react_loop(
            query=query,
            context=context,
            event_queue=event_queue,
            thinking_effort=state.get("thinking_effort"),
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
        event_queue=None,
        thinking_effort: str = None,
    ) -> Tuple[str, List[Dict], Optional[str], bool]:
        """
        ReAct loop for product search.

        Returns:
            (response_text, tools_used, thinking_content, answer_streamed_via_bus)
        """
        if not self._llm:
            return "Xin lỗi, hệ thống tìm kiếm sản phẩm chưa sẵn sàng.", [], None, False

        # Rebuild LLM if effort override
        llm_to_use = self._llm_with_tools
        if thinking_effort and self._llm:
            try:
                from app.engine.multi_agent.agent_config import AgentConfigRegistry
                llm_override = AgentConfigRegistry.get_llm("product_search", effort_override=thinking_effort)
                if llm_override and self._tools:
                    llm_to_use = llm_override.bind_tools(self._tools)
            except Exception:
                pass

        # Event push helpers
        async def _push(evt):
            if event_queue is not None:
                try:
                    event_queue.put_nowait(evt)
                except Exception:
                    pass

        async def _push_thinking_deltas(text: str):
            for i in range(0, len(text), _CHUNK_SIZE):
                sub = text[i:i + _CHUNK_SIZE]
                await _push({"type": "thinking_delta", "content": sub, "node": "product_search_agent"})
                if i + _CHUNK_SIZE < len(text):
                    await asyncio.sleep(_CHUNK_DELAY)

        async def _push_answer_deltas(text: str):
            for i in range(0, len(text), _CHUNK_SIZE):
                sub = text[i:i + _CHUNK_SIZE]
                await _push({"type": "answer_delta", "content": sub, "node": "product_search_agent"})
                if i + _CHUNK_SIZE < len(text):
                    await asyncio.sleep(_CHUNK_DELAY)

        # Build messages
        messages = [SystemMessage(content=_SYSTEM_PROMPT)]
        # Inject conversation history (last 6 turns — product search is usually standalone)
        lc_messages = context.get("langchain_messages", [])
        if lc_messages:
            messages.extend(lc_messages[-6:])
        messages.append(HumanMessage(content=query))

        tools_used = []
        all_thinking = []
        final_response = ""
        answer_streamed = False
        response = None

        for iteration in range(_MAX_ITERATIONS):
            # Emit thinking_start
            if event_queue is not None:
                _label = _iteration_label(iteration, tools_used)
                await _push({
                    "type": "thinking_start",
                    "content": _label,
                    "node": "product_search_agent",
                    "summary": f"Tìm kiếm sản phẩm: {query[:50]}",
                })

            # LLM inference (streaming if event queue available)
            if event_queue is not None:
                response = None
                async for chunk in llm_to_use.astream(messages):
                    if response is None:
                        response = chunk
                    else:
                        response = response + chunk
                    # Extract text from chunk for thinking delta
                    text = ""
                    if hasattr(chunk, 'content'):
                        content = chunk.content
                        if isinstance(content, str):
                            text = content
                        elif isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    text += block.get("text", "")
                                elif isinstance(block, str):
                                    text += block
                    if text:
                        await _push_thinking_deltas(text)
            else:
                response = await llm_to_use.ainvoke(messages)

            if response is None:
                break

            # Check for tool calls
            tool_calls = getattr(response, 'tool_calls', [])
            if not tool_calls:
                # No tools — extract final response
                if event_queue is not None:
                    await _push({"type": "thinking_end", "content": "", "node": "product_search_agent"})

                final_response = self._extract_text(response.content)
                thinking_text = self._extract_thinking(response.content)
                if thinking_text:
                    all_thinking.append(thinking_text)

                # Stream answer
                if event_queue is not None and final_response:
                    answer_streamed = True
                    await _push_answer_deltas(final_response)
                break

            # Execute tool calls
            for tool_call in tool_calls:
                tool_name = tool_call.get("name", "unknown")
                tool_args = tool_call.get("args", {})
                tool_id = tool_call.get("id", f"tc_{iteration}")

                # Push tool_call event
                await _push({
                    "type": "tool_call",
                    "content": {"name": tool_name, "args": tool_args, "id": tool_id},
                    "node": "product_search_agent",
                })

                # Execute tool
                matched = next((t for t in self._tools if t.name == tool_name), None)
                try:
                    if matched:
                        result = await asyncio.to_thread(matched.invoke, tool_args)
                    else:
                        result = json.dumps({"error": f"Unknown tool: {tool_name}"}, ensure_ascii=False)
                except Exception as e:
                    logger.warning("[PRODUCT_SEARCH] Tool %s failed: %s", tool_name, e)
                    result = json.dumps({"error": f"Tool {tool_name} failed: {str(e)[:200]}"}, ensure_ascii=False)

                # Push tool_result event
                await _push({
                    "type": "tool_result",
                    "content": {"name": tool_name, "result": str(result)[:500], "id": tool_id},
                    "node": "product_search_agent",
                })

                # Post-tool acknowledgment
                _ack = _TOOL_ACK.get(tool_name, f"Đã nhận kết quả từ {tool_name}.")
                await _push_thinking_deltas(f"\n\n{_ack}")

                # Add to message history (OBSERVE step)
                messages.append(AIMessage(content="", tool_calls=[tool_call]))
                messages.append(ToolMessage(content=str(result), tool_call_id=tool_id))

                tools_used.append({"name": tool_name, "args": tool_args, "iteration": iteration})

            # Close thinking block AFTER tools (Sprint 146b pattern)
            if event_queue is not None:
                await _push({"type": "thinking_end", "content": "", "node": "product_search_agent"})

        # If no final response yet (loop exhausted), do final generation
        if not final_response and response is not None:
            if event_queue is not None:
                await _push({
                    "type": "thinking_start",
                    "content": "Tổng hợp kết quả cuối cùng",
                    "node": "product_search_agent",
                })

            # Use base LLM (no tools) for final synthesis
            if event_queue is not None:
                final_chunks = []
                async for chunk in self._llm.astream(messages):
                    text = ""
                    if hasattr(chunk, 'content'):
                        content = chunk.content
                        if isinstance(content, str):
                            text = content
                        elif isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    text += block.get("text", "")
                    if text:
                        final_chunks.append(text)
                        await _push_answer_deltas(text)
                final_response = "".join(final_chunks)
                answer_streamed = True

                await _push({"type": "thinking_end", "content": "", "node": "product_search_agent"})
            else:
                final_gen = await self._llm.ainvoke(messages)
                final_response = self._extract_text(final_gen.content)

        combined_thinking = "\n\n".join(all_thinking) if all_thinking else None
        return final_response, tools_used, combined_thinking, answer_streamed

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


def get_product_search_agent_node() -> ProductSearchAgentNode:
    """Get or create ProductSearchAgentNode singleton."""
    global _product_search_node
    if _product_search_node is None:
        _product_search_node = ProductSearchAgentNode()
    return _product_search_node
