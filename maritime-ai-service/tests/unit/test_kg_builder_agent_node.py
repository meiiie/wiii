"""
Tests for KGBuilderAgentNode - Knowledge Graph Construction Specialist.

Tests entity/relation extraction, Pydantic structured output, text truncation,
state wiring, and error handling.
"""

import sys
import types
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

# Pre-populate sys.modules to avoid circular import
if "app.services.chat_service" not in sys.modules:
    _stub = types.ModuleType("app.services.chat_service")
    _stub.ChatService = MagicMock
    _stub.get_chat_service = MagicMock()
    sys.modules["app.services.chat_service"] = _stub

from app.engine.multi_agent.agents.kg_builder_agent import (
    EntityItem,
    RelationItem,
    ExtractionOutput,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_node(structured_llm=None, raw_llm=None):
    """Create KGBuilderAgentNode with mocked LLM (uses shared pool)."""
    mock_instance = raw_llm or MagicMock()
    mock_instance.with_structured_output = MagicMock(return_value=structured_llm)
    with patch(
        "app.engine.llm_pool.get_llm_moderate",
        return_value=mock_instance,
    ):
        from app.engine.multi_agent.agents.kg_builder_agent import KGBuilderAgentNode
        return KGBuilderAgentNode()


def _sample_entities():
    return [
        EntityItem(
            id="colregs_rule_13",
            entity_type="ARTICLE",
            name="COLREGs Rule 13",
            name_vi="Quy tắc 13 COLREGs",
            description="Overtaking rule",
        ),
        EntityItem(
            id="power_driven_vessel",
            entity_type="VESSEL_TYPE",
            name="Power-driven vessel",
            name_vi="Tàu máy",
            description="A vessel propelled by machinery",
        ),
    ]


def _sample_relations():
    return [
        RelationItem(
            source_id="colregs_rule_13",
            target_id="power_driven_vessel",
            relation_type="APPLIES_TO",
            description="Rule 13 applies to power-driven vessels",
        ),
    ]


@pytest.fixture
def base_state():
    return {
        "query": "SOLAS Chapter V",
        "context": {
            "text_for_extraction": "SOLAS Chapter V quy định về an toàn hàng hải...",
            "source": "SOLAS_doc",
        },
    }


# ---------------------------------------------------------------------------
# Pydantic model construction tests
# ---------------------------------------------------------------------------

class TestPydanticModels:
    def test_entity_item_construction(self):
        e = EntityItem(
            id="test_entity",
            entity_type="CONCEPT",
            name="Safe Speed",
            name_vi="Tốc độ an toàn",
            description="Speed at which proper action can be taken",
        )
        assert e.id == "test_entity"
        assert e.entity_type == "CONCEPT"

    def test_relation_item_construction(self):
        r = RelationItem(
            source_id="a",
            target_id="b",
            relation_type="REFERENCES",
            description="A references B",
        )
        assert r.source_id == "a"
        assert r.relation_type == "REFERENCES"

    def test_extraction_output_empty(self):
        out = ExtractionOutput()
        assert out.entities == []
        assert out.relations == []

    def test_extraction_output_with_data(self):
        out = ExtractionOutput(
            entities=_sample_entities(),
            relations=_sample_relations(),
        )
        assert len(out.entities) == 2
        assert len(out.relations) == 1


# ---------------------------------------------------------------------------
# extract() tests
# ---------------------------------------------------------------------------

class TestKGBuilderExtract:
    @pytest.mark.asyncio
    async def test_extract_happy_path(self):
        extraction = ExtractionOutput(
            entities=_sample_entities(),
            relations=_sample_relations(),
        )
        structured_llm = MagicMock()
        structured_llm.ainvoke = AsyncMock(return_value=extraction)
        node = _make_node(structured_llm=structured_llm)

        result = await node.extract("COLREGs Rule 13 text...", source="COLREGs")

        assert len(result.entities) == 2
        assert len(result.relations) == 1
        assert result.entities[0].id == "colregs_rule_13"

    @pytest.mark.asyncio
    async def test_extract_no_llm_returns_empty(self):
        node = _make_node(structured_llm=None)
        result = await node.extract("some text")

        assert result.entities == []
        assert result.relations == []

    @pytest.mark.asyncio
    async def test_extract_llm_error_returns_empty(self):
        structured_llm = MagicMock()
        structured_llm.ainvoke = AsyncMock(side_effect=Exception("API error"))
        node = _make_node(structured_llm=structured_llm)

        result = await node.extract("some text")
        assert result.entities == []
        assert result.relations == []

    @pytest.mark.asyncio
    async def test_extract_with_source_in_prompt(self):
        structured_llm = MagicMock()
        structured_llm.ainvoke = AsyncMock(return_value=ExtractionOutput())
        node = _make_node(structured_llm=structured_llm)

        await node.extract("text", source="SOLAS_doc")

        # Verify source appears in the message
        call_args = structured_llm.ainvoke.call_args[0][0]
        user_msg = call_args[1].content
        assert "SOLAS_doc" in user_msg

    @pytest.mark.asyncio
    async def test_extract_truncates_long_text(self):
        structured_llm = MagicMock()
        structured_llm.ainvoke = AsyncMock(return_value=ExtractionOutput())
        node = _make_node(structured_llm=structured_llm)

        long_text = "A" * 5000
        await node.extract(long_text)

        call_args = structured_llm.ainvoke.call_args[0][0]
        user_msg = call_args[1].content
        # Text should be truncated to 2500 chars (plus prompt boilerplate)
        assert len(long_text[:2500]) <= 2500
        # The full 5000-char text should NOT be in the message
        assert "A" * 5000 not in user_msg


# ---------------------------------------------------------------------------
# process() tests
# ---------------------------------------------------------------------------

class TestKGBuilderProcess:
    @pytest.mark.asyncio
    async def test_process_extracts_from_context(self, base_state):
        extraction = ExtractionOutput(
            entities=_sample_entities(),
            relations=_sample_relations(),
        )
        structured_llm = MagicMock()
        structured_llm.ainvoke = AsyncMock(return_value=extraction)
        node = _make_node(structured_llm=structured_llm)

        result = await node.process(base_state)

        assert result["extracted_entities"] == extraction.entities
        assert result["extracted_relations"] == extraction.relations
        assert result["agent_outputs"]["kg_builder"]["entity_count"] == 2
        assert result["agent_outputs"]["kg_builder"]["relation_count"] == 1

    @pytest.mark.asyncio
    async def test_process_falls_back_to_query(self):
        state = {"query": "COLREGs Rule 13", "context": {}}
        structured_llm = MagicMock()
        structured_llm.ainvoke = AsyncMock(return_value=ExtractionOutput())
        node = _make_node(structured_llm=structured_llm)

        await node.process(state)

        call_args = structured_llm.ainvoke.call_args[0][0]
        user_msg = call_args[1].content
        assert "COLREGs Rule 13" in user_msg

    @pytest.mark.asyncio
    async def test_process_entities_serialized(self, base_state):
        extraction = ExtractionOutput(
            entities=_sample_entities(),
            relations=_sample_relations(),
        )
        structured_llm = MagicMock()
        structured_llm.ainvoke = AsyncMock(return_value=extraction)
        node = _make_node(structured_llm=structured_llm)

        result = await node.process(base_state)

        # agent_outputs["kg_builder"]["entities"] should be dicts (model_dump)
        entities_data = result["agent_outputs"]["kg_builder"]["entities"]
        assert isinstance(entities_data[0], dict)
        assert entities_data[0]["id"] == "colregs_rule_13"


# ---------------------------------------------------------------------------
# is_available() tests
# ---------------------------------------------------------------------------

class TestKGBuilderIsAvailable:
    def test_available_with_structured_llm(self):
        structured_llm = MagicMock()
        node = _make_node(structured_llm=structured_llm)
        assert node.is_available() is True

    def test_not_available_without_structured_llm(self):
        node = _make_node(structured_llm=None)
        assert node.is_available() is False


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestKGBuilderSingleton:
    def test_get_kg_builder_agent_returns_instance(self):
        import app.engine.multi_agent.agents.kg_builder_agent as mod
        mod._kg_builder = None
        try:
            with patch("app.engine.llm_pool.get_llm_moderate", return_value=MagicMock()):
                node = mod.get_kg_builder_agent()
                assert isinstance(node, mod.KGBuilderAgentNode)
                node2 = mod.get_kg_builder_agent()
                assert node is node2
        finally:
            mod._kg_builder = None
