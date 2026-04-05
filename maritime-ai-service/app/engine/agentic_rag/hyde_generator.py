"""
HyDE Generator — Hypothetical Document Embeddings.
Sprint 187: "RAG Nâng Cao" — Advanced RAG Techniques.

Implements the HyDE pattern (Gao et al., 2022):
1. Given a query, generate a hypothetical document that would answer it
2. Embed the hypothetical document (RETRIEVAL_DOCUMENT task type)
3. Use that embedding to find real documents via dense search

The hypothetical embedding captures the "shape" of a good answer,
often retrieving more relevant documents than the raw query embedding.

Feature-gated by enable_hyde in config.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)

# Vietnamese prompt template for generating hypothetical answers
_HYDE_PROMPT_VI = """Bạn là chuyên gia hàng hải. Hãy viết một đoạn văn ngắn (100-200 từ) trả lời câu hỏi sau dựa trên kiến thức chuyên ngành.
Viết như thể đoạn văn được trích từ sách giáo khoa hoặc quy tắc hàng hải.
Không cần ghi nguồn. Chỉ viết nội dung trả lời.

Câu hỏi: {query}

Đoạn văn:"""


@dataclass
class HyDEResult:
    """Result from HyDE generation."""

    hypothetical_doc: str = ""
    hyde_embedding: List[float] = field(default_factory=list)
    original_embedding: List[float] = field(default_factory=list)
    generation_time_ms: float = 0.0
    embedding_time_ms: float = 0.0
    total_time_ms: float = 0.0
    used: bool = False  # Whether HyDE was actually used


async def generate_hyde_embedding(
    query: str,
    query_embedding: Optional[List[float]] = None,
) -> HyDEResult:
    """Generate a hypothetical document embedding for the query.

    Uses LLM to generate a hypothetical answer, then embeds it using
    RETRIEVAL_DOCUMENT task type (same as indexed documents).

    Args:
        query: User query string.
        query_embedding: Pre-computed query embedding (optional, for fallback).

    Returns:
        HyDEResult with hypothetical embedding, or empty result on failure.
    """
    start = time.time()

    try:
        # Step 1: Generate hypothetical document
        gen_start = time.time()
        hypothetical_doc = await _generate_hypothetical_doc(query)
        gen_time = (time.time() - gen_start) * 1000

        if not hypothetical_doc:
            logger.debug("[HyDE] No hypothetical document generated, skipping")
            return HyDEResult(
                original_embedding=query_embedding or [],
                total_time_ms=(time.time() - start) * 1000,
            )

        # Step 2: Embed the hypothetical document
        emb_start = time.time()
        hyde_embedding = await _embed_hypothetical_doc(hypothetical_doc)
        emb_time = (time.time() - emb_start) * 1000

        if not hyde_embedding:
            logger.warning("[HyDE] Failed to embed hypothetical doc, falling back to query embedding")
            return HyDEResult(
                hypothetical_doc=hypothetical_doc,
                original_embedding=query_embedding or [],
                generation_time_ms=gen_time,
                total_time_ms=(time.time() - start) * 1000,
            )

        total_time = (time.time() - start) * 1000
        logger.info(
            "[HyDE] Generated hypothetical doc (%d chars) + embedding (%d dims) in %.0fms",
            len(hypothetical_doc),
            len(hyde_embedding),
            total_time,
        )

        return HyDEResult(
            hypothetical_doc=hypothetical_doc,
            hyde_embedding=hyde_embedding,
            original_embedding=query_embedding or [],
            generation_time_ms=gen_time,
            embedding_time_ms=emb_time,
            total_time_ms=total_time,
            used=True,
        )

    except Exception as e:
        logger.warning("[HyDE] Generation failed: %s", e)
        return HyDEResult(
            original_embedding=query_embedding or [],
            total_time_ms=(time.time() - start) * 1000,
        )


async def _generate_hypothetical_doc(query: str) -> str:
    """Generate a hypothetical document using LLM light tier.

    Uses the lightweight LLM tier to minimize latency and cost.
    The prompt instructs the model to write as if from a textbook.

    Args:
        query: User query string.

    Returns:
        Hypothetical document text, or empty string on failure.
    """
    try:
        from app.engine.agentic_rag.runtime_llm_socket import ainvoke_agentic_rag_llm
        from app.engine.llm_factory import ThinkingTier
        from app.engine.llm_pool import get_llm_light
        from langchain_core.messages import HumanMessage

        llm = get_llm_light()
        if not llm:
            logger.debug("[HyDE] LLM light tier unavailable")
            return ""

        prompt = _HYDE_PROMPT_VI.format(query=query)
        response = await ainvoke_agentic_rag_llm(
            llm=llm,
            messages=[HumanMessage(content=prompt)],
            tier=ThinkingTier.LIGHT,
            component="HyDEGenerator",
        )

        # Extract content, strip thinking tags if present
        content = response.content
        if not content:
            return ""

        # Remove thinking blocks if present (Qwen3/DeepSeek pattern)
        from app.services.output_processor import extract_thinking_from_response
        cleaned, _ = extract_thinking_from_response(content)

        result = cleaned.strip()
        if len(result) < 20:
            logger.debug("[HyDE] Hypothetical doc too short (%d chars), discarding", len(result))
            return ""

        return result

    except Exception as e:
        logger.warning("[HyDE] Hypothetical doc generation failed: %s", e)
        return ""


async def _embed_hypothetical_doc(doc: str) -> List[float]:
    """Embed the hypothetical document using RETRIEVAL_DOCUMENT task type.

    This is the key insight of HyDE: embed the hypothetical answer as if it
    were a real document, so the embedding captures the "document space" rather
    than the "query space".

    Args:
        doc: Hypothetical document text.

    Returns:
        Embedding vector, or empty list on failure.
    """
    try:
        from app.engine.agentic_rag.corrective_rag_runtime_support import (
            get_document_embedding_impl,
        )

        # Use the shared embedding authority but keep document-style embedding
        # semantics for HyDE's "document space" retrieval heuristic.
        return await get_document_embedding_impl(doc)
    except Exception as e:
        logger.warning("[HyDE] Embedding failed: %s", e)
        return []


def blend_embeddings(
    query_embedding: List[float],
    hyde_embedding: List[float],
    alpha: float = 0.5,
) -> List[float]:
    """Blend query and HyDE embeddings for ensemble retrieval.

    Combines the query embedding (captures intent) with the HyDE embedding
    (captures document shape) using weighted average.

    Args:
        query_embedding: Original query embedding (RETRIEVAL_QUERY).
        hyde_embedding: HyDE embedding (RETRIEVAL_DOCUMENT).
        alpha: Weight for HyDE embedding (0=query only, 1=HyDE only).

    Returns:
        Blended embedding vector, L2-normalized.
    """
    if not query_embedding or not hyde_embedding:
        return query_embedding or hyde_embedding or []

    if len(query_embedding) != len(hyde_embedding):
        logger.warning(
            "[HyDE] Dimension mismatch: query=%d, hyde=%d",
            len(query_embedding),
            len(hyde_embedding),
        )
        return query_embedding

    import math

    # Weighted average
    blended = [
        (1 - alpha) * q + alpha * h
        for q, h in zip(query_embedding, hyde_embedding)
    ]

    # L2 normalize
    norm = math.sqrt(sum(x * x for x in blended))
    if norm > 0:
        blended = [x / norm for x in blended]

    return blended
