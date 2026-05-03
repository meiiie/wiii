"""Chaos scenario: 50 successful turns populate Phase 13 metrics correctly.

Validates that the Phase 13 metrics façade — counter + duration
histogram — produces sensible aggregates under sustained load. If
this scenario degrades, the SLO doc's p50/p99 targets become
unverifiable, so this test is part of the "metrics pipeline working
end-to-end" gate.
"""

from __future__ import annotations

import statistics
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.engine.runtime.native_dispatch import native_chat_dispatch


def _make_request(idx: int):
    return SimpleNamespace(
        user_id=f"chaos-volume-{idx}",
        session_id=f"chaos-volume-session-{idx}",
        message=f"prompt {idx}",
        organization_id="chaos-org",
        role=SimpleNamespace(value="student"),
        domain_id="maritime",
    )


def _make_response(text: str = "ok"):
    return SimpleNamespace(
        message=text,
        metadata={"latency_ms": 100},
        agent_type=SimpleNamespace(value="rag"),
    )


@pytest.mark.asyncio
async def test_50_successful_runs_populate_metrics(
    wiii_session_log, runtime_metrics_reset
):
    fake_service = SimpleNamespace(
        process_message=AsyncMock(return_value=_make_response())
    )
    with patch(
        "app.services.chat_service.get_chat_service", return_value=fake_service
    ):
        for i in range(50):
            await native_chat_dispatch(
                _make_request(i), event_log=wiii_session_log
            )

    snap = runtime_metrics_reset.snapshot()
    # Counter: exactly 50 successes.
    assert (
        snap["counters"]["runtime.native_dispatch.runs"][
            (("status", "success"),)
        ]
        == 50
    )
    # Histogram: 50 observations, all non-negative.
    durations = snap["histograms"]["runtime.native_dispatch.duration_ms"][
        (("status", "success"),)
    ]
    assert len(durations) == 50
    assert all(d >= 0 for d in durations)
    # Median sanity check — should be tiny since the inner call is
    # mocked. If this becomes flaky, the in-memory sink has slowed down.
    median_ms = statistics.median(durations)
    assert median_ms < 100, f"median latency {median_ms}ms suspiciously slow"


@pytest.mark.asyncio
async def test_mixed_success_and_error_buckets_separated(
    wiii_session_log, runtime_metrics_reset
):
    """Status label must keep success / error counts distinct."""
    successes = [_make_response() for _ in range(7)]
    fake_service = SimpleNamespace(process_message=AsyncMock())

    # Interleave successes and errors so timing variance doesn't corrupt
    # the per-bucket count.
    fake_service.process_message.side_effect = [
        successes[0],
        RuntimeError("boom"),
        successes[1],
        successes[2],
        RuntimeError("boom"),
        RuntimeError("boom"),
        successes[3],
        successes[4],
        successes[5],
        successes[6],
    ]
    with patch(
        "app.services.chat_service.get_chat_service", return_value=fake_service
    ):
        for i in range(10):
            try:
                await native_chat_dispatch(
                    _make_request(i), event_log=wiii_session_log
                )
            except RuntimeError:
                pass

    snap = runtime_metrics_reset.snapshot()
    counters = snap["counters"]["runtime.native_dispatch.runs"]
    assert counters[(("status", "success"),)] == 7
    assert counters[(("status", "error"),)] == 3
