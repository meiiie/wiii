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
import re
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


# Sprint 201b: Extract rating/sold_count from Serper organic snippets
# Shopee/Lazada/TikTok snippets often contain "4.8/5", "đánh giá 4.8", "đã bán 1.2k"
_RATING_RE = re.compile(
    r"(\d+[.,]\d+)\s*(?:/\s*5|sao|stars?)"
    r"|(?:đánh giá|rating)[:\s]*(\d+[.,]\d+)",
    re.IGNORECASE,
)
_SOLD_RE = re.compile(
    r"đã bán\s*([\d.,]+\s*[kKmM]?)"
    r"|([\d.,]+\s*[kKmM]?)\s*đã bán",
    re.IGNORECASE,
)


def _extract_rating(text: str) -> float | None:
    """Extract product rating (0-5) from snippet text.

    Patterns matched: "4.8/5", "4.8 sao", "đánh giá 4.8", "rating: 4.8"
    Returns None if no rating found.
    """
    if not text:
        return None
    m = _RATING_RE.search(text)
    if not m:
        return None
    raw = (m.group(1) or m.group(2) or "").replace(",", ".")
    try:
        val = float(raw)
        if 0.0 < val <= 5.0:
            return round(val, 1)
    except (ValueError, TypeError):
        pass
    return None


def _parse_sold_number(raw: str) -> int | None:
    """Parse sold count string like '1.2k', '523', '1,5k' into integer."""
    if not raw:
        return None
    raw = raw.strip().replace(",", ".").lower()
    multiplier = 1
    if raw.endswith("k"):
        multiplier = 1000
        raw = raw[:-1]
    elif raw.endswith("m"):
        multiplier = 1_000_000
        raw = raw[:-1]
    # Remove thousands separator dots (e.g. "1.234" as 1234)
    # But keep decimal dots for multiplied values (e.g. "1.2" * 1000 = 1200)
    try:
        val = float(raw) * multiplier
        return int(val)
    except (ValueError, TypeError):
        return None


def _extract_sold(text: str) -> int | None:
    """Extract sold count from snippet text.

    Patterns matched: "đã bán 1.2k", "đã bán 523", "1k đã bán"
    Returns None if no sold count found.
    """
    if not text:
        return None
    m = _SOLD_RE.search(text)
    if not m:
        return None
    raw = (m.group(1) or m.group(2) or "").strip()
    return _parse_sold_number(raw)


# ─── Helpers ──────────────────────────────────────────────────────────


def _get_event_queue(bus_id: Optional[str]):
    """Lazy-import event queue from graph_streaming."""
    if not bus_id:
        return None
    try:
        from app.engine.multi_agent.graph_streaming import _get_event_queue
        return _get_event_queue(bus_id)
    except Exception as _e:
        logger.debug("[WORKER] Event queue unavailable: %s", _e)
        return None


async def _push(queue, event: dict) -> None:
    """Non-blocking push to event queue."""
    if queue is not None:
        try:
            queue.put_nowait(event)
        except Exception as _e:
            logger.debug("[WORKER] Event push failed: %s", _e)


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
    except Exception as _e:
        logger.debug("[WORKER] Platform registry unavailable, using defaults: %s", _e)
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
    Sprint 197: Optionally runs LLM Query Planner for optimized search queries.
    """
    query = state.get("query", "")
    available = _get_available_platforms()
    ordered = _order_platforms(available)
    eq = _get_event_queue(state.get("_event_bus_id"))

    # Sprint 197: LLM Query Planner pre-step
    query_plan_text = None
    _query_plan = None
    try:
        from app.core.config import get_settings as _gs197
        if _gs197().enable_query_planner:
            from app.engine.tools.query_planner import plan_search_queries, format_plan_for_prompt
            if eq:
                await _push(eq, {
                    "type": "thinking_start",
                    "content": "Lập kế hoạch tìm kiếm thông minh",
                    "node": "product_search_agent",
                    "summary": f"Phân tích: {query[:50]}",
                })
            context = state.get("context", {})
            _query_plan = await plan_search_queries(query, context)
            if _query_plan:
                query_plan_text = format_plan_for_prompt(_query_plan)
                if eq:
                    await _push_thinking_deltas(
                        eq,
                        f"Đã lập kế hoạch: {_query_plan.intent.value}, "
                        f"{len(_query_plan.sub_queries)} truy vấn tối ưu",
                    )
                logger.info(
                    "[PLAN_SEARCH] Query plan: intent=%s, strategy=%s, %d sub_queries",
                    _query_plan.intent.value,
                    _query_plan.search_strategy.value,
                    len(_query_plan.sub_queries),
                )
            if eq:
                await _push(eq, {"type": "thinking_end", "content": "", "node": "product_search_agent"})
    except Exception as _plan_err:
        logger.debug("[PLAN_SEARCH] Query planner skipped: %s", _plan_err)

    # Push platform planning event
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

    # Sprint 202b: Rewrite query when planner detects follow-up with more specific product
    effective_query = query
    if query_plan_text and _query_plan:
        plan_product = _query_plan.product_name_vi or ""
        # If planner found a product name that's more specific than the raw query,
        # rewrite the query to include the product name (follow-up detection)
        if plan_product and plan_product.lower() not in query.lower() and len(plan_product) > len(query):
            effective_query = f"{plan_product} {query}"
            logger.info(
                "[PLAN_SEARCH] Follow-up detected: rewriting '%s' → '%s'",
                query, effective_query,
            )

    result: Dict[str, Any] = {
        "platforms_to_search": ordered,
        "query": effective_query,  # Sprint 202b: may be rewritten for follow-ups
        "query_variants": [effective_query],
        "search_round": 1,
        "current_agent": "product_search_agent",
    }
    # Sprint 197: Pass plan text to synthesize_response
    if query_plan_text:
        result["_query_plan_text"] = query_plan_text
    return result


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

    # Sprint 205: Record search platform usage for Skill↔Tool bridge
    try:
        from app.engine.skills.skill_tool_bridge import record_tool_usage
        record_tool_usage(
            tool_name=tool_name,
            success=bool(products),
            latency_ms=duration_ms,
            query_snippet=query[:100],
            error_message=error or "",
        )
    except Exception as _e:
        logger.debug("[WORKER] Skill bridge recording failed: %s", _e)

    # Emit tool_result + acknowledgment
    result_summary = f"{len(products)} kết quả" if products else (error or "Không có kết quả")
    await _push(eq, {
        "type": "tool_result",
        "content": {"name": tool_name, "result": result_summary, "id": f"sw_{platform_id}"},
        "node": "product_search_agent",
    })
    ack = _PLATFORM_ACK.get(platform_id, f"Đã tìm trên {platform_id}")
    await _push_thinking_deltas(eq, f"\n{ack} ({len(products)} SP, {duration_ms}ms)")

    # Sprint 201: Image enrichment — add Google-cached thumbnails before preview emission
    try:
        from app.core.config import get_settings as _gs201
        _s201 = _gs201()
        if getattr(_s201, "enable_product_image_enrichment", False) and products:
            from app.engine.search_platforms.image_enricher import enrich_product_images
            products = enrich_product_images(products, query, platform_id)
    except Exception as _e:
        logger.debug("[WORKER] Image enrichment failed for %s: %s", platform_id, _e)

    # Sprint 201b: Extract rating/sold_count from snippets when missing
    for product in products:
        if not product.get("rating"):
            _r = _extract_rating(
                (product.get("snippet") or "") + " " + (product.get("title") or "")
            )
            if _r is not None:
                product["rating"] = _r
        if not product.get("sold_count"):
            _s = _extract_sold(product.get("snippet") or "")
            if _s is not None:
                product["sold_count"] = _s

    # Sprint 200: Emit product preview cards in real-time
    # Sprint 202: Suppress raw previews when curation is active
    if eq is not None and products:
        try:
            from app.core.config import get_settings as _gs200
            _s200 = _gs200()
            _curation_active_raw = getattr(_s200, "enable_curated_product_cards", False)
            _curation_active = _curation_active_raw is True
            if _s200.enable_product_preview_cards and not _curation_active:
                _max_per_platform = min(8, _s200.product_preview_max_cards)
                for i, product in enumerate(products[:_max_per_platform]):
                    title = product.get("title") or product.get("name", "")
                    if not title:
                        continue
                    link = product.get("link") or product.get("url", "")
                    pid = f"sw_{platform_id}_{hash(link) % 100000}_{i}" if link else f"sw_{platform_id}_{i}"
                    await _push(eq, {
                        "type": "preview",
                        "content": {
                            "preview_type": "product",
                            "preview_id": pid,
                            "title": title[:120],
                            "snippet": (product.get("snippet") or product.get("description", ""))[:150],
                            "url": link,
                            "image_url": product.get("image") or product.get("image_url") or product.get("thumbnail", ""),
                            "metadata": {
                                "price": product.get("price", ""),
                                "platform": platform_id,
                                "seller": product.get("seller", ""),
                                "rating": product.get("rating"),
                                "sold_count": product.get("sold_count"),
                                "delivery": product.get("delivery", ""),
                                "extracted_price": product.get("extracted_price"),
                                "location": product.get("location", ""),
                            },
                        },
                        "node": "product_search_agent",
                    })
        except Exception as _e:
            logger.debug("[WORKER] Preview emission failed for %s: %s", platform_id, _e)

    return {
        "all_products": products,
        "platform_errors": [error] if error else [],
        "platforms_searched": [platform_id],
        "tools_used": [{"name": tool_name, "args": {"query": query}, "duration_ms": duration_ms}],
    }


async def aggregate_results(state: Dict[str, Any]) -> dict:
    """Deduplicate products, optionally generate Excel."""
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

    # Sprint 202b: Removed pre-curation price sort — curation LLM should
    # see platform-interleaved results, not price-biased. Excel tool does
    # its own sorting internally.

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


async def _emit_curated_previews(eq, curated_products: List[Dict[str, Any]], query: str) -> None:
    """Emit preview events for curated products (same format as Sprint 200)."""
    if eq is None or not curated_products:
        return
    for i, product in enumerate(curated_products):
        title = product.get("title") or product.get("name", "")
        if not title:
            continue
        link = product.get("link") or product.get("url", "")
        pid = f"curated_{hash(link) % 100000}_{i}" if link else f"curated_{i}"
        metadata = {
            "price": product.get("price", ""),
            "platform": product.get("platform", ""),
            "seller": product.get("seller", ""),
            "rating": product.get("rating"),
            "sold_count": product.get("sold_count"),
            "delivery": product.get("delivery", ""),
            "extracted_price": product.get("extracted_price"),
            "location": product.get("location", ""),
        }
        # Sprint 202: Add curation metadata
        if product.get("_highlight"):
            metadata["highlight"] = product["_highlight"]
        if product.get("_relevance_score") is not None:
            metadata["relevance_score"] = product["_relevance_score"]

        await _push(eq, {
            "type": "preview",
            "content": {
                "preview_type": "product",
                "preview_id": pid,
                "title": title[:120],
                "snippet": (product.get("snippet") or product.get("description", ""))[:150],
                "url": link,
                "image_url": product.get("image") or product.get("image_url") or product.get("thumbnail", ""),
                "metadata": metadata,
            },
            "node": "product_search_agent",
        })


async def curate_products(state: Dict[str, Any]) -> dict:
    """Sprint 202: LLM-curate top products from deduped results.

    Feature gate: ``enable_curated_product_cards``.
    When disabled or when product count <= max, passes products through unchanged.
    On LLM failure, falls back to top-N sorted by price.
    """
    deduped = state.get("deduped_products", [])
    query = state.get("query", "")
    eq = _get_event_queue(state.get("_event_bus_id"))

    try:
        from app.core.config import get_settings as _gs202
        _s202 = _gs202()
        curation_enabled = getattr(_s202, "enable_curated_product_cards", False)
        max_curated = getattr(_s202, "curated_product_max_cards", 8)
        llm_tier = getattr(_s202, "curated_product_llm_tier", "light")
    except Exception as _e:
        logger.debug("[CURATE] Config load failed, curation disabled: %s", _e)
        curation_enabled = False
        max_curated = 8
        llm_tier = "light"

    # Skip LLM curation when disabled or when few enough products
    if not curation_enabled or len(deduped) <= max_curated:
        curated = deduped[:max_curated]
        # Still emit previews (these are the "curated" result when skipping LLM)
        if curation_enabled:
            await _emit_curated_previews(eq, curated, query)
        return {"curated_products": curated}

    # LLM curation
    await _push(eq, {
        "type": "thinking_start",
        "content": "Lọc sản phẩm tốt nhất bằng AI",
        "node": "product_search_agent",
        "summary": f"Lọc {len(deduped)} → top {max_curated}",
    })

    curated = None
    try:
        from app.engine.multi_agent.subagents.search.curation import curate_with_llm

        selection = await curate_with_llm(
            query=query,
            products=deduped,
            max_curated=max_curated,
            llm_tier=llm_tier,
        )

        if selection and selection.selected:
            curated = []
            for pick in selection.selected:
                product = deduped[pick.index].copy()
                product["_highlight"] = pick.highlight
                product["_relevance_score"] = pick.relevance_score
                product["_curation_reason"] = pick.reason
                curated.append(product)

            await _push_thinking_deltas(
                eq,
                f"Đã chọn {len(curated)}/{len(deduped)} sản phẩm tốt nhất: "
                + ", ".join(p.get("_highlight", "") for p in curated[:5]),
            )
    except Exception as exc:
        logger.warning("[CURATE_NODE] LLM curation failed: %s", exc)

    # Fallback: top-N by price
    if not curated:
        curated = deduped[:max_curated]
        await _push_thinking_deltas(eq, f"Hiển thị top {len(curated)} sản phẩm giá tốt nhất")

    await _push(eq, {"type": "thinking_end", "content": "", "node": "product_search_agent"})

    # Emit curated preview cards
    await _emit_curated_previews(eq, curated, query)

    return {"curated_products": curated}


async def synthesize_response(state: Dict[str, Any]) -> dict:
    """Generate final user-facing response from aggregated results via LLM."""
    # Sprint 202: Prefer curated products over raw deduped
    products = state.get("curated_products", state.get("deduped_products", state.get("all_products", [])))
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
        f"Top {len(top_products)} sản phẩm ({'đã được LLM lọc chọn' if state.get('curated_products') else 'sắp xếp giá rẻ nhất'}):\n{product_text}\n\n"
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

        # Sprint 197: Inject query plan context for better synthesis
        system_content = "Bạn là Wiii — trợ lý tìm kiếm sản phẩm. Tổng hợp kết quả tìm kiếm và trình bày rõ ràng."
        plan_text = state.get("_query_plan_text", "")
        if plan_text:
            system_content += "\n\n" + plan_text

        messages = [
            SystemMessage(content=system_content),
        ]

        # Sprint 202b: Inject recent conversation for follow-up awareness
        lc_messages = state.get("context", {}).get("langchain_messages", [])
        if lc_messages:
            from langchain_core.messages import AIMessage

            for msg in lc_messages[-4:]:
                if isinstance(msg, dict):
                    role = msg.get("role", "human")
                    content = str(msg.get("content", ""))
                else:
                    role = getattr(msg, "type", "human")
                    content = str(getattr(msg, "content", ""))
                if content.strip():
                    if role in ("human", "user"):
                        messages.append(HumanMessage(content=content[:500]))
                    elif role in ("ai", "assistant"):
                        messages.append(AIMessage(content=content[:500]))

        messages.append(HumanMessage(content=synthesis_prompt))

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

    # Sprint 202b: Preserve full product list for follow-up requests (e.g. Excel)
    all_products_json = ""
    try:
        deduped = state.get("deduped_products", [])
        if deduped:
            all_products_json = json.dumps(deduped[:100], ensure_ascii=False)[:50000]
    except Exception as _e:
        logger.debug("[SYNTHESIZE] Product JSON serialization failed: %s", _e)

    return {
        "final_response": final_response,
        "agent_outputs": {"product_search": final_response},
        "current_agent": "product_search_agent",
        "_answer_streamed_via_bus": answer_streamed,
        "thinking": f"Tìm kiếm song song trên {len(platforms)} nền tảng, thu được {len(products)} SP",
        "_all_search_products_json": all_products_json,
    }
