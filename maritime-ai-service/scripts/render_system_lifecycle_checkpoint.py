#!/usr/bin/env python3
"""
Run the key lifecycle regression suites and render a unified checkpoint report.

This script creates both JSON and Markdown artifacts under `.Codex/reports/`
so operators can quickly see which parts of the system lifecycle are covered
and whether the current checkpoint is green.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


SUMMARY_PATTERNS = {
    "passed": re.compile(r"(?P<count>\d+)\s+passed"),
    "failed": re.compile(r"(?P<count>\d+)\s+failed"),
    "errors": re.compile(r"(?P<count>\d+)\s+errors?"),
    "skipped": re.compile(r"(?P<count>\d+)\s+skipped"),
}


@dataclass(frozen=True)
class SuiteSpec:
    name: str
    category: str
    cwd: Path
    command: list[str]
    covers: list[str]


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _service_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _reports_dir() -> Path:
    return _workspace_root() / ".Codex" / "reports"


def _venv_python() -> str:
    candidate = _service_root() / ".venv" / "Scripts" / "python.exe"
    if candidate.exists():
        return str(candidate)
    return sys.executable


def _npx_command() -> str:
    if os.name == "nt":
        return "npx.cmd"
    return "npx"


def _parse_summary(output: str) -> dict[str, int]:
    summary = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    for key, pattern in SUMMARY_PATTERNS.items():
        match = pattern.search(output)
        if match:
            summary[key] = int(match.group("count"))
    return summary


def _suite_specs() -> list[SuiteSpec]:
    workspace = _workspace_root()
    service = _service_root()
    python_exe = _venv_python()
    desktop = workspace / "wiii-desktop"
    tests = service / "tests" / "unit"

    return [
        SuiteSpec(
            name="chat_lifecycle_core",
            category="backend",
            cwd=workspace,
            command=[
                python_exe,
                "-m",
                "pytest",
                str(tests / "test_chat_lifecycle_e2e_matrix.py"),
                str(tests / "test_chat_failover_e2e_matrix.py"),
                "-q",
                "-p",
                "no:capture",
                "--tb=short",
            ],
            covers=["direct", "memory", "rag", "tutor", "failover", "sync", "stream"],
        ),
        SuiteSpec(
            name="multimodal_lifecycle",
            category="backend",
            cwd=workspace,
            command=[
                python_exe,
                "-m",
                "pytest",
                str(tests / "test_multimodal_lifecycle_e2e_matrix.py"),
                str(tests / "test_sprint179_visual_rag.py"),
                str(tests / "test_sprint186_visual_memory.py"),
                str(tests / "test_vision_runtime.py"),
                str(tests / "test_sprint50_vision_extractor.py"),
                "-q",
                "-p",
                "no:capture",
                "--tb=short",
            ],
            covers=["ocr", "visual_rag", "visual_memory", "vision_runtime"],
        ),
        SuiteSpec(
            name="product_code_lifecycle",
            category="backend",
            cwd=workspace,
            command=[
                python_exe,
                "-m",
                "pytest",
                str(tests / "test_product_code_lifecycle_e2e_matrix.py"),
                str(tests / "test_code_studio_streaming.py"),
                str(tests / "test_product_search_model_passthrough.py"),
                "-q",
                "-p",
                "no:capture",
                "--tb=short",
            ],
            covers=["product_search", "code_studio", "stream_contract"],
        ),
        SuiteSpec(
            name="frontend_socket_runtime",
            category="frontend",
            cwd=desktop,
            command=[
                _npx_command(),
                "vitest",
                "run",
                "src/__tests__/model-store.test.ts",
                "src/__tests__/use-sse-stream-concurrency.test.ts",
                "src/__tests__/admin-runtime-tab.test.tsx",
            ],
            covers=["request_socket", "sse_stream", "runtime_admin_ui"],
        ),
    ]


def _run_suite(spec: SuiteSpec) -> dict[str, Any]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    result = subprocess.run(
        spec.command,
        cwd=str(spec.cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    combined_output = "\n".join(part for part in [result.stdout, result.stderr] if part)
    summary = _parse_summary(combined_output)
    return {
        "name": spec.name,
        "category": spec.category,
        "covers": spec.covers,
        "cwd": str(spec.cwd),
        "command": spec.command,
        "exit_code": result.returncode,
        "status": "pass" if result.returncode == 0 else "fail",
        "summary": summary,
        "output": combined_output.strip(),
    }


def _build_report(results: list[dict[str, Any]]) -> dict[str, Any]:
    totals = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    for result in results:
        for key in totals:
            totals[key] += int((result.get("summary") or {}).get(key) or 0)

    covered_lanes = sorted(
        {
            lane
            for result in results
            if result.get("status") == "pass"
            for lane in (result.get("covers") or [])
        }
    )

    failing_suites = [result["name"] for result in results if result.get("status") != "pass"]
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "overall_status": "pass" if not failing_suites else "fail",
        "suite_count": len(results),
        "failing_suites": failing_suites,
        "totals": totals,
        "covered_lanes": covered_lanes,
        "results": results,
    }


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# System Lifecycle Checkpoint",
        "",
        f"Date: {report['generated_at']}",
        "",
        "## Summary",
        "",
        f"- overall status: `{report['overall_status']}`",
        f"- suites: `{report['suite_count']}`",
        f"- totals: `{report['totals']['passed']} passed`, `{report['totals']['failed']} failed`, `{report['totals']['errors']} errors`, `{report['totals']['skipped']} skipped`",
        "",
        "## Covered Lanes",
        "",
    ]
    for lane in report.get("covered_lanes") or []:
        lines.append(f"- `{lane}`")

    lines.extend(["", "## Suite Results", ""])
    for result in report.get("results") or []:
        summary = result.get("summary") or {}
        lines.extend(
            [
                f"### {result['name']}",
                "",
                f"- category: `{result['category']}`",
                f"- status: `{result['status']}`",
                f"- summary: `{summary.get('passed', 0)} passed`, `{summary.get('failed', 0)} failed`, `{summary.get('errors', 0)} errors`, `{summary.get('skipped', 0)} skipped`",
                f"- covers: {', '.join(f'`{item}`' for item in result.get('covers') or [])}",
                "",
            ]
        )

    if report.get("failing_suites"):
        lines.extend(["## Failing Suites", ""])
        for name in report["failing_suites"]:
            lines.append(f"- `{name}`")
    else:
        lines.extend(
            [
                "## Current Truth",
                "",
                "The focused lifecycle checkpoint is green across backend and frontend slices included in this harness.",
                "",
                "This means the system now has repeatable checkpoint coverage for:",
                "",
                "- chat core lifecycle",
                "- provider failover lifecycle",
                "- multimodal lifecycle",
                "- product search lifecycle",
                "- code studio lifecycle",
                "- desktop request/runtime socket surfaces",
            ]
        )

    return "\n".join(lines) + "\n"


def main() -> int:
    reports_dir = _reports_dir()
    reports_dir.mkdir(parents=True, exist_ok=True)

    results = [_run_suite(spec) for spec in _suite_specs()]
    report = _build_report(results)

    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    json_path = reports_dir / f"system-lifecycle-checkpoint-{timestamp}.json"
    md_path = reports_dir / f"SYSTEM-LIFECYCLE-CHECKPOINT-{timestamp}.md"
    latest_md_path = reports_dir / "SYSTEM-LIFECYCLE-CHECKPOINT-LATEST.md"

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown = _render_markdown(report)
    md_path.write_text(markdown, encoding="utf-8")
    latest_md_path.write_text(markdown, encoding="utf-8")

    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "latest": str(latest_md_path)}, ensure_ascii=False))
    return 0 if report["overall_status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
