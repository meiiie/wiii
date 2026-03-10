#!/usr/bin/env python3
"""Benchmark local Ollama models against Wiii-style prompts.

Measures wall-clock latency plus Ollama's token accounting fields for a small
set of interactive and reasoning tasks. This is meant for machine-local model
selection, not for synthetic leaderboard benchmarking.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx


DEFAULT_BASE_URL = "http://localhost:11434"

DEFAULT_CASES = [
    {
        "id": "vn_chat_fast",
        "think": False,
        "max_tokens": 160,
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are Wiii. Reply in concise Vietnamese for a student chat UI."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Giai thich ngan gon su khac nhau giua SOLAS va MARPOL, "
                    "toi da dang hoc co ban."
                ),
            },
        ],
    },
    {
        "id": "maritime_reasoning",
        "think": True,
        "max_tokens": 256,
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a maritime tutor. Reply in Vietnamese with clear reasoning "
                    "and practical examples."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Tau A dang cat ngang tu ben phai, tau B la tau may dang giu "
                    "huong. Theo COLREGs, tau nao phai nhuong duong va vi sao?"
                ),
            },
        ],
    },
    {
        "id": "json_extract_fast",
        "think": False,
        "max_tokens": 120,
        "temperature": 0.1,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Return only compact JSON with keys topic, urgency, action_items."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Thong bao: Kiem tra ao phao vao 07:30 sang mai, tap trung tai "
                    "boong chinh, mang theo so tay va the sinh vien."
                ),
            },
        ],
    },
]


@dataclass
class RunMetrics:
    model: str
    case_id: str
    think_requested: bool
    first_token_ms: float | None
    wall_ms: float
    total_ms: float | None
    load_ms: float | None
    prompt_eval_ms: float | None
    eval_ms: float | None
    prompt_eval_count: int | None
    eval_count: int | None
    tokens_per_sec: float | None
    output_chars: int
    done_reason: str | None
    error: str | None = None


def _ns_to_ms(value: Any) -> float | None:
    if value in (None, 0):
        return None
    return round(float(value) / 1_000_000, 2)


def _tokens_per_sec(eval_count: Any, eval_duration: Any) -> float | None:
    if not eval_count or not eval_duration:
        return None
    seconds = float(eval_duration) / 1_000_000_000
    if seconds <= 0:
        return None
    return round(float(eval_count) / seconds, 2)


def fetch_installed_models(base_url: str, timeout: float) -> list[str]:
    with httpx.Client(timeout=timeout) as client:
        response = client.get(f"{base_url.rstrip('/')}/api/tags")
        response.raise_for_status()
        payload = response.json()
    return [item.get("name", "") for item in payload.get("models", []) if item.get("name")]


def run_case(
    *,
    base_url: str,
    model: str,
    case: dict[str, Any],
    timeout: float,
    keep_alive: str | None,
) -> RunMetrics:
    payload = {
        "model": model,
        "messages": case["messages"],
        "stream": True,
        "think": case["think"],
        "options": {
            "temperature": case["temperature"],
            "num_predict": case["max_tokens"],
        },
    }
    if keep_alive:
        payload["keep_alive"] = keep_alive

    started = time.perf_counter()
    first_token_ms: float | None = None
    try:
        with httpx.Client(timeout=timeout) as client:
            with client.stream(
                "POST",
                f"{base_url.rstrip('/')}/api/chat",
                json=payload,
            ) as response:
                response.raise_for_status()
                data: dict[str, Any] | None = None
                output_parts: list[str] = []
                for raw_line in response.iter_lines():
                    if not raw_line:
                        continue
                    chunk = json.loads(raw_line)
                    message = chunk.get("message", {}) or {}
                    content = message.get("content", "") or ""
                    if content and first_token_ms is None:
                        first_token_ms = round(
                            (time.perf_counter() - started) * 1000,
                            2,
                        )
                    if content:
                        output_parts.append(content)
                    if chunk.get("done"):
                        data = chunk
                        break

                if data is None:
                    raise RuntimeError("Ollama stream ended without final done chunk")
                data = dict(data)
                data["_combined_output"] = "".join(output_parts)
    except Exception as exc:
        wall_ms = round((time.perf_counter() - started) * 1000, 2)
        return RunMetrics(
            model=model,
            case_id=case["id"],
            think_requested=bool(case["think"]),
            first_token_ms=first_token_ms,
            wall_ms=wall_ms,
            total_ms=None,
            load_ms=None,
            prompt_eval_ms=None,
            eval_ms=None,
            prompt_eval_count=None,
            eval_count=None,
            tokens_per_sec=None,
            output_chars=0,
            done_reason=None,
            error=str(exc),
        )

    wall_ms = round((time.perf_counter() - started) * 1000, 2)
    content = data.get("_combined_output", "") or ""

    return RunMetrics(
        model=model,
        case_id=case["id"],
        think_requested=bool(case["think"]),
        first_token_ms=first_token_ms,
        wall_ms=wall_ms,
        total_ms=_ns_to_ms(data.get("total_duration")),
        load_ms=_ns_to_ms(data.get("load_duration")),
        prompt_eval_ms=_ns_to_ms(data.get("prompt_eval_duration")),
        eval_ms=_ns_to_ms(data.get("eval_duration")),
        prompt_eval_count=data.get("prompt_eval_count"),
        eval_count=data.get("eval_count"),
        tokens_per_sec=_tokens_per_sec(data.get("eval_count"), data.get("eval_duration")),
        output_chars=len(content),
        done_reason=data.get("done_reason"),
    )


def summarize_runs(runs: list[RunMetrics]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[RunMetrics]] = {}
    for run in runs:
        grouped.setdefault((run.model, run.case_id), []).append(run)

    summary: list[dict[str, Any]] = []
    for (model, case_id), items in grouped.items():
        successful = [item for item in items if item.error is None]
        if not successful:
            summary.append(
                {
                    "model": model,
                    "case_id": case_id,
                    "runs": len(items),
                    "ok_runs": 0,
                    "avg_first_token_ms": None,
                    "avg_wall_ms": None,
                    "avg_tokens_per_sec": None,
                    "errors": [item.error for item in items],
                }
            )
            continue

        summary.append(
            {
                "model": model,
                "case_id": case_id,
                "runs": len(items),
                "ok_runs": len(successful),
                "avg_first_token_ms": round(
                    statistics.mean(
                        item.first_token_ms
                        for item in successful
                        if item.first_token_ms is not None
                    ),
                    2,
                )
                if any(item.first_token_ms is not None for item in successful)
                else None,
                "avg_wall_ms": round(
                    statistics.mean(item.wall_ms for item in successful), 2
                ),
                "avg_total_ms": round(
                    statistics.mean(
                        item.total_ms for item in successful if item.total_ms is not None
                    ),
                    2,
                )
                if any(item.total_ms is not None for item in successful)
                else None,
                "avg_tokens_per_sec": round(
                    statistics.mean(
                        item.tokens_per_sec
                        for item in successful
                        if item.tokens_per_sec is not None
                    ),
                    2,
                )
                if any(item.tokens_per_sec is not None for item in successful)
                else None,
                "think_requested": successful[0].think_requested,
            }
        )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark Ollama models with Wiii-style prompts."
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Ollama base URL (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--model",
        action="append",
        required=True,
        help="Model tag to benchmark. Repeat for multiple models.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=2,
        help="Number of runs per model/case (default: 2).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=180.0,
        help="Per-request timeout in seconds (default: 180).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional path to write full JSON results.",
    )
    parser.add_argument(
        "--keep-alive",
        default=None,
        help="Optional Ollama keep_alive value to send with each request (e.g. 30m, 0, -1).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    installed_models = fetch_installed_models(args.base_url, args.timeout)
    print("Installed models:")
    for item in installed_models:
        print(f"  - {item}")
    if not installed_models:
        print("  (none)")

    runs: list[RunMetrics] = []
    requested_models = args.model

    for model in requested_models:
        if model not in installed_models:
            print(f"[skip] {model}: not installed in local Ollama")
            continue

        for case in DEFAULT_CASES:
            for index in range(1, args.runs + 1):
                print(
                    f"[run] model={model} case={case['id']} "
                    f"run={index}/{args.runs} think={case['think']}"
                )
                metrics = run_case(
                    base_url=args.base_url,
                    model=model,
                    case=case,
                    timeout=args.timeout,
                    keep_alive=args.keep_alive,
                )
                runs.append(metrics)
                if metrics.error:
                    print(f"  -> error: {metrics.error}")
                else:
                    print(
                        "  -> first_token_ms={first} wall_ms={wall:.2f} total_ms={total} tok/s={tps}".format(
                            first=metrics.first_token_ms,
                            wall=metrics.wall_ms,
                            total=metrics.total_ms,
                            tps=metrics.tokens_per_sec,
                        )
                    )

    summary = summarize_runs(runs)
    print("\nSummary:")
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if args.out is not None:
        payload = {
            "base_url": args.base_url,
            "requested_models": requested_models,
            "installed_models": installed_models,
            "keep_alive": args.keep_alive,
            "cases": DEFAULT_CASES,
            "runs": [asdict(item) for item in runs],
            "summary": summary,
        }
        args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nWrote JSON report to {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
