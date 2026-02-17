"""
Tests for Sprint 49: Observability module coverage.

Tests OpenTelemetry setup including:
- init_telemetry (disabled, no packages, success, general error)
- get_tracer (with initialized tracer, without OTel, with OTel fallback)
- _NoOpSpan (context manager, set_attribute, set_status, record_exception)
- _NoOpTracer (start_as_current_span, start_span)
"""

import pytest
from unittest.mock import MagicMock, patch
import sys


# ============================================================================
# _NoOpSpan
# ============================================================================


class TestNoOpSpan:
    """Test no-op span."""

    def test_context_manager(self):
        from app.core.observability import _NoOpSpan
        span = _NoOpSpan()
        with span as s:
            assert s is span

    def test_set_attribute(self):
        from app.core.observability import _NoOpSpan
        span = _NoOpSpan()
        span.set_attribute("key", "value")  # Should not raise

    def test_set_status(self):
        from app.core.observability import _NoOpSpan
        span = _NoOpSpan()
        span.set_status("OK")  # Should not raise

    def test_record_exception(self):
        from app.core.observability import _NoOpSpan
        span = _NoOpSpan()
        span.record_exception(ValueError("test"))  # Should not raise


# ============================================================================
# _NoOpTracer
# ============================================================================


class TestNoOpTracer:
    """Test no-op tracer."""

    def test_start_as_current_span(self):
        from app.core.observability import _NoOpTracer, _NoOpSpan
        tracer = _NoOpTracer()
        span = tracer.start_as_current_span("test.operation")
        assert isinstance(span, _NoOpSpan)

    def test_start_span(self):
        from app.core.observability import _NoOpTracer, _NoOpSpan
        tracer = _NoOpTracer()
        span = tracer.start_span("test.operation")
        assert isinstance(span, _NoOpSpan)

    def test_context_manager_usage(self):
        from app.core.observability import _NoOpTracer
        tracer = _NoOpTracer()
        with tracer.start_as_current_span("op") as span:
            span.set_attribute("key", "value")
            # Should not raise


# ============================================================================
# init_telemetry
# ============================================================================


class TestInitTelemetry:
    """Test telemetry initialization."""

    def test_disabled(self):
        import app.core.observability as mod
        old_tracer = mod._tracer
        mod._tracer = None

        mod.init_telemetry(enabled=False)
        assert mod._tracer is None

        mod._tracer = old_tracer

    def test_no_otel_packages(self):
        import app.core.observability as mod
        old_tracer = mod._tracer
        mod._tracer = None

        with patch.dict(sys.modules, {"opentelemetry": None}):
            with patch("builtins.__import__", side_effect=ImportError("No OTel")):
                mod.init_telemetry(enabled=True)
        # Should not crash; tracer stays None
        assert mod._tracer is None

        mod._tracer = old_tracer

    def test_success(self):
        import app.core.observability as mod
        old_tracer = mod._tracer
        mod._tracer = None

        mock_trace = MagicMock()
        mock_provider = MagicMock()
        mock_resource = MagicMock()
        mock_tracer = MagicMock()

        mock_trace.get_tracer.return_value = mock_tracer

        mock_otel_trace = MagicMock()
        mock_otel_trace.TracerProvider = MagicMock(return_value=mock_provider)

        mock_otel_resource = MagicMock()
        mock_otel_resource.Resource.create.return_value = mock_resource

        with patch.dict(sys.modules, {
            "opentelemetry": MagicMock(trace=mock_trace),
            "opentelemetry.trace": mock_trace,
            "opentelemetry.sdk.trace": mock_otel_trace,
            "opentelemetry.sdk.resources": mock_otel_resource,
        }):
            mod.init_telemetry(service_name="test-service", enabled=True)

        assert mod._tracer is mock_tracer

        mod._tracer = old_tracer

    def test_general_error(self):
        import app.core.observability as mod
        old_tracer = mod._tracer
        mod._tracer = None

        mock_trace = MagicMock()
        mock_otel_trace = MagicMock()
        mock_otel_trace.TracerProvider.side_effect = RuntimeError("Config error")

        mock_otel_resource = MagicMock()
        mock_otel_resource.Resource.create.return_value = MagicMock()

        with patch.dict(sys.modules, {
            "opentelemetry": MagicMock(trace=mock_trace),
            "opentelemetry.trace": mock_trace,
            "opentelemetry.sdk.trace": mock_otel_trace,
            "opentelemetry.sdk.resources": mock_otel_resource,
        }):
            mod.init_telemetry(enabled=True)

        # Should not crash; tracer stays None
        assert mod._tracer is None

        mod._tracer = old_tracer


# ============================================================================
# get_tracer
# ============================================================================


class TestGetTracer:
    """Test tracer retrieval."""

    def test_returns_initialized_tracer(self):
        import app.core.observability as mod
        old_tracer = mod._tracer
        mock_tracer = MagicMock()
        mod._tracer = mock_tracer

        result = mod.get_tracer("test")
        assert result is mock_tracer

        mod._tracer = old_tracer

    def test_returns_noop_when_no_otel(self):
        import app.core.observability as mod
        from app.core.observability import _NoOpTracer
        old_tracer = mod._tracer
        mod._tracer = None

        with patch.dict(sys.modules, {"opentelemetry": None}):
            with patch("builtins.__import__", side_effect=ImportError("No OTel")):
                result = mod.get_tracer("test")

        assert isinstance(result, _NoOpTracer)

        mod._tracer = old_tracer

    def test_otel_fallback_with_name(self):
        import app.core.observability as mod
        old_tracer = mod._tracer
        mod._tracer = None

        mock_trace = MagicMock()
        mock_fallback_tracer = MagicMock()
        mock_trace.get_tracer.return_value = mock_fallback_tracer

        with patch.dict(sys.modules, {
            "opentelemetry": MagicMock(trace=mock_trace),
            "opentelemetry.trace": mock_trace,
        }):
            result = mod.get_tracer("my_module")

        assert result is mock_fallback_tracer
        mock_trace.get_tracer.assert_called_with("my_module")

        mod._tracer = old_tracer

    def test_otel_fallback_default_name(self):
        import app.core.observability as mod
        old_tracer = mod._tracer
        mod._tracer = None

        mock_trace = MagicMock()
        mock_fallback_tracer = MagicMock()
        mock_trace.get_tracer.return_value = mock_fallback_tracer

        with patch.dict(sys.modules, {
            "opentelemetry": MagicMock(trace=mock_trace),
            "opentelemetry.trace": mock_trace,
        }):
            result = mod.get_tracer()

        mock_trace.get_tracer.assert_called_with("wiii")

        mod._tracer = old_tracer
