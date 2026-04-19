"""Tests for universal agentic loop (Phase 4)."""

import pytest

from app.engine.multi_agent.agent_config import AgentConfigRegistry, AgentNodeConfig


class TestAgentConfigAgenticLoop:
    """Verify agentic loop is enabled for expected agents."""

    def test_tutor_has_agentic_loop(self):
        config = AgentConfigRegistry.get_config("tutor_agent")
        assert config.enable_agentic_loop is True

    def test_code_studio_has_agentic_loop(self):
        config = AgentConfigRegistry.get_config("code_studio_agent")
        assert config.enable_agentic_loop is True

    def test_rag_has_agentic_loop(self):
        """Phase 4: RAG agent now has agentic loop enabled."""
        config = AgentConfigRegistry.get_config("rag_agent")
        assert config.enable_agentic_loop is True

    def test_direct_has_agentic_loop(self):
        """Phase 4: Direct agent now has agentic loop enabled."""
        config = AgentConfigRegistry.get_config("direct")
        assert config.enable_agentic_loop is True

    def test_supervisor_no_agentic_loop(self):
        config = AgentConfigRegistry.get_config("supervisor")
        assert config.enable_agentic_loop is False

    def test_guardian_no_agentic_loop(self):
        config = AgentConfigRegistry.get_config("guardian")
        assert config.enable_agentic_loop is False

    def test_synthesizer_no_agentic_loop(self):
        config = AgentConfigRegistry.get_config("synthesizer")
        assert config.enable_agentic_loop is False


class TestRunnerAgenticLoopSignal:
    """Test that runner detects _agentic_continue and respects config."""

    @pytest.fixture
    def runner(self):
        from app.engine.multi_agent.runner import WiiiRunner
        return WiiiRunner()

    def test_agent_with_loop_enabled(self, runner):
        """Agents with enable_agentic_loop=True should be re-invocable."""
        assert runner._agent_has_agentic_loop("rag_agent") is True
        assert runner._agent_has_agentic_loop("direct") is True
        assert runner._agent_has_agentic_loop("tutor_agent") is True

    def test_agent_without_loop(self, runner):
        """Agents with enable_agentic_loop=False should not be re-invoked."""
        assert runner._agent_has_agentic_loop("supervisor") is False
        assert runner._agent_has_agentic_loop("synthesizer") is False

    @pytest.mark.asyncio
    async def test_resolve_next_step_with_agentic_continue(self, runner):
        """When _agentic_continue is set and agent has loop, return NextStepRunAgain."""
        from app.engine.multi_agent.next_step import NextStepRunAgain

        state = {
            "current_agent": "rag_agent",
            "_agentic_continue": True,
            "_orchestrator_turn": 1,
        }
        # Turn > 0, so _resolve_next_step checks _agentic_continue
        step = await runner._resolve_next_step(state, turn=1)
        assert isinstance(step, NextStepRunAgain)
        assert step.agent_name == "rag_agent"

    @pytest.mark.asyncio
    async def test_resolve_next_step_ignores_continue_for_no_loop_agent(self, runner):
        """When _agentic_continue is set but agent lacks loop, finalize."""
        from app.engine.multi_agent.next_step import NextStepFinalOutput

        state = {
            "current_agent": "supervisor",
            "_agentic_continue": True,
            "_orchestrator_turn": 1,
            "final_response": "Response is long enough to avoid self-correction",
            "_self_correction_retry": 0,
        }
        step = await runner._resolve_next_step(state, turn=1)
        assert isinstance(step, NextStepFinalOutput)

    @pytest.mark.asyncio
    async def test_resolve_next_step_clears_agentic_continue(self, runner):
        """_agentic_continue should be cleared after detection."""
        state = {
            "current_agent": "rag_agent",
            "_agentic_continue": True,
            "_orchestrator_turn": 1,
            "final_response": "Response is long enough to avoid self-correction",
        }
        await runner._resolve_next_step(state, turn=1)
        assert state.get("_agentic_continue") is None
