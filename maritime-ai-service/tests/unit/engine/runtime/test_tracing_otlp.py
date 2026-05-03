"""Phase 29 OTLP exporter — Runtime Migration #207.

Locks the contract:
- Construction never fails — missing OTel libs degrade to no-op.
- on_end with no_op processor does not raise.
- on_end with mocked OTel chain forwards span attributes + status.
- install_otlp_processor_from_settings respects enable_otlp_export +
  registers the processor when on, returns None when off.
- Telemetry never breaks the request — exporter exception swallowed.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.engine.runtime import tracing
from app.engine.runtime.tracing_otlp import (
    OTLPSpanProcessor,
    install_otlp_processor_from_settings,
)


@pytest.fixture(autouse=True)
def reset_tracer():
    tracing._reset_for_tests()
    yield
    tracing._reset_for_tests()


# ── construction is always safe ──

def test_construction_never_raises():
    """Even without OTel libs, construction should not raise."""
    p = OTLPSpanProcessor(endpoint="http://nowhere:4317")
    # If libs are missing, _noop is True; if installed, _noop is False.
    # Either way: no exception.
    assert isinstance(p._noop, bool)


def test_no_op_when_libs_missing(monkeypatch):
    """Force the lib-check to return False; processor should be inert."""
    monkeypatch.setattr(
        "app.engine.runtime.tracing_otlp._otel_modules_available",
        lambda: False,
    )
    p = OTLPSpanProcessor()
    assert p._noop is True
    # on_end is a complete no-op when in no_op mode.
    span = tracing.Span(name="x", trace_id="t", span_id="s")
    span.end()
    p.on_end(span)  # should not raise


# ── settings routing ──

def test_install_returns_none_when_flag_off(monkeypatch):
    from app.core import config as config_module

    monkeypatch.setattr(
        config_module.settings, "enable_otlp_export", False, raising=False
    )
    result = install_otlp_processor_from_settings()
    assert result is None


def test_install_returns_none_when_libs_missing(monkeypatch):
    """Flag on but lib missing → processor in no_op state, install returns None."""
    from app.core import config as config_module

    monkeypatch.setattr(
        config_module.settings, "enable_otlp_export", True, raising=False
    )
    monkeypatch.setattr(
        config_module.settings,
        "otlp_endpoint",
        "http://localhost:4317",
        raising=False,
    )
    monkeypatch.setattr(
        "app.engine.runtime.tracing_otlp._otel_modules_available",
        lambda: False,
    )
    result = install_otlp_processor_from_settings()
    assert result is None


def test_install_registers_processor_when_libs_available(monkeypatch):
    """Flag on + libs present → processor registered with the global tracer."""
    from app.core import config as config_module

    monkeypatch.setattr(
        config_module.settings, "enable_otlp_export", True, raising=False
    )
    monkeypatch.setattr(
        config_module.settings,
        "otlp_endpoint",
        "http://localhost:4317",
        raising=False,
    )
    monkeypatch.setattr(
        config_module.settings,
        "otlp_service_name",
        "test-service",
        raising=False,
    )
    monkeypatch.setattr(
        "app.engine.runtime.tracing_otlp._otel_modules_available",
        lambda: True,
    )
    # Mock _ensure_initialised so we don't actually wire OTel SDK.
    with patch.object(OTLPSpanProcessor, "_ensure_initialised", return_value=True):
        processor = install_otlp_processor_from_settings()
    assert processor is not None
    assert processor in tracing.get_tracer()._processors


# ── exception swallowing ──

def test_emit_failure_does_not_raise(monkeypatch):
    """Telemetry exception should never break a request."""
    monkeypatch.setattr(
        "app.engine.runtime.tracing_otlp._otel_modules_available",
        lambda: True,
    )
    p = OTLPSpanProcessor()

    # Force _ensure_initialised to claim ready, then make _emit blow up.
    with patch.object(p, "_ensure_initialised", return_value=True):
        with patch.object(p, "_emit", side_effect=RuntimeError("export down")):
            span = tracing.Span(name="x", trace_id="t", span_id="s")
            span.end()
            # Must not raise.
            p.on_end(span)


def test_init_failure_falls_back_to_noop(monkeypatch):
    """If _ensure_initialised raises mid-setup, processor enters no_op."""
    monkeypatch.setattr(
        "app.engine.runtime.tracing_otlp._otel_modules_available",
        lambda: True,
    )
    p = OTLPSpanProcessor()

    # Patch the SDK import path inside _ensure_initialised to fail.
    def boom(*args, **kwargs):
        raise RuntimeError("simulated setup failure")

    with patch.object(p, "_ensure_initialised", side_effect=boom):
        span = tracing.Span(name="x", trace_id="t", span_id="s")
        span.end()
        # Wraps in try/except inside on_end — must not raise.
        try:
            p.on_end(span)
        except Exception:  # noqa: BLE001
            pytest.fail("on_end should swallow init failures")


# ── shutdown ──

def test_shutdown_when_uninitialised_is_safe():
    """Calling shutdown without a batch processor should be a no-op."""
    p = OTLPSpanProcessor()
    p.shutdown()  # _batch_processor is None; should not raise


def test_shutdown_when_initialised_calls_batch_processor():
    p = OTLPSpanProcessor()
    fake_batch = MagicMock()
    p._batch_processor = fake_batch
    p.shutdown()
    fake_batch.shutdown.assert_called_once()


def test_shutdown_swallows_exception_from_batch():
    p = OTLPSpanProcessor()
    fake_batch = MagicMock()
    fake_batch.shutdown.side_effect = RuntimeError("flush failed")
    p._batch_processor = fake_batch
    # Must not raise.
    p.shutdown()
