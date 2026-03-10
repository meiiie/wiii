"""Manifest-driven catalog for privileged sandbox workloads."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import yaml

from app.sandbox.models import SandboxNetworkMode, SandboxWorkloadKind

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SandboxWorkloadProfile:
    """Declarative workload profile loaded from a manifest file."""

    profile_id: str
    display_name: str
    description: str
    workload_kind: SandboxWorkloadKind
    runtime_template: Optional[str] = None
    network_mode: Optional[SandboxNetworkMode] = None
    timeout_seconds: Optional[int] = None
    working_directory: Optional[str] = None
    approval_scope: str = ""
    execution_backend: str = ""
    tool_names: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    manifest_path: Optional[Path] = None


class SandboxWorkloadCatalog:
    """Load and query sandbox workload manifests from disk."""

    def __init__(self, workloads_dir: Optional[Path] = None):
        self._workloads_dir = workloads_dir or Path(__file__).with_name("workloads")
        self._profiles: dict[str, SandboxWorkloadProfile] = {}
        self._tool_index: dict[str, SandboxWorkloadProfile] = {}
        self.refresh()

    def refresh(self) -> int:
        """Reload workload manifests from disk."""
        profiles: dict[str, SandboxWorkloadProfile] = {}
        tool_index: dict[str, SandboxWorkloadProfile] = {}

        if not self._workloads_dir.exists():
            logger.warning(
                "Sandbox workloads directory not found: %s",
                self._workloads_dir,
            )
            self._profiles = {}
            self._tool_index = {}
            return 0

        for path in sorted(self._workloads_dir.glob("*.yaml")):
            profile = self._load_profile(path)
            if profile is None:
                continue

            if profile.profile_id in profiles:
                logger.warning(
                    "Duplicate sandbox workload profile '%s' in %s",
                    profile.profile_id,
                    path,
                )
                continue

            profiles[profile.profile_id] = profile
            for tool_name in profile.tool_names:
                if tool_name in tool_index:
                    logger.warning(
                        "Tool '%s' already mapped to sandbox profile '%s'; skipping '%s'",
                        tool_name,
                        tool_index[tool_name].profile_id,
                        profile.profile_id,
                    )
                    continue
                tool_index[tool_name] = profile

        self._profiles = profiles
        self._tool_index = tool_index
        logger.info("Sandbox workload catalog refreshed: %d profile(s)", len(profiles))
        return len(profiles)

    def get(self, profile_id: str) -> Optional[SandboxWorkloadProfile]:
        """Get a workload profile by ID."""
        return self._profiles.get(profile_id)

    def get_all(self) -> list[SandboxWorkloadProfile]:
        """Return all loaded workload profiles."""
        return list(self._profiles.values())

    def find_by_tool_name(self, tool_name: str) -> Optional[SandboxWorkloadProfile]:
        """Resolve the workload profile bound to a tool name."""
        return self._tool_index.get(tool_name)

    def _load_profile(self, path: Path) -> Optional[SandboxWorkloadProfile]:
        """Parse and validate a single workload manifest."""
        try:
            with path.open("r", encoding="utf-8") as handle:
                raw = yaml.safe_load(handle) or {}
        except Exception as exc:
            logger.warning("Failed to load sandbox workload manifest %s: %s", path, exc)
            return None

        if not isinstance(raw, dict):
            logger.warning("Sandbox workload manifest %s must contain a mapping", path)
            return None

        profile_id = str(raw.get("id", "")).strip()
        workload_kind_raw = str(raw.get("workload_kind", "")).strip()
        if not profile_id or not workload_kind_raw:
            logger.warning(
                "Sandbox workload manifest %s missing required fields 'id'/'workload_kind'",
                path,
            )
            return None

        try:
            workload_kind = SandboxWorkloadKind(workload_kind_raw)
        except ValueError:
            logger.warning(
                "Sandbox workload manifest %s has unknown workload_kind '%s'",
                path,
                workload_kind_raw,
            )
            return None

        network_mode_raw = raw.get("network_mode")
        network_mode = None
        if network_mode_raw:
            try:
                network_mode = SandboxNetworkMode(str(network_mode_raw))
            except ValueError:
                logger.warning(
                    "Sandbox workload manifest %s has unknown network_mode '%s'",
                    path,
                    network_mode_raw,
                )
                return None

        timeout_seconds = raw.get("timeout_seconds")
        if timeout_seconds is not None:
            try:
                timeout_seconds = int(timeout_seconds)
            except (TypeError, ValueError):
                logger.warning(
                    "Sandbox workload manifest %s has invalid timeout_seconds '%s'",
                    path,
                    timeout_seconds,
                )
                return None

        metadata = raw.get("metadata") or {}
        if not isinstance(metadata, dict):
            logger.warning(
                "Sandbox workload manifest %s field 'metadata' must be a mapping",
                path,
            )
            return None

        return SandboxWorkloadProfile(
            profile_id=profile_id,
            display_name=str(raw.get("display_name") or profile_id),
            description=str(raw.get("description") or ""),
            workload_kind=workload_kind,
            runtime_template=_maybe_str(raw.get("runtime_template")),
            network_mode=network_mode,
            timeout_seconds=timeout_seconds,
            working_directory=_maybe_str(raw.get("working_directory")),
            approval_scope=str(raw.get("approval_scope") or ""),
            execution_backend=str(raw.get("execution_backend") or ""),
            tool_names=tuple(
                str(tool_name)
                for tool_name in raw.get("tool_names", []) or []
                if str(tool_name).strip()
            ),
            capabilities=tuple(
                str(capability)
                for capability in raw.get("capabilities", []) or []
                if str(capability).strip()
            ),
            metadata=dict(metadata),
            manifest_path=path,
        )


def _maybe_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


@lru_cache
def get_sandbox_workload_catalog() -> SandboxWorkloadCatalog:
    """Return the singleton sandbox workload catalog."""
    return SandboxWorkloadCatalog()


def reset_sandbox_workload_catalog() -> None:
    """Clear cached catalog instance. Used in tests."""
    get_sandbox_workload_catalog.cache_clear()
