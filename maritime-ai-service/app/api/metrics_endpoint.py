"""Prometheus metrics endpoint — drains the runtime_metrics façade.

Phase 16 of the runtime migration epic (issue #207). The Phase 13
façade collects counters, gauges, and latency histograms in a process-
local sink; this module exposes them at ``GET /metrics`` in the
Prometheus text format (v0.0.4) so a scraper can pull them on a normal
cadence.

Why hand-rolled instead of the prometheus_client library:

- Wiii ships in environments where adding a new dependency triggers
  re-validation. The façade already collects everything we need; the
  only thing missing was a serialization stage.
- The Prometheus text format is a stable spec, ~30 LOC to generate
  faithfully. No need to pull a transitive tree.
- When the team chooses to adopt prometheus_client later, the call
  sites stay identical — only this module changes.

Format reference: https://prometheus.io/docs/instrumenting/exposition_formats/
"""

from __future__ import annotations

import math
import re
import statistics
from typing import Iterable

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from app.engine.runtime.runtime_metrics import snapshot

router = APIRouter(tags=["Metrics"])


_METRIC_NAME_OK = re.compile(r"^[a-zA-Z_:][a-zA-Z0-9_:]*$")
_LABEL_NAME_OK = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _to_metric_name(raw: str) -> str:
    """Convert ``runtime.subagent.runs`` → ``runtime_subagent_runs``.

    Prometheus disallows ``.`` and ``-`` in metric names; the façade uses
    those for readability. Translate dots/dashes to underscores and drop
    anything that does not match the Prometheus character class.
    """
    candidate = raw.replace(".", "_").replace("-", "_")
    cleaned = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in candidate)
    if not cleaned or cleaned[0].isdigit():
        cleaned = "_" + cleaned
    return cleaned


def _format_label_value(value: str) -> str:
    """Escape a label value per Prometheus exposition rules."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _format_labels(label_tuple: tuple) -> str:
    """Render a ``(("k", "v"), ...)`` tuple as ``{k="v",k2="v2"}``."""
    if not label_tuple:
        return ""
    parts: list[str] = []
    for raw_key, raw_value in label_tuple:
        if not _LABEL_NAME_OK.match(str(raw_key)):
            # Skip illegal label names rather than corrupting the line.
            continue
        parts.append(f'{raw_key}="{_format_label_value(str(raw_value))}"')
    if not parts:
        return ""
    return "{" + ",".join(parts) + "}"


def _emit_counter(name: str, buckets: dict[tuple, int]) -> Iterable[str]:
    pname = _to_metric_name(name)
    yield f"# HELP {pname} Wiii runtime counter ({name})."
    yield f"# TYPE {pname} counter"
    for label_tuple, value in buckets.items():
        yield f"{pname}{_format_labels(label_tuple)} {value}"


def _emit_gauge(name: str, buckets: dict[tuple, float]) -> Iterable[str]:
    pname = _to_metric_name(name)
    yield f"# HELP {pname} Wiii runtime gauge ({name})."
    yield f"# TYPE {pname} gauge"
    for label_tuple, value in buckets.items():
        yield f"{pname}{_format_labels(label_tuple)} {value}"


def _emit_histogram(name: str, buckets: dict[tuple, list[float]]) -> Iterable[str]:
    """Emit a synthetic Prometheus summary for a histogram bucket.

    The façade stores raw observations (not pre-bucketed counts) so we
    expose summary-style sample stats: count, sum, p50, p95, p99. A real
    Prometheus histogram with buckets requires deciding the bucket
    boundaries up front; until that decision is made, the summary form
    is the right Prometheus primitive.
    """
    pname = _to_metric_name(name)
    yield f"# HELP {pname} Wiii runtime latency summary ({name})."
    yield f"# TYPE {pname} summary"
    for label_tuple, samples in buckets.items():
        if not samples:
            continue
        labels_str = _format_labels(label_tuple)
        count = len(samples)
        total = math.fsum(samples)
        sorted_samples = sorted(samples)

        def _quantile(q: float) -> float:
            if count == 1:
                return sorted_samples[0]
            idx = int(round(q * (count - 1)))
            return sorted_samples[max(0, min(count - 1, idx))]

        # Per Prometheus summary spec: each quantile is a separate line
        # carrying the same labels plus a {quantile="..."} suffix.
        for q in (0.5, 0.95, 0.99):
            q_label_tuple = label_tuple + (("quantile", str(q)),)
            yield f"{pname}{_format_labels(q_label_tuple)} {_quantile(q)}"
        yield f"{pname}_count{labels_str} {count}"
        yield f"{pname}_sum{labels_str} {total}"


def _render_prometheus(snap: dict) -> str:
    """Materialise the entire snapshot as a single Prometheus payload."""
    lines: list[str] = []
    for name, buckets in sorted(snap.get("counters", {}).items()):
        if not _METRIC_NAME_OK.match(_to_metric_name(name)):
            continue
        lines.extend(_emit_counter(name, buckets))
    for name, buckets in sorted(snap.get("gauges", {}).items()):
        if not _METRIC_NAME_OK.match(_to_metric_name(name)):
            continue
        lines.extend(_emit_gauge(name, buckets))
    for name, buckets in sorted(snap.get("histograms", {}).items()):
        if not _METRIC_NAME_OK.match(_to_metric_name(name)):
            continue
        lines.extend(_emit_histogram(name, buckets))
    # Prometheus requires a trailing newline.
    return "\n".join(lines) + "\n"


@router.get(
    "/metrics",
    response_class=PlainTextResponse,
    tags=["Metrics"],
    summary="Prometheus metrics scrape endpoint",
)
async def get_metrics() -> PlainTextResponse:
    """Expose ``runtime_metrics.snapshot()`` in Prometheus text format.

    Feature-gated by ``settings.enable_prometheus_metrics``. Default off
    so an unconfigured deployment doesn't accidentally publish internal
    metric names. When the gate is on, scrape with::

        curl -s http://wiii-host/metrics
    """
    from app.core.config import settings

    if not getattr(settings, "enable_prometheus_metrics", False):
        raise HTTPException(status_code=404, detail="Not found")

    payload = _render_prometheus(snapshot())
    return PlainTextResponse(
        content=payload,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


__all__ = ["router"]
