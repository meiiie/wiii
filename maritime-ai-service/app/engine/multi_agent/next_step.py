"""NextStep types for the WiiiRunner orchestrator loop.

Inspired by OpenAI Agents SDK Runner pattern:
- NextStepRunAgain:   Continue with same agent (agentic loop not done)
- NextStepHandoff:    Transfer control to a different agent
- NextStepFinalOutput: Terminate loop, go to synthesizer

The orchestrator loop uses these typed variants instead of string-based routing,
enabling multi-turn execution, agent handoffs, and max-turns protection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Union


@dataclass(frozen=True)
class NextStepRunAgain:
    """Continue the current agent's execution (tool calls need more processing).

    Used when an agent sets ``state["_agentic_continue"] = True`` — the
    orchestrator re-invokes the agent for another turn.
    """

    agent_name: str
    reason: str = ""


@dataclass(frozen=True)
class NextStepHandoff:
    """Transfer control to a different agent mid-pipeline.

    Used when an agent calls ``handoff_to_agent`` tool or the supervisor
    routes to a different agent. Context is preserved in AgentState.
    """

    target_agent: str
    context: Dict[str, object] = field(default_factory=dict)
    reason: str = ""


@dataclass(frozen=True)
class NextStepFinalOutput:
    """Terminate the orchestrator loop with a final response.

    The runner proceeds to the synthesizer for output formatting.
    """

    reason: str = ""


NextStep = Union[NextStepRunAgain, NextStepHandoff, NextStepFinalOutput]
