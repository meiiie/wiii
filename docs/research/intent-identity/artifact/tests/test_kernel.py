"""Kernel unit tests (stdlib unittest). Run: python3 -m unittest discover -s tests -v"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intent_identity import belief  # noqa: E402
from intent_identity.abstract import AbstractSink, all_groupings, cut_patterns  # noqa: E402
from intent_identity.contract import (  # noqa: E402
    EffectSpec,
    create_contract,
    group_scoped_key,
    instance_id_for,
    obligation_key,
)
from intent_identity.ledger import Ledger  # noqa: E402
from intent_identity.model_checker import Config, explore  # noqa: E402
from intent_identity.plan import (  # noqa: E402
    Plan,
    PlanRejected,
    ProposedAction,
    Wrapper,
    check_actions_reference,
    check_plan_verified,
    flatten,
    plan_from_grouping,
    residualize,
)

SPECS = [EffectSpec("notify", f"r{i}@example.test", f"body {i}") for i in range(1, 5)]


def contract():
    return create_contract("p", "approval-1", SPECS)


class ContractTests(unittest.TestCase):
    def test_same_approval_event_recovers_same_instance(self):
        self.assertEqual(instance_id_for("p", "a"), instance_id_for("p", "a"))
        self.assertNotEqual(instance_id_for("p", "a"), instance_id_for("p", "b"))
        self.assertNotEqual(instance_id_for("p", "a"), instance_id_for("q", "a"))

    def test_identical_payloads_are_distinct_occurrences(self):
        c = create_contract("p", "a", [SPECS[0], SPECS[0]])
        self.assertEqual(len(c.obligations), 2)
        self.assertNotEqual(obligation_key(c.instance_id, "o1"), obligation_key(c.instance_id, "o2"))

    def test_obligation_key_independent_of_grouping(self):
        c = contract()
        k = obligation_key(c.instance_id, "o1")
        self.assertEqual(k, obligation_key(c.instance_id, "o1"))
        self.assertNotEqual(group_scoped_key(c.instance_id, ["o1"]), group_scoped_key(c.instance_id, ["o1", "o2"]))

    def test_contract_json_roundtrip(self):
        c = contract()
        from intent_identity.contract import ApprovalContract

        self.assertEqual(ApprovalContract.from_json(c.to_json()), c)


class PlanCheckerTests(unittest.TestCase):
    def test_accepts_singletons_batch_and_reordering(self):
        c = contract()
        for grouping in ((("o1",), ("o2",), ("o3",), ("o4",)), (("o4", "o3", "o2", "o1"),), (("o2", "o1"), ("o4",), ("o3",))):
            order = check_plan_verified(c, plan_from_grouping(c, grouping))
            self.assertEqual(sorted(order), ["o1", "o2", "o3", "o4"])

    def test_accepts_partial_plan(self):
        c = contract()
        self.assertEqual(check_plan_verified(c, plan_from_grouping(c, (("o2",),))), ["o2"])

    def test_rejects_unapproved_slot(self):
        c = contract()
        p = Plan(c.instance_id, c.schema_version, (Wrapper("single", (ProposedAction("o9", "notify", "x", "y"),)),))
        with self.assertRaises(PlanRejected):
            check_plan_verified(c, p)

    def test_rejects_duplicate_slot_whole_plan(self):
        c = contract()
        a = ProposedAction("o1", SPECS[0].kind, SPECS[0].target, SPECS[0].body)
        p = Plan(c.instance_id, c.schema_version, (Wrapper("single", (a,)), Wrapper("single", (a,))))
        with self.assertRaises(PlanRejected):
            check_plan_verified(c, p)

    def test_rejects_altered_body_target_kind(self):
        c = contract()
        for field, value in (("body", "changed"), ("target", "other@example.test"), ("kind", "pay")):
            kw = {"occurrence_id": "o1", "kind": SPECS[0].kind, "target": SPECS[0].target, "body": SPECS[0].body}
            kw[field] = value
            p = Plan(c.instance_id, c.schema_version, (Wrapper("single", (ProposedAction(**kw),)),))
            with self.assertRaises(PlanRejected):
                check_plan_verified(c, p)

    def test_rejects_uncertified_wrapper_and_arity(self):
        c = contract()
        a = ProposedAction("o1", SPECS[0].kind, SPECS[0].target, SPECS[0].body)
        b = ProposedAction("o2", SPECS[1].kind, SPECS[1].target, SPECS[1].body)
        with self.assertRaises(PlanRejected):
            check_plan_verified(c, Plan(c.instance_id, c.schema_version, (Wrapper("fanout", (a,)),)))
        with self.assertRaises(PlanRejected):
            check_plan_verified(c, Plan(c.instance_id, c.schema_version, (Wrapper("single", (a, b)),)))

    def test_rejects_instance_and_schema_mismatch(self):
        c = contract()
        good = plan_from_grouping(c, (("o1",),))
        with self.assertRaises(PlanRejected):
            check_plan_verified(c, Plan("other", c.schema_version, good.groups))
        with self.assertRaises(PlanRejected):
            check_plan_verified(c, Plan(c.instance_id, "v0", good.groups))

    def test_no_prefix_dispatched_when_later_slot_bad(self):
        c = contract()
        good = ProposedAction("o1", SPECS[0].kind, SPECS[0].target, SPECS[0].body)
        bad = ProposedAction("o2", SPECS[1].kind, SPECS[1].target, "tampered")
        p = Plan(c.instance_id, c.schema_version, (Wrapper("single", (good,)), Wrapper("single", (bad,))))
        with self.assertRaises(PlanRejected):
            check_plan_verified(c, p)

    def test_reference_checker_matches_same_slots(self):
        c = contract()
        p = plan_from_grouping(c, (("o3", "o1"), ("o2",)))
        self.assertEqual(check_actions_reference(c, flatten(p)), ["o3", "o1", "o2"])
        bad = flatten(p) + [ProposedAction("o1", "notify", SPECS[0].target, SPECS[0].body)]
        with self.assertRaises(PlanRejected):
            check_actions_reference(c, bad)

    def test_residualize_keeps_grouping(self):
        r = residualize([["o1", "o2"], ["o3"], ["o4"]], {"o2", "o3"})
        self.assertEqual(r.remaining, [["o1"], ["o4"]])
        self.assertEqual(sorted(r.skipped), ["o2", "o3"])

    def test_plan_dict_roundtrip(self):
        c = contract()
        p = plan_from_grouping(c, (("o1", "o2"), ("o3",)))
        self.assertEqual(Plan.from_dict(p.to_dict()), p)


class AbstractSinkTests(unittest.TestCase):
    def test_cut_patterns_and_groupings_count(self):
        for n in range(1, 5):
            self.assertEqual(len(cut_patterns(n)), 2 ** (n - 1))
            self.assertEqual(len(all_groupings("abcd"[:n])), 2 ** (n - 1) * __import__("math").factorial(n))

    def test_dedup_and_expiry(self):
        s = AbstractSink()
        s.execute("k", "a")
        s.execute("k", "a")
        self.assertEqual(s.effect_counts()["a"], 1)
        s.expire_retention()
        s.execute("k", "a")
        self.assertEqual(s.effect_counts()["a"], 2)
        self.assertTrue(s.lookup("a"))
        self.assertFalse(s.lookup("b"))


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "c.sqlite"

    def tearDown(self):
        self.tmp.cleanup()

    def test_register_is_idempotent_on_approval_event(self):
        L = Ledger(self.db, "w")
        c = contract()
        L.register_contract(c)
        again = L.register_contract(create_contract("p", "approval-1", SPECS))
        self.assertEqual(again.instance_id, c.instance_id)
        self.assertEqual(L.conn.execute("SELECT COUNT(*) FROM contracts").fetchone()[0], 1)
        self.assertEqual(set(L.states(c.instance_id).values()), {"ready"})

    def test_reserve_transitions_and_lease_takeover(self):
        c = contract()
        A = Ledger(self.db, "A")
        A.register_contract(c)
        held, occ = A.reserve(c.instance_id, "o1", lease_seconds=0.05, retention_seconds=10)
        self.assertFalse(held)
        self.assertEqual(occ.state, "held")
        B = Ledger(self.db, "B")
        held_b, occ_b = B.reserve(c.instance_id, "o1", lease_seconds=1, retention_seconds=10)
        self.assertFalse(held_b)
        self.assertEqual(occ_b.worker_id, "A")  # live lease: no takeover
        import time

        time.sleep(0.08)
        held_b, occ_b = B.reserve(c.instance_id, "o1", lease_seconds=1, retention_seconds=10)
        self.assertTrue(held_b)
        self.assertEqual(occ_b.worker_id, "B")
        self.assertEqual(occ_b.retention_deadline, occ.retention_deadline)  # not extended

    def test_predecessor_takeover_and_confirm_binding(self):
        c = contract()
        A = Ledger(self.db, "A")
        A.register_contract(c)
        A.reserve(c.instance_id, "o2", 100, None)
        S = Ledger(self.db, "S")
        held, occ = S.reserve(c.instance_id, "o2", 100, None, predecessor="A")
        self.assertTrue(held)
        with self.assertRaises(ValueError):
            S.confirm(c.instance_id, "o2", "rcpt", "wrong-hash", occ.effect_key)
        S.confirm(c.instance_id, "o2", "rcpt", SPECS[1].payload_hash(), occ.effect_key)
        self.assertEqual(S.get(c.instance_id, "o2").state, "done")

    def test_unresolved_and_rekey(self):
        c = contract()
        L = Ledger(self.db, "w")
        L.register_contract(c)
        L.reserve(c.instance_id, "o3", 100, None)
        L.rekey(c.instance_id, "o3", "newkey", 1)
        self.assertEqual(L.get(c.instance_id, "o3").generation, 1)
        L.mark_unresolved(c.instance_id, "o3", "test")
        self.assertEqual(L.get(c.instance_id, "o3").state, "unresolved")


class ModelCheckerTests(unittest.TestCase):
    def test_safe_configuration_exhausts(self):
        r = explore(Config())
        self.assertTrue(r.exhausted)
        self.assertIsNone(r.violation)

    def test_each_mutant_has_witness(self):
        for cfg, expected in (
            (Config(name="a", certify_requires_fence=False), "duplicate"),
            (Config(name="b", fresh_key_requires_certificate=False), "duplicate"),
            (Config(name="c", done_requires_receipt=False), "false success"),
            (Config(name="d", sink_dedup=False), "duplicate"),
            (Config(name="e", send_respects_retention=False), "duplicate"),
        ):
            r = explore(cfg)
            self.assertEqual(r.violation, expected, cfg.name)


class BeliefTests(unittest.TestCase):
    def test_frontier_matches_bruteforce_small(self):
        B = belief.family([{0}, {0, 1}])
        self.assertEqual(belief.certainly_absent(B, 3), frozenset({2}))
        self.assertTrue(belief.safe_fresh_dispatch_bruteforce(B, frozenset({2})))
        self.assertFalse(belief.safe_fresh_dispatch_bruteforce(B, frozenset({1})))

    def test_ternary_projection_and_witness(self):
        B1 = belief.family([{0}, {1}])
        B2 = belief.independent_family(2)
        self.assertEqual(belief.ternary_projection(B1, 2), belief.ternary_projection(B2, 2))
        self.assertEqual(belief.optimal_probe_cost(B1), 1.0)
        self.assertEqual(belief.optimal_probe_cost(B2), 2.0)

    def test_closed_forms(self):
        self.assertAlmostEqual(belief.exact_k_expected_cost(8, 4), 6.4)
        self.assertAlmostEqual(belief.optimal_probe_cost(belief.exact_k_family(8, 4)), 6.4)
        for n in range(1, 9):
            self.assertAlmostEqual(belief.optimal_probe_cost(belief.prefix_family(n)), belief.prefix_expected_cost(n))
            self.assertEqual(belief.optimal_probe_cost(belief.atomic_family(n)), 1.0)
            self.assertEqual(belief.optimal_probe_cost(belief.independent_family(n)), float(n))


if __name__ == "__main__":
    unittest.main()
