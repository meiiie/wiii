"""Retrieval runtime helpers for Corrective RAG."""

from __future__ import annotations

import asyncio
from typing import Any, Optional


async def retrieve_impl(
    crag: Any,
    *,
    query: str,
    context: dict[str, Any],
    query_embedding_override: Optional[list[float]],
    logger: Any,
    _prefetch_docs: Optional[list[dict[str, Any]]] = None,
) -> list[dict[str, Any]]:
    """Retrieve grading-ready documents with full content preserved."""
    if _prefetch_docs:
        logger.info("[CRAG] Using %d pre-fetched documents, skipping retrieval", len(_prefetch_docs))
        return _prefetch_docs

    if not crag._rag:
        logger.warning("[CRAG] No RAG agent available")
        return []

    try:
        hybrid_search = getattr(crag._rag, "_hybrid_search", None)

        if hybrid_search and hybrid_search.is_available():
            org_id = context.get("organization_id")

            if query_embedding_override is not None:
                try:
                    dense_repo = getattr(hybrid_search, "_dense_repo", None)
                    sparse_repo = getattr(hybrid_search, "_sparse_repo", None)
                    reranker = getattr(hybrid_search, "_reranker", None)
                    dense_weight = getattr(hybrid_search, "_dense_weight", 0.7)
                    sparse_weight = getattr(hybrid_search, "_sparse_weight", 0.3)
                    if dense_repo and sparse_repo and reranker:
                        dense_task = dense_repo.search(
                            query_embedding_override, limit=20, org_id=org_id
                        )
                        sparse_task = sparse_repo.search(query, limit=20, org_id=org_id)
                        dense_results, sparse_results = await asyncio.gather(
                            dense_task, sparse_task, return_exceptions=True
                        )
                        if isinstance(dense_results, Exception):
                            dense_results = []
                        if isinstance(sparse_results, Exception):
                            sparse_results = []
                        results = reranker.merge(
                            dense_results,
                            sparse_results,
                            dense_weight=dense_weight,
                            sparse_weight=sparse_weight,
                            limit=10,
                            query=query,
                        )
                        logger.info(
                            "[CRAG] HyDE retrieval: %d docs (dense=%d sparse=%d)",
                            len(results),
                            len(dense_results),
                            len(sparse_results),
                        )
                    else:
                        results = await hybrid_search.search(
                            query=query,
                            limit=10,
                            org_id=org_id,
                        )
                except Exception as hyde_error:
                    logger.warning(
                        "[CRAG] HyDE dense retrieval failed, falling back: %s",
                        hyde_error,
                    )
                    results = await hybrid_search.search(query=query, limit=10, org_id=org_id)
            else:
                results = await hybrid_search.search(
                    query=query,
                    limit=10,
                    org_id=org_id,
                )

            documents: list[dict[str, Any]] = []
            for result in results:
                documents.append(
                    {
                        "node_id": result.node_id,
                        "content": result.content,
                        "title": result.title,
                        "score": result.rrf_score,
                        "image_url": result.image_url,
                        "page_number": result.page_number if hasattr(result, "page_number") else None,
                        "document_id": result.document_id if hasattr(result, "document_id") else None,
                        "bounding_boxes": result.bounding_boxes if hasattr(result, "bounding_boxes") else None,
                        "content_type": result.content_type if hasattr(result, "content_type") else "text",
                    }
                )

            logger.info(
                "[CRAG] Retrieved %d documents via HybridSearchService (SOTA)",
                len(documents),
            )
            return documents

        logger.warning("[CRAG] HybridSearch unavailable, falling back to RAGAgent")
        user_role = context.get("user_role", "student")
        history = context.get("conversation_history", "")

        response = await crag._rag.query(
            question=query,
            limit=10,
            conversation_history=history,
            user_role=user_role,
        )

        documents = []
        for citation in response.citations:
            documents.append(
                {
                    "node_id": getattr(citation, "node_id", ""),
                    "content": getattr(citation, "title", ""),
                    "title": getattr(citation, "title", "Unknown"),
                    "score": getattr(citation, "relevance_score", 0),
                    "image_url": getattr(citation, "image_url", None),
                    "page_number": getattr(citation, "page_number", None),
                    "document_id": getattr(citation, "document_id", None),
                    "bounding_boxes": getattr(citation, "bounding_boxes", None),
                }
            )

        logger.info("[CRAG] Retrieved %d documents via RAGAgent (fallback)", len(documents))
        return documents

    except Exception as exc:
        logger.error("[CRAG] RAGAgent retrieval failed: %s", exc)
        return []
