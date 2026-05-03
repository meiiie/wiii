"""Chaos scenario: ChatService raises mid-turn.

Asserts the Phase 19 contract: native_dispatch still emits the
``assistant_message`` event with ``status=error`` even when the inner
ChatService call blows up. wake() / replay must always see a clean
closure — partial state corrupts the regression net.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.engine.runtime.native_dispatch import native_chat_dispatch


def _make_request(*, session_id="chaos-1", org_id="chaos-org"):
    return SimpleNamespace(
        user_id="chaos-user",
        session_id=session_id,
        message="trigger the bomb",
        organization_id=org_id,
        role=SimpleNamespace(value="student"),
        domain_id="maritime",
    )


@pytest.mark.asyncio
async def test_chatservice_runtime_error_records_clean_closure(
    wiii_session_log, runtime_metrics_reset
):
    """Provider crash → native_dispatch records error, propagates exception."""
    fake_service = SimpleNamespace(
        process_message=AsyncMock(side_effect=RuntimeError("provider exploded"))
    )
    with patch(
        "app.services.chat_service.get_chat_service", return_value=fake_service
    ):
        with pytest.raises(RuntimeError, match="provider exploded"):
            await native_chat_dispatch(
                _make_request(), event_log=wiii_session_log
            )

    events = await wiii_session_log.get_events(session_id="chaos-1")
    types = [e.event_type for e in events]
    # Both bookends present so wake() sees a clean closure.
    assert types == ["user_message", "assistant_message"]
    assistant = events[1].payload
    assert assistant["status"] == "error"
    assert "provider exploded" in assistant["error"]
    assert assistant["text"] == ""
    # Error metric incremented — alerting rule reads from this.
    snap = runtime_metrics_reset.snapshot()
    assert (
        snap["counters"]["runtime.native_dispatch.runs"][
            (("status", "error"),)
        ]
        == 1
    )


@pytest.mark.asyncio
async def test_chatservice_timeout_error_treated_same_as_runtime_error(
    wiii_session_log, runtime_metrics_reset
):
    """Different exception class → same closure protocol."""
    fake_service = SimpleNamespace(
        process_message=AsyncMock(side_effect=TimeoutError("provider timeout"))
    )
    with patch(
        "app.services.chat_service.get_chat_service", return_value=fake_service
    ):
        with pytest.raises(TimeoutError):
            await native_chat_dispatch(
                _make_request(session_id="chaos-2"),
                event_log=wiii_session_log,
            )

    events = await wiii_session_log.get_events(session_id="chaos-2")
    assert [e.event_type for e in events] == [
        "user_message",
        "assistant_message",
    ]
    assert events[1].payload["status"] == "error"
    assert "TimeoutError" in events[1].payload["error"]


@pytest.mark.asyncio
async def test_consecutive_errors_increment_counter_correctly(
    wiii_session_log, runtime_metrics_reset
):
    """5 consecutive failures → counter reads 5 — alerting rules need this."""
    fake_service = SimpleNamespace(
        process_message=AsyncMock(side_effect=RuntimeError("oops"))
    )
    with patch(
        "app.services.chat_service.get_chat_service", return_value=fake_service
    ):
        for i in range(5):
            with pytest.raises(RuntimeError):
                await native_chat_dispatch(
                    _make_request(session_id=f"chaos-loop-{i}"),
                    event_log=wiii_session_log,
                )

    snap = runtime_metrics_reset.snapshot()
    assert (
        snap["counters"]["runtime.native_dispatch.runs"][
            (("status", "error"),)
        ]
        == 5
    )
    # Each session has its own pair of events — no cross-session bleed.
    for i in range(5):
        events = await wiii_session_log.get_events(session_id=f"chaos-loop-{i}")
        assert len(events) == 2
