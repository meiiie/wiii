"""
Semantic Tool Selector for Intelligent Pre-Filtering.

Sprint 138: AWS research shows embedding-based tool pre-filtering achieves
82.3% accuracy. Claude uses "Tool Search Tool" pattern.

Pre-computes embeddings for all tool descriptions at startup,
then selects the most relevant subset for each query.

Feature-gated: enable_tool_selection=False by default.
"""
import logging
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_selector_instance: Optional["ToolSelector"] = None


class ToolSelector:
    """
    Semantic tool pre-filter using embedding similarity.

    At initialization:
    - Compute embeddings for all tool descriptions
    - Cache in memory (tools don't change at runtime)

    Per query:
    - Embed query
    - Cosine similarity vs cached tool embeddings
    - Return top-k most relevant tools
    - Always include core tools (datetime, knowledge_search)
    """

    def __init__(self):
        self._tool_embeddings: Dict[str, List[float]] = {}
        self._tool_map: Dict[str, Callable] = {}
        self._initialized = False
        self._embeddings = None

    async def initialize(self, tools: List[Callable]) -> None:
        """
        Compute and cache embeddings for all tool descriptions.

        Args:
            tools: List of LangChain tool functions
        """
        if self._initialized:
            return

        try:
            from app.engine.gemini_embedding import GeminiOptimizedEmbeddings
            self._embeddings = GeminiOptimizedEmbeddings()
        except Exception as e:
            logger.warning("ToolSelector: embedding model unavailable: %s", e)
            return

        descriptions = []
        tool_names = []

        for tool in tools:
            name = tool.name if hasattr(tool, "name") else tool.__name__
            desc = tool.description if hasattr(tool, "description") else name
            self._tool_map[name] = tool
            tool_names.append(name)
            descriptions.append(f"{name}: {desc}")

        if not descriptions:
            logger.warning("ToolSelector: no tools to index")
            return

        try:
            embeddings = await self._embeddings.aembed_documents(descriptions)
            for name, emb in zip(tool_names, embeddings):
                if emb:
                    self._tool_embeddings[name] = emb

            self._initialized = True
            logger.info(
                "ToolSelector initialized: %d tools indexed",
                len(self._tool_embeddings),
            )
        except Exception as e:
            logger.error("ToolSelector initialization failed: %s", e)

    async def select_tools(
        self,
        query: str,
        available_tools: List[Callable],
        top_k: int = 5,
        core_tool_names: Optional[List[str]] = None,
    ) -> List[Callable]:
        """
        Select the most relevant tools for a query.

        Args:
            query: User query text
            available_tools: Full list of available tools
            top_k: Maximum tools to return
            core_tool_names: Tools always included regardless of score

        Returns:
            Subset of available_tools most relevant to query
        """
        from app.core.config import settings

        if not settings.enable_tool_selection:
            return available_tools

        if core_tool_names is None:
            core_tool_names = settings.tool_selection_core_tools

        # Ensure initialized with current tools
        if not self._initialized:
            await self.initialize(available_tools)

        if not self._initialized or not self._embeddings:
            logger.warning("ToolSelector not initialized, returning all tools")
            return available_tools

        try:
            # Embed query
            query_embedding = await self._embeddings.aembed_query(query)
            if not query_embedding:
                return available_tools

            # Calculate similarity for each tool
            scores: List[Tuple[str, float, Callable]] = []
            tool_name_map = {}

            for tool in available_tools:
                name = tool.name if hasattr(tool, "name") else tool.__name__
                tool_name_map[name] = tool

                if name in self._tool_embeddings:
                    sim = self._cosine_similarity(
                        query_embedding, self._tool_embeddings[name]
                    )
                    scores.append((name, sim, tool))
                else:
                    # Tool not indexed — give it a baseline score
                    scores.append((name, 0.0, tool))

            # Sort by similarity descending
            scores.sort(key=lambda x: x[1], reverse=True)

            # Build result: core tools first, then top-k by similarity
            selected = {}

            # Always include core tools
            for core_name in core_tool_names:
                if core_name in tool_name_map:
                    selected[core_name] = tool_name_map[core_name]

            # Add top-k by similarity (excluding already-selected core tools)
            for name, sim, tool in scores:
                if len(selected) >= top_k:
                    break
                if name not in selected:
                    selected[name] = tool

            logger.info(
                "ToolSelector: %d/%d tools selected for query (top scores: %s)",
                len(selected),
                len(available_tools),
                ", ".join(f"{n}={s:.2f}" for n, s, _ in scores[:3]),
            )

            return list(selected.values())

        except Exception as e:
            logger.error("ToolSelector.select_tools failed: %s", e)
            return available_tools

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if len(a) != len(b) or not a:
            return 0.0

        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot / (norm_a * norm_b)


def get_tool_selector() -> ToolSelector:
    """Get singleton ToolSelector instance."""
    global _selector_instance
    if _selector_instance is None:
        _selector_instance = ToolSelector()
    return _selector_instance
