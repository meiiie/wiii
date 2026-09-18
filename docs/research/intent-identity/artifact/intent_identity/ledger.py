"""Durable controller ledger (SQLite, WAL, synchronous=FULL).

Stores immutable contracts, per-occurrence key/payload bindings, occurrence
states, receipts and an event log. Conversation state is never consulted to
restore these facts.

Occurrence states: ``ready -> held -> done``; ``unresolved`` is a terminal
"held but no longer safely retryable" state used by the retention-aware and
opaque-profile recovery paths (safe, not complete).
"""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

from .contract import ApprovalContract, EffectSpec, obligation_key

SCHEMA = """
CREATE TABLE IF NOT EXISTS contracts (
  instance_id TEXT PRIMARY KEY,
  principal TEXT NOT NULL,
  approval_event TEXT NOT NULL,
  contract_json TEXT NOT NULL,
  created_at REAL NOT NULL,
  UNIQUE(principal, approval_event)
);
CREATE TABLE IF NOT EXISTS occurrences (
  instance_id TEXT NOT NULL,
  occurrence_id TEXT NOT NULL,
  effect_key TEXT NOT NULL UNIQUE,
  payload_hash TEXT NOT NULL,
  state TEXT NOT NULL,
  generation INTEGER NOT NULL DEFAULT 0,
  worker_id TEXT,
  held_at REAL,
  lease_expires REAL,
  retention_deadline REAL,
  receipt TEXT,
  PRIMARY KEY (instance_id, occurrence_id)
);
CREATE TABLE IF NOT EXISTS requests (
  request_id TEXT PRIMARY KEY,
  instance_id TEXT NOT NULL,
  batch_class TEXT NOT NULL,
  members_json TEXT NOT NULL,
  sent_at REAL NOT NULL,
  reconciled INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  worker_id TEXT,
  instance_id TEXT,
  occurrence_id TEXT,
  kind TEXT NOT NULL,
  detail TEXT
);
"""


@dataclass
class Occurrence:
    instance_id: str
    occurrence_id: str
    effect_key: str
    payload_hash: str
    state: str
    generation: int
    worker_id: Optional[str]
    held_at: Optional[float]
    lease_expires: Optional[float]
    retention_deadline: Optional[float]
    receipt: Optional[str]


class Ledger:
    def __init__(self, path: str | Path, worker_id: str = "controller"):
        self.path = str(path)
        self.worker_id = worker_id
        self.conn = sqlite3.connect(self.path, timeout=30.0, isolation_level=None)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=FULL")
        self.conn.execute("PRAGMA busy_timeout=30000")
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            yield self.conn
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise
        else:
            self.conn.execute("COMMIT")

    def log(self, kind: str, instance_id: str | None = None, occurrence_id: str | None = None, **detail) -> None:
        self.conn.execute(
            "INSERT INTO events(ts, worker_id, instance_id, occurrence_id, kind, detail) VALUES (?,?,?,?,?,?)",
            (time.time(), self.worker_id, instance_id, occurrence_id, kind, json.dumps(detail, sort_keys=True)),
        )

    # -- contracts -----------------------------------------------------------

    def register_contract(self, contract: ApprovalContract) -> ApprovalContract:
        """Insert a contract; re-presenting the same approval event recovers the
        existing contract instead of creating a second instance."""
        with self.tx() as c:
            row = c.execute(
                "SELECT contract_json FROM contracts WHERE principal=? AND approval_event=?",
                (contract.principal, contract.approval_event),
            ).fetchone()
            if row:
                return ApprovalContract.from_json(row[0])
            c.execute(
                "INSERT INTO contracts(instance_id, principal, approval_event, contract_json, created_at) VALUES (?,?,?,?,?)",
                (contract.instance_id, contract.principal, contract.approval_event, contract.to_json(), time.time()),
            )
            for occ, spec in contract.obligations.items():
                c.execute(
                    "INSERT INTO occurrences(instance_id, occurrence_id, effect_key, payload_hash, state) VALUES (?,?,?,?, 'ready')",
                    (contract.instance_id, occ, obligation_key(contract.instance_id, occ), spec.payload_hash()),
                )
            self.log("contract-registered", contract.instance_id, n=len(contract.obligations))
        return contract

    def load_contract(self, instance_id: str) -> ApprovalContract:
        row = self.conn.execute(
            "SELECT contract_json FROM contracts WHERE instance_id=?", (instance_id,)
        ).fetchone()
        if not row:
            raise KeyError(instance_id)
        return ApprovalContract.from_json(row[0])

    # -- occurrences ---------------------------------------------------------

    def get(self, instance_id: str, occurrence_id: str) -> Occurrence:
        row = self.conn.execute(
            "SELECT instance_id, occurrence_id, effect_key, payload_hash, state, generation, worker_id, held_at, lease_expires, retention_deadline, receipt FROM occurrences WHERE instance_id=? AND occurrence_id=?",
            (instance_id, occurrence_id),
        ).fetchone()
        if not row:
            raise KeyError((instance_id, occurrence_id))
        return Occurrence(*row)

    def states(self, instance_id: str) -> dict[str, str]:
        return dict(
            self.conn.execute(
                "SELECT occurrence_id, state FROM occurrences WHERE instance_id=? ORDER BY occurrence_id",
                (instance_id,),
            ).fetchall()
        )

    def reserve(
        self,
        instance_id: str,
        occurrence_id: str,
        lease_seconds: float,
        retention_seconds: Optional[float],
        predecessor: Optional[str] = None,
    ) -> tuple[bool, Occurrence]:
        """Atomically move ready->held, or take over a held occurrence whose
        lease expired or whose holder is the predecessor this worker restarts.

        Returns (was_previously_held, occurrence_after). The retention
        deadline is set only on the first dispatch of a generation and is not
        extended by a takeover: the sink's window started at the first send.
        """
        now = time.time()
        with self.tx() as c:
            occ = self.get(instance_id, occurrence_id)
            if occ.state == "done" or occ.state == "unresolved":
                return False, occ
            if occ.state == "held":
                takeover_ok = (occ.lease_expires or 0) < now or (
                    predecessor is not None and occ.worker_id == predecessor
                )
                if not takeover_ok:
                    return False, occ
                c.execute(
                    "UPDATE occurrences SET worker_id=?, lease_expires=? WHERE instance_id=? AND occurrence_id=?",
                    (self.worker_id, now + lease_seconds, instance_id, occurrence_id),
                )
                self.log("takeover", instance_id, occurrence_id, previous_worker=occ.worker_id)
                return True, self.get(instance_id, occurrence_id)
            deadline = None if retention_seconds is None else now + retention_seconds
            c.execute(
                "UPDATE occurrences SET state='held', worker_id=?, held_at=?, lease_expires=?, retention_deadline=? WHERE instance_id=? AND occurrence_id=? AND state='ready'",
                (self.worker_id, now, now + lease_seconds, deadline, instance_id, occurrence_id),
            )
            self.log("reserved", instance_id, occurrence_id)
            return False, self.get(instance_id, occurrence_id)

    def confirm(self, instance_id: str, occurrence_id: str, receipt: str, payload_hash: str, effect_key: str) -> None:
        with self.tx() as c:
            occ = self.get(instance_id, occurrence_id)
            if occ.payload_hash != payload_hash or occ.effect_key != effect_key:
                raise ValueError("provider response does not bind to the reserved occurrence")
            c.execute(
                "UPDATE occurrences SET state='done', receipt=? WHERE instance_id=? AND occurrence_id=?",
                (receipt, instance_id, occurrence_id),
            )
            self.log("done", instance_id, occurrence_id, receipt=receipt)

    def mark_unresolved(self, instance_id: str, occurrence_id: str, reason: str) -> None:
        with self.tx() as c:
            c.execute(
                "UPDATE occurrences SET state='unresolved' WHERE instance_id=? AND occurrence_id=? AND state='held'",
                (instance_id, occurrence_id),
            )
            self.log("unresolved", instance_id, occurrence_id, reason=reason)

    def rekey(self, instance_id: str, occurrence_id: str, new_key: str, generation: int) -> None:
        """Bind a fresh key after a certified no-effect/fence on the old one."""
        with self.tx() as c:
            c.execute(
                "UPDATE occurrences SET effect_key=?, generation=?, retention_deadline=NULL WHERE instance_id=? AND occurrence_id=?",
                (new_key, generation, instance_id, occurrence_id),
            )
            self.log("rekeyed", instance_id, occurrence_id, generation=generation)

    def spec_for(self, contract: ApprovalContract, occurrence_id: str) -> EffectSpec:
        return contract.spec(occurrence_id)

    # -- request journal (structured evidence) --------------------------------

    def record_request(self, request_id: str, instance_id: str, batch_class: str, members: list[str]) -> None:
        """Journal one multi-entry request before transport: membership, order
        and the provider's documented processing class."""
        with self.tx() as c:
            c.execute(
                "INSERT INTO requests(request_id, instance_id, batch_class, members_json, sent_at) VALUES (?,?,?,?,?)",
                (request_id, instance_id, batch_class, json.dumps(members), time.time()),
            )
            self.log("request-journaled", instance_id, kind_detail=batch_class, members=members)

    def open_requests(self, instance_id: str) -> list[tuple[str, str, list[str]]]:
        rows = self.conn.execute(
            "SELECT request_id, batch_class, members_json FROM requests WHERE instance_id=? AND reconciled=0 ORDER BY sent_at",
            (instance_id,),
        ).fetchall()
        return [(r[0], r[1], json.loads(r[2])) for r in rows]

    def close_request(self, request_id: str) -> None:
        with self.tx() as c:
            c.execute("UPDATE requests SET reconciled=1 WHERE request_id=?", (request_id,))
