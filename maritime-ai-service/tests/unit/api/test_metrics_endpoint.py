"""Phase 16 Prometheus /metrics endpoint — Runtime Migration #207.

Locks the Prometheus text-format contract: hand-rolled exposition is
faithful to the v0.0.4 spec, the route is feature-gated, illegal metric
names are dropped not corrupted, summaries report the quantile lines
+ count + sum.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI

from app.api.metrics_endpoint import (
    _emit_counter,
    _emit_gauge,
    _emit_histogram,
    _format_label_value,
    _format_labels,
    _render_prometheus,
    _to_metric_name,
    router as metrics_router,
)
from app.engine.runtime import runtime_metrics as rm


@pytest.fixture(autouse=True)
def reset_metrics():
    rm._reset_for_tests()
    yield
    rm._reset_for_tests()


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(metrics_router)
    return app


def _enable(monkeypatch):
    from app.core import config as config_module

    monkeypatch.setattr(
        config_module.settings, "enable_prometheus_metrics", True, raising=False
    )


# ── name + label sanitisation ──

def test_dotted_names_become_underscored():
    assert _to_metric_name("runtime.subagent.runs") == "runtime_subagent_runs"


def test_dashed_names_become_underscored():
    assert _to_metric_name("edge.openai-chat.duration_ms") == "edge_openai_chat_duration_ms"


def test_leading_digit_gets_underscore_prefix():
    assert _to_metric_name("123foo") == "_123foo"


def test_label_value_escapes_quotes_and_backslashes():
    assert _format_label_value('a"b\\c') == 'a\\"b\\\\c'


def test_label_value_escapes_newlines():
    assert _format_label_value("first\nsecond") == "first\\nsecond"


def test_format_labels_renders_sorted_pairs():
    out = _format_labels((("status", "success"), ("org", "A")))
    assert out == '{status="success",org="A"}'


def test_format_labels_skips_invalid_label_names():
    out = _format_labels((("good", "1"), ("bad-name", "2")))
    assert "good=" in out
    assert "bad-name" not in out


def test_format_labels_empty_tuple_returns_empty_string():
    assert _format_labels(()) == ""


# ── counter / gauge emission ──

def test_emit_counter_includes_help_and_type():
    lines = list(_emit_counter("foo.count", {(): 5}))
    assert lines[0].startswith("# HELP foo_count")
    assert lines[1] == "# TYPE foo_count counter"
    assert lines[2] == "foo_count 5"


def test_emit_counter_emits_one_line_per_label_bucket():
    lines = list(
        _emit_counter(
            "foo.count",
            {(("status", "ok"),): 3, (("status", "err"),): 1},
        )
    )
    body = [l for l in lines if not l.startswith("#")]
    assert len(body) == 2
    assert any('status="ok"' in l and l.endswith(" 3") for l in body)
    assert any('status="err"' in l and l.endswith(" 1") for l in body)


def test_emit_gauge_uses_gauge_type():
    lines = list(_emit_gauge("temp", {(): 42.5}))
    assert lines[1] == "# TYPE temp gauge"
    assert lines[2] == "temp 42.5"


# ── histogram → summary ──

def test_emit_histogram_emits_quantiles_count_and_sum():
    lines = list(
        _emit_histogram("rag.duration", {(): [10.0, 20.0, 30.0, 40.0, 50.0]})
    )
    text = "\n".join(lines)
    assert "# TYPE rag_duration summary" in text
    assert 'quantile="0.5"' in text
    assert 'quantile="0.95"' in text
    assert 'quantile="0.99"' in text
    assert "rag_duration_count 5" in text
    assert "rag_duration_sum 150.0" in text


def test_emit_histogram_skips_empty_buckets():
    lines = list(_emit_histogram("rag.duration", {(): []}))
    body = [l for l in lines if not l.startswith("#")]
    # No samples → only HELP + TYPE; no series lines.
    assert body == []


def test_emit_histogram_quantile_labels_inherit_existing_labels():
    lines = list(
        _emit_histogram(
            "edge.duration",
            {(("org", "A"),): [100.0, 200.0]},
        )
    )
    quantile_lines = [l for l in lines if "quantile=" in l]
    for ql in quantile_lines:
        assert 'org="A"' in ql


# ── full render ──

def test_render_prometheus_full_snapshot():
    rm.inc_counter("runtime.subagent.runs", labels={"status": "success"})
    rm.set_gauge("runtime.queue.depth", 7.0)
    rm.record_latency_ms("edge.duration", 100.0)
    rm.record_latency_ms("edge.duration", 200.0)
    payload = _render_prometheus(rm.snapshot())
    assert "# TYPE runtime_subagent_runs counter" in payload
    assert "# TYPE runtime_queue_depth gauge" in payload
    assert "# TYPE edge_duration summary" in payload
    assert payload.endswith("\n")


def test_render_handles_empty_snapshot():
    payload = _render_prometheus(rm.snapshot())
    # Even empty, still ends with newline (Prometheus requires it).
    assert payload == "\n"


# ── HTTP route gating ──

@pytest.mark.asyncio
async def test_metrics_404_when_flag_off(app, monkeypatch):
    from app.core import config as config_module

    monkeypatch.setattr(
        config_module.settings, "enable_prometheus_metrics", False, raising=False
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/metrics")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_metrics_returns_prometheus_text_when_enabled(app, monkeypatch):
    _enable(monkeypatch)
    rm.inc_counter("runtime.subagent.runs", labels={"status": "success"}, by=2)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    body = resp.text
    assert "# TYPE runtime_subagent_runs counter" in body
    assert 'runtime_subagent_runs{status="success"} 2' in body


@pytest.mark.asyncio
async def test_metrics_content_type_includes_version(app, monkeypatch):
    _enable(monkeypatch)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/metrics")
    # Prometheus scrapers look for the specific version header.
    assert "version=0.0.4" in resp.headers["content-type"]
