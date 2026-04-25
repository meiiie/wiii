"""
Tests for thread identity handling and the runner-backed multi-agent runtime.

Verifies:
- retired graph/checkpointer entrypoints are no longer public APIs
- WiiiRunner is registered with the core orchestration nodes
- process_with_multi_agent preserves user/session identity and thread views
"""

import importlib.util
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestRemovedGraphEntrypoints:
    """Test the retired graph/checkpointer APIs are gone from public surface."""

    def test_graph_builder_symbols_are_removed(self):
        import app.engine.multi_agent.graph as graph_mod

        removed = {
            "build_multi_agent_graph",
            "get_multi_agent_graph",
            "get_multi_agent_graph_async",
            "open_multi_agent_graph",
        }
        for name in removed:
            assert not hasattr(graph_mod, name)

    def test_package_no_longer_exports_graph_builder_symbols(self):
        import app.engine.multi_agent as multi_agent

        removed = {
            "build_multi_agent_graph",
            "get_multi_agent_graph",
        }
        for name in removed:
            assert name not in multi_agent.__all__
            with pytest.raises(AttributeError):
                getattr(multi_agent, name)

    def test_checkpointer_module_is_removed(self):
        assert importlib.util.find_spec("app.engine.multi_agent.checkpointer") is None


class TestRunnerRegistration:
    """Test WiiiRunner replaces the previous graph node registry."""

    @pytest.fixture(autouse=True)
    def reset_runner(self):
        """Reset runner singleton between tests."""
        import app.engine.multi_agent.runner as runner_mod

        runner_mod._RUNNER = None
        yield
        runner_mod._RUNNER = None

    def test_runner_has_expected_core_nodes(self):
        """Runner contains the core agent nodes used by the main path."""
        from app.engine.multi_agent.runner import get_wiii_runner

        runner = get_wiii_runner()

        node_names = set(runner._nodes.keys())
        expected = {
            "guardian",
            "supervisor",
            "rag_agent",
            "tutor_agent",
            "memory_agent",
            "direct",
            "code_studio_agent",
            "synthesizer",
        }
        assert expected.issubset(node_names)

    def test_runner_registers_feature_nodes(self):
        """Feature-gated nodes remain registered on the runner shell."""
        from app.engine.multi_agent.runner import get_wiii_runner

        runner = get_wiii_runner()

        feature_node_names = set(runner._feature_nodes.keys())
        assert "colleague_agent" in feature_node_names
        assert "product_search_agent" in feature_node_names
        assert "parallel_dispatch" in feature_node_names


class TestAgentStateSchema:
    """Guard critical runtime metadata fields from being dropped by state schema."""

    def test_agent_state_declares_execution_runtime_fields(self):
        """Execution provider/model must exist in AgentState so sync metadata survives hops."""
        from app.engine.multi_agent.state import AgentState

        annotations = getattr(AgentState, "__annotations__", {})
        assert "_execution_provider" in annotations
        assert "_execution_model" in annotations
        assert "model" in annotations


class TestThreadIdPassing:
    """Test thread identity is preserved through the WiiiRunner path."""

    def _mock_registry(self):
        mock_registry = MagicMock()
        mock_registry.start_request_trace.return_value = "trace-123"
        mock_registry.end_request_trace.return_value = {
            "span_count": 0,
            "total_duration_ms": 0,
        }
        return mock_registry

    @pytest.mark.asyncio
    async def test_process_preserves_thread_identity(self):
        """process_with_multi_agent passes identity through runner state."""
        mock_runner = MagicMock()
        mock_runner.run = AsyncMock(
            return_value={
                "final_response": "test",
                "sources": [],
                "tools_used": [],
                "grader_score": 8,
                "agent_outputs": {},
                "error": None,
                "reasoning_trace": None,
                "thinking": None,
                "thinking_content": None,
                "_execution_provider": "zhipu",
                "_execution_model": "glm-5",
            }
        )
        mock_registry = self._mock_registry()
        mock_thread_repo = MagicMock()
        mock_thread_repo.upsert_thread.return_value = {"message_count": 1}

        with patch(
            "app.engine.multi_agent.runner.get_wiii_runner",
            return_value=mock_runner,
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

            run_state = mock_runner.run.call_args.args[0]
            assert run_state["user_id"] == "user-1"
            assert run_state["session_id"] == "session-abc"
            upsert_kwargs = mock_thread_repo.upsert_thread.call_args.kwargs
            assert "user-1" in upsert_kwargs["thread_id"]
            assert "session-abc" in upsert_kwargs["thread_id"]
            assert result["provider"] == "zhipu"
            assert result["model"] == "glm-5"
            assert result["_execution_provider"] == "zhipu"
            assert result["_execution_model"] == "glm-5"

    @pytest.mark.asyncio
    async def test_process_empty_session_id(self):
        """Empty session_id skips thread view persistence."""
        mock_runner = MagicMock()
        mock_runner.run = AsyncMock(
            return_value={
                "final_response": "test",
                "sources": [],
                "tools_used": [],
                "grader_score": 8,
                "agent_outputs": {},
                "error": None,
                "reasoning_trace": None,
                "thinking": None,
                "thinking_content": None,
            }
        )
        mock_registry = self._mock_registry()
        mock_thread_repo = MagicMock()

        with patch(
            "app.engine.multi_agent.runner.get_wiii_runner",
            return_value=mock_runner,
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
                session_id="",
            )

            run_state = mock_runner.run.call_args.args[0]
            assert run_state["user_id"] == "user-1"
            assert run_state["session_id"] == ""
            mock_thread_repo.upsert_thread.assert_not_called()
            assert result["response"] == "test"
