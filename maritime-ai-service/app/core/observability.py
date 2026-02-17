"""
Wiii Observability Setup — OpenTelemetry GenAI Tracing

SOTA 2026: Standardized LLM tracing using OpenTelemetry GenAI Semantic Conventions.
Provides spans for LLM calls, retrieval, grading, and agent processing.

Usage:
    from app.core.observability import init_telemetry, get_tracer

    # At app startup:
    init_telemetry()

    # In any module:
    tracer = get_tracer(__name__)
    with tracer.start_as_current_span("rag.retrieve") as span:
        span.set_attribute("gen_ai.system", "gemini")
        ...
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

_tracer = None


def init_telemetry(service_name: str = "wiii", enabled: bool = True) -> None:
    """
    Initialize OpenTelemetry tracing.

    Call once at application startup. Safe to call multiple times (idempotent).
    If OTel packages are not installed, logs a warning and continues.
    """
    global _tracer

    if not enabled:
        logger.info("[OTEL] Telemetry disabled by configuration")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.resources import Resource

        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)

        _tracer = trace.get_tracer(service_name)
        logger.info("[OTEL] Telemetry initialized for service '%s'", service_name)

    except ImportError:
        logger.info("[OTEL] opentelemetry packages not installed, tracing disabled")
    except Exception as e:
        logger.warning("[OTEL] Failed to initialize telemetry: %s", e)


def get_tracer(name: Optional[str] = None):
    """
    Get an OpenTelemetry tracer instance.

    Returns a no-op tracer if OTel is not initialized.
    """
    global _tracer

    if _tracer is not None:
        return _tracer

    try:
        from opentelemetry import trace
        return trace.get_tracer(name or "wiii")
    except ImportError:
        return _NoOpTracer()


class _NoOpSpan:
    """No-op span for when OTel is not available."""

    def set_attribute(self, key, value):
        pass

    def set_status(self, status):
        pass

    def record_exception(self, exception):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class _NoOpTracer:
    """No-op tracer for when OTel is not available."""

    def start_as_current_span(self, name, **kwargs):
        return _NoOpSpan()

    def start_span(self, name, **kwargs):
        return _NoOpSpan()
