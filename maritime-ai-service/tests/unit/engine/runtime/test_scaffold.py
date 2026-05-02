"""Phase 0 scaffold smoke tests — Runtime Migration Epic #207.

These tests just lock in the public surface introduced by Phase 0. They
deliberately stay shallow: full lane-resolver + capability-detection
coverage lands in Phase 4.
"""
from __future__ import annotations

import pytest


# ── ExecutionLane enum ──

def test_execution_lane_has_six_canonical_values():
    from app.engine.runtime import ExecutionLane

    expected = {
        "cloud_native_sdk",
        "openai_compatible_http",
        "local_worker",
        "tool_orchestrated",
        "embedding",
        "vision_extraction",
    }
    assert {lane.value for lane in ExecutionLane} == expected


def test_execution_lane_is_string_enum():
    from app.engine.runtime import ExecutionLane

    assert ExecutionLane.OPENAI_COMPATIBLE_HTTP == "openai_compatible_http"
    assert isinstance(ExecutionLane.CLOUD_NATIVE_SDK.value, str)


# ── RuntimeModelSpec dataclass ──

def test_runtime_model_spec_has_sensible_defaults():
    from app.engine.runtime import RuntimeModelSpec

    spec = RuntimeModelSpec(provider="google", model="gemini-3.1-flash-lite-preview")
    assert spec.provider == "google"
    assert spec.tier == "moderate"
    assert spec.supports_streaming is True
    assert spec.supports_tools is True
    assert spec.supports_vision is False
    assert spec.supports_reasoning is False


def test_runtime_model_spec_is_frozen():
    from app.engine.runtime import RuntimeModelSpec
    from dataclasses import FrozenInstanceError

    spec = RuntimeModelSpec(provider="openai", model="gpt-4o-mini")
    with pytest.raises(FrozenInstanceError):
        spec.provider = "anthropic"  # type: ignore[misc]


def test_runtime_model_spec_uses_slots():
    """Slots prevent typo-driven attribute leaks at runtime."""
    from app.engine.runtime import RuntimeModelSpec

    spec = RuntimeModelSpec(provider="ollama", model="qwen3:8b")
    with pytest.raises((AttributeError, TypeError)):
        spec.provicer = "typo"  # type: ignore[attr-defined]


# ── Feature flag ──

def test_enable_native_runtime_flag_defaults_off():
    from app.core.config import settings

    assert settings.enable_native_runtime is False, (
        "Phase 0 ships scaffold only; flag must remain off until Phase 4+."
    )


def test_supervisor_route_timeout_setting_default():
    from app.core.config import settings

    assert settings.supervisor_route_sync_timeout_seconds == 10.0
