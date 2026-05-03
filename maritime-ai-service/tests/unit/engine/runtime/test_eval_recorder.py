"""Phase 6 eval recorder — Runtime Migration #207.

Locks in JSONL on-disk shape, partition layout, path-traversal safety,
and the simple diff metric helper. Anything that consumes recordings
later (replay scripts, regression CI, dashboards) relies on this exact
contract.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.engine.runtime.eval_recorder import (
    EvalRecord,
    EvalRecorder,
    diff_records,
)


def _make_record(**overrides) -> EvalRecord:
    base = {
        "session_id": "s1",
        "request": {"messages": [{"role": "user", "content": "hi"}]},
    }
    base.update(overrides)
    return EvalRecord(**base)


# ── EvalRecord shape ──

def test_eval_record_defaults():
    rec = _make_record()
    assert rec.record_id  # uuid generated
    assert rec.org_id is None
    assert re.match(r"^\d{4}-\d{2}-\d{2}T", rec.timestamp)
    assert rec.retrieved_docs == []
    assert rec.tool_calls == []
    assert rec.response == ""
    assert rec.sources == []
    assert rec.metadata == {}
    assert rec.replay_seed is None


def test_eval_record_round_trips_through_json():
    rec = _make_record(response="hello", metadata={"latency_ms": 42})
    blob = rec.model_dump_json()
    revived = EvalRecord.model_validate_json(blob)
    assert revived.response == "hello"
    assert revived.metadata == {"latency_ms": 42}


# ── Recorder write/read ──

@pytest.fixture
def recorder(tmp_path: Path) -> EvalRecorder:
    return EvalRecorder(base_dir=tmp_path)


async def test_write_creates_partitioned_file(tmp_path: Path, recorder: EvalRecorder):
    rec = _make_record(org_id="org-1", session_id="sess-A")
    path = await recorder.write(rec)
    expected_day = rec.timestamp[:10]
    assert path == tmp_path / "org-1" / expected_day / "sess-A.jsonl"
    assert path.exists()


async def test_write_falls_back_for_personal_org(recorder: EvalRecorder):
    rec = _make_record(org_id=None)
    path = await recorder.write(rec)
    assert "_personal" in path.parts


async def test_write_appends_one_record_per_call(recorder: EvalRecorder):
    rec1 = _make_record(response="r1")
    rec2 = _make_record(response="r2")
    path1 = await recorder.write(rec1)
    path2 = await recorder.write(rec2)
    assert path1 == path2  # same partition (same session/day)
    lines = path1.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["response"] == "r1"
    assert json.loads(lines[1])["response"] == "r2"


async def test_write_path_traversal_is_neutralised(recorder: EvalRecorder, tmp_path: Path):
    """Hostile session_id must not escape base_dir."""
    rec = _make_record(session_id="../../../etc/passwd", org_id="../escape")
    path = await recorder.write(rec)
    # Path stays under base_dir.
    assert tmp_path in path.parents
    # Dangerous segments collapsed to underscores.
    assert ".." not in path.parts


async def test_read_session_returns_appended_records(recorder: EvalRecorder):
    rec1 = _make_record(response="r1")
    rec2 = _make_record(response="r2")
    await recorder.write(rec1)
    await recorder.write(rec2)
    day = rec1.timestamp[:10]
    records = await recorder.read_session(session_id="s1", day=day)
    assert [r.response for r in records] == ["r1", "r2"]


async def test_read_session_missing_partition_returns_empty(recorder: EvalRecorder):
    records = await recorder.read_session(session_id="missing", day="2026-01-01")
    assert records == []


async def test_read_session_skips_malformed_lines(tmp_path: Path, recorder: EvalRecorder):
    rec = _make_record(response="ok")
    path = await recorder.write(rec)
    # Inject a garbage line between valid ones.
    with path.open("a", encoding="utf-8") as f:
        f.write("not-json-at-all\n")
    rec2 = _make_record(response="next")
    await recorder.write(rec2)
    day = rec.timestamp[:10]
    records = await recorder.read_session(session_id="s1", day=day)
    # Only the two valid lines come back.
    assert [r.response for r in records] == ["ok", "next"]


async def test_list_sessions(recorder: EvalRecorder):
    a = _make_record(session_id="a")
    b = _make_record(session_id="b")
    await recorder.write(a)
    await recorder.write(b)
    day = a.timestamp[:10]
    listed = await recorder.list_sessions(day=day)
    assert listed == ["a", "b"]


# ── list_days ──

async def test_list_days_empty(recorder: EvalRecorder):
    assert await recorder.list_days() == []


async def test_list_days_returns_date_partitions(tmp_path: Path, recorder: EvalRecorder):
    # Manually create partitions to simulate multiple days.
    org_dir = tmp_path / "_personal"
    for day in ("2026-05-01", "2026-05-02", "2026-05-03"):
        (org_dir / day).mkdir(parents=True)
    days = await recorder.list_days()
    assert days == ["2026-05-01", "2026-05-02", "2026-05-03"]


async def test_list_days_filters_non_date_dirs(tmp_path: Path, recorder: EvalRecorder):
    org_dir = tmp_path / "_personal"
    (org_dir / "2026-05-01").mkdir(parents=True)
    (org_dir / "junk-folder").mkdir(parents=True)
    (org_dir / "2026").mkdir(parents=True)  # too short
    days = await recorder.list_days()
    assert days == ["2026-05-01"]


async def test_list_days_rejects_malformed_dates(tmp_path: Path, recorder: EvalRecorder):
    """Length+hyphen heuristic alone passes garbage like ``2026-XX-01`` —
    list_days must validate via strptime so callers can trust the output."""
    org_dir = tmp_path / "_personal"
    for name in ("2026-05-01", "2026-XX-01", "abcd-ef-gh", "2026-13-01", "2026-02-30"):
        (org_dir / name).mkdir(parents=True)
    days = await recorder.list_days()
    assert days == ["2026-05-01"]


# ── prune_older_than ──

async def test_prune_older_than_removes_old_partitions(tmp_path: Path, recorder: EvalRecorder):
    org_dir = tmp_path / "_personal"
    # Old: should be removed.
    old_day = org_dir / "2026-04-01"
    old_day.mkdir(parents=True)
    (old_day / "session_x.jsonl").write_text('{"n": 1}\n', encoding="utf-8")
    # Recent: should stay.
    recent_day = org_dir / "2026-05-02"
    recent_day.mkdir(parents=True)
    (recent_day / "session_y.jsonl").write_text('{"n": 2}\n', encoding="utf-8")

    removed = await recorder.prune_older_than(retention_days=7, today="2026-05-03")
    assert removed.get("_personal") == 1
    assert not old_day.exists()
    assert recent_day.exists()


async def test_prune_older_than_zero_retention_is_noop(tmp_path: Path, recorder: EvalRecorder):
    (tmp_path / "_personal" / "2026-04-01").mkdir(parents=True)
    removed = await recorder.prune_older_than(retention_days=0)
    assert removed == {}


async def test_prune_older_than_skips_malformed_day_dirs(
    tmp_path: Path, recorder: EvalRecorder
):
    org_dir = tmp_path / "_personal"
    (org_dir / "junk-folder").mkdir(parents=True)
    (org_dir / "not-a-date").mkdir(parents=True)
    removed = await recorder.prune_older_than(retention_days=1, today="2026-05-03")
    # Both garbage dirs left alone.
    assert removed == {}
    assert (org_dir / "junk-folder").exists()


async def test_prune_older_than_handles_multiple_orgs(
    tmp_path: Path, recorder: EvalRecorder
):
    for org in ("org-1", "org-2"):
        old = tmp_path / org / "2026-04-01"
        old.mkdir(parents=True)
        (old / "s.jsonl").write_text("{}\n", encoding="utf-8")
    removed = await recorder.prune_older_than(retention_days=1, today="2026-05-03")
    assert removed == {"org-1": 1, "org-2": 1}


# ── diff_records ──

def test_diff_identical_response_full_overlap():
    rec = _make_record(response="hello world")
    diff = diff_records(rec, {"response": "hello world", "tool_calls": [], "sources": []})
    assert diff["token_jaccard"] == 1.0
    assert diff["tool_calls_match"] is True
    assert diff["sources_overlap"] == 1.0


def test_diff_partial_word_overlap():
    rec = _make_record(response="alpha beta gamma")
    diff = diff_records(rec, {"response": "alpha beta delta"})
    # 2 shared / 4 union = 0.5
    assert diff["token_jaccard"] == pytest.approx(0.5)


def test_diff_tool_call_mismatch_is_flagged():
    rec = _make_record(
        tool_calls=[{"name": "search", "args": {"q": "x"}}],
        response="r",
    )
    diff = diff_records(
        rec,
        {
            "response": "r",
            "tool_calls": [{"name": "search", "args": {"q": "y"}}],
            "sources": [],
        },
    )
    assert diff["tool_calls_match"] is False


def test_diff_source_overlap_partial():
    rec = _make_record(
        sources=[{"id": "doc1"}, {"id": "doc2"}, {"id": "doc3"}],
    )
    diff = diff_records(
        rec,
        {"response": "", "tool_calls": [], "sources": [{"id": "doc1"}, {"id": "doc4"}]},
    )
    # 1 shared / 3 in original = ~0.333
    assert diff["sources_overlap"] == pytest.approx(1 / 3)


def test_diff_latency_delta_signed():
    rec = _make_record(metadata={"latency_ms": 100})
    diff = diff_records(rec, {"response": "", "latency_ms": 75})
    assert diff["latency_delta_ms"] == -25


def test_diff_handles_empty_responses():
    rec = _make_record(response="")
    diff = diff_records(rec, {"response": "", "tool_calls": [], "sources": []})
    assert diff["token_jaccard"] == 1.0  # both empty → identical
