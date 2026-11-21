"""Render and write registry validation reports for the command line."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from safe_report_output import safe_write_report_text

from .constants import (
    DEFAULT_REGISTRY,
    REGISTRY_NAME,
    REGISTRY_OUTPUT_PATH_DIRECTORY_ERROR,
    REGISTRY_OUTPUT_PATH_PARENT_SYMLINK_ERROR,
    REGISTRY_OUTPUT_PATH_SYMLINK_ERROR,
    REGISTRY_VALIDATION_SCHEMA_VERSION,
    REPO_ROOT,
)
from .report import (
    _error_code,
    format_summary,
)
from .validator import (
    load_registry,
    validate_registry,
)


def validate_output_path(*, registry_path: Path, out_path: Path | None) -> None:
    if out_path is None:
        return
    if out_path.resolve() == registry_path.resolve():
        raise ValueError("registry validation output path must not overwrite registry")
    if out_path.is_symlink():
        raise ValueError(REGISTRY_OUTPUT_PATH_SYMLINK_ERROR)
    if _path_has_symlink_parent(out_path):
        raise ValueError(REGISTRY_OUTPUT_PATH_PARENT_SYMLINK_ERROR)
    if out_path.exists() and out_path.is_dir():
        raise ValueError(REGISTRY_OUTPUT_PATH_DIRECTORY_ERROR)


def _path_has_symlink_parent(path: Path) -> bool:
    return any(parent.is_symlink() for parent in path.parents)


def write_cli_output(rendered: str, out_path: Path | None) -> None:
    if out_path is None:
        print(rendered)
        return
    safe_write_report_text(out_path, rendered + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=f"Validate {REGISTRY_NAME}.")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable validation output.")
    parser.add_argument("--out", type=Path, default=None, help="Write output directly to a UTF-8 file.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        validate_output_path(registry_path=args.registry, out_path=args.out)
    except Exception as exc:
        if args.json:
            error_code = _error_code(str(exc))
            print(
                json.dumps(
                    {
                        "validation_schema_version": REGISTRY_VALIDATION_SCHEMA_VERSION,
                        "ok": False,
                        "errors": [str(exc)],
                        "error_codes": [error_code],
                        "error_code_counts": {error_code: 1},
                    },
                    indent=2,
                    sort_keys=True,
                ),
                file=sys.stdout,
            )
        else:
            print(f"{REGISTRY_NAME}: FAIL\n- {exc}", file=sys.stderr)
        return 1

    try:
        data = load_registry(args.registry)
    except Exception as exc:
        if args.json:
            error_code = _error_code(str(exc))
            write_cli_output(
                json.dumps(
                    {
                        "validation_schema_version": REGISTRY_VALIDATION_SCHEMA_VERSION,
                        "ok": False,
                        "errors": [str(exc)],
                        "error_codes": [error_code],
                        "error_code_counts": {error_code: 1},
                    },
                    indent=2,
                    sort_keys=True,
                ),
                args.out,
            )
        else:
            print(f"{REGISTRY_NAME}: FAIL\n- {exc}", file=sys.stderr)
        return 1

    result = validate_registry(data, repo_root=args.repo_root, registry_path=args.registry)
    if args.json:
        write_cli_output(json.dumps(result.to_dict(), indent=2, sort_keys=True), args.out)
    else:
        write_cli_output(format_summary(result), args.out)
    return 0 if result.ok else 1
