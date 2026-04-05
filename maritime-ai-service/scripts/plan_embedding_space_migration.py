"""Plan or execute a full embedding-space migration with maintenance safeguards."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.embedding_space_migration_service import (
    migrate_embedding_space_rows,
    plan_embedding_space_migration,
)
from app.services.llm_runtime_policy_service import apply_persisted_llm_runtime_policy


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plan or run a full embedding-space migration for semantic memories and knowledge embeddings.",
    )
    parser.add_argument(
        "--target-model",
        required=True,
        help="Target embedding model (for example: embeddinggemma, text-embedding-3-small).",
    )
    parser.add_argument(
        "--target-dimensions",
        type=int,
        default=None,
        help="Optional explicit dimensions when target model supports override.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Thuc thi migration that su. Mac dinh chi lap plan dry-run.",
    )
    parser.add_argument(
        "--ack-maintenance-window",
        action="store_true",
        help="Xac nhan da co maintenance window/drain traffic truoc khi apply.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=16,
        help="So row moi batch embedding.",
    )
    parser.add_argument(
        "--limit-per-table",
        type=int,
        default=None,
        help="Gioi han so row moi bang de smoke/an toan.",
    )
    parser.add_argument(
        "--tables",
        nargs="*",
        default=None,
        help="Danh sach bang can xu ly: semantic_memories knowledge_embeddings",
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="Ghi JSON report vao .Codex/reports.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    apply_persisted_llm_runtime_policy()

    if args.apply:
        payload = migrate_embedding_space_rows(
            target_model=args.target_model,
            target_dimensions=args.target_dimensions,
            dry_run=False,
            batch_size=max(1, args.batch_size),
            limit_per_table=args.limit_per_table,
            tables=args.tables,
            acknowledge_maintenance_window=args.ack_maintenance_window,
        ).to_dict()
    else:
        payload = plan_embedding_space_migration(
            target_model=args.target_model,
            target_dimensions=args.target_dimensions,
            tables=args.tables,
        ).to_dict()

    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if args.write_report:
        root = Path(__file__).resolve().parents[2]
        reports_dir = root / ".Codex" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        report_path = reports_dir / f"embedding-space-migration-{stamp}.json"
        report_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(str(report_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
