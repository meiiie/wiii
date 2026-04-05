"""Comprehensive Gemini API key validation and load probe for Wiii.

This script is intentionally more complete than a one-shot smoke test:

- model discovery (`models.list`, `models.get`)
- token counting
- Vietnamese text generation
- streaming generation
- structured JSON generation
- native thinking config matrix
- embeddings (document/query)
- lightweight multimodal prompt
- concurrent burst probe

The output is written as both Markdown and JSON so the team can compare runs
across keys, models, and quota tiers without manually digging through logs.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv
from PIL import Image, ImageDraw
from google import genai
from google.genai import types

SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[0]
REPORTS_ROOT = REPO_ROOT / ".Codex" / "reports"

if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

load_dotenv(SERVICE_ROOT / ".env")
load_dotenv(SERVICE_ROOT / ".env.local")

from app.core.config import settings
from app.engine.model_catalog import DEFAULT_EMBEDDING_MODEL


DEFAULT_PROMPT = "Hãy chào ngắn gọn bằng tiếng Việt và xác nhận bạn đang hoạt động bình thường."
DEFAULT_STRUCTURED_PROMPT = (
    "Tóm tắt tình trạng thị trường dầu trong 2 câu tiếng Việt. "
    "Sau đó trả về đúng JSON theo schema."
)
DEFAULT_STREAM_PROMPT = (
    "Viết một đoạn ngắn 4 câu tiếng Việt giải thích vì sao kiểm thử API key cần cả smoke và load test."
)
DEFAULT_MULTIMODAL_PROMPT = (
    "Bạn nhìn thấy màu gì là chủ đạo và có ký tự nào trong ảnh? "
    "Trả lời 1 câu tiếng Việt."
)
DEFAULT_COUNT_TOKENS_PROMPT = (
    "Wiii đang kiểm thử Gemini API key để đảm bảo đường text, stream, JSON, embeddings và quota đều hoạt động ổn định."
)


@dataclass
class TestCaseResult:
    name: str
    ok: bool
    elapsed_ms: float
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class SuiteSummary:
    mode: str
    started_at: str
    finished_at: str
    google_model: str
    embedding_model: str
    api_key_masked: str
    success_count: int
    failure_count: int
    total_elapsed_ms: float
    results: list[TestCaseResult]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("smoke", "full", "stress"),
        default="full",
        help="Preset test bundle. smoke=minimal, full=balanced, stress=heavier burst probe.",
    )
    parser.add_argument("--api-key", default=os.getenv("GOOGLE_API_KEY") or settings.google_api_key)
    parser.add_argument("--model", default=settings.google_model)
    parser.add_argument(
        "--probe-models",
        default="",
        help="Comma-separated extra text models to probe with a lightweight generation test.",
    )
    parser.add_argument(
        "--mixed-text-models",
        default="",
        help="Comma-separated text models for simultaneous mixed workload probing.",
    )
    parser.add_argument(
        "--mixed-thinking-levels",
        default="medium,high",
        help="Comma-separated thinking levels for mixed workload text calls.",
    )
    parser.add_argument(
        "--mixed-rounds",
        type=int,
        default=6,
        help="How many task rounds to enqueue for the mixed workload probe.",
    )
    parser.add_argument(
        "--mixed-concurrency",
        type=int,
        default=6,
        help="Concurrency for the mixed workload probe.",
    )
    parser.add_argument("--embedding-model", default=settings.embedding_model or DEFAULT_EMBEDDING_MODEL)
    parser.add_argument(
        "--thinking-levels",
        default="minimal,medium,high",
        help="Comma-separated native Gemini thinking levels to probe.",
    )
    parser.add_argument(
        "--burst-requests",
        type=int,
        default=None,
        help="Override number of burst requests. Defaults by mode.",
    )
    parser.add_argument(
        "--burst-concurrency",
        type=int,
        default=None,
        help="Override concurrent workers for the burst probe. Defaults by mode.",
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=None,
        help="Markdown report path. Defaults to .Codex/reports with a timestamped filename.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="JSON report path. Defaults next to the markdown report.",
    )
    parser.add_argument("--skip-multimodal", action="store_true")
    parser.add_argument("--skip-embeddings", action="store_true")
    parser.add_argument("--skip-structured", action="store_true")
    parser.add_argument("--skip-stream", action="store_true")
    parser.add_argument("--skip-thinking", action="store_true")
    parser.add_argument("--skip-burst", action="store_true")
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_burst_config(mode: str) -> tuple[int, int]:
    if mode == "smoke":
        return 4, 2
    if mode == "stress":
        return 24, 8
    return 10, 4


def mask_api_key(value: str | None) -> str:
    if not value:
        return "(missing)"
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:6]}...{value[-4:]}"


def compact_text(value: str | None, limit: int = 220) -> str:
    if not value:
        return ""
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def make_client(api_key: str) -> genai.Client:
    return genai.Client(api_key=api_key)


def create_test_image() -> Image.Image:
    image = Image.new("RGB", (240, 120), color=(248, 214, 96))
    draw = ImageDraw.Draw(image)
    draw.rectangle((12, 12, 228, 108), outline=(225, 120, 50), width=4)
    draw.text((26, 42), "WIII", fill=(80, 40, 20))
    return image


def build_json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "risk_level": {"type": "string", "enum": ["low", "medium", "high"]},
            "confidence": {"type": "number"},
        },
        "required": ["summary", "risk_level", "confidence"],
    }


def thinking_level_from_name(name: str) -> types.ThinkingLevel:
    normalized = name.strip().upper()
    return types.ThinkingLevel[normalized]


def run_case(name: str, fn: Callable[[], dict[str, Any]]) -> TestCaseResult:
    started = time.perf_counter()
    try:
        details = fn()
        elapsed_ms = (time.perf_counter() - started) * 1000
        return TestCaseResult(name=name, ok=True, elapsed_ms=elapsed_ms, details=details)
    except Exception as exc:  # noqa: BLE001 - audit script needs broad capture
        elapsed_ms = (time.perf_counter() - started) * 1000
        return TestCaseResult(
            name=name,
            ok=False,
            elapsed_ms=elapsed_ms,
            error=f"{exc.__class__.__name__}: {exc}",
            details={"traceback": traceback.format_exc(limit=6)},
        )


def test_model_discovery(client: genai.Client, model: str) -> list[TestCaseResult]:
    def _list_models() -> dict[str, Any]:
        pager = client.models.list(config=types.ListModelsConfig(page_size=20))
        models = list(pager)
        names = [item.name for item in models[:20]]
        matched = [name for name in names if model.replace("models/", "") in name]
        return {
            "listed_count": len(models),
            "first_models": names[:10],
            "target_model_seen_in_first_page": bool(matched),
        }

    def _get_model() -> dict[str, Any]:
        target = model if model.startswith("models/") else f"models/{model}"
        info = client.models.get(model=target)
        return {
            "name": getattr(info, "name", target),
            "display_name": getattr(info, "display_name", None),
            "description": compact_text(getattr(info, "description", None), 180),
            "input_token_limit": getattr(info, "input_token_limit", None),
            "output_token_limit": getattr(info, "output_token_limit", None),
        }

    return [
        run_case("models.list", _list_models),
        run_case("models.get", _get_model),
    ]


def test_count_tokens(client: genai.Client, model: str) -> TestCaseResult:
    def _call() -> dict[str, Any]:
        response = client.models.count_tokens(model=model, contents=DEFAULT_COUNT_TOKENS_PROMPT)
        return {
            "total_tokens": getattr(response, "total_tokens", None),
        }

    return run_case("count_tokens", _call)


def test_generate_text(client: genai.Client, model: str) -> TestCaseResult:
    def _call() -> dict[str, Any]:
        response = client.models.generate_content(
            model=model,
            contents=DEFAULT_PROMPT,
            config=types.GenerateContentConfig(temperature=0.2),
        )
        text = getattr(response, "text", None)
        return {
            "response_preview": compact_text(text, 260),
            "response_length": len(text or ""),
            "usage_metadata": compact_text(getattr(response, "usage_metadata", None), 180),
        }

    return run_case(f"generate_text_vi:{model}", _call)


def test_streaming(client: genai.Client, model: str) -> TestCaseResult:
    def _call() -> dict[str, Any]:
        chunks: list[str] = []
        chunk_count = 0
        for chunk in client.models.generate_content_stream(
            model=model,
            contents=DEFAULT_STREAM_PROMPT,
            config=types.GenerateContentConfig(temperature=0.3),
        ):
            text = getattr(chunk, "text", None)
            if text:
                chunks.append(text)
                chunk_count += 1
        combined = "".join(chunks)
        return {
            "chunk_count": chunk_count,
            "response_preview": compact_text(combined, 260),
            "response_length": len(combined),
        }

    return run_case("generate_stream", _call)


def test_structured_json(client: genai.Client, model: str) -> TestCaseResult:
    schema = build_json_schema()

    def _call() -> dict[str, Any]:
        response = client.models.generate_content(
            model=model,
            contents=DEFAULT_STRUCTURED_PROMPT,
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        raw = getattr(response, "text", None) or ""
        parsed = json.loads(raw)
        return {
            "raw_preview": compact_text(raw, 220),
            "parsed": parsed,
        }

    return run_case("structured_json", _call)


def test_thinking_matrix(client: genai.Client, model: str, level_names: list[str]) -> list[TestCaseResult]:
    cases: list[TestCaseResult] = []
    cases.append(
        run_case(
            "thinking_budget_probe",
            lambda: {
                "response_preview": compact_text(
                    getattr(
                        client.models.generate_content(
                            model=model,
                            contents="Viết 2 câu tiếng Việt về lợi ích của deliberate reasoning.",
                            config=types.GenerateContentConfig(
                                temperature=0.2,
                                thinking_config=types.ThinkingConfig(
                                    thinking_budget=256,
                                    include_thoughts=True,
                                ),
                            ),
                        ),
                        "text",
                        None,
                    ),
                    220,
                ),
            },
        )
    )
    for level_name in level_names:
        level = thinking_level_from_name(level_name)

        def _call(level_name: str = level_name, level: types.ThinkingLevel = level) -> dict[str, Any]:
            response = client.models.generate_content(
                model=model,
                contents="Hãy giải thích trong 2 câu vì sao một hệ thống AI cần phân biệt giữa thinking và debug trace.",
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    thinking_config=types.ThinkingConfig(
                        thinking_level=level,
                        include_thoughts=True,
                    ),
                ),
            )
            text = getattr(response, "text", None) or ""
            candidates = getattr(response, "candidates", None) or []
            return {
                "level": level_name,
                "response_preview": compact_text(text, 220),
                "candidate_count": len(candidates),
            }

        cases.append(run_case(f"thinking_level:{level_name}", _call))
    return cases


def test_embeddings(client: genai.Client, embedding_model: str) -> TestCaseResult:
    def _call() -> dict[str, Any]:
        response = client.models.embed_content(
            model=embedding_model,
            contents=[
                "Wiii dùng embedding để lưu ký ức và truy hồi theo ngữ cảnh.",
                "Người dùng hỏi bằng tiếng Việt về trạng thái cảm xúc.",
            ],
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=settings.embedding_dimensions,
            ),
        )
        vectors = response.embeddings
        dims = [len(item.values) for item in vectors]
        return {
            "embedding_count": len(vectors),
            "dimensions": dims,
        }

    return run_case("embeddings_document_batch", _call)


def test_multimodal(client: genai.Client, model: str) -> TestCaseResult:
    image = create_test_image()

    def _call() -> dict[str, Any]:
        response = client.models.generate_content(
            model=model,
            contents=[image, DEFAULT_MULTIMODAL_PROMPT],
            config=types.GenerateContentConfig(temperature=0.1),
        )
        text = getattr(response, "text", None) or ""
        return {
            "response_preview": compact_text(text, 220),
            "response_length": len(text),
        }

    return run_case("multimodal_image_understanding", _call)


async def run_burst_probe(
    client: genai.Client,
    model: str,
    *,
    requests_count: int,
    concurrency: int,
) -> TestCaseResult:
    async def _one_call(index: int) -> dict[str, Any]:
        prompt = f"Trả lời đúng 1 câu tiếng Việt. Đây là burst probe số {index} để kiểm tra quota và độ ổn định."
        started = time.perf_counter()

        def _sync_call() -> Any:
            return client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.1),
            )

        response = await asyncio.to_thread(_sync_call)
        elapsed_ms = (time.perf_counter() - started) * 1000
        return {
            "ok": True,
            "elapsed_ms": elapsed_ms,
            "preview": compact_text(getattr(response, "text", None), 120),
        }

    started = time.perf_counter()
    semaphore = asyncio.Semaphore(concurrency)
    results: list[dict[str, Any]] = []

    async def _worker(index: int) -> None:
        async with semaphore:
            try:
                result = await _one_call(index)
            except Exception as exc:  # noqa: BLE001
                result = {
                    "ok": False,
                    "error": f"{exc.__class__.__name__}: {exc}",
                }
            results.append(result)

    await asyncio.gather(*[_worker(i + 1) for i in range(requests_count)])
    elapsed_ms = (time.perf_counter() - started) * 1000
    successes = [item for item in results if item.get("ok")]
    failures = [item for item in results if not item.get("ok")]
    latencies = [item["elapsed_ms"] for item in successes if "elapsed_ms" in item]
    details = {
        "requests": requests_count,
        "concurrency": concurrency,
        "successes": len(successes),
        "failures": len(failures),
        "sample_failure": failures[0] if failures else None,
        "mean_latency_ms": round(statistics.mean(latencies), 2) if latencies else None,
        "p95_latency_ms": round(statistics.quantiles(latencies, n=20)[18], 2) if len(latencies) >= 2 else None,
    }
    return TestCaseResult(
        name="burst_probe",
        ok=len(failures) == 0,
        elapsed_ms=elapsed_ms,
        details=details,
        error=failures[0]["error"] if failures else None,
    )


async def run_mixed_workload_probe(
    client: genai.Client,
    *,
    text_models: list[str],
    embedding_model: str,
    thinking_levels: list[str],
    rounds: int,
    concurrency: int,
) -> TestCaseResult:
    jobs: list[tuple[str, str, str]] = []
    for round_index in range(rounds):
        for model in text_models:
            for level in thinking_levels:
                jobs.append(("text", model, level))
        jobs.append(("embedding", embedding_model, ""))

    semaphore = asyncio.Semaphore(concurrency)
    results: list[dict[str, Any]] = []
    started = time.perf_counter()

    async def _run_text(model: str, level_name: str) -> dict[str, Any]:
        level = thinking_level_from_name(level_name)
        prompt = (
            "Giải thích trong 2 câu tiếng Việt vì sao một hệ thống AI cần "
            "tách thinking khỏi debug trace."
        )
        op_started = time.perf_counter()

        def _sync_call() -> Any:
            return client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    thinking_config=types.ThinkingConfig(
                        thinking_level=level,
                        include_thoughts=True,
                    ),
                ),
            )

        response = await asyncio.to_thread(_sync_call)
        return {
            "kind": "text",
            "model": model,
            "thinking_level": level_name,
            "elapsed_ms": (time.perf_counter() - op_started) * 1000,
            "preview": compact_text(getattr(response, "text", None), 140),
        }

    async def _run_embedding(model: str) -> dict[str, Any]:
        op_started = time.perf_counter()

        def _sync_call() -> Any:
            return client.models.embed_content(
                model=model,
                contents=[
                    "Wiii ghi nhớ những gì người dùng đã trải qua.",
                    "Gemini embeddings hỗ trợ truy hồi theo ngữ cảnh.",
                ],
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT",
                    output_dimensionality=settings.embedding_dimensions,
                ),
            )

        response = await asyncio.to_thread(_sync_call)
        dims = [len(item.values) for item in response.embeddings]
        return {
            "kind": "embedding",
            "model": model,
            "elapsed_ms": (time.perf_counter() - op_started) * 1000,
            "dimensions": dims,
        }

    async def _worker(kind: str, model: str, level_name: str) -> None:
        async with semaphore:
            try:
                if kind == "text":
                    result = await _run_text(model, level_name)
                else:
                    result = await _run_embedding(model)
                result["ok"] = True
            except Exception as exc:  # noqa: BLE001
                result = {
                    "ok": False,
                    "kind": kind,
                    "model": model,
                    "thinking_level": level_name or None,
                    "error": f"{exc.__class__.__name__}: {exc}",
                }
            results.append(result)

    await asyncio.gather(*[_worker(kind, model, level) for kind, model, level in jobs])
    elapsed_ms = (time.perf_counter() - started) * 1000

    successes = [item for item in results if item.get("ok")]
    failures = [item for item in results if not item.get("ok")]
    rate_limit_failures = [
        item for item in failures
        if "429" in str(item.get("error", "")) or "RESOURCE_EXHAUSTED" in str(item.get("error", ""))
    ]
    per_lane: dict[str, Any] = {}
    for lane_key, lane_items in {
        "text": [item for item in successes if item.get("kind") == "text"],
        "embedding": [item for item in successes if item.get("kind") == "embedding"],
    }.items():
        latencies = [item["elapsed_ms"] for item in lane_items if "elapsed_ms" in item]
        per_lane[lane_key] = {
            "count": len(lane_items),
            "mean_latency_ms": round(statistics.mean(latencies), 2) if latencies else None,
            "p95_latency_ms": round(statistics.quantiles(latencies, n=20)[18], 2) if len(latencies) >= 2 else None,
        }

    per_model: dict[str, Any] = {}
    for model in text_models + [embedding_model]:
        model_items = [item for item in successes if item.get("model") == model]
        latencies = [item["elapsed_ms"] for item in model_items if "elapsed_ms" in item]
        per_model[model] = {
            "successes": len(model_items),
            "failures": len([item for item in failures if item.get("model") == model]),
            "mean_latency_ms": round(statistics.mean(latencies), 2) if latencies else None,
            "p95_latency_ms": round(statistics.quantiles(latencies, n=20)[18], 2) if len(latencies) >= 2 else None,
        }

    details = {
        "rounds": rounds,
        "concurrency": concurrency,
        "text_models": text_models,
        "embedding_model": embedding_model,
        "thinking_levels": thinking_levels,
        "total_jobs": len(jobs),
        "successes": len(successes),
        "failures": len(failures),
        "rate_limit_failures": len(rate_limit_failures),
        "sample_failure": failures[0] if failures else None,
        "per_lane": per_lane,
        "per_model": per_model,
    }

    return TestCaseResult(
        name="mixed_text_embedding_rate_limit_probe",
        ok=len(failures) == 0,
        elapsed_ms=elapsed_ms,
        details=details,
        error=failures[0]["error"] if failures else None,
    )


def ensure_report_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    REPORTS_ROOT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    md_path = args.output_md or (REPORTS_ROOT / f"GEMINI-API-KEY-TEST-{stamp}.md")
    json_path = args.output_json or md_path.with_suffix(".json")
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    return md_path, json_path


def write_markdown_report(path: Path, summary: SuiteSummary) -> None:
    lines: list[str] = []
    lines.append("# Gemini API Key Test Report")
    lines.append("")
    lines.append(f"> Date: {summary.finished_at}")
    lines.append(f"> Mode: {summary.mode}")
    lines.append(f"> Model: `{summary.google_model}`")
    lines.append(f"> Embedding Model: `{summary.embedding_model}`")
    lines.append(f"> API Key: `{summary.api_key_masked}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Successes: `{summary.success_count}`")
    lines.append(f"- Failures: `{summary.failure_count}`")
    lines.append(f"- Total elapsed: `{summary.total_elapsed_ms:.2f} ms`")
    lines.append("")
    lines.append("## Results")
    lines.append("")
    for result in summary.results:
        status = "PASS" if result.ok else "FAIL"
        lines.append(f"### {status} — {result.name}")
        lines.append("")
        lines.append(f"- Elapsed: `{result.elapsed_ms:.2f} ms`")
        if result.error:
            lines.append(f"- Error: `{result.error}`")
        if result.details:
            lines.append("- Details:")
            lines.append("```json")
            lines.append(json.dumps(result.details, ensure_ascii=False, indent=2))
            lines.append("```")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def run_suite(args: argparse.Namespace) -> SuiteSummary:
    if not args.api_key:
        raise SystemExit("GOOGLE_API_KEY is missing. Pass --api-key or set it in .env.")

    md_path, json_path = ensure_report_paths(args)
    client = make_client(args.api_key)
    started_at = utc_now()
    started = time.perf_counter()
    level_names = [item.strip() for item in args.thinking_levels.split(",") if item.strip()]
    burst_requests, burst_concurrency = default_burst_config(args.mode)
    burst_requests = args.burst_requests or burst_requests
    burst_concurrency = args.burst_concurrency or burst_concurrency
    probe_models = [item.strip() for item in args.probe_models.split(",") if item.strip()]
    mixed_text_models = [item.strip() for item in args.mixed_text_models.split(",") if item.strip()]
    mixed_thinking_levels = [item.strip() for item in args.mixed_thinking_levels.split(",") if item.strip()]
    all_text_models: list[str] = []
    for item in [args.model, *probe_models]:
        if item not in all_text_models:
            all_text_models.append(item)

    results: list[TestCaseResult] = []
    results.extend(test_model_discovery(client, args.model))
    results.append(test_count_tokens(client, args.model))
    for text_model in all_text_models:
        results.append(test_generate_text(client, text_model))

    if not args.skip_stream:
        results.append(test_streaming(client, args.model))
    if not args.skip_structured:
        results.append(test_structured_json(client, args.model))
    if not args.skip_thinking:
        results.extend(test_thinking_matrix(client, args.model, level_names))
    if not args.skip_embeddings:
        results.append(test_embeddings(client, args.embedding_model))
    if not args.skip_multimodal:
        results.append(test_multimodal(client, args.model))
    if not args.skip_burst:
        results.append(
            asyncio.run(
                run_burst_probe(
                    client,
                    args.model,
                    requests_count=burst_requests,
                    concurrency=burst_concurrency,
                )
            )
        )
    if mixed_text_models:
        results.append(
            asyncio.run(
                run_mixed_workload_probe(
                    client,
                    text_models=mixed_text_models,
                    embedding_model=args.embedding_model,
                    thinking_levels=mixed_thinking_levels,
                    rounds=args.mixed_rounds,
                    concurrency=args.mixed_concurrency,
                )
            )
        )

    total_elapsed_ms = (time.perf_counter() - started) * 1000
    success_count = sum(1 for item in results if item.ok)
    failure_count = len(results) - success_count
    summary = SuiteSummary(
        mode=args.mode,
        started_at=started_at,
        finished_at=utc_now(),
        google_model=args.model,
        embedding_model=args.embedding_model,
        api_key_masked=mask_api_key(args.api_key),
        success_count=success_count,
        failure_count=failure_count,
        total_elapsed_ms=total_elapsed_ms,
        results=results,
    )

    json_path.write_text(
        json.dumps(
            {
                **asdict(summary),
                "results": [asdict(item) for item in summary.results],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    write_markdown_report(md_path, summary)

    print(f"[gemini-test] Markdown report: {md_path}")
    print(f"[gemini-test] JSON report: {json_path}")
    print(
        f"[gemini-test] Summary: successes={success_count}, failures={failure_count}, "
        f"elapsed={total_elapsed_ms:.2f}ms",
    )
    return summary


def main() -> int:
    args = parse_args()
    summary = run_suite(args)
    return 0 if summary.failure_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
