"""Approval contracts, obligation occurrences and stable obligation keys.

Three identities (manuscript section III.A):

* approval instance ``iota``: created by the trusted approval layer from the
  authenticated approval event; repeating the same event recovers the same
  instance instead of issuing a new one;
* obligation occurrence ``omega``: one authorized effect occurrence, not a
  payload equivalence class; two identical notifications approved twice are
  two occurrences;
* attempt: a proposed or transmitted implementation of one or more
  occurrences. Attempts never carry authority.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Mapping, Sequence

SCHEMA_VERSION = "intent-identity-contract-v1"
KEY_DOMAIN = "obligation-key-v1"


@dataclass(frozen=True)
class EffectSpec:
    kind: str
    target: str
    body: str

    def canonical(self) -> str:
        return json.dumps(
            {"kind": self.kind, "target": self.target, "body": self.body},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    def payload_hash(self) -> str:
        return hashlib.sha256(self.canonical().encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ApprovalContract:
    instance_id: str
    principal: str
    approval_event: str
    obligations: Mapping[str, EffectSpec]
    schema_version: str = SCHEMA_VERSION

    @property
    def occurrence_ids(self) -> tuple[str, ...]:
        return tuple(self.obligations.keys())

    def spec(self, occurrence_id: str) -> EffectSpec:
        return self.obligations[occurrence_id]

    def to_json(self) -> str:
        return json.dumps(
            {
                "instance_id": self.instance_id,
                "principal": self.principal,
                "approval_event": self.approval_event,
                "schema_version": self.schema_version,
                "obligations": {
                    k: {"kind": v.kind, "target": v.target, "body": v.body}
                    for k, v in self.obligations.items()
                },
            },
            sort_keys=True,
        )

    @staticmethod
    def from_json(text: str) -> "ApprovalContract":
        raw = json.loads(text)
        return ApprovalContract(
            instance_id=raw["instance_id"],
            principal=raw["principal"],
            approval_event=raw["approval_event"],
            schema_version=raw["schema_version"],
            obligations={
                k: EffectSpec(v["kind"], v["target"], v["body"])
                for k, v in raw["obligations"].items()
            },
        )


def instance_id_for(principal: str, approval_event: str) -> str:
    """Deterministic instance identity for one authenticated approval event.

    The trusted layer, not the proposer, derives ``iota``. Re-presenting the
    same (principal, approval_event) must recover the same instance.
    """
    material = "approval-instance-v1\x1f" + principal + "\x1f" + approval_event
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


def create_contract(
    principal: str, approval_event: str, specs: Sequence[EffectSpec]
) -> ApprovalContract:
    iota = instance_id_for(principal, approval_event)
    obligations = {f"o{i + 1}": spec for i, spec in enumerate(specs)}
    return ApprovalContract(iota, principal, approval_event, obligations)


def obligation_key(instance_id: str, occurrence_id: str) -> str:
    """Domain-separated stable key K(iota, omega); independent of grouping."""
    material = KEY_DOMAIN + "\x1f" + instance_id + "\x1f" + occurrence_id
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def group_scoped_key(instance_id: str, members: Sequence[str]) -> str:
    """Request-group-scoped key used only by the weak reference G in D1.

    Stable for the same group membership, different when membership changes.
    """
    material = "group-key-v1\x1f" + instance_id + "\x1f" + ",".join(sorted(members))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
