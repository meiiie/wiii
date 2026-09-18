"""Loopback HTTP effect provider (synthetic sink) with three capability profiles.

The effect *is* the atomic insertion of a row into the provider's own SQLite
database (WAL, synchronous=FULL). No real notification is delivered.

Profiles (manuscript III.C):

* ``PD``: atomic per-key effect/receipt recording, immutable key/payload
  binding, dedup index retained for ``--ttl-seconds`` (None = forever).
  Duplicate key with same payload returns the recorded receipt; different
  payload under an existing key is rejected. No fence.
* ``PF``: no key dedup (a fresh dispatch duplicates), but ``POST /fence``
  finalizes a key: later deliveries under that key are rejected and the
  fence response is trustworthy final outcome evidence.
* ``PO``: no dedup, no fence. ``GET /lookup`` is point-in-time only.

``GET /lookup`` searches the retained *effects* table, not the dedup index,
modelling providers whose evidence contract (history/search) outlives their
idempotency contract. ``--evidence none`` disables it.

Every ``/execute`` call is logged so attempts can be distinguished from
effects. ``delay_ms`` in the request body delays commit to open an in-flight
window for the takeover study; it is a test hook, not a provider feature.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

SCHEMA = """
CREATE TABLE IF NOT EXISTS effects (
  effect_id INTEGER PRIMARY KEY AUTOINCREMENT,
  effect_key TEXT NOT NULL,
  instance_id TEXT NOT NULL,
  occurrence_id TEXT NOT NULL,
  payload_hash TEXT NOT NULL,
  payload TEXT NOT NULL,
  receipt TEXT NOT NULL,
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS dedup (
  effect_key TEXT PRIMARY KEY,
  effect_id INTEGER NOT NULL,
  payload_hash TEXT NOT NULL,
  expires_at REAL
);
CREATE TABLE IF NOT EXISTS fences (
  effect_key TEXT PRIMARY KEY,
  fenced_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS calls (
  call_id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  effect_key TEXT NOT NULL,
  occurrence_id TEXT NOT NULL,
  outcome TEXT NOT NULL
);
"""


class Sink:
    def __init__(self, path: str, profile: str, ttl_seconds: float | None, evidence: str):
        self.profile = profile
        self.ttl = ttl_seconds
        self.evidence = evidence
        self.lock = threading.Lock()
        self.conn = sqlite3.connect(path, timeout=30.0, isolation_level=None, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=FULL")
        self.conn.execute("PRAGMA busy_timeout=30000")
        self.conn.executescript(SCHEMA)

    def execute(self, req: dict) -> tuple[int, dict]:
        key, payload = req["key"], req["payload"]
        payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        if payload_hash != req["payload_hash"]:
            return 400, {"error": "payload hash mismatch"}
        delay = float(req.get("delay_ms", 0)) / 1000.0
        if delay:
            time.sleep(delay)
        now = time.time()
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                if self.conn.execute("SELECT 1 FROM fences WHERE effect_key=?", (key,)).fetchone():
                    self._call(now, key, req["occurrence_id"], "rejected-fenced")
                    self.conn.execute("COMMIT")
                    return 409, {"status": "rejected", "reason": "fenced"}
                if self.profile == "PD":
                    row = self.conn.execute(
                        "SELECT effect_id, payload_hash, expires_at FROM dedup WHERE effect_key=?", (key,)
                    ).fetchone()
                    if row and (row[2] is None or row[2] > now):
                        if row[1] != payload_hash:
                            self._call(now, key, req["occurrence_id"], "rejected-payload")
                            self.conn.execute("COMMIT")
                            return 409, {"status": "rejected", "reason": "payload differs under existing key"}
                        receipt = self.conn.execute(
                            "SELECT receipt FROM effects WHERE effect_id=?", (row[0],)
                        ).fetchone()[0]
                        self._call(now, key, req["occurrence_id"], "duplicate")
                        self.conn.execute("COMMIT")
                        return 200, {"status": "duplicate", "receipt": receipt}
                    if row:
                        self.conn.execute("DELETE FROM dedup WHERE effect_key=?", (key,))
                cur = self.conn.execute(
                    "INSERT INTO effects(effect_key, instance_id, occurrence_id, payload_hash, payload, receipt, created_at) VALUES (?,?,?,?,?,?,?)",
                    (key, req["instance_id"], req["occurrence_id"], payload_hash, payload, "pending", now),
                )
                effect_id = cur.lastrowid
                receipt = hashlib.sha256(f"receipt|{key}|{effect_id}".encode()).hexdigest()[:24]
                self.conn.execute("UPDATE effects SET receipt=? WHERE effect_id=?", (receipt, effect_id))
                if self.profile == "PD":
                    expires = None if self.ttl is None else now + self.ttl
                    self.conn.execute(
                        "INSERT INTO dedup(effect_key, effect_id, payload_hash, expires_at) VALUES (?,?,?,?)",
                        (key, effect_id, payload_hash, expires),
                    )
                self._call(now, key, req["occurrence_id"], "committed")
                self.conn.execute("COMMIT")
            except BaseException:
                self.conn.execute("ROLLBACK")
                raise
        return 200, {"status": "committed", "receipt": receipt}

    def _call(self, ts: float, key: str, occ: str, outcome: str) -> None:
        self.conn.execute(
            "INSERT INTO calls(ts, effect_key, occurrence_id, outcome) VALUES (?,?,?,?)", (ts, key, occ, outcome)
        )

    def fence(self, key: str) -> tuple[int, dict]:
        if self.profile != "PF":
            return 501, {"error": "fence not supported by this profile"}
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            self.conn.execute("INSERT OR IGNORE INTO fences(effect_key, fenced_at) VALUES (?,?)", (key, time.time()))
            row = self.conn.execute("SELECT receipt FROM effects WHERE effect_key=? ORDER BY effect_id LIMIT 1", (key,)).fetchone()
            self.conn.execute("COMMIT")
        return 200, {"fenced": True, "committed": row is not None, "receipt": row[0] if row else None, "final": True}

    def lookup(self, key: str) -> tuple[int, dict]:
        if self.evidence == "none":
            return 501, {"error": "no evidence contract"}
        row = self.conn.execute("SELECT receipt FROM effects WHERE effect_key=? ORDER BY effect_id LIMIT 1", (key,)).fetchone()
        final = self.profile == "PF" and bool(self.conn.execute("SELECT 1 FROM fences WHERE effect_key=?", (key,)).fetchone())
        return 200, {"committed": row is not None, "receipt": row[0] if row else None, "final": final}

    def admin(self, what: str) -> tuple[int, dict]:
        if what == "effects":
            rows = self.conn.execute(
                "SELECT effect_key, instance_id, occurrence_id, payload_hash, receipt, created_at FROM effects ORDER BY effect_id"
            ).fetchall()
            return 200, {"effects": [dict(zip(("key", "instance_id", "occurrence_id", "payload_hash", "receipt", "created_at"), r)) for r in rows]}
        if what == "calls":
            rows = self.conn.execute("SELECT outcome, COUNT(*) FROM calls GROUP BY outcome").fetchall()
            total = self.conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
            return 200, {"total": total, "by_outcome": dict(rows)}
        if what == "health":
            return 200, {"ok": True, "profile": self.profile, "ttl": self.ttl, "evidence": self.evidence}
        return 404, {"error": "unknown"}


def make_handler(sink: Sink):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # silence
            pass

        def _send(self, code: int, body: dict) -> None:
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            try:
                self.wfile.write(data)
            except BrokenPipeError:
                # The client died mid-request (e.g. SIGKILL during transport);
                # the effect, if any, is already committed.
                pass

        def do_GET(self):
            u = urlparse(self.path)
            if u.path == "/lookup":
                key = parse_qs(u.query).get("key", [""])[0]
                self._send(*sink.lookup(key))
            elif u.path.startswith("/admin/"):
                self._send(*sink.admin(u.path[len("/admin/") :]))
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self):
            n = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(n) or b"{}")
            if self.path == "/execute":
                self._send(*sink.execute(body))
            elif self.path == "/fence":
                self._send(*sink.fence(body["key"]))
            else:
                self._send(404, {"error": "not found"})

    return Handler


def serve(db: str, port: int, profile: str, ttl: float | None, evidence: str, ready_file: str | None) -> None:
    sink = Sink(db, profile, ttl, evidence)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(sink))
    server.daemon_threads = True
    if ready_file:
        with open(ready_file, "w") as f:
            f.write(str(server.server_address[1]))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--profile", choices=("PD", "PF", "PO"), default="PD")
    ap.add_argument("--ttl-seconds", type=float, default=None)
    ap.add_argument("--evidence", choices=("lookup", "none"), default="lookup")
    ap.add_argument("--ready-file", default=None)
    a = ap.parse_args(argv)
    serve(a.db, a.port, a.profile, a.ttl_seconds, a.evidence, a.ready_file)


if __name__ == "__main__":
    sys.exit(main())
