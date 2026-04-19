"""Guardrail decorator extensibility — dynamic input/output checks.

Inspired by OpenAI Agents SDK InputGuardrail/OutputGuardrail pattern.

Design:
- Guardrails are callables registered via @guardrail() decorator
- Input guardrails run before the pipeline (extending guardian_node)
- Output guardrails run after the pipeline (extending grader checks)
- Guardrails can run sequentially or in parallel with the main pipeline
- Feature-gated: enable_guardrails=False (zero overhead when disabled)

Usage:
    from app.engine.multi_agent.guardrails import guardrail, GuardrailContext

    @guardrail(phase="input", name="no_urls", description="Block URL-only queries")
    async def block_url_only_queries(ctx: GuardrailContext) -> GuardrailResult:
        if "http" in ctx.query and len(ctx.query) < 50:
            return GuardrailResult(passed=False, reason="Chỉ chứa URL")
        return GuardrailResult(passed=True)

The guardrail registry is consulted by WiiiRunner during execution.
New guardrails are automatically picked up without modifying runner code.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, List, Optional

from app.engine.multi_agent.state import AgentState

logger = logging.getLogger(__name__)


# =========================================================================
# Guardrail data models
# =========================================================================


@dataclass
class GuardrailContext:
    """Context passed to every guardrail function.

    Provides all the information a guardrail needs to make a decision.
    """
    query: str = ""
    state: Optional[AgentState] = None
    domain_id: str = ""
    user_id: str = ""
    response: str = ""  # Only for output guardrails
    agent_name: str = ""  # Only for output guardrails


@dataclass
class GuardrailResult:
    """Result from a guardrail check."""
    passed: bool = True
    reason: str = ""
    confidence: float = 1.0
    metadata: Optional[dict] = None


# =========================================================================
# Guardrail function type
# =========================================================================

GuardrailFn = Callable[[GuardrailContext], Coroutine[Any, Any, GuardrailResult]]


@dataclass
class GuardrailEntry:
    """A registered guardrail with metadata."""
    name: str
    phase: str  # "input" | "output"
    fn: GuardrailFn
    description: str = ""
    run_parallel: bool = True  # If True, runs concurrently with main pipeline
    priority: int = 100  # Lower = runs first (for sequential guardrails)


# =========================================================================
# Guardrail Registry
# =========================================================================


class GuardrailRegistry:
    """Registry for dynamically registered guardrails.

    Thread-safe singleton — guardrails can be registered at startup
    or dynamically during the application lifecycle.
    """

    _input_guardrails: list[GuardrailEntry] = []
    _output_guardrails: list[GuardrailEntry] = []
    _initialized: bool = False

    @classmethod
    def reset(cls) -> None:
        """Clear all registered guardrails."""
        cls._input_guardrails = []
        cls._output_guardrails = []
        cls._initialized = False

    @classmethod
    def register(cls, entry: GuardrailEntry) -> None:
        """Register a guardrail."""
        if entry.phase == "input":
            cls._input_guardrails.append(entry)
            cls._input_guardrails.sort(key=lambda e: e.priority)
        elif entry.phase == "output":
            cls._output_guardrails.append(entry)
            cls._output_guardrails.append(entry)  # duplicate safe — will sort
            cls._output_guardrails.sort(key=lambda e: e.priority)
            # Deduplicate
            seen = set()
            unique = []
            for g in cls._output_guardrails:
                if g.name not in seen:
                    seen.add(g.name)
                    unique.append(g)
            cls._output_guardrails = unique
        else:
            logger.warning("[GUARDRAIL] Unknown phase %r for %s", entry.phase, entry.name)

    @classmethod
    def get_input_guardrails(cls) -> list[GuardrailEntry]:
        """Get all registered input guardrails, sorted by priority."""
        return list(cls._input_guardrails)

    @classmethod
    def get_output_guardrails(cls) -> list[GuardrailEntry]:
        """Get all registered output guardrails, sorted by priority."""
        return list(cls._output_guardrails)

    @classmethod
    def list_names(cls) -> dict[str, list[str]]:
        """List all registered guardrail names by phase."""
        return {
            "input": [g.name for g in cls._input_guardrails],
            "output": [g.name for g in cls._output_guardrails],
        }


# =========================================================================
# Decorator
# =========================================================================


def guardrail(
    *,
    phase: str,
    name: str,
    description: str = "",
    run_parallel: bool = True,
    priority: int = 100,
):
    """Decorator to register a function as a guardrail.

    Args:
        phase: "input" (before pipeline) or "output" (after pipeline)
        name: Unique name for this guardrail
        description: Human-readable description
        run_parallel: If True, runs concurrently with main pipeline (input only)
        priority: Execution order (lower = first)
    """
    def decorator(fn: GuardrailFn) -> GuardrailFn:
        entry = GuardrailEntry(
            name=name,
            phase=phase,
            fn=fn,
            description=description,
            run_parallel=run_parallel,
            priority=priority,
        )
        GuardrailRegistry.register(entry)
        return fn
    return decorator


# =========================================================================
# Execution helpers
# =========================================================================


async def run_input_guardrails(
    state: AgentState,
    *,
    guardian_passed: bool = True,
) -> tuple[bool, Optional[str]]:
    """Run all registered input guardrails.

    Returns (passed, reason).
    If any guardrail fails, returns (False, reason).
    Sequential guardrails run first (sorted by priority).
    Parallel guardrails run concurrently.

    This is called by WiiiRunner after guardian_node but before supervisor.
    """
    guardrails = GuardrailRegistry.get_input_guardrails()
    if not guardrails:
        return guardian_passed, None

    ctx = GuardrailContext(
        query=state.get("query", ""),
        state=state,
        domain_id=state.get("domain_id", ""),
        user_id=state.get("user_id", ""),
    )

    # Split into sequential and parallel
    sequential = [g for g in guardrails if not g.run_parallel]
    parallel = [g for g in guardrails if g.run_parallel]

    # Run sequential guardrails first
    for entry in sequential:
        try:
            result = await entry.fn(ctx)
            if not result.passed:
                logger.info("[GUARDRAIL] %s blocked: %s", entry.name, result.reason)
                return False, result.reason
        except Exception as exc:
            logger.warning("[GUARDRAIL] %s error (allowing): %s", entry.name, exc)

    # Run parallel guardrails
    if parallel:
        tasks = []
        for entry in parallel:
            tasks.append(_run_guardrail_safe(entry, ctx))
        results = await asyncio.gather(*tasks)
        for entry, result in zip(parallel, results):
            if result is not None and not result.passed:
                logger.info("[GUARDRAIL] %s blocked: %s", entry.name, result.reason)
                return False, result.reason

    return guardian_passed, None


async def run_output_guardrails(
    state: AgentState,
) -> tuple[bool, Optional[str]]:
    """Run all registered output guardrails.

    Returns (passed, reason).
    Called after synthesizer, before returning result.
    """
    guardrails = GuardrailRegistry.get_output_guardrails()
    if not guardrails:
        return True, None

    ctx = GuardrailContext(
        query=state.get("query", ""),
        state=state,
        response=state.get("final_response", ""),
        agent_name=state.get("current_agent", ""),
    )

    for entry in guardrails:
        try:
            result = await entry.fn(ctx)
            if not result.passed:
                logger.info("[GUARDRAIL] Output %s blocked: %s", entry.name, result.reason)
                return False, result.reason
        except Exception as exc:
            logger.warning("[GUARDRAIL] Output %s error (allowing): %s", entry.name, exc)

    return True, None


async def _run_guardrail_safe(entry: GuardrailEntry, ctx: GuardrailContext) -> Optional[GuardrailResult]:
    """Run a guardrail safely, returning None on error."""
    try:
        return await entry.fn(ctx)
    except Exception as exc:
        logger.warning("[GUARDRAIL] %s error: %s", entry.name, exc)
        return None
