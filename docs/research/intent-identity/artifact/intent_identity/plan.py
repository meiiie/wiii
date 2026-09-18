"""Untrusted plans, whole-plan checking and the two runtime policies' checkers.

The executable language is deliberately restricted (manuscript III.A):
exact ``(kind, target, body)`` tuples with kind ``notify``, wrapped in a
``single`` wrapper (arity 1) or a ``batch`` wrapper (arity >= 1). No aliases,
no free-text inference, no decomposition, no state-dependent transformation.

Two checkers share the same output type, an ordered list of approved
occurrence ids, so that transport and persistence are identical for both:

* ``check_plan_verified`` (policy V): typed wrapper membership check on the
  whole proposal, then executable payloads are reconstructed from the
  immutable contract;
* ``check_actions_reference`` (policy R): direct canonical-action matching of
  each proposed flat action against the contract slot it claims.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

from .contract import ApprovalContract, EffectSpec

CERTIFIED_WRAPPERS = {"single": (1, 1), "batch": (1, None)}
ALLOWED_KINDS = {"notify"}


class PlanRejected(ValueError):
    """The whole proposal is rejected; no prefix is dispatched."""


@dataclass(frozen=True)
class ProposedAction:
    occurrence_id: str
    kind: str
    target: str
    body: str


@dataclass(frozen=True)
class Wrapper:
    wrapper: str
    actions: tuple[ProposedAction, ...]


@dataclass(frozen=True)
class Plan:
    instance_id: str
    schema_version: str
    groups: tuple[Wrapper, ...]

    def to_dict(self) -> dict:
        return {
            "instance_id": self.instance_id,
            "schema_version": self.schema_version,
            "groups": [
                {
                    "wrapper": g.wrapper,
                    "actions": [
                        {
                            "occurrence_id": a.occurrence_id,
                            "kind": a.kind,
                            "target": a.target,
                            "body": a.body,
                        }
                        for a in g.actions
                    ],
                }
                for g in self.groups
            ],
        }

    @staticmethod
    def from_dict(raw: dict) -> "Plan":
        return Plan(
            instance_id=raw["instance_id"],
            schema_version=raw["schema_version"],
            groups=tuple(
                Wrapper(
                    g["wrapper"],
                    tuple(
                        ProposedAction(
                            a["occurrence_id"], a["kind"], a["target"], a["body"]
                        )
                        for a in g["actions"]
                    ),
                )
                for g in raw["groups"]
            ),
        )


def plan_from_grouping(
    contract: ApprovalContract, grouping: Sequence[Sequence[str]]
) -> Plan:
    """Build an honest proposal for an ordered grouping of occurrence ids."""
    groups = []
    for members in grouping:
        actions = tuple(
            ProposedAction(
                m, contract.spec(m).kind, contract.spec(m).target, contract.spec(m).body
            )
            for m in members
        )
        groups.append(Wrapper("single" if len(members) == 1 else "batch", actions))
    return Plan(contract.instance_id, contract.schema_version, tuple(groups))


def _check_slot(contract: ApprovalContract, a: ProposedAction, seen: set[str]) -> None:
    if a.occurrence_id not in contract.obligations:
        raise PlanRejected(f"unapproved occurrence {a.occurrence_id!r}")
    if a.occurrence_id in seen:
        raise PlanRejected(f"occurrence {a.occurrence_id!r} proposed twice")
    if a.kind not in ALLOWED_KINDS:
        raise PlanRejected(f"kind {a.kind!r} not in executable language")
    spec = contract.spec(a.occurrence_id)
    if (a.kind, a.target, a.body) != (spec.kind, spec.target, spec.body):
        raise PlanRejected(f"occurrence {a.occurrence_id!r} does not match contract")
    seen.add(a.occurrence_id)


def check_plan_verified(contract: ApprovalContract, plan: Plan) -> list[str]:
    """Policy V: whole-plan typed wrapper check. Returns approved slot order."""
    if plan.instance_id != contract.instance_id:
        raise PlanRejected("instance mismatch")
    if plan.schema_version != contract.schema_version:
        raise PlanRejected("schema mismatch")
    seen: set[str] = set()
    order: list[str] = []
    for g in plan.groups:
        if g.wrapper not in CERTIFIED_WRAPPERS:
            raise PlanRejected(f"uncertified wrapper {g.wrapper!r}")
        lo, hi = CERTIFIED_WRAPPERS[g.wrapper]
        if len(g.actions) < lo or (hi is not None and len(g.actions) > hi):
            raise PlanRejected(f"illegal arity {len(g.actions)} for {g.wrapper!r}")
        for a in g.actions:
            _check_slot(contract, a, seen)
            order.append(a.occurrence_id)
    return order


def check_actions_reference(
    contract: ApprovalContract, actions: Iterable[ProposedAction]
) -> list[str]:
    """Policy R: canonical-action matching of a flat action list."""
    seen: set[str] = set()
    order: list[str] = []
    for a in actions:
        _check_slot(contract, a, seen)
        order.append(a.occurrence_id)
    return order


def flatten(plan: Plan) -> list[ProposedAction]:
    return [a for g in plan.groups for a in g.actions]


def executable_spec(contract: ApprovalContract, occurrence_id: str) -> EffectSpec:
    """Executable bytes always come from the immutable contract, never from the plan."""
    return contract.spec(occurrence_id)


@dataclass
class Residual:
    """Policy V residualization: drop already-completed occurrences, keep grouping."""

    remaining: list[list[str]] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def residualize(order_groups: Sequence[Sequence[str]], completed: set[str]) -> Residual:
    res = Residual()
    for members in order_groups:
        keep = [m for m in members if m not in completed]
        res.skipped.extend(m for m in members if m in completed)
        if keep:
            res.remaining.append(keep)
    return res
