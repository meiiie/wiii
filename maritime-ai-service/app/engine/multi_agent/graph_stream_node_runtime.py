"""
Streaming node helpers for the multi-agent graph.

These helpers keep graph_streaming.py focused on orchestration while
preserving the existing event contract.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import AsyncGenerator, Callable, Iterable
from typing import Any

from app.engine.reasoning import capture_thinking_lifecycle_event

logger = logging.getLogger(__name__)


async def emit_tool_call_events_impl(
    *,
    tool_call_events: list[dict[str, Any]] | None,
    node_name: str,
    lifecycle_state: dict[str, Any] | None = None,
    create_tool_call_event: Callable[..., Any],
    create_tool_result_event: Callable[..., Any],
) -> AsyncGenerator[Any, None]:
    for tc_event in tool_call_events or []:
        tool_call_event = await create_tool_call_event(
            tool_name=tc_event.get("name", ""),
            tool_args=tc_event.get("args", {}),
            tool_call_id=tc_event.get("id", ""),
            node=node_name,
        )
        if lifecycle_state is not None:
            capture_thinking_lifecycle_event(lifecycle_state, tool_call_event.to_dict())
        yield tool_call_event
        if "result" in tc_event:
            tool_result_event = await create_tool_result_event(
                tool_name=tc_event.get("name", ""),
                result_summary=str(tc_event.get("result", ""))[:200],
                tool_call_id=tc_event.get("id", ""),
                node=node_name,
            )
            if lifecycle_state is not None:
                capture_thinking_lifecycle_event(lifecycle_state, tool_result_event.to_dict())
            yield tool_result_event


async def emit_node_thinking_impl(
    *,
    streamed_nodes: set[str],
    stream_node_name: str,
    node_label: str,
    node_output: dict[str, Any],
    node_start: float,
    phase: str,
    query: str,
    user_id: str,
    context: dict[str, Any] | None,
    initial_state: dict[str, Any],
    cue: str,
    next_action: str,
    observations: Iterable[str],
    style_tags: list[str],
    extract_thinking_content: Callable[[dict[str, Any]], str],
    render_fallback_narration: Callable[..., Any],
    create_thinking_start_event: Callable[..., Any],
    create_thinking_delta_event: Callable[..., Any],
    create_thinking_end_event: Callable[..., Any],
    narration_delta_chunks: Callable[[Any], Iterable[str]],
    details: dict[str, Any] | None = None,
    confidence: float | None = None,
    extra_already_streamed: bool = False,
    emit_narration_chunks_when_missing: bool = True,
) -> AsyncGenerator[Any, None]:
    if stream_node_name in streamed_nodes or extra_already_streamed:
        return

    thinking_content = extract_thinking_content(node_output)
    narration = None
    if not thinking_content:
        narration = await render_fallback_narration(
            node=stream_node_name,
            phase=phase,
            query=query,
            user_id=user_id,
            context=context,
            initial_state=initial_state,
            node_output=node_output,
            cue=cue,
            next_action=next_action,
            observations=list(observations),
            style_tags=style_tags,
            confidence=confidence,
        )

    lifecycle_phase = "post_tool" if node_output.get("tool_call_events") else phase

    start_event = await create_thinking_start_event(
        node_label,
        stream_node_name,
        summary=narration.summary if narration else None,
        details={
            **(details or {}),
            "phase": lifecycle_phase,
        } if (details or narration) else {"phase": lifecycle_phase},
    )
    capture_thinking_lifecycle_event(node_output, start_event.to_dict())
    yield start_event
    if thinking_content:
        delta_event = await create_thinking_delta_event(thinking_content, stream_node_name)
        capture_thinking_lifecycle_event(node_output, delta_event.to_dict())
        yield delta_event
    elif emit_narration_chunks_when_missing:
        for chunk in narration_delta_chunks(narration):
            delta_event = await create_thinking_delta_event(chunk, stream_node_name)
            capture_thinking_lifecycle_event(node_output, delta_event.to_dict())
            yield delta_event
    end_event = await create_thinking_end_event(
        stream_node_name,
        duration_ms=int((time.time() - node_start) * 1000),
    )
    capture_thinking_lifecycle_event(node_output, end_event.to_dict())
    yield end_event


async def emit_document_previews_impl(
    *,
    enabled: bool,
    preview_types: list[str] | None,
    preview_max: int,
    sources: list[dict[str, Any]] | None,
    emitted_preview_ids: set[str],
    snippet_max_length: int,
    create_preview_event: Callable[..., Any],
) -> AsyncGenerator[Any, None]:
    if not enabled or not sources or (preview_types and "document" not in preview_types):
        return

    for idx, src in enumerate(sources[:preview_max]):
        preview_id = f"doc-{src.get('node_id', src.get('document_id', idx))}"
        if preview_id in emitted_preview_ids:
            continue
        emitted_preview_ids.add(preview_id)
        yield await create_preview_event(
            preview_type="document",
            preview_id=preview_id,
            title=src.get("title", "Nguồn tham khảo"),
            snippet=str(src.get("content", ""))[:snippet_max_length],
            url=None,
            image_url=src.get("image_url"),
            citation_index=idx + 1,
            node="rag_agent",
            metadata={
                "relevance_score": src.get("score"),
                "page_number": src.get("page_number"),
            },
        )


async def emit_web_previews_impl(
    *,
    enabled: bool,
    preview_types: list[str] | None,
    preview_max: int,
    tool_call_events: list[dict[str, Any]] | None,
    emitted_preview_ids: set[str],
    create_preview_event: Callable[..., Any],
) -> AsyncGenerator[Any, None]:
    if not enabled or (preview_types and "web" not in preview_types):
        return

    web_count = 0
    for tc in tool_call_events or []:
        tc_name = tc.get("name", "")
        if "search" not in tc_name and "web" not in tc_name and "news" not in tc_name:
            continue
        if tc.get("type") != "result" or web_count >= preview_max:
            continue
        raw_result = tc.get("result", "")
        try:
            results = []
            try:
                parsed = json.loads(raw_result) if isinstance(raw_result, str) else raw_result
                if isinstance(parsed, dict):
                    results = parsed.get("results", parsed.get("organic", []))
                elif isinstance(parsed, list):
                    results = parsed
            except (ValueError, TypeError):
                pass

            if results:
                for item_index, result in enumerate(results[:8]):
                    if not isinstance(result, dict):
                        continue
                    url = result.get("url") or result.get("link", "")
                    preview_id = f"web-{item_index}-{hash(url) % 10000}"
                    if preview_id in emitted_preview_ids:
                        continue
                    emitted_preview_ids.add(preview_id)
                    web_count += 1
                    yield await create_preview_event(
                        preview_type="web",
                        preview_id=preview_id,
                        title=str(result.get("title", ""))[:120],
                        snippet=str(result.get("snippet", result.get("description", "")))[:300],
                        url=url or None,
                        node="direct",
                        metadata={
                            "date": result.get("date"),
                            "source": result.get("source"),
                        },
                    )
                    if web_count >= preview_max:
                        break
                continue

            blocks = re.split(r"\n---\n", str(raw_result))
            for block_index, block in enumerate(blocks[:8]):
                block = block.strip()
                if not block:
                    continue
                title_match = re.match(r"\*\*(.+?)\*\*", block)
                title = title_match.group(1) if title_match else block.split("\n")[0][:120]
                url_match = re.search(r"URL:\s*(https?://\S+)", block)
                url = url_match.group(1) if url_match else ""
                date_match = re.search(r"\((\d{4}-\d{2}-\d{2}[^)]*)\)", block)
                date = date_match.group(1) if date_match else None
                source_match = re.search(r"\[([^\]]+)\]", block)
                source = source_match.group(1) if source_match else None
                lines = block.split("\n")
                body_lines = [line for line in lines[1:] if not line.startswith("URL:")]
                snippet = " ".join(body_lines).strip()[:300]
                preview_id = f"web-{block_index}-{hash(url or title) % 10000}"
                if preview_id in emitted_preview_ids:
                    continue
                emitted_preview_ids.add(preview_id)
                web_count += 1
                yield await create_preview_event(
                    preview_type="web",
                    preview_id=preview_id,
                    title=title[:120],
                    snippet=snippet,
                    url=url or None,
                    node="direct",
                    metadata={
                        "date": date,
                        "source": source,
                    },
                )
                if web_count >= preview_max:
                    break
        except Exception as preview_error:
            logger.debug("[STREAM] Web preview parse failed: %s", preview_error)
            continue


async def emit_product_previews_impl(
    *,
    enabled: bool,
    realtime_preview: bool,
    preview_types: list[str] | None,
    preview_max: int,
    tool_call_events: list[dict[str, Any]] | None,
    emitted_preview_ids: set[str],
    create_preview_event: Callable[..., Any],
) -> AsyncGenerator[Any, None]:
    if (
        not enabled
        or realtime_preview
        or (preview_types and "product" not in preview_types)
    ):
        return

    product_count = 0
    for tc in tool_call_events or []:
        if tc.get("type") != "result" or product_count >= preview_max:
            continue
        raw_result = tc.get("result", "")
        try:
            parsed = json.loads(raw_result) if isinstance(raw_result, str) else raw_result
            if not isinstance(parsed, dict):
                continue
            platform = parsed.get("platform", "")
            for item_index, product in enumerate(parsed.get("results", [])[:10]):
                if not isinstance(product, dict):
                    continue
                preview_id = f"prod-{platform}-{item_index}"
                if preview_id in emitted_preview_ids:
                    continue
                emitted_preview_ids.add(preview_id)
                product_count += 1
                yield await create_preview_event(
                    preview_type="product",
                    preview_id=preview_id,
                    title=str(product.get("title", product.get("name", "Sản phẩm")))[:120],
                    snippet=str(product.get("description", ""))[:300],
                    url=product.get("url") or product.get("link"),
                    image_url=product.get("image") or product.get("image_url") or product.get("thumbnail"),
                    node="product_search_agent",
                    metadata={
                        "price": product.get("price"),
                        "rating": product.get("rating"),
                        "seller": product.get("seller") or product.get("shop"),
                        "platform": platform,
                    },
                )
                if product_count >= preview_max:
                    break
        except Exception as preview_error:
            logger.debug("[STREAM] Product preview parse failed: %s", preview_error)
            continue
