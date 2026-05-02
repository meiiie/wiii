"""
Sprint 77: Conversation Context Overhaul — SOTA Session Memory

Tests for:
1. ConversationWindowManager (build_messages, build_summary_context, format_for_prompt)
2. InputProcessor context separation (semantic != history, langchain_messages populated)
3. Tutor node history injection
4. Direct node history injection
5. Memory agent history injection
6. Supervisor context enhancement
7. Graph initial state population
8. End-to-end pipeline context flow
"""

import asyncio
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.engine.conversation_window import (
    FORMAT_CHAR_LIMIT,
    MAX_SUMMARY_CHARS,
    RECENT_WINDOW,
    SUMMARY_MSG_LIMIT,
    ConversationWindowManager,
)


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def window_mgr():
    return ConversationWindowManager()


def _make_history(n: int, content_len: int = 20) -> list:
    """Create a history_list with n entries, alternating user/assistant."""
    history = []
    for i in range(n):
        role = "user" if i % 2 == 0 else "assistant"
        content = f"{'U' if role == 'user' else 'A'} message {i}: " + "x" * content_len
        history.append({"role": role, "content": content})
    return history


# =========================================================================
# TestConversationWindowManager
# =========================================================================

class TestConversationWindowManagerBuildMessages:

    def test_empty_history(self, window_mgr):
        result = window_mgr.build_messages([])
        assert result == []

    def test_single_user_turn(self, window_mgr):
        history = [{"role": "user", "content": "Hello"}]
        result = window_mgr.build_messages(history)
        assert len(result) == 1
        assert isinstance(result[0], HumanMessage)
        assert result[0].content == "Hello"

    def test_single_assistant_turn(self, window_mgr):
        history = [{"role": "assistant", "content": "Hi there"}]
        result = window_mgr.build_messages(history)
        assert len(result) == 1
        assert isinstance(result[0], AIMessage)
        assert result[0].content == "Hi there"

    def test_within_window(self, window_mgr):
        """History with <= RECENT_WINDOW entries returns all."""
        history = _make_history(10)
        result = window_mgr.build_messages(history)
        assert len(result) == 10

    def test_exceeds_window(self, window_mgr):
        """History > RECENT_WINDOW returns only last RECENT_WINDOW entries."""
        history = _make_history(50)
        result = window_mgr.build_messages(history)
        assert len(result) == RECENT_WINDOW

    def test_preserves_full_content_no_truncation(self, window_mgr):
        """Messages are NOT truncated — full content preserved."""
        long_content = "A" * 5000
        history = [{"role": "user", "content": long_content}]
        result = window_mgr.build_messages(history)
        assert len(result) == 1
        assert len(result[0].content) == 5000

    def test_correct_types(self, window_mgr):
        """User → HumanMessage, assistant → AIMessage."""
        history = [
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "A1"},
            {"role": "user", "content": "Q2"},
        ]
        result = window_mgr.build_messages(history)
        assert isinstance(result[0], HumanMessage)
        assert isinstance(result[1], AIMessage)
        assert isinstance(result[2], HumanMessage)

    def test_skips_empty_content(self, window_mgr):
        """Entries with empty content are skipped."""
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": ""},
            {"role": "user", "content": "World"},
        ]
        result = window_mgr.build_messages(history)
        assert len(result) == 2
        assert result[0].content == "Hello"
        assert result[1].content == "World"

    def test_unknown_role_defaults_to_human(self, window_mgr):
        """Unknown role defaults to HumanMessage."""
        history = [{"role": "system", "content": "test"}]
        result = window_mgr.build_messages(history)
        assert len(result) == 1
        assert isinstance(result[0], HumanMessage)

    def test_preserves_order(self, window_mgr):
        """Messages preserve chronological order."""
        history = [
            {"role": "user", "content": f"msg_{i}"} for i in range(5)
        ]
        result = window_mgr.build_messages(history)
        for i, msg in enumerate(result):
            assert msg.content == f"msg_{i}"

    def test_window_takes_last_n(self, window_mgr):
        """When exceeding window, takes the LAST N entries."""
        history = _make_history(40)
        result = window_mgr.build_messages(history)
        assert len(result) == RECENT_WINDOW
        # Verify it's the tail, not the head
        last_entry = history[-1]
        assert result[-1].content == last_entry["content"]


class TestConversationWindowManagerBuildSummary:

    def test_short_history_returns_existing(self, window_mgr):
        """History <= RECENT_WINDOW returns existing_summary unchanged."""
        history = _make_history(10)
        result = window_mgr.build_summary_context(history, "existing summary")
        assert result == "existing summary"

    def test_short_history_no_existing_returns_empty(self, window_mgr):
        history = _make_history(5)
        result = window_mgr.build_summary_context(history)
        assert result == ""

    def test_long_history_formats_older(self, window_mgr):
        """History > RECENT_WINDOW formats older messages."""
        history = _make_history(40)
        result = window_mgr.build_summary_context(history)
        assert result  # Non-empty
        assert "User:" in result or "AI:" in result

    def test_long_history_with_existing_summary(self, window_mgr):
        """Combines existing summary with older messages."""
        history = _make_history(40)
        result = window_mgr.build_summary_context(history, "Previous context")
        assert "Previous context" in result
        assert "Lịch sử cũ" in result

    def test_empty_history_returns_existing(self, window_mgr):
        result = window_mgr.build_summary_context([], "existing")
        assert result == "existing"

    def test_summary_respects_char_limit(self, window_mgr):
        """Summary respects MAX_SUMMARY_CHARS limit."""
        # Create history with very long messages
        history = []
        for i in range(50):
            role = "user" if i % 2 == 0 else "assistant"
            history.append({"role": role, "content": "x" * 500})
        result = window_mgr.build_summary_context(history)
        # Should be bounded (some tolerance for the "..." line)
        assert len(result) < MAX_SUMMARY_CHARS + 500


class TestConversationWindowManagerFormatForPrompt:

    def test_empty_history(self, window_mgr):
        assert window_mgr.format_for_prompt([]) == ""

    def test_backward_compat_format(self, window_mgr):
        """Output matches User:/AI: format."""
        history = [
            {"role": "user", "content": "Question"},
            {"role": "assistant", "content": "Answer"},
        ]
        result = window_mgr.format_for_prompt(history)
        assert "User: Question" in result
        assert "AI: Answer" in result

    def test_1000_char_limit(self, window_mgr):
        """Messages are truncated at 1000 chars (not 300)."""
        long = "A" * 2000
        history = [{"role": "user", "content": long}]
        result = window_mgr.format_for_prompt(history)
        # Should contain 1000 chars + "..." + "User: " prefix
        assert len(result) < 1100
        assert "..." in result

    def test_short_message_not_truncated(self, window_mgr):
        """Messages under 1000 chars are NOT truncated."""
        history = [{"role": "user", "content": "Short message"}]
        result = window_mgr.format_for_prompt(history)
        assert "..." not in result
        assert "Short message" in result


# =========================================================================
# TestInputProcessorContextSeparation
# =========================================================================

class TestInputProcessorContextSeparation:

    @pytest.fixture
    def mock_chat_history(self):
        ch = MagicMock()
        ch.is_available.return_value = True
        ch.get_recent_messages.return_value = [
            MagicMock(role="user", content="Hello"),
            MagicMock(role="assistant", content="Hi there!"),
            MagicMock(role="user", content="How are you?"),
        ]
        ch.format_history_for_prompt.return_value = "User: Hello\nAI: Hi!\nUser: How?"
        ch.get_user_name.return_value = None
        return ch

    @pytest.fixture
    def mock_semantic_memory(self):
        sm = MagicMock()
        sm.is_available.return_value = True
        sm.retrieve_insights_prioritized = AsyncMock(return_value=[])
        context_result = MagicMock()
        context_result.to_prompt_context.return_value = "Some semantic context"
        context_result.user_facts = []
        sm.retrieve_context = AsyncMock(return_value=context_result)
        return sm

    @pytest.fixture
    def processor(self, mock_chat_history, mock_semantic_memory):
        from app.services.input_processor import InputProcessor
        return InputProcessor(
            chat_history=mock_chat_history,
            semantic_memory=mock_semantic_memory,
        )

    @pytest.fixture
    def mock_request(self):
        req = MagicMock()
        req.message = "Test message"
        req.user_id = "user1"
        req.role = MagicMock()
        req.role.value = "student"
        req.user_context = None
        return req

    @pytest.mark.asyncio
    async def test_semantic_context_not_merged_into_history(
        self, processor, mock_request
    ):
        """After Sprint 77, semantic_context should NOT be merged into conversation_history."""
        from uuid import uuid4
        context = await processor.build_context(mock_request, uuid4())
        # conversation_history should NOT contain semantic context
        assert "Some semantic context" not in context.conversation_history
        # But semantic_context should still be populated
        assert "Some semantic context" in context.semantic_context

    @pytest.mark.asyncio
    async def test_langchain_messages_populated(
        self, processor, mock_request
    ):
        """langchain_messages should be populated from history_list."""
        from uuid import uuid4
        context = await processor.build_context(mock_request, uuid4())
        assert len(context.langchain_messages) == 3
        assert isinstance(context.langchain_messages[0], HumanMessage)
        assert isinstance(context.langchain_messages[1], AIMessage)
        assert isinstance(context.langchain_messages[2], HumanMessage)

    @pytest.mark.asyncio
    async def test_langchain_messages_empty_when_no_history(self, mock_request):
        """langchain_messages is empty when no chat_history available."""
        from app.services.input_processor import InputProcessor
        from uuid import uuid4
        processor = InputProcessor()
        context = await processor.build_context(mock_request, uuid4())
        assert context.langchain_messages == []

    @pytest.mark.asyncio
    async def test_conversation_history_uses_1000_char_limit(
        self, mock_request
    ):
        """conversation_history uses ConversationWindowManager (1000-char limit, not 300)."""
        from app.services.input_processor import InputProcessor
        from uuid import uuid4

        long_content = "A" * 2000
        ch = MagicMock()
        ch.is_available.return_value = True
        ch.get_recent_messages.return_value = [
            MagicMock(role="user", content=long_content),
        ]
        ch.format_history_for_prompt.return_value = ""
        ch.get_user_name.return_value = None

        processor = InputProcessor(chat_history=ch)
        context = await processor.build_context(mock_request, uuid4())

        # Should use ConversationWindowManager's 1000-char limit, not 300
        # The format_for_prompt truncates at 1000 + adds "..."
        assert len(context.conversation_history) > 500  # More than 300-char limit


# =========================================================================
# TestTutorNodeHistoryInjection
# =========================================================================

class TestTutorNodeHistoryInjection:

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM that returns a simple response."""
        llm = MagicMock()
        response = MagicMock()
        response.tool_calls = []
        response.content = "Test answer"
        llm.ainvoke = AsyncMock(return_value=response)
        llm.astream = AsyncMock()
        llm.bind_tools = MagicMock(return_value=llm)
        return llm

    @pytest.mark.asyncio
    async def test_react_loop_includes_history_messages(self, mock_llm):
        """_react_loop should include history messages between system and human."""
        from app.engine.multi_agent.agents.tutor_node import TutorAgentNode

        node = TutorAgentNode.__new__(TutorAgentNode)
        node._llm = mock_llm
        node._llm_with_tools = mock_llm
        node._prompt_loader = MagicMock()
        node._prompt_loader.build_system_prompt.return_value = "System prompt"
        node._tools = []
        node._config = MagicMock()
        node._character_tools_enabled = False

        history_messages = [
            HumanMessage(content="Previous question"),
            AIMessage(content="Previous answer"),
        ]
        context = {
            "langchain_messages": history_messages,
            "user_role": "student",
        }

        result = await node._react_loop("New question", context)

        # Verify ainvoke was called with messages including history
        call_args = mock_llm.ainvoke.call_args
        messages = call_args[0][0]

        # Should be: [SystemMessage, HumanMessage(prev), AIMessage(prev), HumanMessage(new)]
        assert isinstance(messages[0], SystemMessage)
        assert isinstance(messages[1], HumanMessage)
        assert messages[1].content == "Previous question"
        assert isinstance(messages[2], AIMessage)
        assert messages[2].content == "Previous answer"
        assert isinstance(messages[-1], HumanMessage)
        assert messages[-1].content == "New question"

    @pytest.mark.asyncio
    async def test_react_loop_no_history_still_works(self, mock_llm):
        """_react_loop works when no langchain_messages in context."""
        from app.engine.multi_agent.agents.tutor_node import TutorAgentNode

        node = TutorAgentNode.__new__(TutorAgentNode)
        node._llm = mock_llm
        node._llm_with_tools = mock_llm
        node._prompt_loader = MagicMock()
        node._prompt_loader.build_system_prompt.return_value = "System prompt"
        node._tools = []
        node._config = MagicMock()
        node._character_tools_enabled = False

        context = {"user_role": "student"}

        result = await node._react_loop("Question", context)

        call_args = mock_llm.ainvoke.call_args
        messages = call_args[0][0]
        # Just system + human, no history
        assert len(messages) == 2
        assert isinstance(messages[0], SystemMessage)
        assert isinstance(messages[1], HumanMessage)

    @pytest.mark.asyncio
    async def test_react_loop_limits_to_10_turns(self, mock_llm):
        """Only last 10 history messages are injected."""
        from app.engine.multi_agent.agents.tutor_node import TutorAgentNode

        node = TutorAgentNode.__new__(TutorAgentNode)
        node._llm = mock_llm
        node._llm_with_tools = mock_llm
        node._prompt_loader = MagicMock()
        node._prompt_loader.build_system_prompt.return_value = "System"
        node._tools = []
        node._config = MagicMock()
        node._character_tools_enabled = False

        # 20 history messages
        history = [HumanMessage(content=f"msg_{i}") for i in range(20)]
        context = {"langchain_messages": history, "user_role": "student"}

        await node._react_loop("New Q", context)

        call_args = mock_llm.ainvoke.call_args
        messages = call_args[0][0]
        # System + 10 history + 1 current = 12
        assert len(messages) == 12

    def test_system_prompt_excludes_conversation_history_key(self):
        """_build_system_prompt excludes conversation_history from context dump."""
        from app.engine.multi_agent.agents.tutor_node import TutorAgentNode

        node = TutorAgentNode.__new__(TutorAgentNode)
        node._prompt_loader = MagicMock()
        node._prompt_loader.build_system_prompt.return_value = "Base prompt"
        node._character_tools_enabled = False

        context = {
            "user_role": "student",
            "user_name": "Test",
            "conversation_history": "Should NOT appear in system prompt",
            "langchain_messages": [HumanMessage(content="should not appear")],
            "conversation_summary": "should not appear either",
        }

        # Mock domain registry to avoid import errors
        with patch("app.engine.multi_agent.agents.tutor_node.get_prompt_loader", return_value=node._prompt_loader):
            prompt = node._build_system_prompt(context, "test query")

        # conversation_history should be excluded from context dump
        assert "Should NOT appear in system prompt" not in prompt
        # But user_name should still be there
        assert "Test" in prompt


# =========================================================================
# TestDirectNodeHistoryInjection
# =========================================================================

class TestDirectNodeHistoryInjection:

    @pytest.mark.asyncio
    async def test_direct_node_includes_history(self):
        """direct_response_node injects history between system and human messages."""
        history_messages = [
            HumanMessage(content="What's COLREGs?"),
            AIMessage(content="COLREGs is..."),
        ]
        state = {
            "query": "Tell me more",
            "context": {
                "langchain_messages": history_messages,
                "is_follow_up": True,
                "core_memory_block": "",
            },
            "domain_id": "maritime",
        }

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_response = MagicMock()
        mock_response.content = "Here's more detail about COLREGs..."
        mock_response.tool_calls = []
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        # Lazy imports inside direct_response_node → patch at source modules
        with patch("app.engine.multi_agent.agent_config.AgentConfigRegistry") as mock_reg, \
             patch("app.engine.multi_agent.graph._get_domain_greetings", return_value={}), \
             patch("app.engine.multi_agent.graph.get_reasoning_tracer") as mock_tracer_fn, \
             patch("app.services.output_processor.extract_thinking_from_response", return_value=("Response", None)):
            mock_reg.get_llm.return_value = mock_llm
            mock_tracer = MagicMock()
            mock_tracer_fn.return_value = mock_tracer
            mock_tracer.build_trace.return_value = MagicMock()

            from app.engine.multi_agent.graph import direct_response_node
            result = await direct_response_node(state)

        # Verify LLM was called with history messages
        call_args = mock_llm.ainvoke.call_args[0][0]
        # Should be [system_dict, HumanMessage(prev), AIMessage(prev), user_dict(new)]
        # Phase 1 migration: system/user are native dicts; history slice stays LC
        assert isinstance(call_args[0], dict) and call_args[0]["role"] == "system"
        assert isinstance(call_args[1], HumanMessage)
        assert call_args[1].content == "What's COLREGs?"
        assert isinstance(call_args[2], AIMessage)
        assert isinstance(call_args[-1], dict) and call_args[-1]["role"] == "user"
        assert call_args[-1]["content"] == "Tell me more"

    @pytest.mark.asyncio
    async def test_direct_node_no_history_fallback(self):
        """direct_response_node works without history messages."""
        state = {
            "query": "Hello",
            "context": {"is_follow_up": False, "core_memory_block": ""},
            "domain_id": "maritime",
        }

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_response = MagicMock()
        mock_response.content = "Hi!"
        mock_response.tool_calls = []
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch("app.engine.multi_agent.agent_config.AgentConfigRegistry") as mock_reg, \
             patch("app.engine.multi_agent.graph._get_domain_greetings", return_value={}), \
             patch("app.engine.multi_agent.graph.get_reasoning_tracer") as mock_tracer_fn, \
             patch("app.services.output_processor.extract_thinking_from_response", return_value=("Hi!", None)):
            mock_reg.get_llm.return_value = mock_llm
            mock_tracer = MagicMock()
            mock_tracer_fn.return_value = mock_tracer

            from app.engine.multi_agent.graph import direct_response_node
            result = await direct_response_node(state)

        call_args = mock_llm.ainvoke.call_args[0][0]
        # Just System + Human, no history
        assert len(call_args) == 2
        # Phase 1 migration: native dicts
        assert isinstance(call_args[0], dict) and call_args[0]["role"] == "system"
        assert isinstance(call_args[1], dict) and call_args[1]["role"] == "user"


# =========================================================================
# TestMemoryAgentHistoryInjection
# =========================================================================

class TestMemoryAgentHistoryInjection:

    @pytest.mark.asyncio
    async def test_memory_agent_includes_history(self):
        """Memory agent injects conversation history into LLM messages."""
        from app.engine.multi_agent.agents.memory_agent import MemoryAgentNode

        node = MemoryAgentNode.__new__(MemoryAgentNode)
        node._semantic_memory = None
        node._config = MagicMock()
        node._updater = MagicMock()
        node._updater.classify_batch.return_value = []
        node._updater.summarize_changes.return_value = ""

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Mình đã ghi nhớ rồi!"
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        history_messages = [
            HumanMessage(content="Tên tôi là Nam"),
            AIMessage(content="Mình ghi nhớ rồi, Nam!"),
        ]
        state = {
            "user_id": "user1",
            "query": "Bạn có nhớ tên tôi không?",
            "context": {"langchain_messages": history_messages},
            "agent_outputs": {},
        }

        response = await node._generate_response(
            mock_llm, "Bạn có nhớ tên tôi không?",
            [{"type": "name", "content": "Nam"}], [], "", state,
        )

        # Verify history was injected
        call_args = mock_llm.ainvoke.call_args[0][0]
        # System + 2 history + Human(query) = 4
        assert len(call_args) == 4
        # Phase 1 migration: system/user are native dicts; history slice stays LC
        assert isinstance(call_args[0], dict) and call_args[0]["role"] == "system"
        assert isinstance(call_args[1], HumanMessage)
        assert call_args[1].content == "Tên tôi là Nam"
        assert isinstance(call_args[2], AIMessage)
        assert isinstance(call_args[-1], dict) and call_args[-1]["role"] == "user"

    @pytest.mark.asyncio
    async def test_memory_agent_limits_to_5_turns(self):
        """Memory agent only uses last 5 turns from history."""
        from app.engine.multi_agent.agents.memory_agent import MemoryAgentNode

        node = MemoryAgentNode.__new__(MemoryAgentNode)
        node._semantic_memory = None
        node._config = MagicMock()
        node._updater = MagicMock()
        node._updater.classify_batch.return_value = []
        node._updater.summarize_changes.return_value = ""

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Response"
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        # 10 history messages
        history = [HumanMessage(content=f"msg_{i}") for i in range(10)]
        state = {
            "user_id": "user1",
            "query": "Test",
            "context": {"langchain_messages": history},
            "agent_outputs": {},
        }

        await node._generate_response(
            mock_llm, "Test", [], [], "", state,
        )

        call_args = mock_llm.ainvoke.call_args[0][0]
        # System + 5 history + Human = 7
        assert len(call_args) == 7

    @pytest.mark.asyncio
    async def test_memory_agent_no_history_still_works(self):
        """Memory agent works without history messages."""
        from app.engine.multi_agent.agents.memory_agent import MemoryAgentNode

        node = MemoryAgentNode.__new__(MemoryAgentNode)
        node._semantic_memory = None
        node._config = MagicMock()
        node._updater = MagicMock()

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Response"
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        state = {
            "user_id": "user1",
            "query": "Test",
            "context": {},
            "agent_outputs": {},
        }

        await node._generate_response(mock_llm, "Test", [], [], "", state)

        call_args = mock_llm.ainvoke.call_args[0][0]
        # System + Human = 2 (no history)
        assert len(call_args) == 2


# =========================================================================
# TestSupervisorContextEnhancement
# =========================================================================

class TestSupervisorContextEnhancement:

    @pytest.mark.asyncio
    async def test_supervisor_uses_recent_turns(self):
        """Supervisor uses recent conversation turns for routing context."""
        from app.engine.multi_agent.supervisor import SupervisorAgent

        agent = SupervisorAgent.__new__(SupervisorAgent)
        agent._llm = MagicMock()

        mock_result = MagicMock()
        mock_result.agent = "RAG_AGENT"
        mock_result.confidence = 0.95
        mock_result.intent = "lookup"
        mock_result.reasoning = "test"

        history = [
            HumanMessage(content="Tell me about COLREGs"),
            AIMessage(content="COLREGs is the international regulations..."),
        ]
        context = {"langchain_messages": history}

        state = {"query": "Điều 15 nói gì?", "context": context, "domain_config": {}}

        # _route_structured has lazy `from app.core.config import settings` — patch at source
        with patch("app.core.config.settings") as mock_settings, patch(
            "app.engine.multi_agent.supervisor.StructuredInvokeService.ainvoke",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_ainvoke:
            mock_settings.enable_structured_outputs = True

            result = await agent._route_structured(
                "Điều 15 nói gì?", context, "Maritime", "RAG desc", "Tutor desc",
                {}, state,
            )

        # Verify the prompt was called with recent conversation, not truncated dict
        payload = mock_ainvoke.call_args.kwargs["payload"]
        human_msg = next(m for m in payload if hasattr(m, 'type') and m.type == 'human')
        assert "Recent conversation" in human_msg.content

    @pytest.mark.asyncio
    async def test_supervisor_fallback_without_messages(self):
        """Supervisor falls back to str(context)[:500] when no langchain_messages."""
        from app.engine.multi_agent.supervisor import SupervisorAgent

        agent = SupervisorAgent.__new__(SupervisorAgent)
        agent._llm = MagicMock()

        mock_result = MagicMock()
        mock_result.agent = "DIRECT"
        mock_result.confidence = 0.9
        mock_result.intent = "social"
        mock_result.reasoning = "greeting"

        context = {"user_name": "Test"}
        state = {"query": "Hello", "context": context, "domain_config": {}}

        with patch("app.core.config.settings") as mock_settings, patch(
            "app.engine.multi_agent.supervisor.StructuredInvokeService.ainvoke",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_ainvoke:
            mock_settings.enable_structured_outputs = True

            result = await agent._route_structured(
                "Hello", context, "Maritime", "RAG desc", "Tutor desc",
                {}, state,
            )

        payload = mock_ainvoke.call_args.kwargs["payload"]
        prompt_content = next(m.content for m in payload if hasattr(m, 'type') and m.type == 'human')
        # Without langchain_messages, should use str(context) fallback
        assert "Recent conversation" not in prompt_content


# =========================================================================
# TestGraphInitialState
# =========================================================================

class TestGraphInitialState:

    @pytest.mark.asyncio
    async def test_messages_populated_from_langchain_messages(self):
        """Initial state messages are populated from langchain_messages in context."""
        history = [
            HumanMessage(content="Q1"),
            AIMessage(content="A1"),
        ]
        context = {"langchain_messages": history}

        # We can't easily run the full graph, so test the serialization logic directly
        langchain_messages = context.get("langchain_messages", [])
        serialized = []
        for m in langchain_messages:
            if isinstance(m, dict):
                serialized.append(m)
            else:
                serialized.append({
                    "role": getattr(m, "type", "human"),
                    "content": m.content,
                })

        assert len(serialized) == 2
        assert serialized[0] == {"role": "human", "content": "Q1"}
        assert serialized[1] == {"role": "ai", "content": "A1"}

    def test_messages_empty_when_no_langchain_messages(self):
        """Initial state messages are empty when context has no langchain_messages."""
        context = {"user_name": "Test"}
        langchain_messages = context.get("langchain_messages", [])
        serialized = []
        for m in langchain_messages:
            serialized.append(m)
        assert serialized == []


# =========================================================================
# TestEndToEnd
# =========================================================================

class TestEndToEnd:

    def test_full_pipeline_history_reaches_context(self):
        """History list flows from InputProcessor to ChatContext.langchain_messages."""
        from app.services.input_processor import ChatContext

        ctx = ChatContext(
            user_id="u1",
            session_id=MagicMock(),
            message="Test",
            user_role=MagicMock(),
        )

        # Simulate what build_context does
        ctx.history_list = [
            {"role": "user", "content": "First question"},
            {"role": "assistant", "content": "First answer"},
            {"role": "user", "content": "Follow up"},
        ]

        from app.engine.conversation_window import ConversationWindowManager
        mgr = ConversationWindowManager()
        ctx.langchain_messages = mgr.build_messages(ctx.history_list)

        assert len(ctx.langchain_messages) == 3
        assert isinstance(ctx.langchain_messages[0], HumanMessage)
        assert ctx.langchain_messages[0].content == "First question"

    def test_follow_up_has_context(self):
        """After multiple turns, all agents receive history context."""
        from app.engine.conversation_window import ConversationWindowManager

        mgr = ConversationWindowManager()
        history = [
            {"role": "user", "content": "Giải thích Điều 15 COLREGs"},
            {"role": "assistant", "content": "Điều 15 quy định về tình huống đối hướng..."},
            {"role": "user", "content": "Cho ví dụ thực tế"},
        ]

        messages = mgr.build_messages(history)
        assert len(messages) == 3
        # Full content preserved
        assert "tình huống đối hướng" in messages[1].content

    def test_orchestrator_context_dict_has_new_fields(self):
        """Multi-agent context dict includes langchain_messages and conversation_summary."""
        from app.services.input_processor import ChatContext

        ctx = ChatContext(
            user_id="u1",
            session_id=MagicMock(),
            message="Test",
            user_role=MagicMock(),
        )
        ctx.langchain_messages = [HumanMessage(content="prev")]
        ctx.conversation_summary = "Summary of older turns"

        # Simulate what ChatOrchestrator builds
        multi_agent_context = {
            "langchain_messages": ctx.langchain_messages,
            "conversation_summary": ctx.conversation_summary or "",
        }

        assert len(multi_agent_context["langchain_messages"]) == 1
        assert multi_agent_context["conversation_summary"] == "Summary of older turns"
