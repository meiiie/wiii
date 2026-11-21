from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.engine.multi_agent.graph import supervisor_node


class TestSupervisorNodeThinkingEffort:
    @pytest.mark.asyncio
    async def test_escalates_recipe_backed_premium_simulation_to_high_when_not_explicit(self):
        state = {
            "query": "Hãy mô phỏng vật lý con lắc có thể kéo thả chuột",
            "context": {},
        }
        result_state = {
            "query": state["query"],
            "context": {},
            "routing_metadata": {"intent": "code_execution"},
            "next_agent": "code_studio_agent",
        }
        fake_supervisor = SimpleNamespace(process=AsyncMock(return_value=result_state))
        fake_registry = SimpleNamespace(tracer=SimpleNamespace(span=lambda *args, **kwargs: nullcontext()))
        fake_tracer = MagicMock()

        with patch("app.engine.multi_agent.graph.get_supervisor_agent", return_value=fake_supervisor), \
             patch("app.engine.multi_agent.graph.get_agent_registry", return_value=fake_registry), \
             patch("app.engine.multi_agent.graph.get_reasoning_tracer", return_value=fake_tracer):
            result = await supervisor_node(state)

        assert result["thinking_effort"] == "max"

    @pytest.mark.asyncio
    async def test_preserves_explicit_thinking_effort(self):
        state = {
            "query": "Hãy mô phỏng vật lý con lắc có thể kéo thả chuột",
            "context": {},
            "thinking_effort": "low",
        }
        result_state = {
            "query": state["query"],
            "context": {},
            "routing_metadata": {"intent": "code_execution"},
            "next_agent": "code_studio_agent",
        }
        fake_supervisor = SimpleNamespace(process=AsyncMock(return_value=result_state))
        fake_registry = SimpleNamespace(tracer=SimpleNamespace(span=lambda *args, **kwargs: nullcontext()))
        fake_tracer = MagicMock()

        with patch("app.engine.multi_agent.graph.get_supervisor_agent", return_value=fake_supervisor), \
             patch("app.engine.multi_agent.graph.get_agent_registry", return_value=fake_registry), \
             patch("app.engine.multi_agent.graph.get_reasoning_tracer", return_value=fake_tracer):
            result = await supervisor_node(state)

        assert result["thinking_effort"] == "low"
