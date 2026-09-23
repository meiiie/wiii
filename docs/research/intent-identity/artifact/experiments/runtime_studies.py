"""I1-I6: process-crash, concurrency, takeover, retention, batch-journal and
zombie-predecessor studies.

Each trial uses a fresh controller database and a fresh approval instance on a
shared loopback provider process. The success oracle reads the provider's own
effect table (independent of controller self-report) and the controller's
final occurrence states.

I1  (v0.2 reproduction): 2 policies x 6 grouping pairs x 4 SIGKILL fault
    points x 5 repetitions = 240 trials on P_D, unlimited retention.
I2  (v0.2 reproduction): 12 three-worker races per policy on one instance.
I3  (v0.3): lease takeover while the crashed worker's request is still in
    flight, on P_D / P_F / P_O, naive vs profile-aware recovery.
I4  (v0.3): recovery after the P_D dedup window lapsed (finite retention),
    with and without an evidence contract, naive vs retention-aware.
I5  (v0.3): lost response to a journaled multi-entry request; ternary vs
    structured journal under two evidence-cost accountings; misdeclared class.
I6  (v0.3): predecessor suspended (SIGSTOP) rather than killed, overtaken by
    a successor, then resumed (SIGCONT) with a stale lease.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from intent_identity.contract import EffectSpec, create_contract  # noqa: E402
from intent_identity.ledger import Ledger  # noqa: E402
from intent_identity.plan import plan_from_grouping  # noqa: E402

PY = sys.executable
OCC = ("o1", "o2", "o3", "o4")
GROUPING_PAIRS = [
    ((("o1", "o2", "o3", "o4"),), (("o1",), ("o2",), ("o3",), ("o4",))),
    ((("o1",), ("o2",), ("o3",), ("o4",)), (("o1", "o2", "o3", "o4"),)),
    ((("o1", "o2"), ("o3", "o4")), (("o3", "o4"), ("o1", "o2"))),
    ((("o1", "o2"), ("o3", "o4")), (("o4", "o3", "o2", "o1"),)),
    ((("o4",), ("o3",), ("o2",), ("o1",)), (("o1", "o2"), ("o3",), ("o4",))),
    ((("o1",), ("o2", "o3", "o4")), (("o2",), ("o1", "o4"), ("o3",))),
]
FAULTS_I1 = ("after-first-reservation", "after-first-effect", "after-first-confirm", "after-third-effect")


class Provider:
    def __init__(self, workdir: Path, profile: str, ttl: float | None, evidence: str):
        stamp = time.time_ns()
        self.db = workdir / f"provider-{profile}-{ttl}-{evidence}-{stamp}.sqlite"
        ready = workdir / f"ready-{profile}-{ttl}-{evidence}-{os.getpid()}-{time.time_ns()}"
        if ready.exists():
            ready.unlink()
        cmd = [PY, "-m", "intent_identity.provider", "--db", str(self.db), "--profile", profile, "--evidence", evidence, "--ready-file", str(ready)]
        if ttl is not None:
            cmd += ["--ttl-seconds", str(ttl)]
        self.log = open(workdir / f"provider-{profile}-{ttl}-{evidence}-{stamp}.log", "a")
        self.proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=self.log, stderr=self.log)
        for _ in range(200):
            if ready.exists() and ready.read_text().strip():
                break
            time.sleep(0.05)
        self.url = f"http://127.0.0.1:{ready.read_text().strip()}"

    def get(self, path: str) -> dict:
        with urllib.request.urlopen(self.url + path, timeout=30) as r:
            return json.loads(r.read())

    def effects_for(self, instance_id: str) -> Counter:
        eff = self.get("/admin/effects")["effects"]
        return Counter(e["occurrence_id"] for e in eff if e["instance_id"] == instance_id)

    def calls(self) -> dict:
        return self.get("/admin/calls")

    def stop(self) -> None:
        self.proc.terminate()
        self.proc.wait(timeout=10)
        self.log.close()


def new_instance(workdir: Path, tag: str, n: int = 4) -> tuple[Path, str, object]:
    db = workdir / f"controller-{tag}.sqlite"
    specs = [EffectSpec("notify", f"recipient-{i}@example.test", f"deployment notice {i} for {tag}") for i in range(1, n + 1)]
    contract = create_contract("principal-a", f"approval-{tag}", specs)
    ledger = Ledger(db, "orchestrator")
    ledger.register_contract(contract)
    ledger.close()
    return db, contract.instance_id, contract


def write_plan(workdir: Path, contract, grouping, name: str) -> Path:
    p = workdir / f"plan-{name}.json"
    p.write_text(json.dumps(plan_from_grouping(contract, grouping).to_dict()))
    return p


def worker_cmd(policy, db, url, instance, plan, worker_id, **kw) -> list[str]:
    cmd = [PY, "-m", "intent_identity.worker", "--policy", policy, "--controller-db", str(db), "--provider-url", url, "--instance", instance, "--plan", str(plan), "--worker-id", worker_id]
    for k, v in kw.items():
        if v is not None:
            cmd += [f"--{k.replace('_', '-')}", str(v)]
    return cmd


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)


def last_json(text: str) -> dict:
    for line in reversed(text.strip().splitlines()):
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    return {}


def oracle(prov: Provider, db: Path, instance: str) -> dict:
    eff = prov.effects_for(instance)
    ledger = Ledger(db, "oracle")
    states = ledger.states(instance)
    ledger.close()
    occ = tuple(sorted(states))
    return {
        "effects": dict(eff),
        "states": states,
        "duplicate": any(eff[o] > 1 for o in occ),
        "incomplete_world": any(eff[o] == 0 for o in occ),
        "all_done": all(states[o] == "done" for o in occ),
        "unresolved": [o for o in occ if states[o] == "unresolved"],
    }


# ---------------------------------------------------------------------------


def study_i1(workdir: Path, out, reps: int) -> dict:
    prov = Provider(workdir, "PD", None, "lookup")
    summary = Counter()
    times = {"R": [], "V": []}
    try:
        for policy in ("R", "V"):
            for gi, (src, dst) in enumerate(GROUPING_PAIRS):
                for fault in FAULTS_I1:
                    for rep in range(reps):
                        tag = f"i1-{policy}-g{gi}-{fault}-{rep}"
                        db, inst, contract = new_instance(workdir, tag)
                        p_src = write_plan(workdir, contract, src, tag + "-src")
                        p_dst = write_plan(workdir, contract, dst, tag + "-dst")
                        child = run(worker_cmd(policy, db, prov.url, inst, p_src, "w-child", fault_point=fault))
                        t0 = time.perf_counter()
                        succ = run(worker_cmd(policy, db, prov.url, inst, p_dst, "w-succ", predecessor="w-child"))
                        dt = time.perf_counter() - t0
                        o = oracle(prov, db, inst)
                        ok = child.returncode == -9 and succ.returncode == 0 and not o["duplicate"] and o["all_done"] and not o["incomplete_world"]
                        summary[(policy, "pass" if ok else "fail")] += 1
                        times[policy].append(dt)
                        out.write(json.dumps({"study": "I1", "policy": policy, "pair": gi, "fault": fault, "rep": rep, "child_rc": child.returncode, "crash_marker": last_json(child.stdout).get("crash_marker"), "succ_rc": succ.returncode, "succ_summary": last_json(succ.stdout), "oracle": o, "succ_wall_s": dt, "pass": ok}) + "\n")
        calls = prov.calls()
    finally:
        prov.stop()
    med = {p: sorted(t)[len(t) // 2] for p, t in times.items()}
    return {"trials": sum(summary.values()), "pass": {p: summary[(p, "pass")] for p in ("R", "V")}, "fail": {p: summary[(p, "fail")] for p in ("R", "V")}, "provider_calls": calls, "median_successor_wall_s": med}


def study_i2(workdir: Path, out, races: int) -> dict:
    prov = Provider(workdir, "PD", None, "lookup")
    summary = Counter()
    groupings = [(("o1", "o2", "o3", "o4"),), (("o4",), ("o3",), ("o2",), ("o1",)), (("o2", "o3"), ("o1",), ("o4",))]
    try:
        for policy in ("R", "V"):
            for r in range(races):
                tag = f"i2-{policy}-{r}"
                db, inst, contract = new_instance(workdir, tag)
                procs = []
                for wi, g in enumerate(groupings):
                    plan = write_plan(workdir, contract, g, f"{tag}-w{wi}")
                    procs.append(subprocess.Popen(worker_cmd(policy, db, prov.url, inst, plan, f"w{wi}"), cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
                rcs = [p.wait(timeout=120) for p in procs]
                o = oracle(prov, db, inst)
                ok = all(rc == 0 for rc in rcs) and not o["duplicate"] and o["all_done"]
                summary[(policy, "pass" if ok else "fail")] += 1
                out.write(json.dumps({"study": "I2", "policy": policy, "race": r, "rcs": rcs, "oracle": o, "pass": ok}) + "\n")
        calls = prov.calls()
    finally:
        prov.stop()
    return {"trials": sum(summary.values()), "pass": {p: summary[(p, "pass")] for p in ("R", "V")}, "provider_calls": calls}


def study_i3(workdir: Path, out, reps: int) -> dict:
    """In-flight takeover. Variant 'early': successor acts before the old
    request commits; 'late': after it committed."""
    rows = {}
    variants = {"early": {"delay_ms": 1000, "succ_start": 0.5}, "late": {"delay_ms": 200, "succ_start": 0.9}}
    src = (("o1", "o2", "o3", "o4"),)
    dst = (("o1",), ("o2",), ("o3",), ("o4",))
    for profile in ("PD", "PF", "PO"):
        prov = Provider(workdir, profile, None, "lookup")
        try:
            for variant, vp in variants.items():
                for recovery in ("naive", "lookup-fresh", "aware"):
                    c = Counter()
                    for rep in range(reps):
                        tag = f"i3-{profile}-{variant}-{recovery}-{rep}"
                        db, inst, contract = new_instance(workdir, tag)
                        p_src = write_plan(workdir, contract, src, tag + "-src")
                        p_dst = write_plan(workdir, contract, dst, tag + "-dst")
                        t_start = time.time()
                        child = run(worker_cmd("V", db, prov.url, inst, p_src, "w-a", fault_point="during-first-transport", transport_kill_ms=150, delay_ms=vp["delay_ms"], lease_seconds=0.3, profile=profile))
                        succ = run(worker_cmd("V", db, prov.url, inst, p_dst, "w-b", start_delay=max(0.0, vp["succ_start"] - (time.time() - t_start)), lease_seconds=5, profile=profile, recovery=recovery))
                        # let the crashed worker's in-flight request land
                        time.sleep(max(0.0, t_start + vp["delay_ms"] / 1000.0 + 0.6 - time.time()))
                        o = oracle(prov, db, inst)
                        c["trials"] += 1
                        c["duplicate"] += o["duplicate"]
                        c["all_done"] += o["all_done"]
                        c["unresolved"] += bool(o["unresolved"])
                        c["world_complete"] += not o["incomplete_world"]
                        c["child_killed"] += child.returncode == -9
                        c["succ_ok"] += succ.returncode == 0
                        out.write(json.dumps({"study": "I3", "profile": profile, "variant": variant, "recovery": recovery, "rep": rep, "child_rc": child.returncode, "succ_rc": succ.returncode, "succ_summary": last_json(succ.stdout), "oracle": o}) + "\n")
                    rows[f"{profile}/{variant}/{recovery}"] = dict(c)
                    print("I3", profile, variant, recovery, dict(c), flush=True)
        finally:
            prov.stop()
    return rows


def study_i4(workdir: Path, out, reps: int) -> dict:
    """Retention expiry on P_D. Successor runs after the dedup window lapsed."""
    ttl = 0.5
    rows = {}
    src = (("o1", "o2", "o3", "o4"),)
    dst = (("o3", "o4"), ("o1", "o2"))
    for evidence in ("lookup", "none"):
        prov = Provider(workdir, "PD", ttl, evidence)
        try:
            for fault in ("after-first-effect", "after-first-reservation"):
                for recovery in ("naive", "aware"):
                    for policy in ("R", "V"):
                        c = Counter()
                        for rep in range(reps):
                            tag = f"i4-{evidence}-{fault}-{recovery}-{policy}-{rep}"
                            db, inst, contract = new_instance(workdir, tag)
                            p_src = write_plan(workdir, contract, src, tag + "-src")
                            p_dst = write_plan(workdir, contract, dst, tag + "-dst")
                            child = run(worker_cmd(policy, db, prov.url, inst, p_src, "w-child", fault_point=fault, retention_seconds=ttl, profile="PD"))
                            time.sleep(ttl + 0.3)
                            succ = run(worker_cmd(policy, db, prov.url, inst, p_dst, "w-succ", predecessor="w-child", retention_seconds=ttl, profile="PD", recovery=recovery))
                            o = oracle(prov, db, inst)
                            c["trials"] += 1
                            c["duplicate"] += o["duplicate"]
                            c["all_done"] += o["all_done"]
                            c["unresolved"] += bool(o["unresolved"])
                            c["world_complete"] += not o["incomplete_world"]
                            c["child_killed"] += child.returncode == -9
                            c["succ_ok"] += succ.returncode == 0
                            out.write(json.dumps({"study": "I4", "evidence": evidence, "fault": fault, "recovery": recovery, "policy": policy, "rep": rep, "child_rc": child.returncode, "succ_rc": succ.returncode, "succ_summary": last_json(succ.stdout), "oracle": o}) + "\n")
                        rows[f"{evidence}/{fault}/{recovery}/{policy}"] = dict(c)
                        print("I4", evidence, fault, recovery, policy, dict(c), flush=True)
        finally:
            prov.stop()
    return rows


def study_i5(workdir: Path, out) -> dict:
    """Lost response to a multi-entry request: ternary vs structured journal.

    The crashed worker sends one batch request whose per-entry outcome is set
    by the world (which entries the provider fails). The successor starts
    after the provider finished, reconciles from its journal and completes.
    Measured: decision probes (lookups) and exactly-once/completion oracle.
    """
    from itertools import combinations

    from intent_identity.belief import atomic_family, independent_family, optimal_fence_cost, optimal_probe_cost, prefix_family

    def worlds(cls, n):
        occ = [f"o{i}" for i in range(1, n + 1)]
        if cls == "independent":
            return [",".join(c) for r in range(n + 1) for c in combinations(occ, r)]
        if cls == "atomic":
            return ["", occ[0]]
        if cls == "prefix":
            return [""] + occ
        raise ValueError(cls)

    designs = [("independent", 4), ("atomic", 4), ("prefix", 4), ("prefix", 8), ("atomic", 8)]
    rows = {}
    prov = Provider(workdir, "PF", None, "lookup")

    def trial(cls, n, journal, evidence_op, fail_set, tag, override=None):
        db, inst, contract = new_instance(workdir, tag, n)
        grouping = (tuple(f"o{i}" for i in range(1, n + 1)),)
        plan = write_plan(workdir, contract, grouping, tag)
        t_start = time.time()
        child = run(worker_cmd("V", db, prov.url, inst, plan, "w-a", fault_point="during-first-transport", transport_kill_ms=150, delay_ms=300, lease_seconds=0.3, profile="PF", batch_transport=cls, fail_set=fail_set or None))
        succ = run(worker_cmd("V", db, prov.url, inst, plan, "w-b", start_delay=max(0.0, 0.8 - (time.time() - t_start)), lease_seconds=5, profile="PF", journal=journal, evidence_op=evidence_op, journal_class_override=override))
        o = oracle(prov, db, inst)
        ss = last_json(succ.stdout)
        out.write(json.dumps({"study": "I5", "class": cls, "n": n, "journal": journal, "evidence_op": evidence_op, "class_override": override, "world_fail_set": fail_set, "child_rc": child.returncode, "succ_rc": succ.returncode, "probes": ss.get("probes"), "extra_fences": ss.get("extra_fences"), "evidence_calls": ss.get("evidence_calls"), "succ_summary": ss, "oracle": o}) + "\n")
        return child, succ, o, ss

    try:
        for evidence_op in ("lookup", "fence"):
            for cls, n in designs:
                fam = {"independent": independent_family, "atomic": atomic_family, "prefix": prefix_family}[cls](n)
                probe_cost = {"structured": optimal_probe_cost(fam), "ternary": float(n)}
                fence_cost = {"structured": optimal_fence_cost(fam, n), "ternary": float(n)}
                for journal in ("ternary", "structured"):
                    c = Counter()
                    probes, calls = [], []
                    for wi, fail_set in enumerate(worlds(cls, n)):
                        child, succ, o, ss = trial(cls, n, journal, evidence_op, fail_set, f"i5-{evidence_op}-{cls}-{n}-{journal}-{wi}")
                        c["trials"] += 1
                        c["duplicate"] += o["duplicate"]
                        c["all_done"] += o["all_done"]
                        c["world_complete"] += not o["incomplete_world"]
                        c["child_killed"] += child.returncode == -9
                        c["succ_ok"] += succ.returncode == 0
                        probes.append(ss.get("probes"))
                        calls.append(ss.get("evidence_calls"))
                    valid = [p for p in probes if p is not None]
                    vcalls = [p for p in calls if p is not None]
                    row = dict(c)
                    row["mean_probes"] = round(sum(valid) / len(valid), 4) if valid else None
                    row["max_probes"] = max(valid) if valid else None
                    row["mean_evidence_calls"] = round(sum(vcalls) / len(vcalls), 4) if vcalls else None
                    row["expected_mean_probes"] = round(probe_cost[journal], 4)
                    row["expected_mean_calls"] = round(fence_cost[journal] if evidence_op == "fence" else probe_cost[journal], 4)
                    rows[f"{evidence_op}/{cls}/n{n}/{journal}"] = row
                    print("I5", evidence_op, cls, n, journal, row, flush=True)
        # Trusted-class misdeclaration: provider processes as prefix, journal claims atomic.
        c = Counter()
        for wi, fail_set in enumerate(worlds("prefix", 4)):
            child, succ, o, ss = trial("prefix", 4, "structured", "fence", fail_set, f"i5-misdeclared-{wi}", override="atomic")
            c["trials"] += 1
            c["duplicate"] += o["duplicate"]
            c["controller_all_done"] += o["all_done"]
            c["world_incomplete"] += o["incomplete_world"]
            c["false_success"] += o["all_done"] and o["incomplete_world"]
        rows["misdeclared-class/prefix-as-atomic/n4"] = dict(c)
        print("I5 misdeclared", dict(c), flush=True)
    finally:
        prov.stop()
    return rows


def study_i6(workdir: Path, out, reps: int) -> dict:
    """Resumed predecessor (zombie). Worker A is SIGSTOPped instead of killed,
    either right after reserving o1 (its request not yet sent) or 150 ms into
    its first transport (request in flight, provider delaying commit). Worker
    B takes over after the 0.3 s lease lapses with profile-aware recovery.
    A is then resumed with SIGCONT and runs to completion with a stale lease.

    Measured: duplicates at the provider; A's stale ledger writes (rejected by
    the lease-holder check); A's return code; B's final states.
    """
    import signal

    rows = {}
    src = (("o1", "o2", "o3", "o4"),)
    dst = (("o1",), ("o2",), ("o3",), ("o4",))
    stop_points = {"after-first-reservation": {"delay_ms": 0}, "during-first-transport": {"delay_ms": 1000}}
    for profile in ("PD", "PF", "PO"):
        prov = Provider(workdir, profile, None, "lookup")
        try:
            for (point, pp), late in ((x, y) for x in stop_points.items() for y in ("reject", "adopt")):
                c = Counter()
                for rep in range(reps):
                    tag = f"i6-{profile}-{point}-{late}-{rep}"
                    db, inst, contract = new_instance(workdir, tag)
                    p_src = write_plan(workdir, contract, src, tag + "-src")
                    p_dst = write_plan(workdir, contract, dst, tag + "-dst")
                    t_start = time.time()
                    zombie = subprocess.Popen(
                        worker_cmd("V", db, prov.url, inst, p_src, "w-a", fault_point=point, fault_action="stop", transport_kill_ms=150, delay_ms=pp["delay_ms"], lease_seconds=0.3, profile=profile, late_evidence=late),
                        cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                    )
                    succ = run(worker_cmd("V", db, prov.url, inst, p_dst, "w-b", start_delay=max(0.0, 0.5 - (time.time() - t_start)), lease_seconds=5, profile=profile, recovery="aware"))
                    # let any in-flight request of A land, then wake A up
                    time.sleep(max(0.0, t_start + pp["delay_ms"] / 1000.0 + 0.6 - time.time()))
                    stopped_before_resume = zombie.poll() is None
                    os.kill(zombie.pid, signal.SIGCONT)
                    try:
                        z_out, z_err = zombie.communicate(timeout=30)
                    except subprocess.TimeoutExpired:
                        zombie.kill()
                        z_out, z_err = zombie.communicate()
                    zs = last_json(z_out)
                    o = oracle(prov, db, inst)
                    ledger = Ledger(db, "oracle")
                    events = ledger.conn.execute("SELECT kind, COUNT(*) FROM events WHERE instance_id=? AND worker_id='w-a' GROUP BY kind", (inst,)).fetchall()
                    ledger.close()
                    ev = dict(events)
                    c["trials"] += 1
                    c["duplicate"] += o["duplicate"]
                    c["all_done"] += o["all_done"]
                    c["unresolved"] += bool(o["unresolved"])
                    c["world_complete"] += not o["incomplete_world"]
                    c["zombie_was_stopped"] += stopped_before_resume
                    c["zombie_resumed_and_exited_0"] += zombie.returncode == 0
                    c["zombie_stale_confirms_rejected"] += ev.get("stale-confirm-rejected", 0)
                    c["zombie_provider_rejections"] += ev.get("provider-rejected", 0)
                    c["zombie_done_writes"] += ev.get("done", 0)
                    c["zombie_late_receipts_adopted"] += ev.get("late-receipt-adopted", 0)
                    c["succ_ok"] += succ.returncode == 0
                    out.write(json.dumps({"study": "I6", "profile": profile, "stop_point": point, "late_evidence": late, "rep": rep, "zombie_rc": zombie.returncode, "zombie_summary": zs, "zombie_events": ev, "zombie_stderr_tail": z_err[-400:], "succ_rc": succ.returncode, "succ_summary": last_json(succ.stdout), "oracle": o}) + "\n")
                rows[f"{profile}/{point}/{late}"] = dict(c)
                print("I6", profile, point, late, dict(c), flush=True)
        finally:
            prov.stop()
    return rows


def main(argv: list[str]) -> None:
    all_studies = {"I1", "I2", "I3", "I4", "I5", "I6"}
    which = set(argv[1:]) or set(all_studies)
    reps = int(os.environ.get("II_REPS", "5"))
    out_dir = ROOT / "results"
    out_dir.mkdir(exist_ok=True)
    summary = {}
    # A full run regenerates the trial log from scratch; a partial run appends
    # so that the other studies' raw records are preserved.
    mode = "w" if which == all_studies else "a"
    with tempfile.TemporaryDirectory(prefix="intent-identity-") as tmp, open(out_dir / "runtime_trials.jsonl", mode) as out:
        workdir = Path(tmp)
        t0 = time.time()
        if "I1" in which:
            summary["I1"] = study_i1(workdir, out, reps)
            print("I1", summary["I1"], flush=True)
        if "I2" in which:
            summary["I2"] = study_i2(workdir, out, 12)
            print("I2", summary["I2"], flush=True)
        if "I3" in which:
            summary["I3"] = study_i3(workdir, out, reps)
        if "I4" in which:
            summary["I4"] = study_i4(workdir, out, reps)
        if "I5" in which:
            summary["I5"] = study_i5(workdir, out)
        if "I6" in which:
            summary["I6"] = study_i6(workdir, out, reps)
        elapsed = round(time.time() - t0, 2)
    prev = {}
    p = out_dir / "runtime_summary.json"
    if p.exists():
        prev = json.loads(p.read_text())
    prev.pop("elapsed_s", None)
    prev.update(summary)
    prev.setdefault("elapsed_s_by_run", []).append({"studies": sorted(which), "elapsed_s": elapsed})
    p.write_text(json.dumps(prev, indent=2))


if __name__ == "__main__":
    main(sys.argv)
