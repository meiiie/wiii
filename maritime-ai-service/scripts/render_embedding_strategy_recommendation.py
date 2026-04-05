"""Render a durable embedding strategy report for Wiii."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings
from app.services.embedding_strategy_recommendation import (
    benchmark_canonical_dimensions,
    benchmark_snapshot,
    build_embedding_strategy_guardrails,
    load_latest_embedding_benchmark,
    recommend_embedding_strategies,
    render_embedding_strategy_markdown,
)


def _workspace_root() -> Path:
    return CURRENT_FILE.parents[2]


def _reports_dir() -> Path:
    return _workspace_root() / ".Codex" / "reports"


def main() -> None:
    reports_dir = _reports_dir()
    reports_dir.mkdir(parents=True, exist_ok=True)

    benchmark_source, benchmark_payload = load_latest_embedding_benchmark(reports_dir)
    snapshot = benchmark_snapshot(benchmark_payload)
    canonical_dimensions = benchmark_canonical_dimensions(benchmark_payload) or getattr(
        settings,
        "embedding_dimensions",
        768,
    )

    recommendations = recommend_embedding_strategies(
        canonical_dimensions=canonical_dimensions,
        snapshot=snapshot,
        benchmark_payload=benchmark_payload,
    )
    markdown = render_embedding_strategy_markdown(
        canonical_dimensions=canonical_dimensions,
        recommendations=recommendations,
        benchmark_payload=benchmark_payload,
        benchmark_source=benchmark_source.name if benchmark_source else None,
    )

    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    markdown_path = reports_dir / f"EMBEDDING-MODEL-SELECTION-{stamp}.md"
    json_path = reports_dir / f"embedding-model-selection-{stamp}.json"

    payload = {
        "generated_at": datetime.now().isoformat(),
        "canonical_dimensions": canonical_dimensions,
        "benchmark_source": str(benchmark_source) if benchmark_source else None,
        "guardrails": build_embedding_strategy_guardrails(),
        "recommendations": [item.to_dict() for item in recommendations],
    }

    markdown_path.write_text(markdown, encoding="utf-8")
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({"markdown": str(markdown_path), "json": str(json_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
