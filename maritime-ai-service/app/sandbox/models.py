"""Internal models for privileged sandbox execution.

These models define Wiii's execution contract independently from any single
runtime provider. OpenSandbox is the first planned remote provider, but the
tool/MCP layers should depend on these neutral models rather than vendor APIs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Optional

from app.sandbox.path_grants import SandboxPathGrant


class SandboxProvider(StrEnum):
    DISABLED = "disabled"
    LOCAL_SUBPROCESS = "local_subprocess"
    OPENSANDBOX = "opensandbox"


class SandboxWorkloadKind(StrEnum):
    PYTHON = "python"
    COMMAND = "command"
    BROWSER = "browser"


class SandboxNetworkMode(StrEnum):
    DISABLED = "disabled"
    BRIDGE = "bridge"
    EGRESS = "egress"


@dataclass(slots=True)
class SandboxArtifact:
    """Execution artifact returned by a sandbox workload."""

    name: str
    content_type: str = "text/plain"
    url: Optional[str] = None
    path: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SandboxExecutionRequest:
    """Neutral request for a privileged execution workload."""

    workload_kind: SandboxWorkloadKind
    code: Optional[str] = None
    command: Optional[list[str]] = None
    files: dict[str, str] = field(default_factory=dict)
    env: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: Optional[int] = None
    network_mode: Optional[SandboxNetworkMode] = None
    runtime_template: Optional[str] = None
    working_directory: Optional[str] = None
    organization_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None

    # Phase 23 (#207): fine-grained path access. Empty list = backward
    # compat — executors fall back to ``working_directory`` semantics.
    path_grants: list[SandboxPathGrant] = field(default_factory=list)

    # Phase 23: optional snapshot to restore from before workload runs.
    # The executor consumes the snapshot id, materialises files, then
    # runs the workload on top of the restored state.
    restore_snapshot_id: Optional[str] = None


@dataclass(slots=True)
class SandboxExecutionResult:
    """Normalized result from a privileged sandbox workload."""

    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: Optional[int] = None
    error: Optional[str] = None
    sandbox_id: Optional[str] = None
    duration_ms: Optional[int] = None
    artifacts: list[SandboxArtifact] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
