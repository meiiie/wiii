"""Workspace path grants — fine-grained file access for sandbox workloads.

Phase 23 of the runtime migration epic (issue #207). The existing
``SandboxExecutionRequest.working_directory`` is a single flat path; that
works fine for short-lived single-purpose workloads but breaks down when
an agent needs:

- Read access to a shared corpus directory + write access to a scratch
  output directory (different paths, different modes).
- Read-only access to a project tree but write access only to one
  subfolder.
- Mounting an artifact bundle without granting write to the host.

This module models that as a list of explicit ``SandboxPathGrant`` rows.
Each grant declares a path, a mode, and whether the grant recurses.
Executors that honor grants (today: opensandbox; future: any provider
that maps to OCI bind mounts) consume the list at sandbox-spawn time.

Defaults are deliberately permissive at the model layer (no implicit
deny) — the executor decides how to map grants to the underlying
sandbox API. Wiii's OpenSandbox executor today maps grants to bind-mount
spec strings; the LocalSubprocess executor logs them as advisory and
falls back to ``working_directory``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Optional


class SandboxPathMode(StrEnum):
    """Access mode for a single ``SandboxPathGrant``."""

    READ = "read"
    WRITE = "write"
    READWRITE = "readwrite"


@dataclass(slots=True, frozen=True)
class SandboxPathGrant:
    """A single fine-grained path access declaration.

    ``recursive=True`` means the grant applies to the named path and
    every descendant. ``recursive=False`` restricts to the literal path
    (typical for single-file mounts).

    The model is provider-neutral; mapping to bind-mount strings or
    capability tokens happens in the executor.
    """

    path: str
    mode: SandboxPathMode = SandboxPathMode.READ
    recursive: bool = True
    label: Optional[str] = None
    """Optional human-readable tag for telemetry / log lines."""

    def to_mount_string(self) -> str:
        """Render in the canonical Docker-style ``src:dst:mode`` form.

        OpenSandbox accepts mount specs in this shape; other backends
        may want a different rendering (volumes API, OCI spec). This
        helper centralises the convention so executors don't drift.
        """
        mode_token = {
            SandboxPathMode.READ: "ro",
            SandboxPathMode.WRITE: "rw",
            SandboxPathMode.READWRITE: "rw",
        }[self.mode]
        # Single-path bind: src and dst are the same; the executor can
        # remap if it needs to (e.g. chrooted destinations).
        return f"{self.path}:{self.path}:{mode_token}"


def merge_grants(grants: list[SandboxPathGrant]) -> list[SandboxPathGrant]:
    """De-duplicate + sort grants for deterministic executor input.

    When two grants name the same path, the more permissive mode wins
    (``READWRITE`` > ``WRITE`` > ``READ``) and ``recursive=True`` wins
    over False. Labels from both grants are preserved as a comma-joined
    string so log lines do not lose provenance.
    """
    bucket: dict[str, SandboxPathGrant] = {}
    rank = {
        SandboxPathMode.READ: 0,
        SandboxPathMode.WRITE: 1,
        SandboxPathMode.READWRITE: 2,
    }
    for grant in grants:
        existing = bucket.get(grant.path)
        if existing is None:
            bucket[grant.path] = grant
            continue
        # Stronger mode wins; recursive=True wins; labels concatenate.
        winning_mode = (
            grant.mode if rank[grant.mode] > rank[existing.mode] else existing.mode
        )
        winning_recursive = existing.recursive or grant.recursive
        labels = sorted(
            {l for l in (existing.label, grant.label) if l}
        )
        bucket[grant.path] = SandboxPathGrant(
            path=grant.path,
            mode=winning_mode,
            recursive=winning_recursive,
            label=",".join(labels) if labels else None,
        )
    return sorted(bucket.values(), key=lambda g: g.path)


__all__ = ["SandboxPathGrant", "SandboxPathMode", "merge_grants"]
