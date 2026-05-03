"""Phase 23 sandbox path grants — Runtime Migration #207.

Locks the model contract: render canonical mount strings, merge with
mode-precedence + recursive-sticky semantics.
"""

from __future__ import annotations

from app.sandbox.path_grants import (
    SandboxPathGrant,
    SandboxPathMode,
    merge_grants,
)


# ── render ──

def test_to_mount_string_read_mode():
    grant = SandboxPathGrant(path="/data/corpus", mode=SandboxPathMode.READ)
    assert grant.to_mount_string() == "/data/corpus:/data/corpus:ro"


def test_to_mount_string_write_mode():
    grant = SandboxPathGrant(path="/scratch", mode=SandboxPathMode.WRITE)
    assert grant.to_mount_string() == "/scratch:/scratch:rw"


def test_to_mount_string_readwrite_mode():
    grant = SandboxPathGrant(path="/work", mode=SandboxPathMode.READWRITE)
    assert grant.to_mount_string() == "/work:/work:rw"


# ── default values ──

def test_default_mode_is_read():
    grant = SandboxPathGrant(path="/data")
    assert grant.mode == SandboxPathMode.READ


def test_default_recursive_is_true():
    grant = SandboxPathGrant(path="/data")
    assert grant.recursive is True


def test_default_label_is_none():
    grant = SandboxPathGrant(path="/data")
    assert grant.label is None


# ── frozen ──

def test_grant_is_immutable():
    """Phase 23 contract: grants are hashable + frozen so they can be
    cached + compared as dict keys."""
    import dataclasses

    grant = SandboxPathGrant(path="/data")
    try:
        grant.path = "/elsewhere"  # type: ignore[misc]
    except (dataclasses.FrozenInstanceError, AttributeError):
        return  # expected
    raise AssertionError("grant should be frozen")


# ── merge_grants ──

def test_merge_empty_returns_empty():
    assert merge_grants([]) == []


def test_merge_single_grant_returns_single():
    g = SandboxPathGrant(path="/data")
    assert merge_grants([g]) == [g]


def test_merge_distinct_paths_keeps_both():
    a = SandboxPathGrant(path="/a", mode=SandboxPathMode.READ)
    b = SandboxPathGrant(path="/b", mode=SandboxPathMode.WRITE)
    out = merge_grants([a, b])
    assert len(out) == 2
    # Sorted by path.
    assert [g.path for g in out] == ["/a", "/b"]


def test_merge_same_path_picks_stronger_mode():
    """READWRITE > WRITE > READ when two grants name the same path."""
    weak = SandboxPathGrant(path="/x", mode=SandboxPathMode.READ)
    strong = SandboxPathGrant(path="/x", mode=SandboxPathMode.READWRITE)
    out = merge_grants([weak, strong])
    assert len(out) == 1
    assert out[0].mode == SandboxPathMode.READWRITE


def test_merge_same_path_recursive_sticky():
    """Once any grant says recursive=True, the merged grant is recursive."""
    a = SandboxPathGrant(path="/x", recursive=False)
    b = SandboxPathGrant(path="/x", recursive=True)
    out = merge_grants([a, b])
    assert out[0].recursive is True


def test_merge_concatenates_labels():
    a = SandboxPathGrant(path="/x", label="from-tool-a")
    b = SandboxPathGrant(path="/x", label="from-tool-b")
    out = merge_grants([a, b])
    assert out[0].label == "from-tool-a,from-tool-b"


def test_merge_drops_empty_labels():
    a = SandboxPathGrant(path="/x", label=None)
    b = SandboxPathGrant(path="/x", label="real-label")
    out = merge_grants([a, b])
    assert out[0].label == "real-label"


def test_merge_returns_sorted_by_path():
    grants = [
        SandboxPathGrant(path="/zebra"),
        SandboxPathGrant(path="/apple"),
        SandboxPathGrant(path="/mango"),
    ]
    out = merge_grants(grants)
    assert [g.path for g in out] == ["/apple", "/mango", "/zebra"]
