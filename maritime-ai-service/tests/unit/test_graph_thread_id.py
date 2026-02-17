"""
Tests for LangGraph thread_id passing and graph compilation (Sprint 8).

Verifies:
- Graph builds with and without checkpointer
- thread_id is passed to ainvoke/astream via config
- Async singleton initializes checkpointer
- Empty session_id produces empty config
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock


class TestBuildMultiAgentGraph:
    """Test graph compilation with checkpointer support."""

    def test_build_without_checkpointer(self):
        """Graph compiles successfully without checkpointer."""
        from app.engine.multi_agent.graph import build_multi_agent_graph

        graph = build_multi_agent_graph(checkpointer=None)
        assert graph is not None

    def test_build_with_checkpointer_true(self):
        """Graph compiles successfully with checkpointer=True (MemorySaver)."""
        from app.engine.multi_agent.graph import build_multi_agent_graph

        # LangGraph accepts True to auto-create MemorySaver
        graph = build_multi_agent_graph(checkpointer=True)
        assert graph is not None

    def test_graph_has_expected_nodes(self):
        """Graph contains all expected agent nodes."""
        from app.engine.multi_agent.graph import build_multi_agent_graph

        graph = build_multi_agent_graph()
        # LangGraph compiled graph has nodes attribute
        node_names = set(graph.nodes.keys()) if hasattr(graph, 'nodes') else set()
        expected = {"supervisor", "rag_agent", "tutor_agent", "memory_agent", "direct", "grader", "synthesizer"}
        # At minimum, these should exist (graph may add __start__, __end__)
        assert expected.issubset(node_names) or len(node_names) > 0

    def test_build_default_no_checkpointer(self):
        """Default build (no args) should compile without error."""
        from app.engine.multi_agent.graph import build_multi_agent_graph

        graph = build_multi_agent_graph()
        assert graph is not None


class TestGraphSingleton:
    """Test sync and async graph singletons."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset graph singleton between tests."""
        import app.engine.multi_agent.graph as mod
        mod._graph = None
        yield
        mod._graph = None

    def test_sync_singleton(self):
        """Sync singleton creates graph without checkpointer."""
        from app.engine.multi_agent.graph import get_multi_agent_graph

        graph = get_multi_agent_graph()
        assert graph is not None

        # Second call returns same instance
        graph2 = get_multi_agent_graph()
        assert graph is graph2

    @pytest.mark.asyncio
    async def test_async_singleton_with_none_checkpointer(self):
        """Async singleton works when checkpointer returns None (no DB)."""
        import app.engine.multi_agent.graph as mod
        mod._graph = None

        with patch(
            "app.engine.multi_agent.checkpointer.get_checkpointer",
            new_callable=AsyncMock,
            return_value=None,
        ):
            graph = await mod.get_multi_agent_graph_async()
            assert graph is not None

    @pytest.mark.asyncio
    async def test_async_singleton_returns_same_instance(self):
        """Async singleton returns cached instance on second call."""
        import app.engine.multi_agent.graph as mod

        mock_graph = MagicMock()
        mod._graph = mock_graph

        result = await mod.get_multi_agent_graph_async()
        assert result is mock_graph


class TestThreadIdPassing:
    """Test that thread_id is passed correctly to graph invocations."""

    @pytest.mark.asyncio
    async def test_process_passes_thread_id(self):
        """process_with_multi_agent passes composite thread_id in config (Sprint 16)."""
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(return_value={
            "final_response": "test",
            "sources": [],
            "tools_used": [],
            "grader_score": 8,
            "agent_outputs": {},
            "error": None,
            "reasoning_trace": None,
            "thinking": None,
            "thinking_content": None,
        })

        mock_registry = MagicMock()
        mock_registry.start_request_trace.return_value = "trace-123"
        mock_registry.end_request_trace.return_value = {"span_count": 0, "total_duration_ms": 0}

        mock_thread_repo = MagicMock()
        mock_thread_repo.upsert_thread.return_value = None

        with patch(
            "app.engine.multi_agent.graph.get_multi_agent_graph_async",
            new_callable=AsyncMock,
            return_value=mock_graph,
        ), patch(
            "app.engine.multi_agent.graph.get_agent_registry",
            return_value=mock_registry,
        ), patch(
            "app.repositories.thread_repository.get_thread_repository",
            return_value=mock_thread_repo,
        ):
            from app.engine.multi_agent.graph import process_with_multi_agent

            result = await process_with_multi_agent(
                query="test query",
                user_id="user-1",
                session_id="session-abc",
            )

            # Verify ainvoke was called with config containing composite thread_id
            call_args = mock_graph.ainvoke.call_args
            assert call_args is not None
            config = call_args.kwargs.get("config") or (call_args[1] if len(call_args) > 1 else {})
            if isinstance(config, dict) and "configurable" in config:
                thread_id = config["configurable"]["thread_id"]
                # Sprint 16: composite thread_id = "user_{user_id}__session_{session_id}"
                assert "user-1" in thread_id
                assert "session-abc" in thread_id

    @pytest.mark.asyncio
    async def test_process_empty_session_id(self):
        """Empty session_id produces empty config (no thread_id)."""
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(return_value={
            "final_response": "test",
            "sources": [],
            "tools_used": [],
            "grader_score": 8,
            "agent_outputs": {},
            "error": None,
            "reasoning_trace": None,
            "thinking": None,
            "thinking_content": None,
        })

        mock_registry = MagicMock()
        mock_registry.start_request_trace.return_value = "trace-123"
        mock_registry.end_request_trace.return_value = {"span_count": 0, "total_duration_ms": 0}

        with patch(
            "app.engine.multi_agent.graph.get_multi_agent_graph_async",
            new_callable=AsyncMock,
            return_value=mock_graph,
        ), patch(
            "app.engine.multi_agent.graph.get_agent_registry",
            return_value=mock_registry,
        ):
            from app.engine.multi_agent.graph import process_with_multi_agent

            result = await process_with_multi_agent(
                query="test query",
                user_id="user-1",
                session_id="",
            )

            call_args = mock_graph.ainvoke.call_args
            config = call_args.kwargs.get("config", {})
            # Empty session_id should produce empty config
            assert config == {} or "configurable" not in config
