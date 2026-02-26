"""
Adaptive RAG — Dynamic retrieval strategy routing.
Sprint 187: "RAG Nâng Cao" — Advanced RAG Techniques.

Routes queries to different retrieval strategies based on analysis:
- SIMPLE → Dense-only search (fast, low latency)
- MODERATE → Hybrid search (dense + sparse + RRF, standard path)
- COMPLEX → Multi-step retrieval (decompose → parallel → merge)
- FACTUAL → Sparse-first search (keyword-dominant, rule lookups)

Feature-gated by enable_adaptive_rag in config.
When disabled, all queries use the standard hybrid search path.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class RetrievalStrategy(str, Enum):
    """Available retrieval strategies."""

    DENSE_ONLY = "dense_only"    # Fast vector search
    SPARSE_FIRST = "sparse_first"  # Keyword-dominant search
    HYBRID = "hybrid"            # Standard dense + sparse + RRF
    MULTI_STEP = "multi_step"    # Decompose → parallel → merge
    HYDE_ENHANCED = "hyde_enhanced"  # HyDE + hybrid


@dataclass
class RoutingDecision:
    """Decision from adaptive routing."""

    strategy: RetrievalStrategy
    reason: str
    dense_weight: float = 0.5
    sparse_weight: float = 0.5
    enable_hyde: bool = False
    enable_verification: bool = False
    max_iterations: int = 2
    sub_queries: Optional[List[str]] = None


# Keywords that indicate factual/rule lookup queries (prefer sparse search)
_FACTUAL_KEYWORDS = {
    "rule", "quy tắc", "điều", "khoản", "mục",
    "article", "regulation", "chapter", "chương",
    "solas", "colregs", "marpol", "stcw",
    "số mấy", "bao nhiêu", "mấy", "là gì",
}

# Keywords that indicate complex multi-step queries
_COMPLEX_KEYWORDS = {
    "so sánh", "compare", "khác nhau", "difference",
    "phân tích", "analyze", "tổng hợp", "summarize",
    "liên hệ", "relation", "ảnh hưởng", "impact",
    "tất cả", "all", "liệt kê", "list",
    "giải thích chi tiết", "explain in detail",
}

# Keywords that indicate simple/direct queries
_SIMPLE_KEYWORDS = {
    "là gì", "what is", "định nghĩa", "definition",
    "nghĩa là", "means",
}


def route_query(
    query: str,
    complexity: str = "moderate",
    is_domain_related: bool = True,
    detected_topics: Optional[List[str]] = None,
    requires_multi_step: bool = False,
) -> RoutingDecision:
    """Route a query to the optimal retrieval strategy.

    Uses query analysis results to pick the best strategy.
    Combines complexity classification with keyword signals.

    Args:
        query: User query string.
        complexity: From QueryAnalyzer ("simple", "moderate", "complex").
        is_domain_related: Whether query is domain-specific.
        detected_topics: Topics detected by QueryAnalyzer.
        requires_multi_step: Whether multi-step retrieval is needed.

    Returns:
        RoutingDecision with strategy and parameters.
    """
    query_lower = query.lower()

    # Rule 1: Complex queries with multi-step requirement
    if complexity == "complex" or requires_multi_step:
        has_complex_kw = any(kw in query_lower for kw in _COMPLEX_KEYWORDS)
        if has_complex_kw or requires_multi_step:
            return RoutingDecision(
                strategy=RetrievalStrategy.MULTI_STEP,
                reason="Complex query requiring multi-step retrieval",
                dense_weight=0.5,
                sparse_weight=0.5,
                enable_verification=True,
                max_iterations=3,
            )

    # Rule 2: Factual/rule lookup queries → sparse-first
    has_factual_kw = any(kw in query_lower for kw in _FACTUAL_KEYWORDS)
    if has_factual_kw and is_domain_related:
        return RoutingDecision(
            strategy=RetrievalStrategy.SPARSE_FIRST,
            reason="Factual domain query — sparse keyword search prioritized",
            dense_weight=0.3,
            sparse_weight=0.7,
            max_iterations=1,
        )

    # Rule 3: Simple queries → dense-only (fastest)
    has_simple_kw = any(kw in query_lower for kw in _SIMPLE_KEYWORDS)
    if complexity == "simple" and has_simple_kw:
        return RoutingDecision(
            strategy=RetrievalStrategy.DENSE_ONLY,
            reason="Simple definitional query — dense search sufficient",
            dense_weight=1.0,
            sparse_weight=0.0,
            max_iterations=1,
        )

    # Rule 4: Non-domain queries → HyDE enhanced (better semantic matching)
    if not is_domain_related:
        return RoutingDecision(
            strategy=RetrievalStrategy.HYDE_ENHANCED,
            reason="Non-domain query — HyDE for better semantic matching",
            dense_weight=0.6,
            sparse_weight=0.4,
            enable_hyde=True,
            max_iterations=2,
        )

    # Default: Standard hybrid search
    return RoutingDecision(
        strategy=RetrievalStrategy.HYBRID,
        reason="Standard domain query — hybrid search",
        dense_weight=0.5,
        sparse_weight=0.5,
        max_iterations=2,
    )


def get_search_weights(decision: RoutingDecision) -> Dict[str, float]:
    """Extract search weights from routing decision.

    Returns a dict compatible with HybridSearchService parameters.

    Args:
        decision: Routing decision from route_query.

    Returns:
        Dict with dense_weight and sparse_weight keys.
    """
    return {
        "dense_weight": decision.dense_weight,
        "sparse_weight": decision.sparse_weight,
    }


def should_use_hyde(decision: RoutingDecision) -> bool:
    """Check if HyDE should be used for this routing decision.

    Args:
        decision: Routing decision from route_query.

    Returns:
        True if HyDE is recommended.
    """
    return decision.enable_hyde or decision.strategy == RetrievalStrategy.HYDE_ENHANCED


def should_decompose_query(decision: RoutingDecision) -> bool:
    """Check if query should be decomposed into sub-queries.

    Args:
        decision: Routing decision from route_query.

    Returns:
        True if multi-step decomposition is recommended.
    """
    return decision.strategy == RetrievalStrategy.MULTI_STEP
