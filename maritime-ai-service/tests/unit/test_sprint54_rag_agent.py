"""
Tests for Sprint 54: RAGAgent coverage.

Tests RAG agent components:
- RAGResponse dataclass (__post_init__, has_citations, has_evidence_images, has_entity_context)
- EvidenceImage dataclass
- MaritimeDocumentParser (parse_regulation, serialize_to_document)
- RAGAgent init, _init_llm paths, query paths, generate_from_documents
- Singleton pattern (get_rag_agent, is_rag_agent_initialized, reset_rag_agent)
- get_knowledge_repository singleton
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.engine.agentic_rag.rag_agent import (
    RAGResponse,
    EvidenceImage,
    RAGAgent,
    MaritimeDocumentParser,
    get_rag_agent,
    is_rag_agent_initialized,
    reset_rag_agent,
    get_knowledge_repository,
)
from app.models.knowledge_graph import (
    Citation,
    KnowledgeNode,
    NodeType,
    RelationType,
)


# ============================================================================
# Helpers
# ============================================================================


def _make_rag_agent(**overrides):
    """Create RAGAgent with all deps mocked."""
    defaults = dict(
        knowledge_graph=MagicMock(),
        hybrid_search_service=MagicMock(),
        graph_rag_service=MagicMock(),
    )
    defaults.update(overrides)
    with patch("app.engine.agentic_rag.rag_agent.PromptLoader"):
        with patch("app.engine.agentic_rag.rag_agent.get_llm_moderate", return_value=MagicMock()):
            agent = RAGAgent(**defaults)
    return agent


def _make_citation(**overrides):
    """Create a Citation with defaults."""
    defaults = dict(
        node_id="node1",
        title="SOLAS Chapter III",
        source="SOLAS Convention",
        relevance_score=0.9,
    )
    defaults.update(overrides)
    return Citation(**defaults)


# ============================================================================
# EvidenceImage
# ============================================================================


class TestEvidenceImage:
    """Test EvidenceImage dataclass."""

    def test_creation(self):
        img = EvidenceImage(url="https://example.com/img.png", page_number=5, document_id="doc1")
        assert img.url == "https://example.com/img.png"
        assert img.page_number == 5
        assert img.document_id == "doc1"

    def test_default_document_id(self):
        img = EvidenceImage(url="https://example.com/img.png", page_number=1)
        assert img.document_id == ""


# ============================================================================
# RAGResponse
# ============================================================================


class TestRAGResponse:
    """Test RAGResponse dataclass."""

    def test_defaults(self):
        resp = RAGResponse(content="Answer", citations=[])
        assert resp.is_fallback is False
        assert resp.disclaimer is None
        assert resp.evidence_images == []
        assert resp.entity_context is None
        assert resp.related_entities == []
        assert resp.native_thinking is None

    def test_post_init_none_defaults(self):
        resp = RAGResponse(content="A", citations=[], evidence_images=None, related_entities=None)
        assert resp.evidence_images == []
        assert resp.related_entities == []

    def test_has_citations_true(self):
        resp = RAGResponse(content="A", citations=[_make_citation()])
        assert resp.has_citations() is True

    def test_has_citations_false(self):
        resp = RAGResponse(content="A", citations=[])
        assert resp.has_citations() is False

    def test_has_evidence_images_true(self):
        img = EvidenceImage(url="https://x.com/img.png", page_number=1)
        resp = RAGResponse(content="A", citations=[], evidence_images=[img])
        assert resp.has_evidence_images() is True

    def test_has_evidence_images_false(self):
        resp = RAGResponse(content="A", citations=[])
        assert resp.has_evidence_images() is False

    def test_has_entity_context_true(self):
        resp = RAGResponse(content="A", citations=[], entity_context="Some context")
        assert resp.has_entity_context() is True

    def test_has_entity_context_false(self):
        resp = RAGResponse(content="A", citations=[], entity_context="")
        assert resp.has_entity_context() is False

    def test_has_entity_context_none(self):
        resp = RAGResponse(content="A", citations=[], entity_context=None)
        assert resp.has_entity_context() is False


# ============================================================================
# MaritimeDocumentParser
# ============================================================================


class TestMaritimeDocumentParser:
    """Test document parser."""

    def test_parse_regulation(self):
        node = MaritimeDocumentParser.parse_regulation(
            code="SOLAS II-2/10",
            title="Fire Safety",
            content="Regulation about fire safety.",
            source="SOLAS Convention"
        )
        assert isinstance(node, KnowledgeNode)
        assert node.id == "reg_solas ii_2_10"  # space preserved from "SOLAS II-2/10"
        assert node.title == "Fire Safety"
        assert node.content == "Regulation about fire safety."
        assert node.source == "SOLAS Convention"
        assert node.metadata["code"] == "SOLAS II-2/10"
        assert node.node_type == NodeType.REGULATION

    def test_serialize_to_document(self):
        node = KnowledgeNode(
            id="reg_test",
            node_type=NodeType.REGULATION,
            title="Test Reg",
            content="Test content",
            source="Test Source",
            metadata={"code": "TEST-001"}
        )
        result = MaritimeDocumentParser.serialize_to_document(node)
        assert "Code: TEST-001" in result
        assert "Title: Test Reg" in result
        assert "Content: Test content" in result
        assert "Source: Test Source" in result

    def test_serialize_no_code(self):
        node = KnowledgeNode(
            id="test",
            node_type=NodeType.REGULATION,
            title="No Code",
            content="Content",
            source="",
            metadata={}
        )
        result = MaritimeDocumentParser.serialize_to_document(node)
        assert "Code:" not in result
        assert "Source:" not in result
        assert "Title: No Code" in result


# ============================================================================
# RAGAgent Init
# ============================================================================


class TestRAGAgentInit:
    """Test RAGAgent initialization."""

    def test_with_all_deps(self):
        agent = _make_rag_agent()
        assert agent._kg is not None
        assert agent._hybrid_search is not None
        assert agent._graph_rag is not None

    def test_graph_rag_none(self):
        agent = _make_rag_agent(graph_rag_service=None)
        # Will try lazy import, might be None
        assert True  # No error

    def test_init_llm_no_keys(self):
        """When no API keys, LLM should be None."""
        mock_kg = MagicMock()
        mock_hs = MagicMock()
        mock_gr = MagicMock()

        with patch("app.engine.agentic_rag.rag_agent.PromptLoader"):
            with patch("app.engine.agentic_rag.rag_agent.settings") as mock_settings:
                mock_settings.google_api_key = ""
                mock_settings.openai_api_key = ""
                mock_settings.llm_provider = "google"
                with patch("app.engine.agentic_rag.rag_agent.get_llm_moderate", side_effect=Exception("No key")):
                    agent = RAGAgent(
                        knowledge_graph=mock_kg,
                        hybrid_search_service=mock_hs,
                        graph_rag_service=mock_gr
                    )
        assert agent._llm is None


# ============================================================================
# RAGAgent — Fallback / No Results Responses
# ============================================================================


class TestRAGAgentResponses:
    """Test helper response methods."""

    def test_create_fallback_response(self):
        agent = _make_rag_agent()
        resp = agent._create_fallback_response("What is SOLAS?")
        assert resp.is_fallback is True
        assert "What is SOLAS?" in resp.content
        assert resp.disclaimer is not None
        assert resp.citations == []

    def test_create_no_results_response(self):
        agent = _make_rag_agent()
        resp = agent._create_no_results_response("unknown topic")
        assert resp.is_fallback is False
        assert "unknown topic" in resp.content
        assert resp.citations == []

    @pytest.mark.asyncio
    async def test_expand_context_returns_unchanged(self):
        """_expand_context returns nodes unchanged (Neo4j disabled)."""
        agent = _make_rag_agent()
        nodes = [MagicMock(), MagicMock()]
        result = await agent._expand_context(nodes)
        assert result == nodes

    def test_is_available_delegates(self):
        agent = _make_rag_agent()
        agent._hybrid_search.is_available.return_value = True
        assert agent.is_available() is True

    def test_generate_response_uses_runtime_socket_llm(self):
        agent = _make_rag_agent()
        runtime_llm = MagicMock()
        node = MagicMock()
        node.title = "Rule 15"
        node.content = "Crossing"
        node.source = "COLREGs"

        with patch.object(agent, "_resolve_runtime_llm", return_value=runtime_llm), \
             patch("app.engine.agentic_rag.rag_agent.AnswerGenerator.generate_response", return_value=("ok", None)) as mock_generate:
            answer, thinking = agent._generate_response("What is Rule 15?", [node])

        assert answer == "ok"
        assert thinking is None
        assert mock_generate.call_args.kwargs["llm"] is runtime_llm

        agent._hybrid_search.is_available.return_value = False
        assert agent.is_available() is False


# ============================================================================
# RAGAgent — query
# ============================================================================


class TestRAGAgentQuery:
    """Test RAGAgent.query() method."""

    @pytest.mark.asyncio
    async def test_query_search_unavailable(self):
        agent = _make_rag_agent()
        agent._hybrid_search.is_available.return_value = False

        resp = await agent.query("What is SOLAS?")
        assert resp.is_fallback is True

    @pytest.mark.asyncio
    async def test_query_no_results(self):
        agent = _make_rag_agent()
        agent._hybrid_search.is_available.return_value = True
        agent._graph_rag.is_available.return_value = False
        agent._hybrid_search.search = AsyncMock(return_value=[])
        agent._kg.hybrid_search = AsyncMock(return_value=[])

        resp = await agent.query("nonexistent topic")
        assert "couldn't find" in resp.content

    @pytest.mark.asyncio
    async def test_query_with_hybrid_results(self):
        agent = _make_rag_agent()
        agent._hybrid_search.is_available.return_value = True
        agent._graph_rag.is_available.return_value = False

        # Create mock hybrid results
        mock_result = MagicMock()
        mock_result.node_id = "node1"
        mock_result.content = "SOLAS Chapter III content"
        mock_result.title = "SOLAS III"
        mock_result.score = 0.9
        mock_result.search_method = "hybrid"
        mock_result.document_id = "doc1"
        mock_result.page_number = 1
        mock_result.chunk_index = 0
        mock_result.metadata = {}
        agent._hybrid_search.search = AsyncMock(return_value=[mock_result])

        # Mock dependent methods
        mock_node = MagicMock(spec=KnowledgeNode)
        mock_node.content = "SOLAS content"
        mock_node.title = "SOLAS"
        mock_node.metadata = {}
        with patch.object(agent, "_hybrid_results_to_nodes", return_value=[mock_node]):
            with patch.object(agent, "_generate_hybrid_citations", return_value=[_make_citation()]):
                with patch.object(agent, "_generate_response", return_value=("Answer text", None)):
                    with patch.object(agent, "_collect_evidence_images", new_callable=AsyncMock, return_value=[]):
                        resp = await agent.query("What is SOLAS?")

        assert resp.content == "Answer text"
        assert resp.is_fallback is False
        assert len(resp.citations) == 1

    @pytest.mark.asyncio
    async def test_query_with_graph_rag(self):
        agent = _make_rag_agent()
        agent._hybrid_search.is_available.return_value = True
        agent._graph_rag.is_available.return_value = True

        # GraphRAG returns results
        mock_graph_result = MagicMock()
        mock_graph_result.related_entities = [{"id": "e1", "name": "SOLAS"}]
        mock_graph_result.related_regulations = ["SOLAS III"]
        agent._graph_rag.search_with_graph_context = AsyncMock(
            return_value=([mock_graph_result], "Entity context about SOLAS")
        )

        mock_hybrid_result = MagicMock()
        mock_hybrid_result.node_id = "n1"
        mock_hybrid_result.search_method = "graph_enhanced"
        with patch.object(agent, "_graph_to_hybrid_results", return_value=[mock_hybrid_result]):
            with patch.object(agent, "_hybrid_results_to_nodes", return_value=[MagicMock()]):
                with patch.object(agent, "_generate_hybrid_citations", return_value=[]):
                    with patch.object(agent, "_generate_response", return_value=("GraphRAG Answer", "thinking")):
                        with patch.object(agent, "_collect_evidence_images", new_callable=AsyncMock, return_value=[]):
                            resp = await agent.query("What is SOLAS?")

        assert resp.content == "GraphRAG Answer"
        assert resp.entity_context == "Entity context about SOLAS"
        assert resp.native_thinking == "thinking"

    @pytest.mark.asyncio
    async def test_query_graph_rag_fallback(self):
        """When GraphRAG fails, falls back to hybrid search."""
        agent = _make_rag_agent()
        agent._hybrid_search.is_available.return_value = True
        agent._graph_rag.is_available.return_value = True
        agent._graph_rag.search_with_graph_context = AsyncMock(
            side_effect=Exception("GraphRAG failed")
        )

        mock_result = MagicMock()
        mock_result.node_id = "n1"
        mock_result.search_method = "hybrid"
        agent._hybrid_search.search = AsyncMock(return_value=[mock_result])

        with patch.object(agent, "_hybrid_results_to_nodes", return_value=[MagicMock()]):
            with patch.object(agent, "_generate_hybrid_citations", return_value=[]):
                with patch.object(agent, "_generate_response", return_value=("Fallback answer", None)):
                    with patch.object(agent, "_collect_evidence_images", new_callable=AsyncMock, return_value=[]):
                        resp = await agent.query("What is SOLAS?")

        assert resp.content == "Fallback answer"
        assert resp.entity_context == ""

    @pytest.mark.asyncio
    async def test_query_legacy_neo4j_fallback(self):
        """When hybrid returns nothing, falls back to legacy Neo4j."""
        agent = _make_rag_agent()
        agent._hybrid_search.is_available.return_value = True
        agent._graph_rag.is_available.return_value = False
        agent._hybrid_search.search = AsyncMock(return_value=[])

        mock_node = MagicMock(spec=KnowledgeNode)
        mock_node.content = "Legacy content"
        agent._kg.hybrid_search = AsyncMock(return_value=[mock_node])
        agent._kg.get_citations = AsyncMock(return_value=[_make_citation()])

        with patch.object(agent, "_generate_response", return_value=("Legacy answer", None)):
            resp = await agent.query("What is SOLAS?")

        assert resp.content == "Legacy answer"
        assert resp.is_fallback is False


# ============================================================================
# RAGAgent — generate_from_documents
# ============================================================================


class TestGenerateFromDocuments:
    """Test RAGAgent.generate_from_documents()."""

    @pytest.mark.asyncio
    async def test_empty_documents(self):
        agent = _make_rag_agent()
        resp = await agent.generate_from_documents("Question", [])
        assert resp.is_fallback is True
        assert resp.citations == []

    @pytest.mark.asyncio
    async def test_with_documents(self):
        agent = _make_rag_agent()
        docs = [
            {"content": "SOLAS content", "title": "SOLAS", "source": "IMO", "document_id": "d1"}
        ]

        with patch.object(agent, "_documents_to_nodes", return_value=[MagicMock()]):
            with patch.object(agent, "_generate_response", return_value=("Generated", "thinking")):
                with patch.object(agent, "_documents_to_citations", return_value=[_make_citation()]):
                    resp = await agent.generate_from_documents("What is SOLAS?", docs)

        assert resp.content == "Generated"
        assert resp.native_thinking == "thinking"
        assert resp.is_fallback is False
        assert len(resp.citations) == 1


# ============================================================================
# RAGAgent — query_streaming
# ============================================================================


class TestQueryStreaming:
    """Test RAGAgent.query_streaming() async generator."""

    @pytest.mark.asyncio
    async def test_search_unavailable(self):
        agent = _make_rag_agent()
        agent._hybrid_search.is_available.return_value = False

        events = []
        async for event in agent.query_streaming("Test?"):
            events.append(event)

        # First event is thinking, then error
        assert any(e["type"] == "error" for e in events)

    @pytest.mark.asyncio
    async def test_no_results(self):
        agent = _make_rag_agent()
        agent._hybrid_search.is_available.return_value = True
        agent._graph_rag.is_available.return_value = False
        agent._hybrid_search.search = AsyncMock(return_value=[])

        events = []
        async for event in agent.query_streaming("Test?"):
            events.append(event)

        assert any(e["type"] == "answer" for e in events)
        assert any(e["type"] == "done" for e in events)


# ============================================================================
# Singleton Pattern
# ============================================================================


class TestSingleton:
    """Test RAGAgent singleton pattern."""

    def setup_method(self):
        """Reset singleton before each test."""
        import app.engine.agentic_rag.rag_agent as mod
        mod._rag_agent_instance = None

    def teardown_method(self):
        """Reset after test."""
        import app.engine.agentic_rag.rag_agent as mod
        mod._rag_agent_instance = None

    def test_is_rag_agent_initialized_false(self):
        assert is_rag_agent_initialized() is False

    def test_reset_rag_agent(self):
        import app.engine.agentic_rag.rag_agent as mod
        mod._rag_agent_instance = MagicMock()
        assert is_rag_agent_initialized() is True
        reset_rag_agent()
        assert is_rag_agent_initialized() is False

    def test_get_rag_agent_creates_instance(self):
        with patch("app.engine.agentic_rag.rag_agent.RAGAgent") as MockRAG:
            mock_instance = MagicMock()
            MockRAG.return_value = mock_instance
            result = get_rag_agent()
            assert result is mock_instance

    def test_get_rag_agent_returns_same_instance(self):
        with patch("app.engine.agentic_rag.rag_agent.RAGAgent") as MockRAG:
            mock_instance = MagicMock()
            MockRAG.return_value = mock_instance
            first = get_rag_agent()
            second = get_rag_agent()
            assert first is second
            MockRAG.assert_called_once()


# ============================================================================
# get_knowledge_repository
# ============================================================================


class TestGetKnowledgeRepository:
    """Test knowledge repository singleton."""

    def setup_method(self):
        import app.engine.agentic_rag.rag_agent as mod
        mod._knowledge_repo = None

    def teardown_method(self):
        import app.engine.agentic_rag.rag_agent as mod
        mod._knowledge_repo = None

    def test_creates_instance(self):
        with patch("app.engine.agentic_rag.rag_agent.Neo4jKnowledgeRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.is_available.return_value = False
            MockRepo.return_value = mock_repo
            result = get_knowledge_repository()
            assert result is mock_repo

    def test_returns_cached_instance(self):
        with patch("app.engine.agentic_rag.rag_agent.Neo4jKnowledgeRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.is_available.return_value = True
            MockRepo.return_value = mock_repo
            first = get_knowledge_repository()
            second = get_knowledge_repository()
            assert first is second
            MockRepo.assert_called_once()
