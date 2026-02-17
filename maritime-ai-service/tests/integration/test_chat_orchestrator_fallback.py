"""
Test ChatOrchestrator fallback behavior.
Verifies graceful fallback when multi-agent graph is unavailable.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.models.schemas import ChatRequest, UserRole


@pytest.mark.asyncio
async def test_fallback_when_multi_agent_graph_none():
    """
    Verify graceful fallback to RAG when multi-agent graph is None.

    Before fix: raised RuntimeError
    After fix: falls back to RAGAgent
    """
    from app.services.chat_orchestrator import ChatOrchestrator

    # Mock RAG agent
    mock_rag = AsyncMock()
    mock_rag.query.return_value = MagicMock(
        answer="Fallback answer from RAG",
        citations=[{"title": "Test Source", "page": 1}]
    )

    # Mock other dependencies
    mock_session_manager = MagicMock()
    mock_session_manager.get_or_create_session.return_value = MagicMock(session_id="test-session-id")

    mock_input_processor = AsyncMock()
    mock_input_processor.validate.return_value = MagicMock(
        blocked=False,
        response=None
    )
    mock_input_processor.build_context.return_value = MagicMock(
        message="Test question",
        user_role=UserRole.STUDENT,
        user_name="Test User"
    )

    mock_output_processor = AsyncMock()
    mock_output_processor.format_response.return_value = MagicMock(
        answer="Test answer",
        sources=[]
    )

    # Create orchestrator WITHOUT multi-agent graph
    orchestrator = ChatOrchestrator(
        multi_agent_graph=None,
        rag_agent=mock_rag,
        input_processor=mock_input_processor,
        output_processor=mock_output_processor,
        session_manager=mock_session_manager,
        background_runner=MagicMock(),
    )

    # Create proper ChatRequest object
    request = ChatRequest(
        message="Test question",
        user_id="test-user",
        role=UserRole.STUDENT
    )

    # Should NOT raise, should use fallback
    result = await orchestrator.process(request)

    # Verify RAG was called as fallback
    mock_rag.query.assert_called_once()


@pytest.mark.asyncio
async def test_error_when_no_agents_available():
    """
    Verify proper error when both multi-agent graph and RAG agent are None.
    """
    from app.services.chat_orchestrator import ChatOrchestrator

    mock_session_manager = MagicMock()
    mock_session_manager.get_or_create_session.return_value = MagicMock(session_id="id")

    mock_input_processor = AsyncMock()
    mock_input_processor.validate.return_value = MagicMock(
        blocked=False,
        response=None
    )
    mock_input_processor.build_context.return_value = MagicMock(
        message="Test",
        user_role=UserRole.STUDENT
    )

    orchestrator = ChatOrchestrator(
        multi_agent_graph=None,
        rag_agent=None,  # Both None
        input_processor=mock_input_processor,
        output_processor=AsyncMock(),
        session_manager=mock_session_manager,
        background_runner=MagicMock(),
    )

    request = ChatRequest(
        message="Test",
        user_id="test",
        role=UserRole.STUDENT
    )

    with pytest.raises(RuntimeError, match="No processing agent"):
        await orchestrator.process(request)
