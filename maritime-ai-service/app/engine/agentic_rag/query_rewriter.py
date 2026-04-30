"""
Query Rewriter - Phase 7.3

Rewrites queries when initial retrieval results are poor.

Features:
- Query expansion with synonyms
- Query decomposition for complex questions
- Feedback-based rewriting
"""

import logging
from typing import List, Optional

from app.core.singleton import singleton_factory
from app.engine.agentic_rag.runtime_llm_socket import (
    ainvoke_agentic_rag_llm,
    make_agentic_rag_messages,
    resolve_agentic_rag_llm,
)
from app.engine.llm_factory import ThinkingTier
from app.engine.llm_pool import get_llm_light  # SOTA: Shared LLM Pool

logger = logging.getLogger(__name__)


REWRITE_PROMPT = """Bạn là Query Rewriter cho hệ thống AI.

Query gốc không tìm được kết quả tốt. Hãy viết lại query để tìm kiếm hiệu quả hơn.

Query gốc: {query}
Feedback: {feedback}

Yêu cầu:
1. Giữ nguyên ý nghĩa câu hỏi
2. Thêm từ khóa chuyên ngành liên quan
3. Sử dụng thuật ngữ chuẩn tiếng Anh nếu phù hợp
4. Đơn giản hóa nếu quá phức tạp

Chỉ trả về query mới, không giải thích."""


EXPAND_PROMPT = """Mở rộng query với các từ đồng nghĩa và thuật ngữ liên quan:

Query: {query}

Trả về query mở rộng với các variations:"""


DECOMPOSE_PROMPT = """Query này quá phức tạp. Hãy chia thành các sub-queries nhỏ hơn:

Query: {query}

Trả về danh sách sub-queries (mỗi dòng một query):"""


class QueryRewriter:
    """
    Rewrites queries for better retrieval.
    
    Usage:
        rewriter = QueryRewriter()
        new_query = await rewriter.rewrite(query, feedback)
    """
    
    def __init__(self):
        """Initialize with Gemini LLM."""
        self._llm = None
        self._init_llm()
    
    def _init_llm(self):
        """Initialize Gemini LLM from shared pool."""
        try:
            # Prefer the currently-selectable runtime provider instead of pinning
            # query rewriting to the default provider forever.
            self._llm = self._resolve_runtime_llm()
            logger.info("QueryRewriter initialized with shared LIGHT tier LLM")
        except Exception as e:
            logger.error("Failed to initialize QueryRewriter LLM: %s", e)
            self._llm = None

    def _resolve_runtime_llm(self):
        """Resolve a request-time LIGHT-tier LLM from the shared provider socket."""
        llm = resolve_agentic_rag_llm(
            tier=ThinkingTier.LIGHT,
            cached_llm=self._llm,
            fallback_factory=get_llm_light,
            component="QueryRewriter",
        )
        if llm is not None:
            self._llm = llm
        return llm
    
    async def rewrite(self, query: str, feedback: str = "") -> str:
        """
        Rewrite query based on feedback.
        
        Args:
            query: Original query
            feedback: Feedback from grading (why it failed)
            
        Returns:
            Rewritten query
        """
        llm = self._resolve_runtime_llm()
        if not llm:
            return self._rule_based_rewrite(query)
        
        try:
            messages = make_agentic_rag_messages(
                system="Bạn là bộ tối ưu truy vấn. Chỉ trả về truy vấn đã cải thiện, không giải thích.",
                user=REWRITE_PROMPT.format(
                    query=query,
                    feedback=feedback or "Documents retrieved were not relevant"
                ),
            )
            
            response = await ainvoke_agentic_rag_llm(
                llm=llm,
                messages=messages,
                tier=ThinkingTier.LIGHT,
                component="QueryRewriter",
            )
            
            # SOTA FIX: Handle Gemini 2.5 Flash content block format
            from app.services.output_processor import extract_thinking_from_response
            text_content, _ = extract_thinking_from_response(response.content)
            new_query = text_content.strip()
            
            # Clean up
            new_query = new_query.strip('"\'')
            
            logger.info("[REWRITER] '%s...' → '%s...'", query[:30], new_query[:30])
            return new_query
            
        except Exception as e:
            logger.warning("LLM rewrite failed: %s", e)
            return self._rule_based_rewrite(query)
    
    async def expand(self, query: str) -> str:
        """
        Expand query with synonyms and related terms.
        
        Args:
            query: Original query
            
        Returns:
            Expanded query
        """
        llm = self._resolve_runtime_llm()
        if not llm:
            return self._add_domain_keywords(query)
        
        try:
            messages = make_agentic_rag_messages(
                user=EXPAND_PROMPT.format(query=query),
            )
            
            response = await ainvoke_agentic_rag_llm(
                llm=llm,
                messages=messages,
                tier=ThinkingTier.LIGHT,
                component="QueryRewriterExpand",
            )
            
            # SOTA FIX: Handle Gemini 2.5 Flash content block format
            from app.services.output_processor import extract_thinking_from_response
            text_content, _ = extract_thinking_from_response(response.content)
            return text_content.strip()
            
        except Exception as e:
            logger.warning("Query expansion failed: %s", e)
            return self._add_domain_keywords(query)
    
    async def decompose(self, query: str) -> List[str]:
        """
        Decompose complex query into sub-queries.
        
        Args:
            query: Complex query
            
        Returns:
            List of simpler sub-queries
        """
        llm = self._resolve_runtime_llm()
        if not llm:
            return [query]  # Can't decompose without LLM
        
        try:
            messages = make_agentic_rag_messages(
                user=DECOMPOSE_PROMPT.format(query=query),
            )
            
            response = await ainvoke_agentic_rag_llm(
                llm=llm,
                messages=messages,
                tier=ThinkingTier.LIGHT,
                component="QueryRewriterDecompose",
            )
            
            # SOTA FIX: Handle Gemini 2.5 Flash content block format
            from app.services.output_processor import extract_thinking_from_response
            text_content, _ = extract_thinking_from_response(response.content)
            lines = text_content.strip().split("\n")
            
            # Clean up
            sub_queries = []
            for line in lines:
                line = line.strip()
                # Remove numbering
                if line and line[0].isdigit():
                    line = line.lstrip("0123456789.-) ")
                if line:
                    sub_queries.append(line)
            
            logger.info("[DECOMPOSE] '%s...' → %d sub-queries", query[:30], len(sub_queries))
            return sub_queries if sub_queries else [query]
            
        except Exception as e:
            logger.warning("Query decomposition failed: %s", e)
            return [query]
    
    def _get_domain_keywords(self) -> list[str]:
        """Load domain keywords from the active domain plugin, falling back to empty."""
        try:
            from app.domains.registry import get_domain_registry
            from app.core.config import settings
            registry = get_domain_registry()
            domain = registry.get(settings.default_domain)
            if domain:
                config = domain.get_config()
                return config.routing_keywords or []
        except Exception as e:
            logger.debug("Failed to load domain keywords: %s", e)
        return []

    def _rule_based_rewrite(self, query: str) -> str:
        """Fallback rule-based rewriting using domain keywords."""
        query_lower = query.lower()

        # Add domain keywords if none present
        domain_keywords = self._get_domain_keywords()
        if domain_keywords:
            has_keyword = any(kw.lower() in query_lower for kw in domain_keywords)
            if not has_keyword:
                query = f"{domain_keywords[0]} {query}"

        return query

    def _add_domain_keywords(self, query: str) -> str:
        """Add domain keywords to query for fallback expansion."""
        keywords = self._get_domain_keywords()
        if not keywords:
            return query

        query_lower = query.lower()

        additions = []
        for kw in keywords:
            if kw.lower() not in query_lower:
                additions.append(kw)
                break  # Add only one

        if additions:
            return f"{query} {' '.join(additions)}"
        return query
    
    def is_available(self) -> bool:
        """Check if LLM is available."""
        return self._llm is not None


get_query_rewriter = singleton_factory(QueryRewriter)
