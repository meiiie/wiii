"""Phase 13 runtime metrics façade — Runtime Migration #207.

Locks the contract: every metric call lands in the in-memory sink
regardless of OTel availability, so tests + /admin endpoints have a
reliable substrate. Label hashing is order-independent. The façade never
raises — metrics must not break a request.
"""

from __future__ import annotations

import threading

import pytest

from app.engine.runtime import runtime_metrics as rm


@pytest.fixture(autouse=True)
def reset_metrics():
    rm._reset_for_tests()
    yield
    rm._reset_for_tests()


def test_inc_counter_records_in_sink():
    rm.inc_counter("foo.count")
    snap = rm.snapshot()
    assert snap["counters"]["foo.count"][()] == 1


def test_inc_counter_with_labels_groups_by_label_set():
    rm.inc_counter("foo.count", labels={"a": "1"})
    rm.inc_counter("foo.count", labels={"a": "1"})
    rm.inc_counter("foo.count", labels={"a": "2"})
    snap = rm.snapshot()
    buckets = snap["counters"]["foo.count"]
    # Two distinct label-buckets.
    assert len(buckets) == 2
    assert buckets[(("a", "1"),)] == 2
    assert buckets[(("a", "2"),)] == 1


def test_inc_counter_label_order_does_not_matter():
    """Labels are sorted into the bucket key — same labels in different order
    must hash to the same bucket."""
    rm.inc_counter("foo", labels={"a": "1", "b": "2"})
    rm.inc_counter("foo", labels={"b": "2", "a": "1"})
    snap = rm.snapshot()
    assert len(snap["counters"]["foo"]) == 1
    assert sum(snap["counters"]["foo"].values()) == 2


def test_inc_counter_with_explicit_by():
    rm.inc_counter("foo", by=5)
    rm.inc_counter("foo", by=3)
    snap = rm.snapshot()
    assert snap["counters"]["foo"][()] == 8


def test_set_gauge_overwrites_value():
    rm.set_gauge("temperature", 70.0)
    rm.set_gauge("temperature", 72.5)
    snap = rm.snapshot()
    assert snap["gauges"]["temperature"][()] == 72.5


def test_record_latency_appends_to_histogram():
    rm.record_latency_ms("rag.duration", 120.0)
    rm.record_latency_ms("rag.duration", 80.0)
    rm.record_latency_ms("rag.duration", 200.0)
    snap = rm.snapshot()
    assert snap["histograms"]["rag.duration"][()] == [120.0, 80.0, 200.0]


def test_time_block_records_duration():
    import time

    with rm.time_block("block.duration"):
        time.sleep(0.01)  # ~10ms
    snap = rm.snapshot()
    observed = snap["histograms"]["block.duration"][()]
    assert len(observed) == 1
    assert observed[0] >= 5  # generous threshold for CI noise


def test_time_block_records_even_on_exception():
    with pytest.raises(RuntimeError):
        with rm.time_block("block.duration", labels={"path": "fail"}):
            raise RuntimeError("boom")
    snap = rm.snapshot()
    assert (("path", "fail"),) in snap["histograms"]["block.duration"]


def test_thread_safety_concurrent_increments():
    """Counter math must be correct under contention."""

    def worker():
        for _ in range(1000):
            rm.inc_counter("concurrent")

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    snap = rm.snapshot()
    assert snap["counters"]["concurrent"][()] == 8 * 1000


def test_reset_clears_all_state():
    rm.inc_counter("a")
    rm.set_gauge("b", 1.0)
    rm.record_latency_ms("c", 5.0)
    rm._reset_for_tests()
    snap = rm.snapshot()
    assert snap["counters"] == {}
    assert snap["gauges"] == {}
    assert snap["histograms"] == {}


def test_snapshot_returns_independent_copy():
    rm.inc_counter("foo")
    snap1 = rm.snapshot()
    rm.inc_counter("foo")
    # Mutating the live sink does not affect the snapshot returned earlier.
    assert snap1["counters"]["foo"][()] == 1


# ── integration with hot paths ──


def test_lane_resolver_records_decision():
    from app.engine.runtime.lane_resolver import resolve_lane
    from app.engine.runtime.runtime_intent import RuntimeIntent

    intent = RuntimeIntent(
        needs_streaming=False,
        needs_tools=False,
        needs_structured_output=False,
        needs_vision=False,
    )
    resolve_lane(intent)
    resolve_lane(intent)
    snap = rm.snapshot()
    bucket = snap["counters"]["runtime.lane_resolver.decisions"]
    assert bucket[(("lane", "openai_compatible_http"),)] == 2


async def test_subagent_runner_records_runs(monkeypatch):
    from app.core import config as config_module
    from app.engine.runtime.session_event_log import InMemorySessionEventLog
    from app.engine.runtime.subagent_runner import (
        SubagentResult,
        SubagentRunner,
        SubagentTask,
    )

    monkeypatch.setattr(
        config_module.settings, "enable_subagent_isolation", True, raising=False
    )

    async def runner(task, child_id):
        return SubagentResult(status="success", summary="done")

    runner_obj = SubagentRunner(
        runner_callable=runner, event_log=InMemorySessionEventLog()
    )
    await runner_obj.run(SubagentTask(description="x", parent_session_id="p1"))

    snap = rm.snapshot()
    assert snap["counters"]["runtime.subagent.runs"][(("status", "success"),)] == 1
    durations = snap["histograms"]["runtime.subagent.duration_ms"][
        (("status", "success"),)
    ]
    assert len(durations) == 1
