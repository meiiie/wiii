"""Chaos scenario: SubagentRunner under provider failure.

Asserts the Phase 12 + 15 contract holds when the inner ChatService
bridge raises: parent log gets exactly the two bookend events, child
session id is recorded, error counter increments. Subagent isolation
must not regress when the subagent's runner blows up — the parent
can't recover if the closure isn't atomic.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.engine.runtime.subagent_runner import (
    SubagentRunner,
    SubagentTask,
)


@pytest.fixture
def enable_subagent(monkeypatch):
    from app.core import config as config_module

    monkeypatch.setattr(
        config_module.settings, "enable_subagent_isolation", True, raising=False
    )


@pytest.mark.asyncio
async def test_subagent_chatservice_bridge_provider_failure(
    enable_subagent, wiii_session_log, runtime_metrics_reset
):
    """ChatService raises inside the bridge → parent log still bookended."""
    from app.engine.runtime.subagent_chatservice_bridge import (
        chatservice_subagent_runner,
    )

    fake_service = SimpleNamespace(
        process_message=AsyncMock(side_effect=RuntimeError("provider 503"))
    )
    runner = SubagentRunner(
        runner_callable=chatservice_subagent_runner, event_log=wiii_session_log
    )
    with patch(
        "app.services.chat_service.get_chat_service", return_value=fake_service
    ):
        result = await runner.run(
            SubagentTask(
                description="Tìm Rule 13 COLREGs",
                parent_session_id="chaos-parent-1",
                parent_org_id="chaos-org",
            )
        )

    # Runner contract: status=error, error message present.
    assert result.status == "error"
    assert "provider 503" in (result.error or "")

    # Parent log: exactly the two bookend events. NO leak of the child's
    # working messages even though the inner call blew up.
    parent_events = await wiii_session_log.get_events(
        session_id="chaos-parent-1"
    )
    assert [e.event_type for e in parent_events] == [
        "subagent_started",
        "subagent_completed",
    ]
    completed_payload = parent_events[1].payload
    assert completed_payload["status"] == "error"
    assert "provider 503" in completed_payload["error"]

    # Metric incremented with the right status label.
    snap = runtime_metrics_reset.snapshot()
    assert (
        snap["counters"]["runtime.subagent.runs"][(("status", "error"),)]
        == 1
    )


@pytest.mark.asyncio
async def test_5_consecutive_subagent_failures_dont_corrupt_log(
    enable_subagent, wiii_session_log, runtime_metrics_reset
):
    """Repeated failures keep producing well-formed bookend pairs."""
    from app.engine.runtime.subagent_chatservice_bridge import (
        chatservice_subagent_runner,
    )

    fake_service = SimpleNamespace(
        process_message=AsyncMock(side_effect=RuntimeError("flaky"))
    )
    runner = SubagentRunner(
        runner_callable=chatservice_subagent_runner, event_log=wiii_session_log
    )
    with patch(
        "app.services.chat_service.get_chat_service", return_value=fake_service
    ):
        for i in range(5):
            await runner.run(
                SubagentTask(
                    description=f"task-{i}",
                    parent_session_id=f"chaos-parent-loop-{i}",
                )
            )

    # Each parent has exactly 2 events.
    for i in range(5):
        events = await wiii_session_log.get_events(
            session_id=f"chaos-parent-loop-{i}"
        )
        assert [e.event_type for e in events] == [
            "subagent_started",
            "subagent_completed",
        ]
    # Counter aggregates correctly.
    snap = runtime_metrics_reset.snapshot()
    assert (
        snap["counters"]["runtime.subagent.runs"][(("status", "error"),)]
        == 5
    )
