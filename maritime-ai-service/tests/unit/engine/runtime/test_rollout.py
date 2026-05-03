"""Phase 14 native runtime rollout resolution — Runtime Migration #207.

Locks the truth table:
- global=True → on for everyone
- global=False + non-empty allowlist → on only for allowlisted orgs
- global=False + empty allowlist → off for everyone
"""

from __future__ import annotations

import pytest

from app.engine.runtime.rollout import (
    is_native_runtime_enabled_for,
    is_native_runtime_enabled_globally_or_canary,
)


@pytest.fixture
def settings_module(monkeypatch):
    """Yield a settings handle bound to ``monkeypatch`` so changes auto-revert."""
    from app.core import config as config_module

    yield (config_module.settings, monkeypatch)


def _set(handle, *, global_on: bool, allowlist):
    """Apply settings via monkeypatch so teardown restores defaults."""
    settings, monkeypatch = handle
    monkeypatch.setattr(settings, "enable_native_runtime", global_on, raising=False)
    monkeypatch.setattr(
        settings, "native_runtime_org_allowlist", list(allowlist), raising=False
    )


# ── per-org gate ──

def test_global_on_allows_any_org(settings_module):
    _set(settings_module, global_on=True, allowlist=[])
    assert is_native_runtime_enabled_for("org-A") is True
    assert is_native_runtime_enabled_for("org-B") is True
    assert is_native_runtime_enabled_for(None) is True


def test_global_off_empty_allowlist_blocks_everyone(settings_module):
    _set(settings_module, global_on=False, allowlist=[])
    assert is_native_runtime_enabled_for("org-A") is False
    assert is_native_runtime_enabled_for(None) is False


def test_global_off_allowlist_admits_only_listed_orgs(settings_module):
    _set(settings_module, global_on=False, allowlist=["org-A", "org-B"])
    assert is_native_runtime_enabled_for("org-A") is True
    assert is_native_runtime_enabled_for("org-B") is True
    assert is_native_runtime_enabled_for("org-C") is False
    # No org id at all → cannot match.
    assert is_native_runtime_enabled_for(None) is False


def test_allowlist_match_is_case_sensitive(settings_module):
    _set(settings_module, global_on=False, allowlist=["org-A"])
    assert is_native_runtime_enabled_for("org-a") is False
    assert is_native_runtime_enabled_for("org-A") is True


# ── startup-time predicate ──

def test_startup_predicate_off_when_both_disabled(settings_module):
    _set(settings_module, global_on=False, allowlist=[])
    assert is_native_runtime_enabled_globally_or_canary() is False


def test_startup_predicate_on_when_canary_active(settings_module):
    _set(settings_module, global_on=False, allowlist=["org-A"])
    assert is_native_runtime_enabled_globally_or_canary() is True


def test_startup_predicate_on_when_global_active(settings_module):
    _set(settings_module, global_on=True, allowlist=[])
    assert is_native_runtime_enabled_globally_or_canary() is True


def test_startup_predicate_global_overrides_empty_allowlist(settings_module):
    _set(settings_module, global_on=True, allowlist=[])
    assert is_native_runtime_enabled_globally_or_canary() is True
    assert is_native_runtime_enabled_for("anything") is True
