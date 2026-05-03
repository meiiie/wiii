"""Sandbox snapshot capture + restore.

Phase 23 of the runtime migration epic (issue #207). The existing Wiii
sandbox layer is provider-neutral and manifest-driven, but every
execution starts from a clean state. For long-running agent flows
(browser session that wants to resume, multi-step Python execution
where intermediate state matters, "warm" sandboxes for repeated tool
calls), starting cold every time is wasteful.

A snapshot is a frozen reference to a point-in-time sandbox state:

- ``snapshot_id`` — opaque, generated.
- ``base_workload`` — the manifest profile used to spawn the original
  sandbox. Restoring requires the same profile to exist.
- ``files`` — dict of in-sandbox path → content hash. Materialization
  reconstructs files on restore by reading from the configured store.
- ``env`` — captured environment variables (caller declares which keys
  to capture; default is none for safety).
- ``metadata`` — execution context (org_id, user_id, parent_session_id,
  the assistant turn that produced this snapshot).

The store interface is deliberately minimal so backends can be added
incrementally. The default ``InMemorySnapshotStore`` is for tests +
dev. ``FilesystemSnapshotStore`` writes JSON manifests to disk and
content-addressed blobs alongside.

Materialization is lazy — restoring a snapshot does NOT immediately
hydrate the files; it returns a ``MaterializationConfig`` that the
executor consumes when it builds the new sandbox. This matches the
openai-agents-python pattern of materializing on demand.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Protocol

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SandboxSnapshot:
    """Frozen reference to a sandbox state at a point in time."""

    snapshot_id: str
    base_workload: str
    """Manifest profile id (e.g. ``python_exec``, ``browser_playwright``)."""

    files: dict[str, str]
    """Map of in-sandbox path → SHA-256 content hash. The actual content
    lives in the snapshot store keyed by hash."""

    env: dict[str, str] = field(default_factory=dict)
    """Captured environment variables. Empty by default — callers opt in
    by passing ``env_keys`` to ``capture``."""

    metadata: dict = field(default_factory=dict)
    """Free-form context: org_id, user_id, parent_session_id, source
    assistant_message seq, etc."""

    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @classmethod
    def new(
        cls,
        *,
        base_workload: str,
        files: Optional[dict[str, str]] = None,
        env: Optional[dict[str, str]] = None,
        metadata: Optional[dict] = None,
    ) -> "SandboxSnapshot":
        """Mint a fresh snapshot id + return the model."""
        return cls(
            snapshot_id=f"snap_{uuid.uuid4().hex[:16]}",
            base_workload=base_workload,
            files=dict(files or {}),
            env=dict(env or {}),
            metadata=dict(metadata or {}),
        )


@dataclass(slots=True)
class MaterializationConfig:
    """How an executor should hydrate a snapshot when spawning a sandbox.

    Returned by ``SnapshotStore.prepare_restore``. The executor consumes
    this when building the sandbox spec — copying files into the
    workspace, exporting env, etc.
    """

    base_workload: str
    files: dict[str, bytes]
    """Hydrated content keyed by in-sandbox path. The store reads from
    its hash-keyed blob layer to populate this."""

    env: dict[str, str] = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


def hash_content(content: bytes) -> str:
    """SHA-256 of the bytes, hex-encoded. Used as the blob key."""
    return hashlib.sha256(content).hexdigest()


class SnapshotStore(Protocol):
    """Backend-neutral interface every snapshot consumer depends on."""

    async def put(
        self, snapshot: SandboxSnapshot, blobs: dict[str, bytes]
    ) -> None:
        """Persist a snapshot manifest plus its blob content.

        ``blobs`` maps content hash → bytes. The store deduplicates by
        hash so two snapshots that share content store the body once.
        """
        ...

    async def get(self, snapshot_id: str) -> Optional[SandboxSnapshot]:
        """Return the snapshot manifest or ``None`` if unknown."""
        ...

    async def prepare_restore(
        self, snapshot_id: str
    ) -> Optional[MaterializationConfig]:
        """Read a snapshot + hydrate its files into a ``MaterializationConfig``.

        Returns ``None`` if the snapshot is missing OR any blob is
        unreadable — partial restore would corrupt the workload.
        """
        ...

    async def delete(self, snapshot_id: str) -> bool:
        """Drop a snapshot. Idempotent. Returns True if anything was removed."""
        ...


class InMemorySnapshotStore:
    """Process-local store used in tests + dev mode.

    Loses state on restart. Backed by two dicts: snapshot_id → manifest,
    content_hash → bytes. A single ``asyncio.Lock`` guards both so
    concurrent put / get / delete stay coherent.
    """

    def __init__(self) -> None:
        self._snapshots: dict[str, SandboxSnapshot] = {}
        self._blobs: dict[str, bytes] = {}
        self._lock = asyncio.Lock()

    async def put(
        self, snapshot: SandboxSnapshot, blobs: dict[str, bytes]
    ) -> None:
        async with self._lock:
            self._snapshots[snapshot.snapshot_id] = snapshot
            for content_hash, body in blobs.items():
                # Verify the hash matches before storing — caller bug
                # otherwise.
                if hash_content(body) != content_hash:
                    raise ValueError(
                        f"blob hash mismatch for {content_hash[:8]}..."
                    )
                self._blobs[content_hash] = body

    async def get(self, snapshot_id: str) -> Optional[SandboxSnapshot]:
        async with self._lock:
            return self._snapshots.get(snapshot_id)

    async def prepare_restore(
        self, snapshot_id: str
    ) -> Optional[MaterializationConfig]:
        async with self._lock:
            snapshot = self._snapshots.get(snapshot_id)
            if snapshot is None:
                return None
            files: dict[str, bytes] = {}
            for in_sandbox_path, content_hash in snapshot.files.items():
                blob = self._blobs.get(content_hash)
                if blob is None:
                    logger.warning(
                        "[InMemorySnapshotStore] missing blob %s for snapshot %s",
                        content_hash[:8],
                        snapshot_id,
                    )
                    return None
                files[in_sandbox_path] = blob
            return MaterializationConfig(
                base_workload=snapshot.base_workload,
                files=files,
                env=dict(snapshot.env),
                metadata=dict(snapshot.metadata),
            )

    async def delete(self, snapshot_id: str) -> bool:
        async with self._lock:
            snapshot = self._snapshots.pop(snapshot_id, None)
            if snapshot is None:
                return False
            # Reference-count blobs across remaining snapshots before
            # garbage-collecting; conservative approach to avoid losing
            # a blob that another snapshot still needs.
            referenced: set[str] = set()
            for snap in self._snapshots.values():
                referenced.update(snap.files.values())
            for content_hash in snapshot.files.values():
                if content_hash not in referenced:
                    self._blobs.pop(content_hash, None)
            return True


class FilesystemSnapshotStore:
    """Disk-backed snapshot store.

    Layout::

        {base_dir}/manifests/{snapshot_id}.json
        {base_dir}/blobs/{first-2-hex}/{rest-of-hex}

    The two-level blob directory keeps inode counts manageable on
    typical filesystems even with millions of blobs. Content addressing
    means two snapshots that share files share blobs automatically.
    """

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self._manifests = self.base_dir / "manifests"
        self._blobs = self.base_dir / "blobs"
        self._lock = asyncio.Lock()

    def _blob_path(self, content_hash: str) -> Path:
        if len(content_hash) < 4:
            raise ValueError("content hash too short")
        return self._blobs / content_hash[:2] / content_hash[2:]

    async def put(
        self, snapshot: SandboxSnapshot, blobs: dict[str, bytes]
    ) -> None:
        async with self._lock:
            self._manifests.mkdir(parents=True, exist_ok=True)
            self._blobs.mkdir(parents=True, exist_ok=True)
            for content_hash, body in blobs.items():
                if hash_content(body) != content_hash:
                    raise ValueError(
                        f"blob hash mismatch for {content_hash[:8]}..."
                    )
                blob_path = self._blob_path(content_hash)
                blob_path.parent.mkdir(parents=True, exist_ok=True)
                if not blob_path.exists():
                    blob_path.write_bytes(body)
            manifest_path = self._manifests / f"{snapshot.snapshot_id}.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "snapshot_id": snapshot.snapshot_id,
                        "base_workload": snapshot.base_workload,
                        "files": snapshot.files,
                        "env": snapshot.env,
                        "metadata": snapshot.metadata,
                        "created_at": snapshot.created_at,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

    async def get(self, snapshot_id: str) -> Optional[SandboxSnapshot]:
        async with self._lock:
            manifest_path = self._manifests / f"{snapshot_id}.json"
            if not manifest_path.exists():
                return None
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            return SandboxSnapshot(**data)

    async def prepare_restore(
        self, snapshot_id: str
    ) -> Optional[MaterializationConfig]:
        snapshot = await self.get(snapshot_id)
        if snapshot is None:
            return None
        files: dict[str, bytes] = {}
        async with self._lock:
            for in_sandbox_path, content_hash in snapshot.files.items():
                blob_path = self._blob_path(content_hash)
                if not blob_path.exists():
                    logger.warning(
                        "[FilesystemSnapshotStore] missing blob %s for snapshot %s",
                        content_hash[:8],
                        snapshot_id,
                    )
                    return None
                files[in_sandbox_path] = blob_path.read_bytes()
        return MaterializationConfig(
            base_workload=snapshot.base_workload,
            files=files,
            env=dict(snapshot.env),
            metadata=dict(snapshot.metadata),
        )

    async def delete(self, snapshot_id: str) -> bool:
        async with self._lock:
            manifest_path = self._manifests / f"{snapshot_id}.json"
            if not manifest_path.exists():
                return False
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            doomed_hashes = set((data.get("files") or {}).values())
            manifest_path.unlink()
            # Reference-count: scan remaining manifests and only remove
            # blobs nobody else references.
            referenced: set[str] = set()
            for path in self._manifests.glob("*.json"):
                try:
                    other = json.loads(path.read_text(encoding="utf-8"))
                    referenced.update((other.get("files") or {}).values())
                except Exception:
                    continue
            for content_hash in doomed_hashes - referenced:
                blob_path = self._blob_path(content_hash)
                if blob_path.exists():
                    try:
                        blob_path.unlink()
                    except OSError:
                        # Concurrent reader / permission glitch — skip; the
                        # next delete pass will pick it up.
                        pass
            return True


_singleton: Optional[SnapshotStore] = None


def get_snapshot_store() -> SnapshotStore:
    """Return the configured snapshot store.

    Routes to ``FilesystemSnapshotStore`` when
    ``settings.sandbox_snapshot_dir`` is set, otherwise falls back to
    in-memory (suitable for tests + dev).
    """
    global _singleton
    if _singleton is not None:
        return _singleton

    try:
        from app.core.config import settings

        snapshot_dir = getattr(settings, "sandbox_snapshot_dir", None)
        if snapshot_dir:
            _singleton = FilesystemSnapshotStore(base_dir=Path(snapshot_dir))
            return _singleton
    except (ImportError, AttributeError):
        logger.debug("[snapshot] settings unavailable; using in-memory")

    _singleton = InMemorySnapshotStore()
    return _singleton


def _reset_for_tests() -> None:
    """Clear the singleton — test fixtures only."""
    global _singleton
    _singleton = None


__all__ = [
    "SandboxSnapshot",
    "MaterializationConfig",
    "SnapshotStore",
    "InMemorySnapshotStore",
    "FilesystemSnapshotStore",
    "get_snapshot_store",
    "hash_content",
]
