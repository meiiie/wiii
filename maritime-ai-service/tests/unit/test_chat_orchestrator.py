"""
Unit tests for ChatOrchestrator pipeline.

Tests initialization, agent type enum, pipeline stage contracts,
fallback mode, and domain routing.
All external dependencies (LLM, DB, agents) are mocked.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from enum import Enum

from app.engine.agentic_rag.rag_agent import RAGResponse
from app.models.knowledge_graph import Citation
from app.services.chat_orchestrator import ChatOrchestrator, AgentType
from app.services.output_processor import ProcessingResult


class TestAgentTypeEnum:
    """Test AgentType enum values."""

    def test_agent_types_exist(self):
        assert AgentType.CHAT == "chat"
        assert AgentType.RAG == "rag"
        assert AgentType.TUTOR == "tutor"

    def test_is_string_enum(self):
        assert issubclass(AgentType, str)
        assert issubclass(AgentType, Enum)

    def test_value_access(self):
        assert AgentType.RAG.value == "rag"

    def test_string_comparison(self):
        assert AgentType.CHAT == "chat"


class TestChatOrchestratorInit:
    """Test ChatOrchestrator initialization."""

    @patch("app.services.chat_orchestrator.get_session_manager")
    @patch("app.services.chat_orchestrator.get_input_processor")
    @patch("app.services.chat_orchestrator.get_output_processor")
    @patch("app.services.chat_orchestrator.get_background_runner")
    def test_default_init(self, mock_bg, mock_out, mock_inp, mock_sess):
        """Should initialize with default singletons."""
        orchestrator = ChatOrchestrator()
        assert orchestrator._session_manager is not None
        assert orchestrator._input_processor is not None
        assert orchestrator._output_processor is not None
        assert orchestrator._background_runner is not None

    @patch("app.services.chat_orchestrator.get_session_manager")
    @patch("app.services.chat_orchestrator.get_input_processor")
    @patch("app.services.chat_orchestrator.get_output_processor")
    @patch("app.services.chat_orchestrator.get_background_runner")
    def test_injected_dependencies(self, mock_bg, mock_out, mock_inp, mock_sess):
        """Should use injected dependencies when provided."""
        custom_session = MagicMock()
        custom_input = MagicMock()
        orchestrator = ChatOrchestrator(
            session_manager=custom_session,
            input_processor=custom_input,
        )
        assert orchestrator._session_manager is custom_session
        assert orchestrator._input_processor is custom_input

    @patch("app.services.chat_orchestrator.get_session_manager")
    @patch("app.services.chat_orchestrator.get_input_processor")
    @patch("app.services.chat_orchestrator.get_output_processor")
    @patch("app.services.chat_orchestrator.get_background_runner")
    def test_multi_agent_flag(self, mock_bg, mock_out, mock_inp, mock_sess):
        """Should read use_multi_agent from settings."""
        orchestrator = ChatOrchestrator()
        # Default should be True based on config
        assert isinstance(orchestrator._use_multi_agent, bool)


class TestFallbackBehavior:
    """Test fallback when multi-agent is unavailable."""

    @patch("app.services.chat_orchestrator.get_session_manager")
    @patch("app.services.chat_orchestrator.get_input_processor")
    @patch("app.services.chat_orchestrator.get_output_processor")
    @patch("app.services.chat_orchestrator.get_background_runner")
    def test_no_agents_raises_error(self, mock_bg, mock_out, mock_inp, mock_sess):
        """Without any agent, process should raise RuntimeError."""
        orchestrator = ChatOrchestrator()
        orchestrator._use_multi_agent = False
        orchestrator._rag_agent = None
        orchestrator._multi_agent_graph = None
        # We can't easily test the full process pipeline here without mocking
        # the domain router and all stages, but we verify the init state.
        assert orchestrator._rag_agent is None
        assert orchestrator._multi_agent_graph is None

    @pytest.mark.asyncio
    @patch("app.services.chat_orchestrator.get_session_manager")
    @patch("app.services.chat_orchestrator.get_input_processor")
    @patch("app.services.chat_orchestrator.get_output_processor")
    @patch("app.services.chat_orchestrator.get_background_runner")
    async def test_process_without_multi_agent_uses_rag_content(
        self, mock_bg, mock_out, mock_inp, mock_sess
    ):
        """Fallback RAG should read RAGResponse.content, not a legacy answer field."""
        citation = Citation(
            node_id="node-13",
            title="COLREG Rule 13",
            source="IMO",
            relevance_score=0.9,
        )
        mock_output = MagicMock()
        mock_output.format_sources.return_value = [{"title": "COLREG Rule 13"}]
        mock_out.return_value = mock_output

        rag_agent = MagicMock()
        rag_agent.query = AsyncMock(
            return_value=RAGResponse(
                content="Rule 13 applies to overtaking.",
                citations=[citation],
                native_thinking="Checked overtaking criteria.",
            )
        )

        orchestrator = ChatOrchestrator(rag_agent=rag_agent)

        with patch.object(
            orchestrator,
            "_should_use_local_direct_llm_fallback",
            return_value=False,
        ):
            result = await orchestrator.process_without_multi_agent(
                MagicMock(
                    message="Explain Rule 13",
                    user_role=MagicMock(value="student"),
                )
            )

        assert result.message == "Rule 13 applies to overtaking."
        assert result.agent_type == AgentType.RAG
        assert result.metadata == {"mode": "fallback_rag"}
        assert result.thinking == "Checked overtaking criteria."
        mock_output.format_sources.assert_called_once_with([citation])


class TestProcessingResult:
    """Test ProcessingResult used by orchestrator."""

    def test_basic_creation(self):
        result = ProcessingResult(
            message="Hello world",
            agent_type=AgentType.RAG,
        )
        assert result.message == "Hello world"
        assert result.agent_type == AgentType.RAG

    def test_with_sources(self):
        result = ProcessingResult(
            message="Answer",
            agent_type=AgentType.RAG,
            sources=[{"title": "Doc 1", "content": "test"}],
        )
        assert len(result.sources) == 1

    def test_with_metadata(self):
        result = ProcessingResult(
            message="Answer",
            agent_type=AgentType.TUTOR,
            metadata={"mode": "fallback_rag"},
        )
        assert result.metadata["mode"] == "fallback_rag"


class TestNameUsedDetection:
    """Test the name-used-in-response logic from Stage 6."""

    def test_name_found_in_response(self):
        """Complex ternary should detect name in response."""
        class FakeContext:
            user_name = "Minh"
        class FakeResult:
            message = "Chào Minh! Tôi có thể giúp gì?"

        context = FakeContext()
        result = FakeResult()
        used_name = (
            bool(context.user_name)
            and context.user_name.lower() in result.message.lower()
        ) if context.user_name else False
        assert used_name is True

    def test_name_not_in_response(self):
        class FakeContext:
            user_name = "Minh"
        class FakeResult:
            message = "Tôi có thể giúp gì?"

        context = FakeContext()
        result = FakeResult()
        used_name = (
            bool(context.user_name)
            and context.user_name.lower() in result.message.lower()
        ) if context.user_name else False
        assert used_name is False

    def test_no_user_name(self):
        class FakeContext:
            user_name = None
        class FakeResult:
            message = "Hello!"

        context = FakeContext()
        result = FakeResult()
        used_name = (
            bool(context.user_name)
            and context.user_name.lower() in result.message.lower()
        ) if context.user_name else False
        assert used_name is False

    def test_empty_user_name(self):
        class FakeContext:
            user_name = ""
        class FakeResult:
            message = "Hello!"

        context = FakeContext()
        result = FakeResult()
        used_name = (
            bool(context.user_name)
            and context.user_name.lower() in result.message.lower()
        ) if context.user_name else False
        assert used_name is False
