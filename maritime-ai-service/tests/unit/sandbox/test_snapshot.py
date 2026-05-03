"""Phase 23 sandbox snapshot store — Runtime Migration #207.

Locks the contract:
- Capture: put manifest + blobs, blob hash matches body.
- Restore: prepare_restore hydrates files; missing blob → None (no
  partial restore that corrupts the workload).
- Delete: idempotent, ref-counts blobs across remaining snapshots.
- Both InMemory and Filesystem backends honour the same contract.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.sandbox.snapshot import (
    FilesystemSnapshotStore,
    InMemorySnapshotStore,
    MaterializationConfig,
    SandboxSnapshot,
    hash_content,
)


def _make_snapshot(files: dict[str, bytes]):
    """Return a (snapshot, blobs) pair ready to put into a store."""
    file_hashes = {path: hash_content(body) for path, body in files.items()}
    snap = SandboxSnapshot.new(
        base_workload="python_exec",
        files=file_hashes,
        env={"FOO": "bar"},
        metadata={"org_id": "org-A"},
    )
    blobs = {hash_content(body): body for body in files.values()}
    return snap, blobs


# ── SandboxSnapshot model ──

def test_new_generates_unique_id():
    a = SandboxSnapshot.new(base_workload="python_exec")
    b = SandboxSnapshot.new(base_workload="python_exec")
    assert a.snapshot_id != b.snapshot_id
    assert a.snapshot_id.startswith("snap_")


def test_new_defaults_are_safe():
    s = SandboxSnapshot.new(base_workload="python_exec")
    assert s.files == {}
    assert s.env == {}
    assert s.metadata == {}
    assert s.created_at  # ISO timestamp string


def test_hash_content_is_deterministic():
    assert hash_content(b"hello") == hash_content(b"hello")
    assert hash_content(b"hello") != hash_content(b"world")


# ── InMemorySnapshotStore ──

@pytest.fixture
def in_memory_store():
    return InMemorySnapshotStore()


async def test_put_and_get_round_trips(in_memory_store):
    snap, blobs = _make_snapshot({"/a.txt": b"first", "/b.txt": b"second"})
    await in_memory_store.put(snap, blobs)
    revived = await in_memory_store.get(snap.snapshot_id)
    assert revived is not None
    assert revived.snapshot_id == snap.snapshot_id
    assert revived.files == snap.files


async def test_put_rejects_blob_hash_mismatch(in_memory_store):
    snap, _ = _make_snapshot({"/a.txt": b"real"})
    bad_blobs = {"deadbeef" * 8: b"different content"}
    with pytest.raises(ValueError, match="hash mismatch"):
        await in_memory_store.put(snap, bad_blobs)


async def test_get_missing_returns_none(in_memory_store):
    assert await in_memory_store.get("snap_does_not_exist") is None


async def test_prepare_restore_hydrates_files(in_memory_store):
    snap, blobs = _make_snapshot({"/a.txt": b"first", "/b.txt": b"second"})
    await in_memory_store.put(snap, blobs)
    config = await in_memory_store.prepare_restore(snap.snapshot_id)
    assert isinstance(config, MaterializationConfig)
    assert config.base_workload == "python_exec"
    assert config.files == {"/a.txt": b"first", "/b.txt": b"second"}
    assert config.env == {"FOO": "bar"}
    assert config.metadata == {"org_id": "org-A"}


async def test_prepare_restore_missing_returns_none(in_memory_store):
    assert await in_memory_store.prepare_restore("snap_unknown") is None


async def test_prepare_restore_missing_blob_returns_none(in_memory_store):
    """Snapshot manifest exists but a blob is gone → fail closed."""
    snap, blobs = _make_snapshot({"/a.txt": b"content"})
    await in_memory_store.put(snap, blobs)
    # Wipe one blob to simulate corruption.
    in_memory_store._blobs.clear()
    assert await in_memory_store.prepare_restore(snap.snapshot_id) is None


async def test_delete_returns_false_for_unknown(in_memory_store):
    assert await in_memory_store.delete("snap_unknown") is False


async def test_delete_drops_manifest_and_orphan_blobs(in_memory_store):
    snap, blobs = _make_snapshot({"/a.txt": b"first"})
    await in_memory_store.put(snap, blobs)
    assert await in_memory_store.delete(snap.snapshot_id) is True
    assert await in_memory_store.get(snap.snapshot_id) is None
    assert in_memory_store._blobs == {}  # orphan blob garbage-collected


async def test_delete_preserves_shared_blobs(in_memory_store):
    """Two snapshots share content → deleting one keeps the blob."""
    snap_a, blobs_a = _make_snapshot({"/file": b"shared content"})
    await in_memory_store.put(snap_a, blobs_a)
    snap_b, blobs_b = _make_snapshot({"/different": b"shared content"})
    await in_memory_store.put(snap_b, blobs_b)
    # Same content → same hash → only one blob.
    assert len(in_memory_store._blobs) == 1
    # Deleting A should NOT remove the blob — B still references it.
    await in_memory_store.delete(snap_a.snapshot_id)
    assert len(in_memory_store._blobs) == 1
    config = await in_memory_store.prepare_restore(snap_b.snapshot_id)
    assert config is not None
    assert config.files == {"/different": b"shared content"}


# ── FilesystemSnapshotStore ──

@pytest.fixture
def fs_store(tmp_path: Path) -> FilesystemSnapshotStore:
    return FilesystemSnapshotStore(base_dir=tmp_path)


async def test_filesystem_put_creates_layout(tmp_path: Path, fs_store):
    snap, blobs = _make_snapshot({"/a.txt": b"hello"})
    await fs_store.put(snap, blobs)
    assert (tmp_path / "manifests" / f"{snap.snapshot_id}.json").exists()
    # Two-level blob dir layout.
    blob_dirs = list((tmp_path / "blobs").iterdir())
    assert len(blob_dirs) == 1
    assert len(blob_dirs[0].name) == 2  # first 2 hex chars of hash


async def test_filesystem_round_trip(fs_store):
    snap, blobs = _make_snapshot({"/a.txt": b"hello", "/b.txt": b"world"})
    await fs_store.put(snap, blobs)
    config = await fs_store.prepare_restore(snap.snapshot_id)
    assert config is not None
    assert config.files == {"/a.txt": b"hello", "/b.txt": b"world"}


async def test_filesystem_dedupes_blob_writes(tmp_path: Path, fs_store):
    """Same content across two snapshots → one blob on disk."""
    snap_a, blobs_a = _make_snapshot({"/x": b"same content"})
    snap_b, blobs_b = _make_snapshot({"/y": b"same content"})
    await fs_store.put(snap_a, blobs_a)
    await fs_store.put(snap_b, blobs_b)
    # Walk the blob directory; expect exactly 1 file.
    blob_files = list((tmp_path / "blobs").rglob("*"))
    blob_files = [b for b in blob_files if b.is_file()]
    assert len(blob_files) == 1


async def test_filesystem_delete_keeps_referenced_blobs(fs_store, tmp_path: Path):
    snap_a, blobs_a = _make_snapshot({"/x": b"shared"})
    snap_b, blobs_b = _make_snapshot({"/y": b"shared"})
    await fs_store.put(snap_a, blobs_a)
    await fs_store.put(snap_b, blobs_b)
    await fs_store.delete(snap_a.snapshot_id)
    config = await fs_store.prepare_restore(snap_b.snapshot_id)
    assert config is not None
    assert config.files == {"/y": b"shared"}


async def test_filesystem_get_missing_returns_none(fs_store):
    assert await fs_store.get("snap_missing") is None


async def test_filesystem_blob_path_rejects_short_hash(fs_store):
    """Defensive check — caller bug otherwise."""
    with pytest.raises(ValueError, match="too short"):
        fs_store._blob_path("ab")


# ── routing singleton ──

def test_get_snapshot_store_uses_in_memory_when_dir_unset(monkeypatch):
    from app.engine.runtime import session_event_log  # noqa: F401 — trigger module
    from app.sandbox import snapshot as snap_mod

    snap_mod._reset_for_tests()
    from app.core import config as config_module
    monkeypatch.setattr(
        config_module.settings, "sandbox_snapshot_dir", None, raising=False
    )
    store = snap_mod.get_snapshot_store()
    assert isinstance(store, snap_mod.InMemorySnapshotStore)
    snap_mod._reset_for_tests()


def test_get_snapshot_store_uses_filesystem_when_dir_set(monkeypatch, tmp_path):
    from app.sandbox import snapshot as snap_mod

    snap_mod._reset_for_tests()
    from app.core import config as config_module
    monkeypatch.setattr(
        config_module.settings,
        "sandbox_snapshot_dir",
        str(tmp_path),
        raising=False,
    )
    store = snap_mod.get_snapshot_store()
    assert isinstance(store, snap_mod.FilesystemSnapshotStore)
    snap_mod._reset_for_tests()
