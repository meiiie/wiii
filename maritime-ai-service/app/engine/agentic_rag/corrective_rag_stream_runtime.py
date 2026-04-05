"""
Streaming runtime helpers for CorrectiveRAG.

Keeps the main CorrectiveRAG class focused on orchestration and ownership while
the large streaming implementation lives in a dedicated module.
"""

import logging
import time
from typing import Any, AsyncGenerator, Dict, Optional


logger = logging.getLogger(__name__)


async def process_streaming_impl(
    owner,
    query: str,
    context: Optional[Dict[str, Any]],
    *,
    result_cls,
    get_reasoning_tracer_fn,
    settings_obj,
    step_names_cls,
    build_retrieval_surface_text_fn,
    build_house_fallback_reply_fn,
    is_no_doc_retrieval_text_fn,
    normalize_visible_text_fn,
    max_content_snippet_length: int,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    SOTA 2025: Full CRAG pipeline with progressive SSE events.

    Yields SSE events at each pipeline stage:
    - status: Processing stage updates (shown as typing indicator)
    - thinking: AI reasoning steps (shown in collapsible section)  
    - answer: Response tokens (streamed real-time via LLM.astream())
    - sources: Citation list with image_url for PDF highlighting
    - metadata: reasoning_trace, confidence, timing
    - done: Stream complete

    Pattern:
    - OpenAI Responses API (event types: reasoning, output, completion)
    - Claude Interleaved Thinking (thinking blocks between steps)
    - LangChain LCEL RunnableParallel (parallel execution)

    **Feature: p3-v3-full-crag-streaming**
    """
    # Note: get_reasoning_tracer and StepNames already imported at module level (line 37-39)

    context = context or {}
    start_time = time.time()
    tracer = get_reasoning_tracer_fn()

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 1: Query Understanding (emit events immediately)
    # ═══════════════════════════════════════════════════════════════════
    yield {"type": "status", "content": "Phân tích câu hỏi"}

    tracer.start_step(step_names_cls.QUERY_ANALYSIS, "Phân tích độ phức tạp câu hỏi")
    logger.info("[CRAG-V3] Phase 1: Analyzing query: '%s...'", query[:50])

    try:
        analysis = await owner._analyzer.analyze(query)
        tracer.end_step(
            result=f"Độ phức tạp: {analysis.complexity.value}, Domain: {analysis.is_domain_related}",
            confidence=analysis.confidence,
            details={"complexity": analysis.complexity.value, "is_domain": analysis.is_domain_related}
        )

        # Sprint 144: Rich analysis thinking — expert-level breakdown
        _analysis_parts = [f"Độ phức tạp: {analysis.complexity.value}"]
        if analysis.detected_topics:
            _analysis_parts.append(f"Chủ đề: {', '.join(analysis.detected_topics[:5])}")
        if analysis.is_domain_related:
            _analysis_parts.append("Thuộc lĩnh vực chuyên ngành → Sử dụng Knowledge Base")
        else:
            _analysis_parts.append("Ngoài chuyên ngành → Sử dụng kiến thức chung LLM")
        if hasattr(analysis, 'confidence') and analysis.confidence:
            _analysis_parts.append(f"Độ tin cậy phân tích: {analysis.confidence:.0%}")
        yield {
            "type": "thinking",
            "content": "\n".join(_analysis_parts),
            "step": "analysis",
            "details": {"topics": analysis.detected_topics, "is_domain": analysis.is_domain_related}
        }
    except Exception as e:
        logger.error("[CRAG-V3] Analysis failed: %s", e)
        yield {"type": "error", "content": "Lỗi phân tích câu hỏi. Vui lòng thử lại."}
        yield {"type": "done", "content": ""}  # Sprint 189b: ensure done
        return

    # Sprint 187: Adaptive RAG routing (streaming path)
    adaptive_decision_stream = None
    if settings_obj.enable_adaptive_rag:
        try:
            from app.engine.agentic_rag.adaptive_rag import route_query
            adaptive_decision_stream = route_query(
                query=query,
                complexity=analysis.complexity.value,
                is_domain_related=analysis.is_domain_related,
                detected_topics=analysis.detected_topics,
                requires_multi_step=analysis.requires_multi_step,
            )
            yield {
                "type": "thinking",
                "content": f"Chiến lược tìm kiếm: {adaptive_decision_stream.strategy.value} — {adaptive_decision_stream.reason}",
                "step": "adaptive_rag",
            }
        except Exception as e:
            logger.warning("[CRAG-V3] Adaptive RAG routing failed: %s", e)

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 2: Retrieval (hybrid search + optional graphrag)
    # ═══════════════════════════════════════════════════════════════════
    yield {"type": "status", "content": "Tìm kiếm tài liệu"}

    tracer.start_step(step_names_cls.RETRIEVAL, "Tìm kiếm tài liệu")
    logger.info("[CRAG-V3] Phase 2: Retrieving documents")

    try:
        documents = await owner._retrieve(query, context)
        tracer.end_step(
            result=f"Tìm thấy {len(documents)} tài liệu",
            confidence=0.8 if documents else 0.3,
            details={"doc_count": len(documents)}
        )

        yield {
            "type": "thinking",
            "content": build_retrieval_surface_text_fn(len(documents)),
            "step": "retrieval",
            "details": {"doc_count": len(documents)}
        }

        # Sprint 179+: Visual RAG enrichment (streaming path)
        if settings_obj.enable_visual_rag and documents:
            try:
                from app.engine.agentic_rag.visual_rag import enrich_documents_with_visual_context

                yield {"type": "status", "content": "Phân tích hình ảnh tài liệu"}
                visual_result = await enrich_documents_with_visual_context(
                    documents=documents,
                    query=query,
                    max_images=settings_obj.visual_rag_max_images,
                )
                if visual_result.total_images_analyzed > 0:
                    documents = visual_result.enriched_documents
                    yield {
                        "type": "thinking",
                        "content": f"Phân tích {visual_result.total_images_analyzed} hình ảnh từ tài liệu ({visual_result.total_time_ms:.0f}ms)",
                        "step": "visual_rag",
                    }
                    logger.info(
                        "[CRAG-V3] Visual RAG: enriched %d documents",
                        visual_result.total_images_analyzed,
                    )
            except Exception as e:
                logger.warning("[CRAG-V3] Visual RAG failed: %s", e)

        # Sprint 182: Graph RAG enrichment (streaming path)
        graph_entity_context_streaming = ""
        if settings_obj.enable_graph_rag and documents:
            try:
                from app.engine.agentic_rag.graph_rag_retriever import enrich_with_graph_context

                yield {"type": "status", "content": "Phân tích đồ thị tri thức"}
                graph_result = await enrich_with_graph_context(
                    documents=documents,
                    query=query,
                )
                if graph_result.entity_context_text:
                    graph_entity_context_streaming = graph_result.entity_context_text
                    yield {
                        "type": "thinking",
                        "content": f"Đồ thị tri thức: {len(graph_result.entities)} thực thể, chế độ {graph_result.mode} ({graph_result.total_time_ms:.0f}ms)",
                        "step": "graph_rag",
                    }
                if graph_result.additional_docs:
                    documents.extend(graph_result.additional_docs)
                    logger.info(
                        "[CRAG-V3] Graph RAG: added %d additional documents",
                        len(graph_result.additional_docs),
                    )
            except Exception as e:
                logger.warning("[CRAG-V3] Graph RAG failed: %s", e)

        if not documents:
            # Sprint 165: LLM fallback — use general knowledge instead of hardcoded error
            yield {"type": "status", "content": "Chuyển sang cách đáp trực tiếp...", "step": "llm_fallback"}
            fallback_answer = await owner._generate_fallback(query, context or {})
            if not fallback_answer:
                fallback_answer = build_house_fallback_reply_fn()
            yield {"type": "answer", "content": fallback_answer}
            yield {"type": "result", "data": result_cls(
                answer=fallback_answer,
                sources=[],
                query_analysis=analysis,
                confidence=45.0,
                was_rewritten=False,          # Sprint 189b-R5: parity with sync
                rewritten_query=None,         # Sprint 189b-R5
                evidence_images=[],           # Sprint 189b: explicit empty
            )}
            yield {"type": "done", "content": ""}
            return

    except Exception as e:
        logger.error("[CRAG-V3] Retrieval failed: %s", e)
        yield {"type": "error", "content": "Lỗi tìm kiếm tài liệu. Vui lòng thử lại."}
        yield {"type": "done", "content": ""}  # Sprint 189b: ensure done
        return

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 3: Grading (CRAG core - quality control!)  
    # ═══════════════════════════════════════════════════════════════════
    yield {"type": "status", "content": "Đánh giá chất lượng tài liệu"}

    tracer.start_step(step_names_cls.GRADING, "Đánh giá độ liên quan của tài liệu")
    logger.info("[CRAG-V3] Phase 3: Grading documents")

    try:
        # FIXED: Use grade_documents (not grade_batch)
        grading_result = await owner._grader.grade_documents(query, documents)
        passed = grading_result.avg_score >= owner._grade_threshold
        grading_confidence = grading_result.relevant_count / len(documents) if documents else 0.5

        tracer.end_step(
            result=f"Điểm: {grading_result.avg_score:.1f}/10 - {'ĐẠT' if passed else 'CHƯA ĐẠT'}",
            confidence=grading_confidence,
            details={
                "score": grading_result.avg_score,
                "passed": passed,
                "relevant_count": grading_result.relevant_count
            }
        )

        # Sprint 144: Rich grading thinking — expert quality assessment
        _grade_icon = "✅" if passed else "⚠️"
        _grade_parts = [
            f"{_grade_icon} Điểm chất lượng: {grading_result.avg_score:.1f}/10 — {'ĐẠT' if passed else 'CHƯA ĐẠT'}",
            f"Tài liệu liên quan: {grading_result.relevant_count}/{len(documents)}",
        ]
        _threshold = getattr(owner, '_grade_threshold', 6.0)
        if not passed:
            _grade_parts.append(f"Ngưỡng yêu cầu: {_threshold}/10 → Cần tinh chỉnh câu hỏi")
        else:
            _grade_parts.append(f"Vượt ngưỡng {_threshold}/10 → Đủ chất lượng để tạo câu trả lời")
        yield {
            "type": "thinking",
            "content": "\n".join(_grade_parts),
            "step": "grading",
            "details": {"score": grading_result.avg_score, "passed": passed}
        }

    except Exception as e:
        logger.error("[CRAG-V3] Grading failed: %s", e)
        yield {"type": "thinking", "content": "⚠️ Bỏ qua đánh giá chất lượng, tiếp tục tạo câu trả lời.", "step": "grading"}
        grading_result = None
        passed = True  # Continue without grading

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 4: Query Rewrite (if grading failed)
    # ═══════════════════════════════════════════════════════════════════
    rewritten_query = None
    if grading_result and not passed and owner._rewriter:
        yield {"type": "status", "content": "Tinh chỉnh câu hỏi"}

        try:
            rewrite_result = await owner._rewriter.rewrite(
                query,
                getattr(grading_result, "feedback", ""),
            )
            candidate_query = getattr(rewrite_result, "rewritten_query", rewrite_result)
            if isinstance(candidate_query, str):
                candidate_query = candidate_query.strip()
            else:
                candidate_query = None

            if candidate_query and candidate_query != query:
                rewritten_query = candidate_query
                logger.info("[CRAG-V3] Query rewritten: %s...", rewritten_query[:50])

                yield {
                    "type": "thinking",
                    "content": f"Tinh chỉnh câu hỏi để tìm kiếm chính xác hơn\nCâu gốc: {query[:80]}\nCâu mới: {rewritten_query[:80]}",
                    "step": "rewrite"
                }

                # Re-retrieve with rewritten query
                documents = await owner._retrieve(rewritten_query, context)

        except Exception as e:
            logger.warning("[CRAG-V3] Rewrite failed: %s", e)

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 5: Generation (TRUE streaming via astream!)
    # ═══════════════════════════════════════════════════════════════════
    yield {"type": "status", "content": "Tạo câu trả lời"}

    tracer.start_step(step_names_cls.GENERATION, "Tạo câu trả lời từ context")
    logger.info("[CRAG-V3] Phase 5: Generating response with streaming")

    gen_start_time = time.time()

    full_answer_parts = []  # Sprint 144: Accumulate answer tokens for result

    if not owner._rag:
        yield {"type": "answer", "content": "Xin lỗi, mình chưa sẵn sàng trả lời câu này nha~ (˶˃ ᵕ ˂˶)"}
        yield {"type": "done", "content": ""}
        return

    try:
        # Build context from documents
        context_parts = []
        sources_data = []

        for doc in documents:
            content = doc.get("content", "")
            title = doc.get("title", "Unknown")
            if content:
                context_parts.append(f"[{title}]: {content}")

            # Prepare source data for later
            sources_data.append({
                "title": title,
                "content": content[:max_content_snippet_length] if content else "",
                "page_number": doc.get("page_number"),
                "image_url": doc.get("image_url"),
                "document_id": doc.get("document_id"),
                "node_id": doc.get("node_id"),              # Sprint 189b-R5: parity with sync
                "bounding_boxes": doc.get("bounding_boxes"),
                "content_type": doc.get("content_type"),    # Sprint 189b
            })

        # Sprint 189b: Collect evidence images from retrieved documents
        evidence_image_list = []
        if documents:
            try:
                node_ids = [d.get("node_id", "") for d in documents if d.get("node_id")]
                if node_ids:
                    from app.engine.agentic_rag.document_retriever import DocumentRetriever
                    ev_imgs = await DocumentRetriever.collect_evidence_images(node_ids, max_images=3)
                    evidence_image_list = [
                        {"url": img.url, "page_number": img.page_number, "document_id": img.document_id}
                        for img in ev_imgs
                    ]
            except Exception as e:
                logger.warning("[CRAG-V3] Evidence image collection failed: %s", e)

        # Get user context
        user_context = context  # The dict passed to process_streaming
        user_role = user_context.get("user_role", "student")
        history = user_context.get("conversation_history", "")

        # SOTA PATTERN: Defensive defaults for data quality issues
        # Following OpenAI/Anthropic pattern - graceful degradation, never crash
        from app.models.knowledge_graph import KnowledgeNode, NodeType

        knowledge_nodes = []
        for i, doc in enumerate(documents):
            # CRITICAL: Use 'or' operator to handle empty strings
            # doc.get("title", "X") returns '' if title is empty string
            # doc.get("title") or "X" returns "X" if title is empty/None
            node = KnowledgeNode(
                id=doc.get("node_id") or f"doc_{i}",
                node_type=NodeType.REGULATION,
                content=doc.get("content") or "No content",
                title=doc.get("title") or f"Document {i+1}",
                source=doc.get("document_id") or ""
            )
            knowledge_nodes.append(node)

        # Sprint 144: Intermediate response — user sees activity before LLM generation
        yield {
            "type": "answer",
            "content": f"Wiii tìm thấy {len(documents)} tài liệu liên quan, đang phân tích để trả lời...\n\n"
        }

        # Stream tokens from RAGAgent
        # FIXED: Removed invalid 'context' param, pass nodes correctly
        token_count = 0
        async for chunk in owner._rag._generate_response_streaming(
            question=rewritten_query or query,
            nodes=knowledge_nodes,
            conversation_history=history,
            user_role=user_role,
            entity_context=graph_entity_context_streaming,
            response_language=context.get("response_language"),
            host_context_prompt=context.get("host_context_prompt", ""),  # Sprint 222
            living_context_prompt=context.get("living_context_prompt", ""),
            skill_context=context.get("skill_context", ""),
            capability_context=context.get("capability_context", ""),
        ):
            token_count += 1
            full_answer_parts.append(chunk)
            yield {"type": "answer", "content": chunk}

        gen_duration = (time.time() - gen_start_time) * 1000
        tracer.end_step(
            result=f"Tạo câu trả lời: {token_count} tokens",
            confidence=0.85,
            details={"token_count": token_count, "duration_ms": gen_duration}
        )

        logger.info("[CRAG-V3] Generation complete: %d tokens in %.0fms", token_count, gen_duration)

    except Exception as e:
        logger.error("[CRAG-V3] Generation failed: %s", e)
        _error_msg = "Xin lỗi, mình chưa tạo được câu trả lời lúc này nha~ ≽^•⩊•^≼"
        yield {"type": "answer", "content": _error_msg}
        full_answer_parts.append(_error_msg)  # Sprint 189b: capture in result

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 6: Finalize (sources + metadata)
    # ═══════════════════════════════════════════════════════════════════
    total_time = time.time() - start_time

    # Calculate confidence
    confidence = owner._calculate_confidence(
        analysis, 
        grading_result, 
        None  # No verification in streaming mode
    )

    # Build reasoning trace
    reasoning_trace = tracer.build_trace(final_confidence=confidence / 100)

    # Sprint 189b-R5: Build thinking_content from tracer (parity with sync path)
    thinking_content = tracer.build_thinking_summary()
    # Note: native_thinking unavailable in streaming (generate_response_streaming yields text only)

    # Emit sources
    yield {
        "type": "sources",
        "content": sources_data
    }

    # Emit metadata with reasoning_trace
    # FIX: ReasoningTrace is Pydantic BaseModel, use model_dump() (v2) or dict() (v1)
    reasoning_dict = None
    if reasoning_trace:
        try:
            # Pydantic v2: model_dump()
            reasoning_dict = reasoning_trace.model_dump()
        except AttributeError:
            # Pydantic v1 fallback: dict()
            reasoning_dict = reasoning_trace.dict()

    yield {
        "type": "metadata",
        "content": {
            "reasoning_trace": reasoning_dict,
            "processing_time": total_time,
            "confidence": confidence,
            "model": settings_obj.rag_model_version,
            "was_rewritten": rewritten_query is not None,
            "doc_count": len(documents),
            "evidence_images": evidence_image_list,  # Sprint 189b
        }
    }

    # Sprint 144: Yield CorrectiveRAGResult for rag_node to capture
    full_answer = "".join(full_answer_parts)
    yield {
        "type": "result",
        "data": result_cls(
            answer=full_answer,
            sources=sources_data,
            query_analysis=analysis,
            grading_result=grading_result,
            was_rewritten=rewritten_query is not None,
            rewritten_query=rewritten_query,
            confidence=confidence,
            reasoning_trace=reasoning_trace,
            thinking_content=thinking_content,  # Sprint 189b-R5: parity with sync
            evidence_images=evidence_image_list,  # Sprint 189b
        )
    }

    yield {"type": "done", "content": ""}

    logger.info("[CRAG-V3] Complete: %.2fs, confidence=%.0f%%", total_time, confidence)
