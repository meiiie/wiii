"""Per-org canary rollout resolution for the native runtime.

Phase 14 of the runtime migration epic (issue #207). Lifts the
"native runtime is on or off globally" constraint so canary rollouts
can target a single org first, validate p50/error rate, then expand.

Truth table:
- ``enable_native_runtime=True`` (global) → on for everyone, allowlist
  ignored. Used for the final cutover.
- ``enable_native_runtime=False`` + non-empty allowlist → on only for
  the orgs in the allowlist. Used for the canary phase.
- ``enable_native_runtime=False`` + empty allowlist → off for everyone.
  The default; pre-canary state.

The same helper underpins both:
- ``include_edge_endpoints()`` — registers the router when ANY org would
  see the runtime.
- ``_ensure_enabled()`` per-request — checks the caller's org against
  the allowlist before running the request.
"""

from __future__ import annotations

from typing import Optional


def is_native_runtime_enabled_for(org_id: Optional[str]) -> bool:
    """True when the native runtime is reachable for ``org_id``.

    Pulls settings at call time rather than module import so test
    monkeypatches and live config flips both work.
    """
    from app.core.config import settings

    if settings.enable_native_runtime:
        return True
    allowlist = settings.native_runtime_org_allowlist or []
    if not allowlist:
        return False
    if org_id is None:
        return False
    return org_id in allowlist


def is_native_runtime_enabled_globally_or_canary() -> bool:
    """True when the native runtime is on for AT LEAST ONE org.

    The router needs this at startup to decide whether to register the
    edge routes. Per-request gating still uses
    ``is_native_runtime_enabled_for(org_id)``.
    """
    from app.core.config import settings

    if settings.enable_native_runtime:
        return True
    return bool(settings.native_runtime_org_allowlist)


__all__ = [
    "is_native_runtime_enabled_for",
    "is_native_runtime_enabled_globally_or_canary",
]
