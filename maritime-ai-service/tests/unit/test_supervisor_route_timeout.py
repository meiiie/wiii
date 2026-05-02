"""Issue #206: bounded sync supervisor route latency.

Verifies:
1. `resolve_supervisor_route_timeout_seconds_impl` returns sensible defaults
   and honors a settings override.
2. When `_route_structured` stalls past the bound, `route()` falls back to
   `_rule_based_route()` with `method="rule_based_timeout"` and emits a
   timeline entry so sync responses can still report routing latency.
3. When `_route_structured` returns quickly, the bound is not engaged and
   the structured route's decision passes through unchanged.
"""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import patch

import pytest

from app.engine.multi_agent.lane_timeout_policy import (
    resolve_supervisor_route_timeout_seconds_impl,
)
from app.engine.multi_agent.supervisor import SupervisorAgent


# ── policy resolver ──

def test_route_timeout_default_is_ten_seconds():
    assert resolve_supervisor_route_timeout_seconds_impl(
        state={}, settings_obj=None
    ) == 10.0


def test_route_timeout_honors_positive_settings_override():
    class FakeSettings:
        supervisor_route_sync_timeout_seconds = 4.5

    assert resolve_supervisor_route_timeout_seconds_impl(
        state={}, settings_obj=FakeSettings()
    ) == 4.5


def test_route_timeout_ignores_non_positive_override():
    class FakeSettings:
        supervisor_route_sync_timeout_seconds = 0

    assert resolve_supervisor_route_timeout_seconds_impl(
        state={}, settings_obj=FakeSettings()
    ) == 10.0


def test_route_timeout_ignores_invalid_type_override():
    class FakeSettings:
        supervisor_route_sync_timeout_seconds = "fifteen"

    assert resolve_supervisor_route_timeout_seconds_impl(
        state={}, settings_obj=FakeSettings()
    ) == 10.0


# ── route() integration ──

@pytest.fixture
def supervisor_with_fast_llm():
    sup = SupervisorAgent()
    sup._llm = object()  # truthy stand-in; structured route is patched in tests
    return sup


@pytest.mark.asyncio
async def test_route_falls_back_to_rule_based_when_structured_route_times_out(
    supervisor_with_fast_llm,
):
    """Issue #206 core: stalled structured route → rule-based fallback."""
    state: dict[str, Any] = {
        "query": "Hi Wiii, trả lời thật ngắn để kiểm tra flow conversation local.",
        "context": {},
        "domain_config": {"domain_name": "AI"},
    }

    async def _stalled_route(*args, **kwargs):
        await asyncio.sleep(30)  # well above the test timeout we patch in
        return "rag_agent"

    fast_path_target = (
        "app.engine.multi_agent.supervisor.SupervisorAgent._conservative_fast_route"
    )
    structured_target = (
        "app.engine.multi_agent.supervisor.SupervisorAgent._route_structured"
    )
    timeout_target = (
        "app.engine.multi_agent.supervisor.resolve_supervisor_route_timeout_seconds_impl"
    )

    # NOTE: the timeout impl is imported lazily inside route(); patch the
    # function at the module where it's resolved at call time.
    with patch(fast_path_target, return_value=None), \
         patch(structured_target, side_effect=_stalled_route), \
         patch(
             "app.engine.multi_agent.lane_timeout_policy.resolve_supervisor_route_timeout_seconds_impl",
             return_value=0.05,
         ):
        chosen = await supervisor_with_fast_llm.route(state)

    metadata = state.get("routing_metadata") or {}
    assert metadata.get("method") == "rule_based_timeout"
    assert metadata.get("final_agent") == chosen
    assert "timeout" in metadata.get("reasoning", "").lower()

    timeline_entries = (state.get("_runtime_latency") or {}).get("timeline", [])
    assert any(
        e.get("stage") == "supervisor.route_timeout" for e in timeline_entries
    ), f"Expected supervisor.route_timeout in timeline, got {timeline_entries}"


@pytest.mark.asyncio
async def test_route_passes_through_when_structured_route_is_fast(
    supervisor_with_fast_llm,
):
    """Sanity: bound does not engage on fast structured routes."""
    state: dict[str, Any] = {
        "query": "Cần hỗ trợ tra cứu quy định.",
        "context": {},
        "domain_config": {"domain_name": "AI"},
    }

    async def _fast_route(*args, **kwargs):
        # Mark routing_metadata like the real impl would.
        s = args[6] if len(args) > 6 else kwargs.get("state")
        if isinstance(s, dict):
            s["routing_metadata"] = {
                "intent": "lookup",
                "confidence": 0.92,
                "reasoning": "structured route happy path",
                "method": "structured",
                "final_agent": "rag_agent",
            }
        return "rag_agent"

    fast_path_target = (
        "app.engine.multi_agent.supervisor.SupervisorAgent._conservative_fast_route"
    )
    structured_target = (
        "app.engine.multi_agent.supervisor.SupervisorAgent._route_structured"
    )

    with patch(fast_path_target, return_value=None), \
         patch(structured_target, side_effect=_fast_route):
        chosen = await supervisor_with_fast_llm.route(state)

    assert chosen == "rag_agent"
    metadata = state.get("routing_metadata") or {}
    assert metadata.get("method") == "structured"
    timeline_entries = (state.get("_runtime_latency") or {}).get("timeline", [])
    assert not any(
        e.get("stage") == "supervisor.route_timeout" for e in timeline_entries
    ), "Timeout entry should not appear on the fast path"
