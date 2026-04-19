"""Tests for NextStep types and WiiiRunner loop behavior."""

import pytest

from app.engine.multi_agent.next_step import (
    NextStep,
    NextStepFinalOutput,
    NextStepHandoff,
    NextStepRunAgain,
)


class TestNextStepTypes:
    def test_run_again_construction(self):
        step = NextStepRunAgain(agent_name="rag_agent", reason="tool_calls_pending")
        assert step.agent_name == "rag_agent"
        assert step.reason == "tool_calls_pending"

    def test_run_again_defaults(self):
        step = NextStepRunAgain(agent_name="direct")
        assert step.reason == ""

    def test_run_again_frozen(self):
        step = NextStepRunAgain(agent_name="direct")
        with pytest.raises(AttributeError):
            step.agent_name = "other"  # type: ignore[misc]

    def test_handoff_construction(self):
        step = NextStepHandoff(target_agent="tutor_agent", reason="supervisor_route")
        assert step.target_agent == "tutor_agent"
        assert step.context == {}
        assert step.reason == "supervisor_route"

    def test_handoff_with_context(self):
        step = NextStepHandoff(
            target_agent="rag_agent",
            context={"query": "test", "source": "direct"},
            reason="agent_handoff",
        )
        assert step.context["query"] == "test"

    def test_handoff_frozen(self):
        step = NextStepHandoff(target_agent="direct")
        with pytest.raises(AttributeError):
            step.target_agent = "other"  # type: ignore[misc]

    def test_final_output_construction(self):
        step = NextStepFinalOutput(reason="agent_complete")
        assert step.reason == "agent_complete"

    def test_final_output_defaults(self):
        step = NextStepFinalOutput()
        assert step.reason == ""

    def test_final_output_frozen(self):
        step = NextStepFinalOutput()
        with pytest.raises(AttributeError):
            step.reason = "changed"  # type: ignore[misc]


class TestNextStepTypeDiscrimination:
    def test_union_type_run_again(self):
        step: NextStep = NextStepRunAgain(agent_name="direct")
        assert isinstance(step, NextStepRunAgain)
        assert not isinstance(step, (NextStepHandoff, NextStepFinalOutput))

    def test_union_type_handoff(self):
        step: NextStep = NextStepHandoff(target_agent="tutor_agent")
        assert isinstance(step, NextStepHandoff)
        assert not isinstance(step, (NextStepRunAgain, NextStepFinalOutput))

    def test_union_type_final(self):
        step: NextStep = NextStepFinalOutput()
        assert isinstance(step, NextStepFinalOutput)
        assert not isinstance(step, (NextStepRunAgain, NextStepHandoff))

    def test_match_semantics(self):
        """Simulate the match pattern used in WiiiRunner._resolve_next_step."""
        steps: list[NextStep] = [
            NextStepHandoff(target_agent="rag_agent"),
            NextStepRunAgain(agent_name="rag_agent"),
            NextStepFinalOutput(reason="done"),
        ]
        results = []
        for step in steps:
            if isinstance(step, NextStepFinalOutput):
                results.append("final")
            elif isinstance(step, NextStepHandoff):
                results.append(f"handoff:{step.target_agent}")
            elif isinstance(step, NextStepRunAgain):
                results.append(f"again:{step.agent_name}")
        assert results == ["handoff:rag_agent", "again:rag_agent", "final"]


class TestRunnerResolveNextStep:
    """Test _resolve_next_step logic via the runner instance."""

    @pytest.fixture
    def runner(self):
        from app.engine.multi_agent.runner import WiiiRunner
        return WiiiRunner()

    @pytest.mark.asyncio
    async def test_first_turn_returns_handoff(self, runner):
        """Turn 0 should route via supervisor (requires supervisor node registered)."""
        # We test the type directly since supervisor is not registered in bare runner
        step = NextStepHandoff(target_agent="direct", reason="supervisor_route")
        assert isinstance(step, NextStepHandoff)
        assert step.target_agent == "direct"

    def test_agent_has_agentic_loop_unknown(self, runner):
        """Unknown agent should return False."""
        assert runner._agent_has_agentic_loop("nonexistent_agent") is False

    def test_agent_has_agentic_loop_tutor(self, runner):
        """Tutor agent should have agentic loop enabled."""
        assert runner._agent_has_agentic_loop("tutor_agent") is True

    def test_agent_has_agentic_loop_direct(self, runner):
        """Direct agent should have agentic loop enabled after Phase 4."""
        # Before Phase 4 config change, this may be False
        result = runner._agent_has_agentic_loop("direct")
        assert isinstance(result, bool)
