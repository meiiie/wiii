"""Worker process: restore from the durable ledger and execute a proposed plan.

Policies:

* ``R``: strong reference. Flat canonical-action matching; every proposed
  occurrence is looked up in the ledger (cached completion for ``done``),
  otherwise reserved and dispatched under its stable obligation key.
* ``V``: verified refinement. Whole-plan typed wrapper check, residualization
  of the destination plan against completed occurrences, same keys.

Recovery modes for an occurrence found ``held`` at restore time:

* ``naive``: same-key retry regardless of provider profile or retention. This
  is the common durable-workflow behaviour and is safe only under P_D with
  unexpired retention.
* ``aware``: profile- and retention-aware. P_D inside retention: same-key
  retry. P_D outside retention or P_O: positive evidence lookup confirms,
  otherwise the occurrence becomes ``unresolved`` (safe, not complete).
  P_F: fence the old key; use its final outcome or dispatch a fresh key.

Fault points terminate this process with a real SIGKILL.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import threading
import time
import urllib.error
import urllib.request

from .contract import obligation_key
from .ledger import Ledger
from .plan import (
    Plan,
    check_actions_reference,
    check_plan_verified,
    flatten,
    residualize,
)

FAULT_POINTS = (
    "none",
    "after-first-reservation",
    "after-first-effect",
    "after-first-confirm",
    "after-third-effect",
    "during-first-transport",
)


FAULT_ACTION = "kill"


def _die() -> None:
    """Apply the configured fault: SIGKILL (crash) or SIGSTOP (suspend).

    A suspended worker is a zombie predecessor: after a successor has taken
    over its held occurrences the orchestrator resumes it with SIGCONT and it
    continues exactly where it was, with a stale lease and possibly a stale
    in-flight request.
    """
    sys.stdout.flush()
    os.kill(os.getpid(), signal.SIGKILL if FAULT_ACTION == "kill" else signal.SIGSTOP)


class Http:
    def __init__(self, base: str):
        self.base = base.rstrip("/")

    def post(self, path: str, body: dict) -> tuple[int, dict]:
        data = json.dumps(body).encode()
        req = urllib.request.Request(self.base + path, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    def get(self, path: str) -> tuple[int, dict]:
        try:
            with urllib.request.urlopen(self.base + path, timeout=60) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")


class Worker:
    def __init__(self, a: argparse.Namespace):
        self.a = a
        self.ledger = Ledger(a.controller_db, a.worker_id, a.late_evidence)
        self.http = Http(a.provider_url)
        self.contract = self.ledger.load_contract(a.instance)
        self.effects_seen = 0
        self.confirms = 0
        self.reservations = 0
        self.summary = {"worker_id": a.worker_id, "policy": a.policy, "actions": []}

    def fault(self, point: str) -> None:
        if self.a.fault_point == point:
            self.ledger.log("fault-injected", self.a.instance, kind_detail=point)
            self.summary["crash_marker"] = point
            print(json.dumps({"crash_marker": point, "worker_id": self.a.worker_id}), flush=True)
            _die()
            # Only reachable after SIGCONT in the zombie configuration.
            self.summary["resumed_after"] = point
            self.ledger.log("resumed", self.a.instance, kind_detail=point)

    # -- planning ---------------------------------------------------------

    def approved_groups(self, plan: Plan) -> list[list[str]]:
        if self.a.policy == "V":
            check_plan_verified(self.contract, plan)
            groups = [[x.occurrence_id for x in g.actions] for g in plan.groups]
            done = {o for o, s in self.ledger.states(self.a.instance).items() if s == "done"}
            res = residualize(groups, done)
            for skipped in res.skipped:
                self.summary["actions"].append({"occurrence": skipped, "outcome": "residualized-done"})
            return res.remaining
        order = check_actions_reference(self.contract, flatten(plan))
        return [[o] for o in order]

    # -- execution --------------------------------------------------------

    def run(self) -> dict:
        plan = Plan.from_dict(json.loads(open(self.a.plan).read()))
        if self.a.start_delay:
            time.sleep(self.a.start_delay)
        if self.a.journal:
            self.reconcile_requests()
        for group in self.approved_groups(plan):
            if self.a.batch_transport and len(group) > 1:
                self.dispatch_batch(group)
                continue
            for occ_id in group:
                self.handle(occ_id)
        self.summary["final_states"] = self.ledger.states(self.a.instance)
        self.summary["effects_seen"] = self.effects_seen
        return self.summary

    # -- multi-entry request transport (I5) --------------------------------

    def dispatch_batch(self, group: list[str]) -> None:
        """Send one wrapper group as a single multi-entry request and journal
        its membership, order and processing class before transport."""
        a = self.a
        reserved = []
        for occ_id in group:
            was_held, occ = self.ledger.reserve(a.instance, occ_id, a.lease_seconds, a.retention_seconds, a.predecessor)
            if occ.state == "held" and occ.worker_id == a.worker_id and not was_held:
                reserved.append(occ)
        if not reserved:
            return
        request_id = f"{a.worker_id}-{int(time.time() * 1e6)}"
        self.ledger.record_request(request_id, a.instance, a.batch_transport, [o.occurrence_id for o in reserved])
        fail_set = set(filter(None, (a.fail_set or "").split(",")))
        entries = []
        for occ in reserved:
            payload, payload_hash = self.payload_for(occ.occurrence_id)
            entries.append({"key": occ.effect_key, "instance_id": a.instance, "occurrence_id": occ.occurrence_id, "payload": payload, "payload_hash": payload_hash, "fail": occ.occurrence_id in fail_set})
        if a.fault_point == "during-first-transport":
            threading.Timer(a.transport_kill_ms / 1000.0, _die).start()
        code, resp = self.http.post("/execute-batch", {"batch_class": a.batch_transport, "entries": entries, "delay_ms": a.delay_ms})
        for r in resp.get("results", []):
            if r.get("status") in ("committed", "duplicate"):
                occ = self.ledger.get(a.instance, r["occurrence_id"])
                _, payload_hash = self.payload_for(occ.occurrence_id)
                self.ledger.confirm(a.instance, occ.occurrence_id, r["receipt"], payload_hash, occ.effect_key)
            self.summary["actions"].append({"occurrence": r["occurrence_id"], "outcome": r.get("status")})
        self.ledger.close_request(request_id)

    def reconcile_requests(self) -> None:
        """Recover held members of journaled requests whose response was lost.

        ``ternary`` journal: probe every held member. ``structured`` journal:
        rebuild the belief family from (members, order, class) and probe
        adaptively with the exact oracle. Finality of the old request is a
        study assumption here (the successor starts after the provider has
        finished); the count of interest is decision probes.
        """
        from . import belief

        a = self.a
        probes = 0
        fences = 0
        for request_id, batch_class, members in self.ledger.open_requests(a.instance):
            if a.journal_class_override:
                batch_class = a.journal_class_override  # trusted-class misdeclaration experiment
            held = [m for m in members if self.ledger.get(a.instance, m).state == "held"]
            if not held:
                self.ledger.close_request(request_id)
                continue
            for m in held:
                self.ledger.reserve(a.instance, m, a.lease_seconds, a.retention_seconds, a.predecessor)
            idx = {m: i for i, m in enumerate(held)}
            n = len(held)
            if a.journal == "ternary":
                B = belief.independent_family(n)
            elif batch_class == "independent":
                B = belief.independent_family(n)
            elif batch_class == "atomic":
                B = belief.atomic_family(n)
            elif batch_class == "prefix":
                B = belief.prefix_family(n)
            else:
                raise ValueError(batch_class)
            receipts: dict[str, str] = {}
            fenced_keys: set[str] = set()
            fenced_mask = 0
            objective = "fence" if a.evidence_op == "fence" else "probes"
            while len(B) > 1:
                # Per-key finality changes the objective: probing an absent
                # member is the fence it needs anyway, so the probe-minimising
                # policy is no longer optimal.
                i = belief.best_probe(B, n, fenced_mask, objective)
                m = held[i]
                committed, receipt = self.probe(self.ledger.get(a.instance, m).effect_key)
                probes += 1
                if a.evidence_op == "fence":
                    fenced_keys.add(m)
                    fenced_mask |= 1 << i
                if committed:
                    receipts[m] = receipt
                B = belief.condition(B, i, committed)
            (world,) = B
            for m in held:
                occ = self.ledger.get(a.instance, m)
                _, payload_hash = self.payload_for(m)
                if idx[m] in world:
                    self.ledger.confirm(a.instance, m, receipts.get(m, f"inferred:{batch_class}"), payload_hash, occ.effect_key)
                    self.summary["actions"].append({"occurrence": m, "outcome": "reconciled-committed" if m in receipts else "reconciled-inferred-committed"})
                else:
                    if a.evidence_op == "fence" and m not in fenced_keys:
                        # Per-key finality: every fresh dispatch is preceded by a
                        # fence on the old key so a late arrival cannot duplicate.
                        self.http.post("/fence", {"key": occ.effect_key})
                        fences += 1
                    gen = occ.generation + 1
                    new_key = obligation_key(a.instance, f"{m}#g{gen}")
                    self.ledger.rekey(a.instance, m, new_key, gen, a.retention_seconds)
                    self.summary["actions"].append({"occurrence": m, "outcome": "reconciled-absent-fresh-key"})
                    self.dispatch(self.ledger.get(a.instance, m))
            self.ledger.close_request(request_id)
        self.summary["probes"] = probes
        self.summary["extra_fences"] = fences
        self.summary["evidence_calls"] = probes + fences

    def probe(self, key: str) -> tuple[bool, str | None]:
        """One evidence call. ``lookup`` is point-in-time (finality must come
        from elsewhere); ``fence`` is final and blocks late delivery."""
        if self.a.evidence_op == "fence":
            code, resp = self.http.post("/fence", {"key": key})
        else:
            code, resp = self.http.get(f"/lookup?key={key}")
        return bool(resp.get("committed")), resp.get("receipt")

    def handle(self, occ_id: str) -> None:
        occ = self.ledger.get(self.a.instance, occ_id)
        if occ.state == "done":
            self.summary["actions"].append({"occurrence": occ_id, "outcome": "cached-done"})
            return
        if occ.state == "unresolved":
            self.summary["actions"].append({"occurrence": occ_id, "outcome": "already-unresolved"})
            return
        was_held, occ = self.ledger.reserve(
            self.a.instance, occ_id, self.a.lease_seconds, self.a.retention_seconds, self.a.predecessor
        )
        if occ.state != "held" or occ.worker_id != self.a.worker_id:
            self.summary["actions"].append({"occurrence": occ_id, "outcome": "held-by-other"})
            return
        self.reservations += 1
        if self.reservations == 1:
            self.fault("after-first-reservation")
        if was_held:
            self.recover(occ)
        else:
            self.dispatch(occ, first=self.reservations == 1)

    def payload_for(self, occ_id: str) -> tuple[str, str]:
        spec = self.contract.spec(occ_id)  # executable bytes from the immutable contract
        return spec.canonical(), spec.payload_hash()

    def dispatch(self, occ, first: bool = False) -> None:
        payload, payload_hash = self.payload_for(occ.occurrence_id)
        body = {
            "key": occ.effect_key,
            "instance_id": self.a.instance,
            "occurrence_id": occ.occurrence_id,
            "payload": payload,
            "payload_hash": payload_hash,
            "delay_ms": self.a.delay_ms,
        }
        if first and self.a.fault_point == "during-first-transport":
            threading.Timer(self.a.transport_kill_ms / 1000.0, _die).start()
        code, resp = self.http.post("/execute", body)
        if first and self.a.fault_point == "during-first-transport" and FAULT_ACTION == "stop":
            self.summary["resumed_after"] = "during-first-transport"
            self.ledger.log("resumed", self.a.instance, occ.occurrence_id, kind_detail="during-first-transport")
        if code != 200:
            self.summary["actions"].append({"occurrence": occ.occurrence_id, "outcome": f"provider-{code}", "resp": resp})
            self.ledger.log("provider-rejected", self.a.instance, occ.occurrence_id, code=code, resp=resp)
            return
        self.effects_seen += 1
        if self.effects_seen == 1:
            self.fault("after-first-effect")
        if self.effects_seen == 3:
            self.fault("after-third-effect")
        try:
            self.ledger.confirm(self.a.instance, occ.occurrence_id, resp["receipt"], payload_hash, occ.effect_key)
        except (PermissionError, ValueError) as e:
            # Stale lease or stale key binding: another worker took this
            # occurrence over (and possibly rekeyed it) while the request was
            # in flight. A binding-matched receipt (PermissionError) is kept as
            # a pending late receipt so a later transition to unresolved can
            # adopt it; a rekeyed binding (ValueError) is not evidence for the
            # new key. The state transition itself is refused either way.
            self.ledger.log("stale-confirm-rejected", self.a.instance, occ.occurrence_id, receipt=resp["receipt"], status=resp["status"], reason=str(e))
            if isinstance(e, PermissionError):
                self.ledger.note_pending_receipt(self.a.instance, occ.occurrence_id, resp["receipt"], payload_hash, occ.effect_key)
            self.summary["stale_confirms_rejected"] = self.summary.get("stale_confirms_rejected", 0) + 1
            self.summary["actions"].append({"occurrence": occ.occurrence_id, "outcome": f"stale-confirm-rejected({resp['status']})"})
            return
        self.confirms += 1
        self.summary["actions"].append({"occurrence": occ.occurrence_id, "outcome": resp["status"]})
        if self.confirms == 1:
            self.fault("after-first-confirm")

    def recover(self, occ) -> None:
        a = self.a
        if a.recovery == "naive":
            self.summary["actions"].append({"occurrence": occ.occurrence_id, "outcome": "naive-same-key-retry"})
            self.dispatch(occ)
            return
        if a.recovery == "lookup-fresh":
            # Durable-execution style: read-then-write without a fence. A
            # negative point-in-time lookup is taken as absence and a fresh
            # key is dispatched. Safe only if the old request can no longer
            # arrive (this is M1's absence-without-fence mutant at runtime).
            code, resp = self.http.get(f"/lookup?key={occ.effect_key}")
            if code == 200 and resp.get("committed"):
                _, payload_hash = self.payload_for(occ.occurrence_id)
                self.ledger.confirm(a.instance, occ.occurrence_id, resp["receipt"], payload_hash, occ.effect_key)
                self.summary["actions"].append({"occurrence": occ.occurrence_id, "outcome": "lookup-positive-receipt"})
                return
            gen = occ.generation + 1
            new_key = obligation_key(a.instance, f"{occ.occurrence_id}#g{gen}")
            self.ledger.rekey(a.instance, occ.occurrence_id, new_key, gen, a.retention_seconds)
            self.summary["actions"].append({"occurrence": occ.occurrence_id, "outcome": "lookup-negative-fresh-key-no-fence"})
            self.dispatch(self.ledger.get(a.instance, occ.occurrence_id))
            return
        now = time.time()
        if a.profile == "PD":
            within = occ.retention_deadline is None or now < occ.retention_deadline - a.clock_skew
            if within:
                self.summary["actions"].append({"occurrence": occ.occurrence_id, "outcome": "same-key-retry-within-retention"})
                self.dispatch(occ)
                return
            self.evidence_or_unresolved(occ, "retention-expired")
        elif a.profile == "PF":
            code, resp = self.http.post("/fence", {"key": occ.effect_key})
            if code != 200:
                self.ledger.mark_unresolved(a.instance, occ.occurrence_id, f"fence-failed-{code}")
                self.summary["actions"].append({"occurrence": occ.occurrence_id, "outcome": "fence-failed"})
                return
            if resp["committed"]:
                _, payload_hash = self.payload_for(occ.occurrence_id)
                self.ledger.confirm(a.instance, occ.occurrence_id, resp["receipt"], payload_hash, occ.effect_key)
                self.summary["actions"].append({"occurrence": occ.occurrence_id, "outcome": "fenced-committed-receipt"})
                return
            gen = occ.generation + 1
            new_key = obligation_key(a.instance, f"{occ.occurrence_id}#g{gen}")
            self.ledger.rekey(a.instance, occ.occurrence_id, new_key, gen, a.retention_seconds)
            occ = self.ledger.get(a.instance, occ.occurrence_id)
            self.summary["actions"].append({"occurrence": occ.occurrence_id, "outcome": "fenced-absent-fresh-key"})
            self.dispatch(occ)
        else:  # PO
            self.evidence_or_unresolved(occ, "opaque-provider")

    def evidence_or_unresolved(self, occ, reason: str) -> None:
        code, resp = self.http.get(f"/lookup?key={occ.effect_key}")
        if code == 200 and resp.get("committed"):
            _, payload_hash = self.payload_for(occ.occurrence_id)
            self.ledger.confirm(self.a.instance, occ.occurrence_id, resp["receipt"], payload_hash, occ.effect_key)
            self.summary["actions"].append({"occurrence": occ.occurrence_id, "outcome": f"evidence-committed({reason})"})
            return
        # A negative point-in-time lookup is not finality evidence.
        self.ledger.mark_unresolved(self.a.instance, occ.occurrence_id, reason)
        self.summary["actions"].append({"occurrence": occ.occurrence_id, "outcome": f"unresolved({reason})"})


def parse(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", choices=("R", "V"), required=True)
    ap.add_argument("--recovery", choices=("naive", "aware", "lookup-fresh"), default="aware")
    ap.add_argument("--profile", choices=("PD", "PF", "PO"), default="PD")
    ap.add_argument("--controller-db", required=True)
    ap.add_argument("--provider-url", required=True)
    ap.add_argument("--instance", required=True)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--worker-id", required=True)
    ap.add_argument("--predecessor", default=None)
    ap.add_argument("--lease-seconds", type=float, default=30.0)
    ap.add_argument("--retention-seconds", type=float, default=None)
    ap.add_argument("--clock-skew", type=float, default=0.0)
    ap.add_argument("--fault-point", choices=FAULT_POINTS, default="none")
    ap.add_argument("--fault-action", choices=("kill", "stop"), default="kill", help="kill: SIGKILL (crash); stop: SIGSTOP (zombie predecessor, resumed by the orchestrator)")
    ap.add_argument("--transport-kill-ms", type=float, default=150.0)
    ap.add_argument("--delay-ms", type=float, default=0.0)
    ap.add_argument("--start-delay", type=float, default=0.0)
    ap.add_argument("--batch-transport", choices=("independent", "atomic", "prefix"), default=None)
    ap.add_argument("--fail-set", default=None, help="comma-separated occurrence ids the provider should fail (test hook)")
    ap.add_argument("--journal", choices=("ternary", "structured"), default=None)
    ap.add_argument("--journal-class-override", choices=("independent", "atomic", "prefix"), default=None)
    ap.add_argument("--evidence-op", choices=("lookup", "fence"), default="lookup")
    ap.add_argument("--late-evidence", choices=("reject", "adopt"), default="adopt", help="how the ledger treats a receipt presented by a worker that no longer holds the lease")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    global FAULT_ACTION
    a = parse(argv)
    FAULT_ACTION = a.fault_action
    w = Worker(a)
    summary = w.run()
    print(json.dumps(summary, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
