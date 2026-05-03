"""Shared chaos-test fixtures.

Phase 20 of the runtime migration epic (issue #207). Each scenario
imports fixtures from here rather than the unit-test conftest because
chaos tests live outside ``tests/`` (different audience, different
runtime — they hit a real Wiii instance over HTTP, optionally).

The fixtures here are:

- ``wiii_session_log`` — clean InMemorySessionEventLog for the duration
  of one test, with the singleton swapped out and restored afterward.
- ``runtime_metrics_reset`` — resets the Phase 13 façade between tests
  so counters / histograms don't bleed across scenarios.
- ``enable_native_runtime`` — monkeypatches the canary gate fully open
  so the ``native_chat_dispatch`` path runs.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make ``app.*`` importable when pytest is invoked from the repo root.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "maritime-ai-service"))


@pytest.fixture
def runtime_metrics_reset():
    """Snapshot-and-clear the in-memory metrics sink for one test."""
    from app.engine.runtime import runtime_metrics as rm

    rm._reset_for_tests()
    yield rm
    rm._reset_for_tests()


@pytest.fixture
def wiii_session_log(monkeypatch):
    """Provide a clean in-memory event log + swap it for the singleton.

    Yields the log instance so the test can inspect events directly.
    """
    from app.engine.runtime import session_event_log as log_mod
    from app.engine.runtime.session_event_log import InMemorySessionEventLog

    log = InMemorySessionEventLog()
    log_mod._reset_for_tests()
    monkeypatch.setattr(log_mod, "_singleton", log, raising=False)
    yield log
    log_mod._reset_for_tests()


@pytest.fixture
def enable_native_runtime(monkeypatch):
    """Force the Phase 14 canary gate open globally for one test."""
    from app.core import config as config_module

    monkeypatch.setattr(
        config_module.settings, "enable_native_runtime", True, raising=False
    )
    monkeypatch.setattr(
        config_module.settings,
        "native_runtime_org_allowlist",
        [],
        raising=False,
    )
