"""
RAG Agent for maritime knowledge retrieval.

This module implements the RAG (Retrieval-Augmented Generation) agent
that queries the Knowledge Graph and generates responses with citations.
Now uses Hybrid Search (Dense + Sparse) for improved retrieval.

Feature: sparse-search-migration
- RAG now uses PostgreSQL for both dense (pgvector) and sparse (tsvector) search
- Neo4j is OPTIONAL and reserved for future Learning Graph integration
- System works fully without Neo4j connection

**Feature: wiii, hybrid-search, sparse-search-migration**
**Validates: Requirements 4.1, 4.2, 4.4, 8.3**
"""

import logging
from typing import Any, Dict, List, Optional, Tuple


# CHỈ THỊ SỐ 29: Lazy import for thinking extraction utility (avoid circular import)
# extract_thinking_from_response is imported inside functions where needed

# CHỈ THỊ SỐ 29: PromptLoader for SOTA thinking instruction
from app.prompts.prompt_loader import PromptLoader, get_prompt_loader

from app.core.config import settings
from app.engine.agentic_rag.runtime_llm_socket import resolve_agentic_rag_llm
from app.engine.llm_factory import ThinkingTier
from app.engine.openrouter_routing import build_openrouter_extra_body
from app.engine.llm_pool import get_llm_moderate

# Lazy import for optional LLM providers
ChatOpenAI = None  # Will be imported if needed
from app.models.knowledge_graph import (
    Citation,
    KnowledgeNode,
    RelationType,
)
from app.engine.agentic_rag.rag_agent_contracts import (
    EvidenceImage,
    MaritimeDocumentParser,
    RAGResponse,
)
from app.repositories.neo4j_knowledge_repository import Neo4jKnowledgeRepository
from app.engine.rrf_reranker import HybridSearchResult
from app.engine.agentic_rag.rag_agent_runtime import (
    query_impl,
    query_streaming_impl,
)

# Extracted modules for document retrieval and answer generation
from app.engine.agentic_rag.document_retriever import DocumentRetriever
from app.engine.agentic_rag.answer_generator import AnswerGenerator

# Lazy import to avoid circular dependency with app.services
# HybridSearchService is imported in __init__ method

logger = logging.getLogger(__name__)


# Cached repository instance
_knowledge_repo = None


def get_knowledge_repository():
    """
    Get the Neo4j knowledge repository (cached).

    Feature: sparse-search-migration
    NOTE: Neo4j is now OPTIONAL for RAG. RAG uses PostgreSQL for both
    dense (pgvector) and sparse (tsvector) search. Neo4j is reserved
    for future Learning Graph integration with LMS.
    """
    global _knowledge_repo

    if _knowledge_repo is not None:
        return _knowledge_repo

    _knowledge_repo = Neo4jKnowledgeRepository()
    if _knowledge_repo.is_available():
        logger.info("Neo4j available (reserved for Learning Graph)")
    else:
        # This is OK - RAG works without Neo4j
        logger.info("Neo4j unavailable - RAG uses PostgreSQL hybrid search")

    return _knowledge_repo


class RAGAgent:
    """
    RAG Agent for maritime knowledge retrieval.

    Combines Knowledge Graph queries with LLM generation
    to provide accurate, cited responses.

    Delegates document retrieval logic to DocumentRetriever
    and answer generation logic to AnswerGenerator.

    **Validates: Requirements 4.1, 4.2, 8.3**
    """

    # Relation types to traverse for context
    CONTEXT_RELATIONS = [
        RelationType.REGULATES,
        RelationType.APPLIES_TO,
        RelationType.RELATED_TO,
        RelationType.REFERENCES,
    ]

    # Fallback disclaimer when KG unavailable
    FALLBACK_DISCLAIMER = (
        "Note: This response is based on general knowledge. "
        "For authoritative information, please consult official maritime regulations."
    )

    def __init__(
        self,
        knowledge_graph=None,
        hybrid_search_service=None,
        graph_rag_service=None  # Feature: document-kg
    ):
        """
        Initialize RAG Agent.

        Args:
            knowledge_graph: Knowledge graph repository instance
            hybrid_search_service: Hybrid search service for Dense+Sparse search
            graph_rag_service: GraphRAG service for entity-enriched search
        """
        self._kg = knowledge_graph or get_knowledge_repository()

        # Lazy import to avoid circular dependency
        if hybrid_search_service is None:
            from app.services.hybrid_search_service import get_hybrid_search_service
            self._hybrid_search = get_hybrid_search_service()
        else:
            self._hybrid_search = hybrid_search_service

        # Feature: document-kg - GraphRAG for entity context
        if graph_rag_service is None:
            try:
                from app.services.graph_rag_service import get_graph_rag_service
                self._graph_rag = get_graph_rag_service()
                logger.info("GraphRAG service initialized for entity context")
            except Exception as e:
                logger.warning("GraphRAG not available: %s", e)
                self._graph_rag = None
        else:
            self._graph_rag = graph_rag_service

        # CHỈ THỊ SỐ 29: Initialize PromptLoader for SOTA thinking instruction
        self._prompt_loader = get_prompt_loader()

        self._llm = self._init_llm()

    def _init_llm(self):
        """
        Initialize LLM for response synthesis.

        CHỈ THỊ SỐ 28: Uses MODERATE tier thinking (4096 tokens) for RAG synthesis.
        Supports Google Gemini (primary) and OpenAI/OpenRouter (fallback).
        """
        provider = getattr(settings, 'llm_provider', 'google')

        runtime_llm = self._resolve_runtime_llm()
        if runtime_llm is not None:
            return runtime_llm

        # Try Google Gemini first with MODERATE tier thinking
        if provider == "google" or (not settings.openai_api_key and settings.google_api_key):
            if settings.google_api_key:
                try:
                    logger.info("RAG using Gemini with MODERATE thinking: %s", settings.google_model)
                    return get_llm_moderate()  # Shared pool instance
                except Exception as e:
                    logger.error("Failed to initialize Gemini for RAG: %s", e)

        # Fallback to OpenAI/OpenRouter (optional)
        if not settings.openai_api_key:
            logger.warning("No LLM API key, RAG will return raw content")
            return None

        try:
            # Lazy import ChatOpenAI only when needed
            global ChatOpenAI
            if ChatOpenAI is None:
                try:
                    from langchain_openai import ChatOpenAI as _ChatOpenAI
                    ChatOpenAI = _ChatOpenAI
                except ImportError:
                    logger.warning("langchain-openai not installed, skipping OpenAI fallback")
                    return None

            llm_kwargs = {
                "api_key": settings.openai_api_key,
                "model": settings.openai_model,
                "temperature": 0.3,  # Lower for factual responses
            }
            if settings.openai_base_url:
                llm_kwargs["base_url"] = settings.openai_base_url
                logger.info("RAG using OpenRouter: %s", settings.openai_model)
            else:
                logger.info("RAG using OpenAI: %s", settings.openai_model)

            openrouter_extra_body = build_openrouter_extra_body(
                settings,
                primary_model=settings.openai_model,
            )
            if openrouter_extra_body:
                llm_kwargs["extra_body"] = openrouter_extra_body

            return ChatOpenAI(**llm_kwargs)
        except Exception as e:
            logger.error("Failed to initialize LLM for RAG: %s", e)
            return None

    def _resolve_runtime_llm(self):
        """Resolve the request-time MODERATE-tier synthesis LLM."""
        llm = resolve_agentic_rag_llm(
            tier=ThinkingTier.MODERATE,
            cached_llm=getattr(self, "_llm", None),
            fallback_factory=get_llm_moderate,
            component="RAGAgent",
        )
        if llm is not None:
            self._llm = llm
        return llm

    async def query(
        self,
        question: str,
        limit: int = 5,
        conversation_history: str = "",
        user_role: str = "student"
    ) -> RAGResponse:
        """
        Query the knowledge graph and generate response.

        Uses GraphRAG (Hybrid Search + Entity Context) for improved retrieval.

        Args:
            question: User's question
            limit: Maximum number of sources to retrieve
            conversation_history: Formatted conversation history for context
            user_role: User role for role-based prompting (student/teacher/admin)

        Returns:
            RAGResponse with content, citations, and entity context

        **Validates: Requirements 4.1, 8.3**
        **Spec: CHỈ THỊ KỸ THUẬT SỐ 03 - Role-Based Prompting**
        **Feature: hybrid-search, document-kg**
        """
        return await query_impl(
            self,
            question=question,
            limit=limit,
            conversation_history=conversation_history,
            user_role=user_role,
            response_cls=RAGResponse,
        )

    # ==========================================================================
    # REFACTOR-005: Direct Generation from Pre-Retrieved Documents
    # ==========================================================================

    async def generate_from_documents(
        self,
        question: str,
        documents: List[Dict[str, Any]],
        conversation_history: str = "",
        user_role: str = "student",
        user_name: Optional[str] = None,
        is_follow_up: bool = False,
        entity_context: str = "",
        response_language: Optional[str] = None,
        host_context_prompt: str = "",  # Sprint 222
        living_context_prompt: str = "",
        skill_context: str = "",
        capability_context: str = "",
    ) -> RAGResponse:
        """
        Generate response from pre-retrieved documents (no re-retrieval).

        REFACTOR-005: This method is used by CorrectiveRAG to avoid duplicate
        retrieval. Documents have already been retrieved and graded by CRAG,
        so we skip the retrieval step and go straight to generation.

        Args:
            question: User's question
            documents: Pre-retrieved documents from CRAG grading
            conversation_history: Formatted conversation history for context
            user_role: User role for role-based prompting

        Returns:
            RAGResponse with content, citations, and native_thinking

        **Feature: refactor-005-no-duplicate-rag**
        """
        if not documents:
            return RAGResponse(
                content="Không tìm thấy thông tin về chủ đề này.",
                citations=[],
                is_fallback=True
            )

        # Convert documents to KnowledgeNodes for _generate_response
        nodes = self._documents_to_nodes(documents)

        # Generate response using existing method
        # Sprint 89: Pass user_name and is_follow_up for persona consistency
        content, native_thinking = self._generate_response(
            question=question,
            nodes=nodes,
            conversation_history=conversation_history,
            user_role=user_role,
            entity_context=entity_context,
            user_name=user_name,
            is_follow_up=is_follow_up,
            response_language=response_language,
            host_context_prompt=host_context_prompt,  # Sprint 222
            living_context_prompt=living_context_prompt,
            skill_context=skill_context,
            capability_context=capability_context,
        )

        # Convert documents to citations
        citations = self._documents_to_citations(documents)

        logger.info("[RAG] Generated from %d pre-retrieved docs", len(documents))

        return RAGResponse(
            content=content,
            citations=citations,
            is_fallback=False,
            native_thinking=native_thinking
        )

    def _documents_to_nodes(self, documents: List[Dict[str, Any]]) -> List[KnowledgeNode]:
        """Convert document dicts to KnowledgeNodes for generation."""
        return DocumentRetriever.documents_to_nodes(documents)

    def _documents_to_citations(self, documents: List[Dict[str, Any]]) -> List[Citation]:
        """Convert document dicts to Citations for response."""
        return DocumentRetriever.documents_to_citations(documents)

    # ==========================================================================
    # P3 SOTA: Streaming Query Method
    # ==========================================================================

    async def query_streaming(
        self,
        question: str,
        limit: int = 5,
        conversation_history: str = "",
        user_role: str = "student"
    ):
        """
        Query with streaming response - yields tokens as they arrive.

        SOTA Dec 2025 Pattern:
        - CRAG pipeline runs normally (retrieval + grading)
        - Generation phase streams token-by-token
        - First token: ~20s instead of ~60s

        Yields:
            dict: {"type": "thinking|answer|sources|done", "content": str}

        **Feature: p3-sota-streaming**
        """
        async for event in query_streaming_impl(
            self,
            question=question,
            limit=limit,
            conversation_history=conversation_history,
            user_role=user_role,
        ):
            yield event

    def _graph_to_hybrid_results(self, graph_results) -> List[HybridSearchResult]:
        """Convert GraphEnhancedResult to HybridSearchResult for compatibility."""
        return DocumentRetriever.graph_to_hybrid_results(graph_results)

    def _hybrid_results_to_nodes(self, results: List[HybridSearchResult]) -> List[KnowledgeNode]:
        """Convert HybridSearchResult to KnowledgeNode for compatibility with chunking metadata."""
        return DocumentRetriever.hybrid_results_to_nodes(results)

    def _format_title_with_hierarchy(self, title: str, result: HybridSearchResult) -> str:
        """
        Format title with document hierarchy (Điều, Khoản, etc.).

        **Feature: semantic-chunking**
        **Validates: Requirements 8.4**
        """
        return DocumentRetriever.format_title_with_hierarchy(title, result)

    def _generate_hybrid_citations(self, results: List[HybridSearchResult]) -> List[Citation]:
        """
        Generate citations from hybrid search results with relevance scores and chunking metadata.

        **Feature: semantic-chunking, source-highlight-citation**
        **Validates: Requirements 8.4, 8.5, 2.1, 2.3**
        """
        return DocumentRetriever.generate_hybrid_citations(results)

    async def _collect_evidence_images(
        self,
        node_ids: List[str],
        max_images: int = 3
    ) -> List[EvidenceImage]:
        """
        Collect evidence images from database for given node IDs.

        CHỈ THỊ KỸ THUẬT SỐ 26: Evidence Images

        **Property 3: Search Results Include Image URL**
        **Property 11: Response Metadata Contains Evidence Images**
        **Property 12: Maximum Evidence Images Per Response**

        Args:
            node_ids: List of node IDs to get images for
            max_images: Maximum number of images to return (default 3)

        Returns:
            List of EvidenceImage objects
        """
        return await DocumentRetriever.collect_evidence_images(node_ids, max_images)


    async def _expand_context(
        self,
        nodes: List[KnowledgeNode]
    ) -> List[KnowledgeNode]:
        """
        Expand context by traversing relations.

        NOTE: Neo4j is DISABLED for RAG as of v0.6.0 (sparse-search-migration).
        Neo4j is reserved for future Learning Graph integration.
        This method is kept for backward compatibility but returns nodes unchanged.

        **Validates: Requirements 4.4**
        """
        # Neo4j disabled for RAG - reserved for Learning Graph (v0.6.0+)
        # See README.md: "Neo4j: Reserved for future Learning Graph (LMS integration)"
        return list(nodes)

    def _generate_response(
        self,
        question: str,
        nodes: List[KnowledgeNode],
        conversation_history: str = "",
        user_role: str = "student",
        entity_context: str = "",  # Feature: document-kg
        user_name: Optional[str] = None,
        is_follow_up: bool = False,
        response_language: Optional[str] = None,
        host_context_prompt: str = "",  # Sprint 222
        living_context_prompt: str = "",
        skill_context: str = "",
        capability_context: str = "",
    ) -> Tuple[str, Optional[str]]:
        """
        Generate response using LLM to synthesize retrieved knowledge.

        Uses RAG pattern: Retrieve -> Augment -> Generate
        Includes conversation history for context continuity.
        Now includes entity context from GraphRAG for enriched responses.

        CHỈ THỊ SỐ 29: Returns tuple of (answer, native_thinking) for hybrid display.

        Role-Based Prompting (CHỈ THỊ KỸ THUẬT SỐ 03):
        - student: AI đóng vai Gia sư (Tutor) - giọng văn khuyến khích, giải thích cặn kẽ
        - teacher/admin: AI đóng vai Trợ lý (Assistant) - chuyên nghiệp, ngắn gọn

        Returns:
            Tuple of (answer_text, native_thinking) where native_thinking may be None

        **Feature: wiii, Week 2: Memory Lite, document-kg**
        **Spec: CHỈ THỊ KỸ THUẬT SỐ 03, CHỈ THỊ SỐ 29**
        """
        return AnswerGenerator.generate_response(
            llm=self._resolve_runtime_llm(),
            prompt_loader=self._prompt_loader,
            question=question,
            nodes=nodes,
            conversation_history=conversation_history,
            user_role=user_role,
            entity_context=entity_context,
            user_name=user_name,
            is_follow_up=is_follow_up,
            response_language=response_language,
            host_context_prompt=host_context_prompt,  # Sprint 222
            living_context_prompt=living_context_prompt,
            skill_context=skill_context,
            capability_context=capability_context,
        )

    def _create_fallback_response(self, question: str) -> RAGResponse:
        """
        Create fallback response when KG is unavailable.

        **Validates: Requirements 8.3**
        """
        logger.warning("Knowledge Graph unavailable, using fallback response")

        content = (
            f"I understand you're asking about: {question}\n\n"
            "While I can provide general guidance on maritime topics, "
            "I'm currently unable to access the detailed knowledge base. "
            "Please try again later for more specific information with citations."
        )

        return RAGResponse(
            content=content,
            citations=[],
            is_fallback=True,
            disclaimer=self.FALLBACK_DISCLAIMER
        )

    def _create_no_results_response(self, question: str) -> RAGResponse:
        """Create response when no results found."""
        content = (
            f"I searched for information about: {question}\n\n"
            "Unfortunately, I couldn't find specific information in the knowledge base. "
            "You might want to:\n"
            "- Rephrase your question\n"
            "- Ask about a more specific topic\n"
            "- Consult official maritime documentation directly"
        )

        return RAGResponse(
            content=content,
            citations=[],
            is_fallback=False
        )

    def is_available(self) -> bool:
        """
        Check if RAG Agent is available.

        Feature: sparse-search-migration
        RAG is available if hybrid search (PostgreSQL) is available.
        Neo4j is optional and not required for RAG functionality.
        """
        return self._hybrid_search.is_available()

    # ==========================================================================
    # P3 SOTA STREAMING: Token-by-token generation (Dec 2025)
    # Pattern: ChatGPT Progressive Response + Claude Interleaved Thinking
    # ==========================================================================

    async def _generate_response_streaming(
        self,
        question: str,
        nodes: List[KnowledgeNode],
        conversation_history: str = "",
        user_role: str = "student",
        entity_context: str = "",
        response_language: Optional[str] = None,
        host_context_prompt: str = "",  # Sprint 222
        living_context_prompt: str = "",
        skill_context: str = "",
        capability_context: str = "",
    ):
        """
        SOTA Streaming Generation - yields tokens as they arrive from LLM.

        Pattern from ChatGPT/Claude Dec 2025:
        - First token appears after ~20s (post-CRAG) instead of ~60s
        - Perceived latency reduced by 3x
        - Uses llm.astream() for true token streaming

        Yields:
            str: Token chunks as they arrive from LLM

        **Feature: p3-sota-streaming**
        """
        async for chunk in AnswerGenerator.generate_response_streaming(
            llm=self._resolve_runtime_llm(),
            prompt_loader=self._prompt_loader,
            question=question,
            nodes=nodes,
            conversation_history=conversation_history,
            user_role=user_role,
            entity_context=entity_context,
            response_language=response_language,
            host_context_prompt=host_context_prompt,  # Sprint 222
            living_context_prompt=living_context_prompt,
            skill_context=skill_context,
            capability_context=capability_context,
        ):
            yield chunk

    def _extract_content_from_chunk(self, chunk) -> str:
        """
        Extract text content from LLM streaming chunk.

        Handles both:
        - String content (simple case)
        - List of content blocks (Gemini with thinking_enabled=True)

        **Feature: p3-sota-streaming, gemini-3-flash-thinking**
        """
        return AnswerGenerator.extract_content_from_chunk(chunk)


# =============================================================================
# SINGLETON PATTERN (SOTA Memory Optimization)
# =============================================================================
# Pattern: Lazy singleton ensures ONE RAGAgent instance across application
# Impact: Prevents ~100MB memory duplication per request
# Reference: OpenAI/Anthropic production patterns (Dec 2025)
# =============================================================================

from typing import Optional as _Optional

_rag_agent_instance: _Optional[RAGAgent] = None


def get_rag_agent(**kwargs) -> RAGAgent:
    """
    Get or create RAGAgent singleton (SOTA memory pattern).

    This follows the Lazy Singleton pattern used by OpenAI and Anthropic
    in production systems to prevent heavy resource duplication.

    Args:
        **kwargs: Optional kwargs for first-time initialization
            (ignored if singleton already exists)

    Returns:
        RAGAgent: The singleton instance

    Example:
        >>> agent = get_rag_agent()
        >>> result = await agent.query("What is Rule 15?")
    """
    global _rag_agent_instance
    if _rag_agent_instance is None:
        _rag_agent_instance = RAGAgent(**kwargs)
        logger.info("[RAGAgent] Singleton instance created (memory optimized)")
    return _rag_agent_instance


def is_rag_agent_initialized() -> bool:
    """Check if RAGAgent singleton has been initialized."""
    return _rag_agent_instance is not None


def reset_rag_agent() -> None:
    """Reset RAGAgent singleton (for testing only)."""
    global _rag_agent_instance
    _rag_agent_instance = None
    logger.info("[RAGAgent] Singleton reset")
