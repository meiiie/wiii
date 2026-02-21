"""Subagent execution wrapper with timeout, retry, and fallback."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Tuple

from app.engine.multi_agent.subagents.config import FallbackBehavior, SubagentConfig
from app.engine.multi_agent.subagents.result import SubagentResult, SubagentStatus

logger = logging.getLogger(__name__)


async def execute_subagent(
    func: Callable,
    config: SubagentConfig,
    state: Dict[str, Any],
    **kwargs: Any,
) -> SubagentResult:
    """Execute a subagent coroutine with timeout and retry.

    Parameters
    ----------
    func:
        An ``async def`` accepting ``(state, **kwargs)`` and returning
        either a :class:`SubagentResult` or a plain ``dict``/``str``.
    config:
        Subagent-specific timeout, retry, and fallback settings.
    state:
        The current agent state (or subset thereof).

    Returns
    -------
    SubagentResult
        Always returns a result — never raises unless
        ``config.fallback_behavior == RAISE_ERROR``.
    """
    last_error: str | None = None
    start = time.monotonic()

    for attempt in range(config.max_retries + 1):
        attempt_start = time.monotonic()
        try:
            raw = await asyncio.wait_for(
                func(state, **kwargs),
                timeout=config.timeout_seconds,
            )

            duration = int((time.monotonic() - attempt_start) * 1000)

            if isinstance(raw, SubagentResult):
                raw.duration_ms = duration
                return raw

            # Wrap a plain dict / str into a SubagentResult
            return SubagentResult(
                status=SubagentStatus.SUCCESS,
                output=str(raw) if isinstance(raw, str) else "",
                data=raw if isinstance(raw, dict) else {},
                duration_ms=duration,
            )

        except asyncio.TimeoutError:
            last_error = (
                f"Timeout after {config.timeout_seconds}s "
                f"(attempt {attempt + 1}/{config.max_retries + 1})"
            )
            logger.warning("Subagent %s: %s", config.name, last_error)

        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            logger.error(
                "Subagent %s error (attempt %d): %s",
                config.name,
                attempt + 1,
                last_error,
            )

    # All retries exhausted -----------------------------------------------
    total_duration = int((time.monotonic() - start) * 1000)

    if config.fallback_behavior == FallbackBehavior.RAISE_ERROR:
        raise RuntimeError(f"Subagent {config.name} failed: {last_error}")

    is_timeout = last_error is not None and "Timeout" in last_error
    return SubagentResult(
        status=SubagentStatus.TIMEOUT if is_timeout else SubagentStatus.ERROR,
        error_message=last_error,
        duration_ms=total_duration,
    )


async def execute_parallel_subagents(
    tasks: List[Tuple[Callable, SubagentConfig, Dict[str, Any], Dict[str, Any]]],
    max_concurrent: int = 5,
) -> List[SubagentResult]:
    """Execute multiple subagent tasks in parallel.

    Parameters
    ----------
    tasks:
        A list of ``(func, config, state, kwargs)`` tuples.
    max_concurrent:
        Concurrency limit (semaphore).

    Returns
    -------
    list[SubagentResult]
        One result per input task, in the same order.  Exceptions inside
        individual tasks are caught and returned as ``SubagentResult``
        with ``status=ERROR``.
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def _guarded(
        func: Callable,
        config: SubagentConfig,
        state: Dict[str, Any],
        kwargs: Dict[str, Any],
    ) -> SubagentResult:
        async with semaphore:
            return await execute_subagent(func, config, state, **kwargs)

    coros = [_guarded(f, c, s, kw) for f, c, s, kw in tasks]
    raw_results = await asyncio.gather(*coros, return_exceptions=True)

    # Ensure every entry is a SubagentResult (wrap unexpected exceptions)
    results: List[SubagentResult] = []
    for r in raw_results:
        if isinstance(r, SubagentResult):
            results.append(r)
        elif isinstance(r, Exception):
            results.append(
                SubagentResult(
                    status=SubagentStatus.ERROR,
                    error_message=f"{type(r).__name__}: {r}",
                )
            )
        else:
            results.append(
                SubagentResult(
                    status=SubagentStatus.SUCCESS,
                    output=str(r),
                )
            )
    return results
