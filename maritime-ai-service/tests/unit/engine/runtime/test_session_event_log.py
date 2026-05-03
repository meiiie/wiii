"""Phase 5 session event log — Runtime Migration #207.

Locks in the in-memory backend contract: monotonic seq, org filtering,
dict-payload immutability, since_seq replay window.
"""

from __future__ import annotations

import pytest

from app.engine.runtime.session_event_log import (
    InMemorySessionEventLog,
    SessionEvent,
    get_session_event_log,
)


@pytest.fixture
def log() -> InMemorySessionEventLog:
    return InMemorySessionEventLog()


# ── append ──

async def test_append_assigns_monotonic_seq_per_session(log):
    e1 = await log.append(session_id="s1", event_type="user_message", payload={"text": "hi"})
    e2 = await log.append(session_id="s1", event_type="assistant_message", payload={"text": "hello"})
    e3 = await log.append(session_id="s2", event_type="user_message", payload={"text": "x"})
    assert e1.seq == 1
    assert e2.seq == 2
    assert e3.seq == 1  # different session, fresh counter


async def test_append_returns_immutable_event(log):
    payload = {"q": "x"}
    event = await log.append(session_id="s", event_type="tool_call", payload=payload)
    assert isinstance(event, SessionEvent)
    payload["q"] = "mutated"
    assert event.payload == {"q": "x"}  # snapshot, not aliased


async def test_append_records_org_id_when_supplied(log):
    event = await log.append(
        session_id="s", event_type="user_message", payload={}, org_id="org-1"
    )
    assert event.org_id == "org-1"


# ── get_events ──

async def test_get_events_returns_in_append_order(log):
    await log.append(session_id="s", event_type="user_message", payload={"i": 1})
    await log.append(session_id="s", event_type="user_message", payload={"i": 2})
    await log.append(session_id="s", event_type="user_message", payload={"i": 3})
    events = await log.get_events(session_id="s")
    assert [e.payload["i"] for e in events] == [1, 2, 3]


async def test_get_events_unknown_session_returns_empty(log):
    assert await log.get_events(session_id="missing") == []


async def test_get_events_since_seq_filters_window(log):
    await log.append(session_id="s", event_type="x", payload={"i": 1})
    await log.append(session_id="s", event_type="x", payload={"i": 2})
    await log.append(session_id="s", event_type="x", payload={"i": 3})
    events = await log.get_events(session_id="s", since_seq=1)
    assert [e.seq for e in events] == [2, 3]


async def test_get_events_filters_by_org(log):
    await log.append(session_id="s", event_type="x", payload={}, org_id="A")
    await log.append(session_id="s", event_type="x", payload={}, org_id="B")
    await log.append(session_id="s", event_type="x", payload={}, org_id="A")
    a_events = await log.get_events(session_id="s", org_id="A")
    assert all(e.org_id == "A" for e in a_events)
    assert len(a_events) == 2


# ── latest_seq ──

async def test_latest_seq_zero_for_unknown_session(log):
    assert await log.latest_seq(session_id="missing") == 0


async def test_latest_seq_tracks_global_seq_without_org(log):
    await log.append(session_id="s", event_type="x", payload={})
    await log.append(session_id="s", event_type="x", payload={})
    assert await log.latest_seq(session_id="s") == 2


async def test_latest_seq_respects_org_filter(log):
    await log.append(session_id="s", event_type="x", payload={}, org_id="A")
    await log.append(session_id="s", event_type="x", payload={}, org_id="B")
    await log.append(session_id="s", event_type="x", payload={}, org_id="A")
    assert await log.latest_seq(session_id="s", org_id="A") == 3
    assert await log.latest_seq(session_id="s", org_id="B") == 2
    assert await log.latest_seq(session_id="s", org_id="C") == 0


# ── singleton ──

def test_get_session_event_log_returns_singleton():
    a = get_session_event_log()
    b = get_session_event_log()
    assert a is b


# ── concurrency safety ──

async def test_concurrent_appends_preserve_monotonic_seq(log):
    import asyncio

    async def write(idx: int) -> SessionEvent:
        return await log.append(
            session_id="s", event_type="x", payload={"i": idx}
        )

    events = await asyncio.gather(*(write(i) for i in range(20)))
    seqs = sorted(e.seq for e in events)
    assert seqs == list(range(1, 21))


# ── PostgresSessionEventLog ──

class _FakeRow(dict):
    """Mimic asyncpg.Record minimal interface."""

    def __getitem__(self, key):
        return super().__getitem__(key)


class _FakeConn:
    def __init__(self, rows=None, fetchval_value=0, raise_unique_n_times: int = 0):
        self.rows = rows or []
        self.fetchval_value = fetchval_value
        self.raise_unique_n_times = raise_unique_n_times
        self.fetchrow_calls: list[tuple] = []
        self.fetch_calls: list[tuple] = []
        self.fetchval_calls: list[tuple] = []

    async def fetchrow(self, sql, *args):
        self.fetchrow_calls.append((sql, args))
        if self.raise_unique_n_times > 0:
            self.raise_unique_n_times -= 1
            import asyncpg
            raise asyncpg.UniqueViolationError("duplicate seq")
        if self.rows:
            return self.rows.pop(0)
        # Default: synthesise a row using args.
        session_id, org_id, event_type, payload_json = args
        import json
        return _FakeRow(
            id=1,
            session_id=session_id,
            org_id=org_id,
            event_type=event_type,
            payload=payload_json,
            seq=1,
            created_at="2026-05-03T00:00:00Z",
        )

    async def fetch(self, sql, *args):
        self.fetch_calls.append((sql, args))
        return self.rows

    async def fetchval(self, sql, *args):
        self.fetchval_calls.append((sql, args))
        return self.fetchval_value


class _FakePool:
    def __init__(self, conn: _FakeConn):
        self._conn = conn

    def acquire(self):
        outer = self

        class _CtxManager:
            async def __aenter__(self):
                return outer._conn

            async def __aexit__(self, *exc):
                return None

        return _CtxManager()


@pytest.fixture
def fake_conn() -> _FakeConn:
    return _FakeConn()


@pytest.fixture
def pg_log(monkeypatch, fake_conn: _FakeConn):
    """PostgresSessionEventLog with the asyncpg pool mocked out."""
    from app.engine.runtime.session_event_log import PostgresSessionEventLog

    log = PostgresSessionEventLog()
    fake_pool = _FakePool(fake_conn)

    async def _pool_stub():
        return fake_pool

    monkeypatch.setattr(log, "_pool", _pool_stub)
    return log


async def test_postgres_append_round_trips_payload(pg_log, fake_conn):
    event = await pg_log.append(
        session_id="s1", event_type="user_message", payload={"text": "hi"}, org_id="org-1"
    )
    assert event.session_id == "s1"
    assert event.event_type == "user_message"
    assert event.payload == {"text": "hi"}
    assert event.org_id == "org-1"
    assert event.seq == 1
    # SQL was issued with the right shape — no jsonb cast missing etc.
    sql_first, args = fake_conn.fetchrow_calls[0]
    assert "INSERT INTO session_events" in sql_first
    assert "$4::jsonb" in sql_first
    assert args[0] == "s1"
    assert args[2] == "user_message"


async def test_postgres_append_retries_on_unique_violation(pg_log, fake_conn):
    fake_conn.raise_unique_n_times = 2  # succeed on 3rd try
    event = await pg_log.append(
        session_id="s1", event_type="x", payload={}
    )
    assert event.seq == 1
    assert len(fake_conn.fetchrow_calls) == 3


async def test_postgres_append_gives_up_after_max_retries(pg_log, fake_conn):
    fake_conn.raise_unique_n_times = 99  # always fail
    with pytest.raises(RuntimeError, match="exceeded retries"):
        await pg_log.append(session_id="s1", event_type="x", payload={})


async def test_postgres_get_events_filters_by_org(pg_log, fake_conn):
    fake_conn.rows = [
        _FakeRow(
            id=1, session_id="s", org_id="A", event_type="x",
            payload='{"i": 1}', seq=1, created_at=None,
        ),
        _FakeRow(
            id=2, session_id="s", org_id="A", event_type="x",
            payload='{"i": 2}', seq=2, created_at=None,
        ),
    ]
    events = await pg_log.get_events(session_id="s", org_id="A", since_seq=0)
    sql, args = fake_conn.fetch_calls[0]
    assert "ORDER BY seq ASC" in sql
    assert "session_id = $1" in sql
    assert "org_id = $2" in sql
    assert "seq > $3" in sql
    assert args == ("s", "A", 0)
    assert len(events) == 2
    assert events[0].payload == {"i": 1}


async def test_postgres_latest_seq_with_org(pg_log, fake_conn):
    fake_conn.fetchval_value = 5
    seq = await pg_log.latest_seq(session_id="s", org_id="A")
    assert seq == 5
    sql, args = fake_conn.fetchval_calls[0]
    assert "WHERE session_id = $1 AND org_id = $2" in sql
    assert args == ("s", "A")


async def test_postgres_latest_seq_without_org(pg_log, fake_conn):
    fake_conn.fetchval_value = 0
    seq = await pg_log.latest_seq(session_id="missing")
    assert seq == 0


async def test_postgres_payload_revives_str_jsonb(pg_log, fake_conn):
    """asyncpg returns jsonb as str; backend must json.loads."""
    fake_conn.rows = [
        _FakeRow(
            id=1, session_id="s", org_id=None, event_type="x",
            payload='{"a": 1, "b": "two"}', seq=1, created_at=None,
        ),
    ]
    events = await pg_log.get_events(session_id="s")
    assert events[0].payload == {"a": 1, "b": "two"}


# ── get_session_event_log routing ──

def test_get_session_event_log_returns_inmemory_when_flag_off(monkeypatch):
    from app.engine.runtime import session_event_log as mod

    mod._reset_for_tests()
    fake_settings = type("S", (), {"enable_session_event_log": False})()
    monkeypatch.setattr(
        "app.core.config.settings", fake_settings, raising=False
    )
    log = mod.get_session_event_log()
    assert isinstance(log, mod.InMemorySessionEventLog)


def test_get_session_event_log_returns_postgres_when_flag_on(monkeypatch):
    from app.engine.runtime import session_event_log as mod

    mod._reset_for_tests()
    fake_settings = type("S", (), {"enable_session_event_log": True})()
    monkeypatch.setattr(
        "app.core.config.settings", fake_settings, raising=False
    )
    log = mod.get_session_event_log()
    assert isinstance(log, mod.PostgresSessionEventLog)
    mod._reset_for_tests()
