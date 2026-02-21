"""Search subgraph node implementations.

Nodes:
- plan_search: Determine platforms and query variants (deterministic)
- platform_worker: Execute search on one platform (Send() target)
- aggregate_results: Deduplicate, sort by price, optional Excel
- synthesize_response: LLM generates final user-facing response
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Platform tiers — most valuable sources first
_TIER1_PLATFORMS = ["websosanh", "google_shopping"]
_TIER2_PLATFORMS = ["shopee", "lazada", "tiktok_shop"]
_TIER3_PLATFORMS = ["all_web", "facebook_marketplace", "instagram_shopping"]
_BROWSER_PLATFORMS = ["facebook_groups_auto"]

# Chunk streaming config (same as product_search_node.py)
_CHUNK_SIZE = 40
_CHUNK_DELAY = 0.008

# Post-tool acknowledgments
_PLATFORM_ACK = {
    "google_shopping": "Tìm được từ Google Shopping!",
    "shopee": "Đã tìm trên Shopee!",
    "lazada": "Đã tìm trên Lazada!",
    "tiktok_shop": "Đã tìm trên TikTok Shop!",
    "websosanh": "Đã so sánh giá trên 94+ cửa hàng!",
    "all_web": "Đã quét web cửa hàng nhỏ!",
    "facebook_marketplace": "Đã tìm trên Facebook Marketplace!",
    "instagram_shopping": "Đã tìm trên Instagram!",
    "facebook_groups_auto": "Đã quét nhóm Facebook!",
}


# ─── Helpers ──────────────────────────────────────────────────────────


def _get_event_queue(bus_id: Optional[str]):
    """Lazy-import event queue from graph_streaming."""
    if not bus_id:
        return None
    try:
        from app.engine.multi_agent.graph_streaming import _get_event_queue
        return _get_event_queue(bus_id)
    except Exception:
        return None


async def _push(queue, event: dict) -> None:
    """Non-blocking push to event queue."""
    if queue is not None:
        try:
            queue.put_nowait(event)
        except Exception:
            pass


async def _push_thinking_deltas(queue, text: str, node: str = "product_search_agent") -> None:
    """Stream text as thinking_delta chunks."""
    for i in range(0, len(text), _CHUNK_SIZE):
        sub = text[i : i + _CHUNK_SIZE]
        await _push(queue, {"type": "thinking_delta", "content": sub, "node": node})
        if i + _CHUNK_SIZE < len(text):
            await asyncio.sleep(_CHUNK_DELAY)


def _get_available_platforms() -> List[str]:
    """Query SearchPlatformRegistry for enabled platform IDs."""
    try:
        from app.engine.search_platforms import get_search_platform_registry

        registry = get_search_platform_registry()
        return [a.get_config().id for a in registry.get_all_enabled()]
    except Exception:
        return ["google_shopping", "shopee", "lazada"]


def _order_platforms(available: List[str]) -> List[str]:
    """Sort platforms by tier priority."""
    ordered = []
    for tier in [_TIER1_PLATFORMS, _TIER2_PLATFORMS, _TIER3_PLATFORMS, _BROWSER_PLATFORMS]:
        for p in tier:
            if p in available:
                ordered.append(p)
    for p in available:
        if p not in ordered:
            ordered.append(p)
    return ordered


# ─── Graph nodes ──────────────────────────────────────────────────────


async def plan_search(state: Dict[str, Any]) -> dict:
    """Analyse query and determine which platforms to search.

    Deterministic (no LLM) — fast and reliable.
    """
    query = state.get("query", "")
    available = _get_available_platforms()
    ordered = _order_platforms(available)

    # Push planning event
    eq = _get_event_queue(state.get("_event_bus_id"))
    if eq:
        await _push(eq, {
            "type": "thinking_start",
            "content": "Lập kế hoạch tìm kiếm",
            "node": "product_search_agent",
            "summary": f"Tìm kiếm sản phẩm: {query[:50]}",
        })
        await _push_thinking_deltas(
            eq,
            f"Sẽ tìm song song trên {len(ordered)} nền tảng: {', '.join(ordered[:6])}{'...' if len(ordered) > 6 else ''}",
        )
        await _push(eq, {"type": "thinking_end", "content": "", "node": "product_search_agent"})

    return {
        "platforms_to_search": ordered,
        "query_variants": [query],
        "search_round": 1,
        "current_agent": "product_search_agent",
    }


async def platform_worker(state: Dict[str, Any]) -> dict:
    """Execute search on a single platform.

    This is the ``Send()`` target — runs in parallel for each platform.
    Returns accumulated products via ``operator.add`` reducer.
    """
    platform_id = state.get("platform_id", "")
    query = state.get("query", "")
    max_results = state.get("max_results", 20)
    page = state.get("page", 1)

    eq = _get_event_queue(state.get("_event_bus_id"))
    tool_name = f"tool_search_{platform_id}"

    # Emit tool_call event
    await _push(eq, {
        "type": "tool_call",
        "content": {"name": tool_name, "args": {"query": query, "max_results": max_results}, "id": f"sw_{platform_id}"},
        "node": "product_search_agent",
    })

    start = time.monotonic()
    products: List[Dict[str, Any]] = []
    error: Optional[str] = None

    try:
        from app.engine.search_platforms import get_search_platform_registry

        adapter = get_search_platform_registry().get(platform_id)
        if adapter is None:
            error = f"Platform {platform_id} not found in registry"
        else:
            results = await asyncio.to_thread(adapter.search_sync, query, max_results, page)
            products = [r.to_dict() for r in results]
    except Exception as exc:
        error = f"{platform_id}: {type(exc).__name__}: {str(exc)[:200]}"
        logger.warning("[SEARCH_WORKER] %s failed: %s", platform_id, error)

    duration_ms = int((time.monotonic() - start) * 1000)

    # Emit tool_result + acknowledgment
    result_summary = f"{len(products)} kết quả" if products else (error or "Không có kết quả")
    await _push(eq, {
        "type": "tool_result",
        "content": {"name": tool_name, "result": result_summary, "id": f"sw_{platform_id}"},
        "node": "product_search_agent",
    })
    ack = _PLATFORM_ACK.get(platform_id, f"Đã tìm trên {platform_id}")
    await _push_thinking_deltas(eq, f"\n{ack} ({len(products)} SP, {duration_ms}ms)")

    return {
        "all_products": products,
        "platform_errors": [error] if error else [],
        "platforms_searched": [platform_id],
        "tools_used": [{"name": tool_name, "args": {"query": query}, "duration_ms": duration_ms}],
    }


async def aggregate_results(state: Dict[str, Any]) -> dict:
    """Deduplicate products, sort by price, optionally generate Excel."""
    all_products: List[Dict[str, Any]] = state.get("all_products", [])
    platforms = state.get("platforms_searched", [])
    query = state.get("query", "")

    eq = _get_event_queue(state.get("_event_bus_id"))
    await _push(eq, {
        "type": "thinking_start",
        "content": "Tổng hợp và sắp xếp kết quả",
        "node": "product_search_agent",
    })

    # Deduplicate by link
    seen_links: set = set()
    unique: List[Dict[str, Any]] = []
    for p in all_products:
        link = p.get("link", "")
        if link and link in seen_links:
            continue
        if link:
            seen_links.add(link)
        unique.append(p)

    # Sort by extracted_price ascending (None/0 at end)
    def _price_key(p: dict) -> float:
        price = p.get("extracted_price")
        if price and price > 0:
            return price
        return float("inf")

    unique.sort(key=_price_key)

    await _push_thinking_deltas(
        eq,
        f"Tổng cộng: {len(unique)} SP (loại trùng {len(all_products) - len(unique)}) từ {len(platforms)} nền tảng",
    )

    # Generate Excel for many results
    excel_path: Optional[str] = None
    if len(unique) >= 5:
        try:
            from app.engine.tools.excel_report_tool import tool_generate_product_report

            excel_result = await asyncio.to_thread(
                tool_generate_product_report.invoke,
                {"query": query, "products_json": json.dumps(unique, ensure_ascii=False)},
            )
            excel_str = str(excel_result)
            if "excel" in excel_str.lower() or "xlsx" in excel_str.lower():
                excel_path = excel_str
        except Exception as exc:
            logger.warning("[AGGREGATE] Excel generation failed: %s", exc)

    await _push(eq, {"type": "thinking_end", "content": "", "node": "product_search_agent"})

    return {
        "deduped_products": unique,
        "excel_path": excel_path,
    }


async def synthesize_response(state: Dict[str, Any]) -> dict:
    """Generate final user-facing response from aggregated results via LLM."""
    products = state.get("deduped_products", state.get("all_products", []))
    platforms = state.get("platforms_searched", [])
    errors = state.get("platform_errors", [])
    query = state.get("query", "")
    excel_path = state.get("excel_path")

    eq = _get_event_queue(state.get("_event_bus_id"))

    # Build context for LLM
    top_products = products[:20]
    product_text = json.dumps(top_products, ensure_ascii=False, indent=2)[:8000]

    synthesis_prompt = (
        f"Tổng hợp kết quả tìm kiếm sản phẩm:\n\n"
        f"Query: {query}\n"
        f"Tìm được: {len(products)} sản phẩm từ {len(platforms)} nền tảng ({', '.join(platforms[:6])})\n"
        f"{'Lỗi: ' + ', '.join(errors[:3]) if errors else ''}\n"
        f"{'File Excel: ' + excel_path if excel_path else ''}\n\n"
        f"Top {len(top_products)} sản phẩm (sắp xếp giá rẻ nhất):\n{product_text}\n\n"
        "YÊU CẦU:\n"
        "- Trả lời tiếng Việt\n"
        "- Format bảng Markdown so sánh\n"
        "- Link sản phẩm: markdown link [Xem ngay](url)\n"
        "- Ghi rõ nguồn (sàn nào), giá VNĐ\n"
        "- Nêu top 5 giá tốt nhất"
    )

    final_response = ""
    answer_streamed = False

    try:
        from app.engine.multi_agent.agent_config import AgentConfigRegistry

        llm = AgentConfigRegistry.get_llm(
            "product_search", effort_override=state.get("thinking_effort")
        )
        if not llm:
            raise RuntimeError("LLM unavailable")

        from langchain_core.messages import HumanMessage, SystemMessage

        messages = [
            SystemMessage(
                content="Bạn là Wiii — trợ lý tìm kiếm sản phẩm. Tổng hợp kết quả tìm kiếm và trình bày rõ ràng."
            ),
            HumanMessage(content=synthesis_prompt),
        ]

        if eq:
            # Streaming synthesis
            await _push(eq, {
                "type": "thinking_start",
                "content": "Tổng hợp kết quả cuối cùng",
                "node": "product_search_agent",
            })

            chunks: List[str] = []
            async for chunk in llm.astream(messages):
                text = ""
                if hasattr(chunk, "content"):
                    content = chunk.content
                    if isinstance(content, str):
                        text = content
                    elif isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                text += block.get("text", "")
                if text:
                    chunks.append(text)
                    for i in range(0, len(text), _CHUNK_SIZE):
                        sub = text[i : i + _CHUNK_SIZE]
                        await _push(eq, {"type": "answer_delta", "content": sub, "node": "product_search_agent"})
                        if i + _CHUNK_SIZE < len(text):
                            await asyncio.sleep(_CHUNK_DELAY)

            final_response = "".join(chunks)
            answer_streamed = True
            await _push(eq, {"type": "thinking_end", "content": "", "node": "product_search_agent"})
        else:
            # Non-streaming synthesis
            result = await llm.ainvoke(messages)
            final_response = result.content if hasattr(result, "content") else str(result)

    except Exception as exc:
        logger.warning("[SYNTHESIZE] LLM failed: %s", exc)
        final_response = f"Tìm thấy {len(products)} sản phẩm từ {len(platforms)} nền tảng."

    return {
        "final_response": final_response,
        "agent_outputs": {"product_search": final_response},
        "current_agent": "product_search_agent",
        "_answer_streamed_via_bus": answer_streamed,
        "thinking": f"Tìm kiếm song song trên {len(platforms)} nền tảng, thu được {len(products)} SP",
    }
