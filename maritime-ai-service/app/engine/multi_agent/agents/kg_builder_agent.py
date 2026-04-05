"""
KG Builder Agent - multi-agent adapter for the shared KG builder service.

Keeps the historical multi-agent surface while delegating extraction logic to a
neutral engine service so GraphRAG does not depend on multi-agent agents.
"""

import logging
from typing import Optional

from app.engine.kg_builder_service import (
    EntityItem,
    ExtractionOutput,
    KGBuilderService,
    RelationItem,
)
from app.engine.multi_agent.state import AgentState
from app.engine.agents import KG_BUILDER_AGENT_CONFIG

logger = logging.getLogger(__name__)


class KGBuilderAgentNode(KGBuilderService):
    """
    KG Builder Agent - Knowledge Graph construction specialist.

    This adapter keeps the old agent interface (`process`) for graph use while
    the actual extraction implementation lives in `app.engine.kg_builder_service`.
    """

    def __init__(self):
        self._config = KG_BUILDER_AGENT_CONFIG
        super().__init__()
        logger.info("KGBuilderAgentNode initialized with config: %s", self._config.id)

    async def process(self, state: AgentState) -> AgentState:
        """
        Process state as KG Builder node.

        Used in multi-agent graph when extraction is needed.
        """
        query = state.get("query", "")
        context = state.get("context", {})

        text_to_extract = context.get("text_for_extraction", query)
        source = context.get("source", "user_query")

        result = await self.extract(text_to_extract, source)

        state["agent_outputs"] = state.get("agent_outputs", {})
        state["agent_outputs"]["kg_builder"] = {
            "entities": [e.model_dump() for e in result.entities],
            "relations": [r.model_dump() for r in result.relations],
            "entity_count": len(result.entities),
            "relation_count": len(result.relations),
        }
        state["extracted_entities"] = result.entities
        state["extracted_relations"] = result.relations

        logger.info("[KG_BUILDER] Extracted %d entities", len(result.entities))
        return state


_kg_builder: Optional[KGBuilderAgentNode] = None


def get_kg_builder_agent() -> KGBuilderAgentNode:
    """Get or create KGBuilderAgent singleton."""
    global _kg_builder
    if _kg_builder is None:
        _kg_builder = KGBuilderAgentNode()
    return _kg_builder
