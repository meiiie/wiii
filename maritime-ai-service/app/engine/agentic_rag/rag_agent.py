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
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


# CHỈ THỊ SỐ 29: Lazy import for thinking extraction utility (avoid circular import)
# extract_thinking_from_response is imported inside functions where needed

# CHỈ THỊ SỐ 29: PromptLoader for SOTA thinking instruction
from app.prompts.prompt_loader import PromptLoader

from app.core.config import settings
from app.engine.openrouter_routing import build_openrouter_extra_body
from app.engine.llm_pool import get_llm_moderate

# Lazy import for optional LLM providers
ChatOpenAI = None  # Will be imported if needed
from app.models.knowledge_graph import (
    Citation,
    KnowledgeNode,
    RelationType,
)
from app.repositories.neo4j_knowledge_repository import Neo4jKnowledgeRepository
from app.engine.rrf_reranker import HybridSearchResult

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


@dataclass
class EvidenceImage:
    """
    Evidence image reference for Multimodal RAG.

    CHỈ THỊ KỸ THUẬT SỐ 26: Evidence Images
    **Feature: multimodal-rag-vision**
    """
    url: str
    page_number: int
    document_id: str = ""


@dataclass
class RAGResponse:
    """
    Response from RAG Agent with citations.

    **Validates: Requirements 4.1**
    **Feature: multimodal-rag-vision** - Added evidence_images
    **Feature: document-kg** - Added entity_context for GraphRAG
    """
    content: str
    citations: List[Citation]
    is_fallback: bool = False
    disclaimer: Optional[str] = None
    evidence_images: List[EvidenceImage] = None  # CHỈ THỊ 26: Evidence Images
    entity_context: Optional[str] = None  # Feature: document-kg - GraphRAG entity context
    related_entities: List[str] = None  # Feature: document-kg - Related entity names
    native_thinking: Optional[str] = None  # CHỈ THỊ SỐ 29: Gemini native thinking for hybrid display

    def __post_init__(self):
        if self.evidence_images is None:
            self.evidence_images = []
        if self.related_entities is None:
            self.related_entities = []

    def has_citations(self) -> bool:
        """Check if response has citations."""
        return len(self.citations) > 0

    def has_evidence_images(self) -> bool:
        """Check if response has evidence images."""
        return len(self.evidence_images) > 0

    def has_entity_context(self) -> bool:
        """Check if response has entity context from GraphRAG."""
        return bool(self.entity_context)


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
        self._prompt_loader = PromptLoader()

        self._llm = self._init_llm()

    def _init_llm(self):
        """
        Initialize LLM for response synthesis.

        CHỈ THỊ SỐ 28: Uses MODERATE tier thinking (4096 tokens) for RAG synthesis.
        Supports Google Gemini (primary) and OpenAI/OpenRouter (fallback).
        """
        provider = getattr(settings, 'llm_provider', 'google')

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
        # Check if search is available
        if not self._hybrid_search.is_available():
            return self._create_fallback_response(question)

        # Feature: document-kg - Use GraphRAG for entity-enriched search
        entity_context = ""
        related_entities = []
        hybrid_results = []

        if self._graph_rag and self._graph_rag.is_available():
            try:
                # GraphRAG search with entity context
                graph_results, entity_ctx = await self._graph_rag.search_with_graph_context(
                    query=question,
                    limit=limit
                )

                if graph_results:
                    # Convert GraphEnhancedResult to HybridSearchResult format
                    hybrid_results = self._graph_to_hybrid_results(graph_results)
                    entity_context = entity_ctx

                    # Collect related entities from results
                    # SOTA FIX: Separate entity dicts and regulation strings to avoid unhashable dict error
                    related_entity_dicts = []  # List[Dict] - not hashable
                    related_regulation_names = []  # List[str] - hashable

                    for gr in graph_results:
                        if gr.related_entities:
                            related_entity_dicts.extend(gr.related_entities[:3])
                        if gr.related_regulations:
                            related_regulation_names.extend(gr.related_regulations[:3])

                    # Deduplicate entities by ID (SOTA: hashable key extraction)
                    seen_entity_ids = set()
                    unique_entities = []
                    for entity in related_entity_dicts:
                        entity_id = entity.get("id") or entity.get("name", str(entity))
                        if entity_id not in seen_entity_ids:
                            seen_entity_ids.add(entity_id)
                            unique_entities.append(entity)

                    # Deduplicate regulation names (strings are hashable)
                    unique_regulations = list(dict.fromkeys(related_regulation_names))

                    # Combine for backward compatibility
                    related_entities = unique_entities[:5] + unique_regulations[:5]

                    logger.info("[GraphRAG] Found %d results with entity context", len(hybrid_results))
            except Exception as e:
                logger.warning("GraphRAG search failed, falling back to hybrid: %s", e)
                hybrid_results = []

        # Fallback to standard hybrid search if GraphRAG unavailable or failed
        if not hybrid_results:
            hybrid_results = await self._hybrid_search.search(question, limit=limit)

        if not hybrid_results:
            # Fallback to legacy Neo4j search
            logger.info("Hybrid search returned no results, falling back to legacy search")
            nodes = await self._kg.hybrid_search(question, limit=limit)
            if not nodes:
                return self._create_no_results_response(question)
            expanded_nodes = await self._expand_context(nodes)
            citations = await self._kg.get_citations(nodes)
            # CHỈ THỊ SỐ 29: Unpack tuple with native_thinking
            content, native_thinking = self._generate_response(question, expanded_nodes, conversation_history, user_role, entity_context)
            return RAGResponse(content=content, citations=citations, is_fallback=False, native_thinking=native_thinking)

        # Convert hybrid results to KnowledgeNodes for compatibility
        nodes = self._hybrid_results_to_nodes(hybrid_results)

        # Expand context with related nodes
        expanded_nodes = await self._expand_context(nodes)

        # Generate citations with relevance scores
        citations = self._generate_hybrid_citations(hybrid_results)

        # Generate response content with entity context
        # CHỈ THỊ SỐ 29: Unpack tuple with native_thinking
        content, native_thinking = self._generate_response(
            question, expanded_nodes, conversation_history, user_role, entity_context
        )

        # Add search method info to response
        search_method = hybrid_results[0].search_method if hybrid_results else "hybrid"
        if entity_context:
            search_method = "graph_enhanced"
        if search_method not in ["hybrid", "graph_enhanced"]:
            content += f"\n\n*[Tìm kiếm: {search_method}]*"

        # CHỈ THỊ 26: Collect evidence images
        node_ids = [r.node_id for r in hybrid_results]
        evidence_images = await self._collect_evidence_images(node_ids, max_images=3)

        return RAGResponse(
            content=content,
            citations=citations,
            is_fallback=False,
            evidence_images=evidence_images,
            entity_context=entity_context,
            related_entities=related_entities,
            native_thinking=native_thinking  # CHỈ THỊ SỐ 29: Propagate native thinking
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
        host_context_prompt: str = "",  # Sprint 222
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
            host_context_prompt=host_context_prompt,  # Sprint 222
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
        # Yield thinking event for retrieval phase
        yield {"type": "thinking", "content": "🔍 Đang tra cứu cơ sở dữ liệu..."}

        # Check if search is available
        if not self._hybrid_search.is_available():
            yield {"type": "error", "content": "Cơ sở dữ liệu không khả dụng"}
            return

        # Perform hybrid search (same as regular query)
        entity_context = ""
        hybrid_results = []

        if self._graph_rag and self._graph_rag.is_available():
            try:
                graph_results, entity_ctx = await self._graph_rag.search_with_graph_context(
                    query=question, limit=limit
                )
                if graph_results:
                    hybrid_results = self._graph_to_hybrid_results(graph_results)
                    entity_context = entity_ctx
            except Exception as e:
                logger.warning("[STREAMING] GraphRAG failed: %s", e)

        if not hybrid_results:
            hybrid_results = await self._hybrid_search.search(question, limit=limit)

        if not hybrid_results:
            yield {"type": "answer", "content": "Không tìm thấy thông tin về chủ đề này."}
            yield {"type": "done", "content": ""}
            return

        # Yield thinking event
        yield {"type": "thinking", "content": f"📚 Tìm thấy {len(hybrid_results)} tài liệu liên quan"}

        # Convert to nodes
        nodes = self._hybrid_results_to_nodes(hybrid_results)
        expanded_nodes = await self._expand_context(nodes)

        # Yield thinking event before generation
        yield {"type": "thinking", "content": "✍️ Đang tạo câu trả lời..."}

        # P3 SOTA: Stream the generation
        async for chunk in self._generate_response_streaming(
            question, expanded_nodes, conversation_history, user_role, entity_context
        ):
            yield {"type": "answer", "content": chunk}

        # After generation, yield sources
        citations = self._generate_hybrid_citations(hybrid_results)
        sources_data = [
            {"title": c.title, "content": c.source or "", "document_id": c.document_id or ""}
            for c in citations
        ]
        yield {"type": "sources", "content": sources_data}

        # Done signal
        yield {"type": "done", "content": ""}

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
        host_context_prompt: str = "",  # Sprint 222
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
            llm=self._llm,
            prompt_loader=self._prompt_loader,
            question=question,
            nodes=nodes,
            conversation_history=conversation_history,
            user_role=user_role,
            entity_context=entity_context,
            user_name=user_name,
            is_follow_up=is_follow_up,
            host_context_prompt=host_context_prompt,  # Sprint 222
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
        host_context_prompt: str = "",  # Sprint 222
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
            llm=self._llm,
            prompt_loader=self._prompt_loader,
            question=question,
            nodes=nodes,
            conversation_history=conversation_history,
            user_role=user_role,
            entity_context=entity_context,
            host_context_prompt=host_context_prompt,  # Sprint 222
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


class MaritimeDocumentParser:
    """
    Parser for maritime regulation documents.

    Extracts structured data from SOLAS, COLREGs, etc.

    **Validates: Requirements 4.5, 4.6**
    """

    @staticmethod
    def parse_regulation(
        code: str,
        title: str,
        content: str,
        source: str = ""
    ) -> KnowledgeNode:
        """
        Parse a regulation into a KnowledgeNode.

        Args:
            code: Regulation code (e.g., "SOLAS II-2/10")
            title: Regulation title
            content: Full regulation text
            source: Source document

        Returns:
            KnowledgeNode representing the regulation

        **Validates: Requirements 4.5**
        """
        from app.models.knowledge_graph import NodeType

        return KnowledgeNode(
            id=f"reg_{code.lower().replace('/', '_').replace('-', '_')}",
            node_type=NodeType.REGULATION,
            title=title,
            content=content,
            source=source,
            metadata={"code": code}
        )

    @staticmethod
    def serialize_to_document(node: KnowledgeNode) -> str:
        """
        Serialize a KnowledgeNode back to document format.

        Args:
            node: The node to serialize

        Returns:
            Document string representation

        **Validates: Requirements 4.6**
        """
        parts = []

        # Add code if available
        code = node.metadata.get("code", "")
        if code:
            parts.append(f"Code: {code}")

        parts.append(f"Title: {node.title}")
        parts.append(f"Content: {node.content}")

        if node.source:
            parts.append(f"Source: {node.source}")

        return "\n".join(parts)


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
