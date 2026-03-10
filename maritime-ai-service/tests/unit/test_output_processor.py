"""
Tests for OutputProcessor — Response formatting and validation.

Sprint 22: Core Pipeline Testing.

Verifies:
- validate_and_format() with/without guardrails, thinking trace, metadata
- merge_same_page_sources() grouping and deduplication
- format_sources() end-to-end merge + Source creation + snippet truncation
- create_blocked_response() with/without custom refusal
- create_clarification_response() basic construction
- extract_thinking_from_response() delegation to ThinkingPostProcessor
- Singleton lifecycle
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.services.output_processor import (
    OutputProcessor,
    ProcessingResult,
    extract_thinking_from_response,
    get_output_processor,
    init_output_processor,
)
from app.models.knowledge_graph import Citation
from app.models.schemas import InternalChatResponse, Source, UserRole, AgentType


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_guardrails():
    """Mock Guardrails."""
    guardrails = MagicMock()
    guardrails.validate_output = AsyncMock()
    guardrails.get_refusal_message.return_value = "Nội dung không phù hợp."
    return guardrails


@pytest.fixture
def mock_response_builder():
    """Mock ChatResponseBuilder."""
    builder = MagicMock()
    builder.merge_same_page_sources = MagicMock(side_effect=lambda x: x)
    return builder


@pytest.fixture
def session_id():
    return uuid4()


@pytest.fixture
def sample_result():
    """Sample ProcessingResult."""
    return ProcessingResult(
        message="COLREGs Rule 13 quy định về tàu vượt.",
        agent_type=AgentType.RAG,
        sources=[],
        metadata={"confidence": 0.85},
    )


@pytest.fixture
def processor(mock_guardrails, mock_response_builder):
    """OutputProcessor with mocked dependencies."""
    return OutputProcessor(
        guardrails=mock_guardrails,
        response_builder=mock_response_builder,
    )


# =============================================================================
# validate_and_format()
# =============================================================================

class TestValidateAndFormat:

    @pytest.mark.asyncio
    async def test_basic_formatting(self, processor, mock_guardrails, sample_result, session_id):
        """Basic formatting returns InternalChatResponse."""
        output_result = MagicMock()
        output_result.status = "PASS"
        mock_guardrails.validate_output.return_value = output_result

        response = await processor.validate_and_format(sample_result, session_id)

        assert isinstance(response, InternalChatResponse)
        assert response.message == "COLREGs Rule 13 quy định về tàu vượt."
        assert response.agent_type == AgentType.RAG

    @pytest.mark.asyncio
    async def test_guardrails_flagged(self, processor, mock_guardrails, sample_result, session_id):
        """Flagged output appends safety note."""
        from enum import Enum

        class ValidationStatus(str, Enum):
            FLAGGED = "FLAGGED"

        output_result = MagicMock()
        output_result.status = ValidationStatus.FLAGGED
        mock_guardrails.validate_output.return_value = output_result

        # ValidationStatus is lazy-imported inside validate_and_format body
        with patch("app.engine.guardrails.ValidationStatus", ValidationStatus):
            response = await processor.validate_and_format(sample_result, session_id)

        assert "_Note: Please verify" in response.message

    @pytest.mark.asyncio
    async def test_no_guardrails(self, sample_result, session_id):
        """Without guardrails, message passes through unchanged."""
        processor = OutputProcessor(guardrails=None)

        response = await processor.validate_and_format(sample_result, session_id)

        assert response.message == sample_result.message

    @pytest.mark.asyncio
    async def test_includes_thinking(self, session_id):
        """Thinking trace included in metadata."""
        processor = OutputProcessor(guardrails=None)
        result = ProcessingResult(
            message="Answer",
            agent_type=AgentType.RAG,
            thinking="I analyzed the COLREGs...",
        )

        response = await processor.validate_and_format(result, session_id)

        assert response.metadata["thinking"] == "I analyzed the COLREGs..."

    @pytest.mark.asyncio
    async def test_metadata_merged(self, sample_result, session_id):
        """Result metadata is merged into response metadata."""
        processor = OutputProcessor(guardrails=None)

        response = await processor.validate_and_format(
            sample_result, session_id, user_name="Minh", user_role=UserRole.STUDENT
        )

        assert response.metadata["user_name"] == "Minh"
        assert response.metadata["user_role"] == "student"
        assert response.metadata["confidence"] == 0.85
        assert response.metadata["session_id"] == str(session_id)


# =============================================================================
# merge_same_page_sources()
# =============================================================================

class TestMergeSamePageSources:

    def test_empty_list(self):
        """Empty sources returns empty list."""
        processor = OutputProcessor()
        assert processor.merge_same_page_sources([]) == []

    def test_no_duplicates(self):
        """Different pages not merged."""
        processor = OutputProcessor()
        sources = [
            {"document_id": "doc1", "page_number": 1, "node_id": "a"},
            {"document_id": "doc1", "page_number": 2, "node_id": "b"},
        ]

        result = processor.merge_same_page_sources(sources)

        assert len(result) == 2

    def test_same_page_merged(self):
        """Same document + page merged, bounding boxes combined."""
        processor = OutputProcessor()
        sources = [
            {"document_id": "doc1", "page_number": 1, "bounding_boxes": [{"x": 0, "y": 0}]},
            {"document_id": "doc1", "page_number": 1, "bounding_boxes": [{"x": 10, "y": 10}]},
        ]

        result = processor.merge_same_page_sources(sources)

        assert len(result) == 1
        assert len(result[0]["bounding_boxes"]) == 2

    def test_no_doc_id_not_merged(self):
        """Sources without document_id added individually."""
        processor = OutputProcessor()
        sources = [
            {"node_id": "a", "title": "Source A"},
            {"node_id": "b", "title": "Source B"},
        ]

        result = processor.merge_same_page_sources(sources)

        assert len(result) == 2

    def test_delegates_to_response_builder(self, mock_response_builder):
        """Uses response_builder when available."""
        processor = OutputProcessor(response_builder=mock_response_builder)
        sources = [
            Citation(
                node_id="n1",
                title="Doc 1",
                source="IMO",
                relevance_score=0.8,
                document_id="doc1",
                page_number=1,
            )
        ]

        processor.merge_same_page_sources(sources)

        mock_response_builder.merge_same_page_sources.assert_called_once_with(
            [
                {
                    "node_id": "n1",
                    "title": "Doc 1",
                    "source": "IMO",
                    "relevance_score": 0.8,
                    "document_id": "doc1",
                    "page_number": 1,
                }
            ]
        )


# =============================================================================
# format_sources()
# =============================================================================

class TestFormatSources:

    def test_empty_list(self):
        """Empty raw sources returns empty list."""
        processor = OutputProcessor()
        assert processor.format_sources([]) == []

    def test_creates_source_objects(self):
        """Raw dicts converted to Source objects."""
        processor = OutputProcessor()
        raw = [
            {
                "node_id": "n1",
                "title": "COLREGs Rule 13",
                "content": "Quy tắc về tàu vượt",
                "page_number": 5,
                "document_id": "doc-1",
            }
        ]

        result = processor.format_sources(raw)

        assert len(result) == 1
        assert isinstance(result[0], Source)
        assert result[0].node_id == "n1"
        assert result[0].title == "COLREGs Rule 13"
        assert result[0].page_number == 5

    def test_snippet_truncation(self):
        """Content snippet truncated to MAX_CONTENT_SNIPPET_LENGTH."""
        from app.core.constants import MAX_CONTENT_SNIPPET_LENGTH

        processor = OutputProcessor()
        raw = [
            {
                "node_id": "n1",
                "title": "Long",
                "content": "A" * 500,
            }
        ]

        result = processor.format_sources(raw)

        assert len(result[0].content_snippet) == MAX_CONTENT_SNIPPET_LENGTH

    def test_merges_before_converting(self):
        """Same-page sources merged before Source creation."""
        processor = OutputProcessor()
        raw = [
            {"document_id": "doc1", "page_number": 1, "node_id": "a", "title": "A", "content": "aaa", "bounding_boxes": [{"x": 0}]},
            {"document_id": "doc1", "page_number": 1, "node_id": "b", "title": "B", "content": "bbb", "bounding_boxes": [{"x": 1}]},
        ]

        result = processor.format_sources(raw)

        # Should be merged into 1 source
        assert len(result) == 1
        assert len(result[0].bounding_boxes) == 2

    def test_accepts_pydantic_citation_models(self):
        """Citation models from RAG are normalized before formatting."""
        processor = OutputProcessor()
        raw = [
            Citation(
                node_id="n1",
                title="COLREG Rule 13",
                source="IMO",
                relevance_score=0.95,
                page_number=7,
                document_id="doc-13",
            )
        ]

        result = processor.format_sources(raw)

        assert len(result) == 1
        assert result[0].node_id == "n1"
        assert result[0].title == "COLREG Rule 13"
        assert result[0].page_number == 7


# =============================================================================
# create_blocked_response()
# =============================================================================

class TestCreateBlockedResponse:

    def test_default_message(self):
        """Uses default refusal message when no guardrails."""
        processor = OutputProcessor(guardrails=None)

        response = processor.create_blocked_response(["spam"])

        assert isinstance(response, InternalChatResponse)
        assert "không thể xử lý" in response.message
        assert response.metadata["blocked"] is True
        assert response.metadata["issues"] == ["spam"]

    def test_custom_refusal_message(self):
        """Uses custom refusal message."""
        processor = OutputProcessor(guardrails=None)

        response = processor.create_blocked_response(["spam"], refusal_message="Custom refusal")

        assert response.message == "Custom refusal"

    def test_guardrails_refusal(self, mock_guardrails):
        """Uses guardrails refusal message when available."""
        processor = OutputProcessor(guardrails=mock_guardrails)

        response = processor.create_blocked_response(["policy violation"])

        assert response.message == "Nội dung không phù hợp."


# =============================================================================
# create_clarification_response()
# =============================================================================

class TestCreateClarificationResponse:

    def test_basic_construction(self):
        """Creates clarification response with metadata."""
        processor = OutputProcessor()

        response = processor.create_clarification_response("Bạn có thể nói rõ hơn?")

        assert isinstance(response, InternalChatResponse)
        assert response.message == "Bạn có thể nói rõ hơn?"
        assert response.metadata["requires_clarification"] is True


# =============================================================================
# extract_thinking_from_response()
# =============================================================================

class TestExtractThinking:

    def test_delegates_to_processor(self):
        """Delegates to ThinkingPostProcessor."""
        mock_processor = MagicMock()
        mock_processor.process.return_value = ("clean text", "thinking trace")

        # get_thinking_processor is lazy-imported inside the function body
        with patch(
            "app.services.thinking_post_processor.get_thinking_processor",
            return_value=mock_processor,
        ):
            text, thinking = extract_thinking_from_response("raw content")

        assert text == "clean text"
        assert thinking == "thinking trace"
        mock_processor.process.assert_called_once_with("raw content")


# =============================================================================
# Singleton
# =============================================================================

class TestSingleton:

    def test_init_output_processor(self, mock_guardrails):
        """init_output_processor sets the singleton."""
        import app.services.output_processor as mod
        old = mod._output_processor

        processor = init_output_processor(guardrails=mock_guardrails)

        assert processor._guardrails is mock_guardrails
        assert mod._output_processor is processor

        mod._output_processor = old  # Restore

    def test_get_output_processor_singleton(self):
        """get_output_processor creates a singleton."""
        import app.services.output_processor as mod
        mod._output_processor = None

        p1 = get_output_processor()
        p2 = get_output_processor()

        assert p1 is p2
        assert isinstance(p1, OutputProcessor)

        mod._output_processor = None  # Clean up
