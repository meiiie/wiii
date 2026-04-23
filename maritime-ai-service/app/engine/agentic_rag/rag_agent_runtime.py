"""Runtime helpers for RAGAgent query flows."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _collect_related_entities(graph_results) -> list:
    """Collect deduplicated entity/regulation hints from GraphRAG results."""
    related_entity_dicts = []
    related_regulation_names = []

    for graph_result in graph_results:
        if graph_result.related_entities:
            related_entity_dicts.extend(graph_result.related_entities[:3])
        if graph_result.related_regulations:
            related_regulation_names.extend(graph_result.related_regulations[:3])

    seen_entity_ids = set()
    unique_entities = []
    for entity in related_entity_dicts:
        entity_id = entity.get("id") or entity.get("name", str(entity))
        if entity_id not in seen_entity_ids:
            seen_entity_ids.add(entity_id)
            unique_entities.append(entity)

    unique_regulations = list(dict.fromkeys(related_regulation_names))
    return unique_entities[:5] + unique_regulations[:5]


async def query_impl(
    rag_agent,
    *,
    question: str,
    limit: int,
    conversation_history: str,
    user_role: str,
    response_cls,
):
    """Run the synchronous RAG query path."""
    if not rag_agent._hybrid_search.is_available():
        return rag_agent._create_fallback_response(question)

    entity_context = ""
    related_entities = []
    hybrid_results = []

    if rag_agent._graph_rag and rag_agent._graph_rag.is_available():
        try:
            graph_results, entity_ctx = await rag_agent._graph_rag.search_with_graph_context(
                query=question,
                limit=limit,
            )

            if graph_results:
                hybrid_results = rag_agent._graph_to_hybrid_results(graph_results)
                entity_context = entity_ctx
                related_entities = _collect_related_entities(graph_results)
                logger.info(
                    "[GraphRAG] Found %d results with entity context",
                    len(hybrid_results),
                )
        except Exception as exc:
            logger.warning(
                "GraphRAG search failed, falling back to hybrid: %s",
                exc,
            )
            hybrid_results = []

    if not hybrid_results:
        hybrid_results = await rag_agent._hybrid_search.search(question, limit=limit)

    if not hybrid_results:
        logger.info(
            "Hybrid search returned no results, falling back to legacy search"
        )
        nodes = await rag_agent._kg.hybrid_search(question, limit=limit)
        if not nodes:
            return rag_agent._create_no_results_response(question)
        expanded_nodes = await rag_agent._expand_context(nodes)
        citations = await rag_agent._kg.get_citations(nodes)
        content, native_thinking = rag_agent._generate_response(
            question,
            expanded_nodes,
            conversation_history,
            user_role,
            entity_context,
        )
        return response_cls(
            content=content,
            citations=citations,
            is_fallback=False,
            native_thinking=native_thinking,
        )

    nodes = rag_agent._hybrid_results_to_nodes(hybrid_results)
    expanded_nodes = await rag_agent._expand_context(nodes)
    citations = rag_agent._generate_hybrid_citations(hybrid_results)
    content, native_thinking = rag_agent._generate_response(
        question,
        expanded_nodes,
        conversation_history,
        user_role,
        entity_context,
    )

    search_method = hybrid_results[0].search_method if hybrid_results else "hybrid"
    if entity_context:
        search_method = "graph_enhanced"
    if search_method not in ["hybrid", "graph_enhanced"]:
        content += f"\n\n*[Tìm kiếm: {search_method}]*"

    node_ids = [result.node_id for result in hybrid_results]
    evidence_images = await rag_agent._collect_evidence_images(
        node_ids,
        max_images=3,
    )

    return response_cls(
        content=content,
        citations=citations,
        is_fallback=False,
        evidence_images=evidence_images,
        entity_context=entity_context,
        related_entities=related_entities,
        native_thinking=native_thinking,
    )


async def query_streaming_impl(
    rag_agent,
    *,
    question: str,
    limit: int,
    conversation_history: str,
    user_role: str,
):
    """Run the streaming RAG query path."""
    yield {"type": "thinking", "content": "🔍 Đang tra cứu cơ sở dữ liệu..."}

    if not rag_agent._hybrid_search.is_available():
        yield {"type": "error", "content": "Cơ sở dữ liệu không khả dụng"}
        return

    entity_context = ""
    hybrid_results = []

    if rag_agent._graph_rag and rag_agent._graph_rag.is_available():
        try:
            graph_results, entity_ctx = await rag_agent._graph_rag.search_with_graph_context(
                query=question,
                limit=limit,
            )
            if graph_results:
                hybrid_results = rag_agent._graph_to_hybrid_results(graph_results)
                entity_context = entity_ctx
        except Exception as exc:
            logger.warning("[STREAMING] GraphRAG failed: %s", exc)

    if not hybrid_results:
        hybrid_results = await rag_agent._hybrid_search.search(question, limit=limit)

    if not hybrid_results:
        yield {"type": "answer", "content": "Không tìm thấy thông tin về chủ đề này."}
        yield {"type": "done", "content": ""}
        return

    yield {
        "type": "thinking",
        "content": f"📚 Tìm thấy {len(hybrid_results)} tài liệu liên quan",
    }

    nodes = rag_agent._hybrid_results_to_nodes(hybrid_results)
    expanded_nodes = await rag_agent._expand_context(nodes)

    yield {"type": "thinking", "content": "✍️ Đang tạo câu trả lời..."}

    async for chunk in rag_agent._generate_response_streaming(
        question=question,
        nodes=expanded_nodes,
        conversation_history=conversation_history,
        user_role=user_role,
        entity_context=entity_context,
        response_language=None,
        host_context_prompt="",
        living_context_prompt="",
        skill_context="",
        capability_context="",
    ):
        yield {"type": "answer", "content": chunk}

    citations = rag_agent._generate_hybrid_citations(hybrid_results)
    sources_data = [
        {
            "title": citation.title,
            "content": citation.source or "",
            "document_id": citation.document_id or "",
        }
        for citation in citations
    ]
    yield {"type": "sources", "content": sources_data}
    yield {"type": "done", "content": ""}
