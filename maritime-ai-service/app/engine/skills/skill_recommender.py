"""
Sprint 192: Intelligent Tool Selection — 4-Step Pipeline

Provides query-aware tool filtering to reduce LLM tool-binding overhead
and improve selection accuracy. Pipeline:

  1. Category filter   (rule-based, ~1ms)  → 20 candidates
  2. Semantic pre-filter (keyword cosine, ~5ms) → 10 candidates
  3. LLM structured output (Gemini LIGHT, ~500ms) → 5 tools (optional)
  4. Metrics reranking  (success_rate × recency × 1/latency) → final list

Feature-gated: enable_intelligent_tool_selection=False (default)

Pattern:
  - Singleton: get_intelligent_tool_selector()
  - Thread-safe via threading.Lock
  - Core tools always included regardless of filtering
  - Backward compatible: default strategy "all" returns all tools unchanged
"""

import logging
import math
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Module-level singleton
_selector_instance: Optional["IntelligentToolSelector"] = None
_selector_lock = threading.Lock()

# Core tools that are ALWAYS included regardless of filtering
CORE_TOOLS = ["tool_current_datetime", "tool_knowledge_search"]


class SelectionStrategy(str, Enum):
    """Tool selection strategies."""
    ALL = "all"                    # Return all tools (backward compat default)
    CATEGORY = "category"          # Filter by ToolCategory based on intent
    SEMANTIC = "semantic"          # Keyword similarity pre-filter
    METRICS = "metrics"            # Rerank by metrics (success_rate, latency)
    HYBRID = "hybrid"              # Category + Semantic + Metrics (recommended)


@dataclass
class ToolRecommendation:
    """A recommended tool with selection metadata."""
    tool_name: str
    confidence: float = 1.0        # 0-1, how confident selection is
    reason: str = ""               # Why selected
    estimated_latency_ms: int = 0  # From metrics (0 = unknown)
    estimated_cost_usd: float = 0.0  # From metrics (0 = unknown)
    score: float = 0.0             # Composite selection score


# ======================================================================
# Intent → Category mapping
# ======================================================================

# Maps supervisor intent to relevant ToolCategory values
_INTENT_TO_CATEGORIES: Dict[str, List[str]] = {
    "product_search": ["product_search"],
    "web_search": ["utility"],
    "lookup": ["rag"],
    "learning": ["learning", "assessment", "character"],
    "personal": ["memory", "memory_control", "character"],
    "social": ["utility", "character"],
    "off_topic": ["utility"],
}

# Keyword groups that hint at specific tool categories
_KEYWORD_CATEGORIES: List[Tuple[List[str], str]] = [
    # Product search keywords → product_search
    (["mua", "bán", "giá", "sản phẩm", "so sánh giá", "tìm hàng",
      "shopee", "lazada", "tiktok shop", "facebook marketplace",
      "price", "buy", "sell", "product", "shop"], "product_search"),
    # Web/news search keywords → utility
    (["tin tức", "news", "thời sự", "mới nhất", "trang web",
      "website", "search", "google", "tìm kiếm web"], "utility"),
    # Legal search keywords → utility (legal tools are in utility)
    (["luật", "pháp luật", "quy định", "nghị định", "thông tư",
      "law", "regulation", "legal"], "utility"),
    # Memory keywords → memory
    (["nhớ", "remember", "quên", "forget", "ghi nhớ", "lưu ý",
      "thông tin cá nhân", "personal info"], "memory"),
    # Learning keywords → learning
    (["học", "bài giảng", "quiz", "ôn tập", "learn", "lesson",
      "kiểm tra", "test", "exam"], "learning"),
    # DateTime keywords → utility
    (["mấy giờ", "ngày", "hôm nay", "thời gian", "time", "date",
      "today", "now", "bao giờ"], "utility"),
    # Chart/visualization keywords → character (chart tools are in character node)
    (["biểu đồ", "chart", "graph", "diagram", "mermaid",
      "sơ đồ", "bảng"], "character"),
]


def get_intelligent_tool_selector() -> "IntelligentToolSelector":
    """Get or create the singleton IntelligentToolSelector."""
    global _selector_instance
    if _selector_instance is None:
        with _selector_lock:
            if _selector_instance is None:
                _selector_instance = IntelligentToolSelector()
    return _selector_instance


def _resolve_tool_name(tool: Callable) -> str:
    """Extract a stable tool name from a callable-like object."""
    return str(
        getattr(tool, "name", None)
        or getattr(tool, "__name__", None)
        or ""
    ).strip()


def select_runtime_tools(
    tools: List[Callable],
    *,
    query: str,
    intent: Optional[str] = None,
    user_role: str = "student",
    max_tools: Optional[int] = None,
    must_include: Optional[List[str]] = None,
    enabled: Optional[bool] = None,
    strategy: SelectionStrategy = SelectionStrategy.HYBRID,
) -> List[Callable]:
    """Select a runtime-safe subset of tool objects for the current turn.

    The selector works on registered tool names, then maps the ranked
    recommendations back to the concrete tool callables that a node will bind
    to its LLM. When the feature is disabled or selection fails, the original
    tool list is returned unchanged.
    """
    if not tools:
        return []

    available_map: Dict[str, Callable] = {}
    ordered_names: List[str] = []
    for tool in tools:
        name = _resolve_tool_name(tool)
        if not name or name in available_map:
            continue
        available_map[name] = tool
        ordered_names.append(name)

    if len(ordered_names) <= 1:
        return list(tools)

    if enabled is None:
        try:
            from app.core.config import settings as _settings

            enabled = bool(getattr(_settings, "enable_intelligent_tool_selection", False))
        except Exception:
            enabled = False

    if not enabled:
        return list(tools)

    selector = get_intelligent_tool_selector()
    resolved_intent = intent or selector.detect_intent_from_query(query)
    selected_max_tools = max_tools or min(len(ordered_names), 8)

    selected_names: List[str] = []
    try:
        recommendations = selector.select_tools(
            query=query,
            intent=resolved_intent,
            user_role=user_role,
            strategy=strategy,
            max_tools=selected_max_tools,
            available_tools=ordered_names,
        )
        selected_names = [
            rec.tool_name
            for rec in recommendations
            if rec.tool_name in available_map
        ]
    except Exception as exc:
        logger.debug("[TOOL_SELECTOR] Runtime selection failed: %s", exc)
        selected_names = []

    try:
        from app.engine.tools.registry import get_tool_registry

        registry = get_tool_registry()
        passthrough_names = [
            name
            for name in ordered_names
            if name not in getattr(registry, "_tools", {})
        ]
    except Exception:
        passthrough_names = []

    for name in passthrough_names:
        if name not in selected_names:
            selected_names.append(name)

    for name in must_include or []:
        if name in available_map and name not in selected_names:
            selected_names.append(name)

    if not selected_names:
        return list(tools)

    return [available_map[name] for name in selected_names if name in available_map]


class IntelligentToolSelector:
    """
    4-step intelligent tool selection pipeline.

    Reduces tool binding overhead by selecting only relevant tools
    for each query, improving LLM focus and response quality.

    Usage:
        selector = get_intelligent_tool_selector()
        recs = selector.select_tools(
            query="tìm đầu in Zebra ZXP7",
            intent="product_search",
            strategy=SelectionStrategy.HYBRID,
        )
        # recs = [ToolRecommendation(tool_name="tool_search_shopee", ...), ...]
    """

    def __init__(self):
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def select_tools(
        self,
        query: str,
        intent: Optional[str] = None,
        user_role: str = "student",
        domain_id: Optional[str] = None,
        strategy: SelectionStrategy = SelectionStrategy.ALL,
        max_tools: int = 15,
        available_tools: Optional[List[str]] = None,
    ) -> List[ToolRecommendation]:
        """
        Select the best tools for a given query and context.

        Args:
            query: User query text
            intent: Supervisor-classified intent (product_search, web_search, etc.)
            user_role: User role for access filtering
            domain_id: Active domain for context
            strategy: Selection strategy to use
            max_tools: Maximum tools to return
            available_tools: Pre-filtered list of available tool names (optional)

        Returns:
            Ordered list of ToolRecommendation objects.
        """
        if strategy == SelectionStrategy.ALL:
            return self._strategy_all(available_tools, user_role)

        # Get all available tools from registry
        tool_pool = self._get_tool_pool(available_tools, user_role)

        if not tool_pool:
            return []

        # Step 1: Category filter
        if strategy in (SelectionStrategy.CATEGORY, SelectionStrategy.HYBRID):
            tool_pool = self._step1_category_filter(
                tool_pool, query, intent
            )

        # Step 2: Semantic pre-filter (keyword matching)
        if strategy in (SelectionStrategy.SEMANTIC, SelectionStrategy.HYBRID):
            tool_pool = self._step2_semantic_filter(
                tool_pool, query, max_candidates=max_tools * 2,
            )

        # Step 3: LLM structured selection (optional, expensive)
        # Skipped in default pipeline — available for future "llm_assisted" mode

        # Step 4: Metrics reranking
        if strategy in (SelectionStrategy.METRICS, SelectionStrategy.HYBRID):
            tool_pool = self._step4_metrics_rerank(
                tool_pool,
                query=query,
                intent=intent,
            )

        # Ensure core tools are always included
        tool_pool = self._ensure_core_tools(tool_pool, available_tools, user_role)

        # Limit and return
        return tool_pool[:max_tools]

    # ------------------------------------------------------------------
    # Strategy: ALL (backward compat)
    # ------------------------------------------------------------------

    def _strategy_all(
        self,
        available_tools: Optional[List[str]],
        user_role: str,
    ) -> List[ToolRecommendation]:
        """Return all available tools without filtering."""
        pool = self._get_tool_pool(available_tools, user_role)
        return pool

    # ------------------------------------------------------------------
    # Tool Pool
    # ------------------------------------------------------------------

    def _get_tool_pool(
        self,
        available_tools: Optional[List[str]],
        user_role: str,
    ) -> List[ToolRecommendation]:
        """Build initial tool pool from registry or provided list."""
        try:
            from app.engine.tools.registry import get_tool_registry
            registry = get_tool_registry()
            # Sprint 195: Fix — registry has no _initialized attribute
            if not getattr(registry, '_tools', None):
                return []
        except ImportError:
            return []

        pool = []
        for name, info in registry._tools.items():
            # Filter by available_tools if provided
            if available_tools is not None and name not in available_tools:
                continue

            # Filter by role
            if user_role and info.roles and user_role not in info.roles:
                continue

            pool.append(ToolRecommendation(
                tool_name=name,
                confidence=1.0,
                reason="available",
                score=0.5,  # Neutral score
            ))

        return pool

    # ------------------------------------------------------------------
    # Step 1: Category Filter
    # ------------------------------------------------------------------

    def _step1_category_filter(
        self,
        pool: List[ToolRecommendation],
        query: str,
        intent: Optional[str],
    ) -> List[ToolRecommendation]:
        """Filter tools by category based on intent and query keywords."""
        relevant_categories = set()

        # From intent (supervisor signal)
        if intent and intent in _INTENT_TO_CATEGORIES:
            relevant_categories.update(_INTENT_TO_CATEGORIES[intent])

        # From query keywords
        query_lower = query.lower()
        for keywords, category in _KEYWORD_CATEGORIES:
            if any(kw in query_lower for kw in keywords):
                relevant_categories.add(category)

        # If no categories detected, return all (don't filter)
        if not relevant_categories:
            return pool

        # Filter + boost
        try:
            from app.engine.tools.registry import get_tool_registry
            registry = get_tool_registry()
            from app.engine.skills.capability_registry import get_capability_registry
            capability_registry = get_capability_registry()
        except ImportError:
            return pool

        filtered = []
        for rec in pool:
            info = registry._tools.get(rec.tool_name)
            if info is None:
                continue

            category_val = info.category.value if info.category else None
            if category_val is None:
                category_val = capability_registry.get_selector_category(rec.tool_name)

            if category_val in relevant_categories:
                rec.confidence = min(rec.confidence + 0.2, 1.0)
                rec.score += 0.3
                rec.reason = f"category:{category_val}"
                filtered.append(rec)
            elif rec.tool_name in CORE_TOOLS:
                # Core tools always pass
                rec.reason = "core_tool"
                filtered.append(rec)

        return filtered if filtered else pool  # Fallback to full pool if nothing matched

    # ------------------------------------------------------------------
    # Step 2: Semantic Pre-Filter (keyword matching)
    # ------------------------------------------------------------------

    def _step2_semantic_filter(
        self,
        pool: List[ToolRecommendation],
        query: str,
        max_candidates: int = 20,
    ) -> List[ToolRecommendation]:
        """Score tools by keyword overlap with query."""
        if not query or not query.strip():
            return pool

        try:
            from app.engine.tools.registry import get_tool_registry
            registry = get_tool_registry()
            from app.engine.skills.capability_registry import get_capability_registry
            capability_registry = get_capability_registry()
        except ImportError:
            return pool

        query_words = set(query.lower().split())

        scored = []
        for rec in pool:
            info = registry._tools.get(rec.tool_name)
            if info is None:
                scored.append(rec)
                continue

            # Build searchable text from tool description
            searchable = " ".join(
                part for part in (
                    info.name,
                    info.description,
                    capability_registry.searchable_text(rec.tool_name),
                ) if part
            ).lower()
            searchable_words = set(searchable.split())

            # Compute Jaccard-like overlap
            overlap = len(query_words & searchable_words)
            total = len(query_words | searchable_words) or 1
            similarity = overlap / total

            rec.score += similarity * 0.3  # Weight: 30% for semantic
            if similarity > 0:
                rec.reason = f"{rec.reason}+semantic({similarity:.2f})"

            scored.append(rec)

        # Sort by score descending
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:max_candidates]

    # ------------------------------------------------------------------
    # Step 4: Metrics Reranking
    # ------------------------------------------------------------------

    def _step4_metrics_rerank(
        self,
        pool: List[ToolRecommendation],
        *,
        query: str = "",
        intent: Optional[str] = None,
    ) -> List[ToolRecommendation]:
        """Rerank tools using handbook competence/cost signals."""
        try:
            from app.engine.skills.skill_handbook import get_skill_handbook
            from app.engine.skills.skill_metrics import get_skill_metrics_tracker
            handbook = get_skill_handbook()
            tracker = get_skill_metrics_tracker()
        except ImportError:
            return pool

        handbook_suggestions: dict[str, int] = {}
        if query or intent:
            suggested_entries = handbook.suggest_for_query(
                query,
                intent=intent,
                max_entries=max(len(pool), 5),
            )
            handbook_suggestions = {
                entry.tool_name: rank
                for rank, entry in enumerate(suggested_entries)
            }

        for rec in pool:
            skill_id = f"tool:{rec.tool_name}"
            metrics = tracker.get_metrics(skill_id)
            entry = handbook.get_tool_entry(rec.tool_name)
            competence = entry.competence_score if entry is not None else 0.0
            estimated_latency = int(entry.avg_latency_ms) if entry and entry.avg_latency_ms > 0 else 0
            estimated_cost = entry.avg_cost_usd if entry is not None else 0.0
            total_invocations = 0
            if metrics is not None:
                try:
                    total_invocations = int(getattr(metrics, "total_invocations", 0))
                except Exception:
                    total_invocations = 0

            handbook_bonus = 0.0
            if rec.tool_name in handbook_suggestions:
                rank = handbook_suggestions[rec.tool_name]
                handbook_bonus = max(0.0, 0.18 - (rank * 0.03))
            if metrics is None or total_invocations == 0:
                # No data — neutral score, but still check mastery
                mastery = self._get_mastery_boost(rec.tool_name)
                if handbook_bonus > 0:
                    rec.score += handbook_bonus
                    rec.reason = f"{rec.reason}+handbook({handbook_bonus:.2f})"
                rec.estimated_latency_ms = estimated_latency or rec.estimated_latency_ms
                rec.estimated_cost_usd = estimated_cost or rec.estimated_cost_usd
                if mastery > 0:
                    rec.score += mastery * 0.15  # Weight: 15% for mastery alone
                    rec.reason = f"{rec.reason}+mastery({mastery:.2f})"
                continue

            # Composite metric score
            success_factor = (metrics.success_rate * 0.7) + (competence * 0.3)
            # Latency factor: lower is better, normalize to 0-1 range
            latency_factor = 1.0 / (1.0 + metrics.avg_latency_ms / 1000.0)
            # Volume factor: more invocations = more reliable signal
            volume_factor = min(math.sqrt(total_invocations) / 10.0, 1.0)
            # Sprint 195: Cost factor — cheaper tools score higher
            avg_cost = metrics.avg_cost_per_invocation
            cost_factor = 1.0 / (1.0 + avg_cost * 100.0)  # Normalize: $0.01 → 0.5

            metrics_score = (
                0.32 * success_factor
                + 0.08 * competence
                + 0.3 * latency_factor
                + 0.2 * volume_factor
                + 0.1 * cost_factor
            )

            # Sprint 205: Mastery boost — mastered skills get priority (Voyager pattern)
            mastery = self._get_mastery_boost(rec.tool_name)

            rec.score += metrics_score * 0.4  # Weight: 40% for metrics
            if handbook_bonus > 0:
                rec.score += handbook_bonus
            if mastery > 0:
                rec.score += mastery * 0.15  # Weight: 15% for mastery
                rec.reason = (
                    f"{rec.reason}+metrics({metrics_score:.2f})"
                    f"+competence({competence:.2f})"
                    f"{f'+handbook({handbook_bonus:.2f})' if handbook_bonus > 0 else ''}"
                    f"+mastery({mastery:.2f})"
                )
            else:
                rec.reason = (
                    f"{rec.reason}+metrics({metrics_score:.2f})"
                    f"+competence({competence:.2f})"
                    f"{f'+handbook({handbook_bonus:.2f})' if handbook_bonus > 0 else ''}"
                )
            rec.estimated_latency_ms = estimated_latency or int(metrics.avg_latency_ms)
            rec.estimated_cost_usd = metrics.cost_estimate_usd or estimated_cost

        # Re-sort by final score
        pool.sort(key=lambda r: r.score, reverse=True)
        return pool

    @staticmethod
    def _get_mastery_boost(tool_name: str) -> float:
        """Get mastery score from Skill↔Tool bridge (Sprint 205).

        Returns 0.0 if bridge disabled or no mastery data.
        """
        try:
            from app.engine.skills.skill_tool_bridge import get_mastery_score
            return get_mastery_score(tool_name)
        except Exception:
            return 0.0

    # ------------------------------------------------------------------
    # Core tool guarantee
    # ------------------------------------------------------------------

    def _ensure_core_tools(
        self,
        pool: List[ToolRecommendation],
        available_tools: Optional[List[str]],
        user_role: str,
    ) -> List[ToolRecommendation]:
        """Ensure core tools are always present in the result."""
        existing_names = {r.tool_name for r in pool}

        for core_name in CORE_TOOLS:
            if core_name in existing_names:
                continue

            # Check if available
            if available_tools is not None and core_name not in available_tools:
                continue

            pool.append(ToolRecommendation(
                tool_name=core_name,
                confidence=1.0,
                reason="core_tool",
                score=0.0,  # Low score but always included
            ))

        return pool

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def detect_intent_from_query(self, query: str) -> Optional[str]:
        """
        Lightweight intent detection from query keywords.

        This is a fallback when supervisor intent is not available.
        Returns intent string or None.
        """
        if not query:
            return None

        query_lower = query.lower()

        # Product search signals
        product_kws = ["mua", "bán", "giá", "sản phẩm", "so sánh giá",
                        "shopee", "lazada", "tiktok", "marketplace",
                        "buy", "sell", "price", "product", "shop"]
        if any(kw in query_lower for kw in product_kws):
            return "product_search"

        # Web search signals
        web_kws = ["tin tức", "news", "thời sự", "mới nhất",
                    "website", "search", "google"]
        if any(kw in query_lower for kw in web_kws):
            return "web_search"

        # Learning signals
        learn_kws = ["học", "bài giảng", "quiz", "ôn tập", "kiểm tra",
                      "learn", "lesson", "exam", "test"]
        if any(kw in query_lower for kw in learn_kws):
            return "learning"

        # Memory signals
        mem_kws = ["nhớ", "remember", "quên", "forget", "ghi nhớ"]
        if any(kw in query_lower for kw in mem_kws):
            return "personal"

        return None

    def get_tool_names(
        self,
        recommendations: List[ToolRecommendation],
    ) -> List[str]:
        """Extract tool names from recommendations."""
        return [r.tool_name for r in recommendations]

    def reset(self) -> None:
        """Reset selector state (for testing)."""
        pass  # Currently stateless
