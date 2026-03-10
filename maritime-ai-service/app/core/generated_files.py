"""Shared helpers for user-facing generated files.

This module centralizes the workspace location and URL contract for files that
Wiii creates or harvests for the user, regardless of whether they come from a
native output tool or a sandbox execution.
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Final
from urllib.parse import quote

GENERATED_MEDIA_TYPES: Final[dict[str, str]] = {
    ".html": "text/html; charset=utf-8",
    ".htm": "text/html; charset=utf-8",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".csv": "text/csv; charset=utf-8",
    ".json": "application/json",
    ".pdf": "application/pdf",
    ".md": "text/markdown; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
}

INLINE_GENERATED_SUFFIXES: Final[set[str]] = {
    ".html",
    ".htm",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".svg",
    ".csv",
    ".json",
    ".pdf",
    ".md",
    ".txt",
}


def get_generated_dir() -> Path:
    """Return the stable directory for user-facing generated files."""
    workspace_root = os.getenv("WORKSPACE_ROOT") or "~/.wiii/workspace"
    workspace = Path(workspace_root).expanduser()
    target = workspace / "generated"
    target.mkdir(parents=True, exist_ok=True)
    return target


def build_generated_file_url(filename: str) -> str:
    """Return the API path that serves a generated file."""
    return f"/api/v1/generated-files/{quote(filename)}"


def guess_generated_media_type(filename_or_path: str | Path) -> str:
    """Return the media type if the suffix is supported by Wiii's file server."""
    suffix = Path(filename_or_path).suffix.lower()
    return GENERATED_MEDIA_TYPES.get(suffix, "application/octet-stream")


def is_allowed_generated_file(filename_or_path: str | Path) -> bool:
    """Return whether the suffix is allowed to be served to the client."""
    suffix = Path(filename_or_path).suffix.lower()
    return suffix in GENERATED_MEDIA_TYPES


def generated_file_disposition(filename_or_path: str | Path) -> str:
    """Choose inline vs attachment based on whether browsers can preview it well."""
    suffix = Path(filename_or_path).suffix.lower()
    return "inline" if suffix in INLINE_GENERATED_SUFFIXES else "attachment"


def persist_generated_file(
    filename_hint: str,
    content: bytes | str,
    *,
    prefix: str = "artifact",
) -> Path:
    """Write generated content into the shared workspace with a stable unique name."""
    filename = Path(filename_hint or "").name
    suffix = Path(filename).suffix.lower()
    stem = Path(filename).stem if suffix else filename
    if not suffix:
        suffix = ".txt"
    safe_stem = _slugify(stem or prefix, prefix)
    target = get_generated_dir() / f"{safe_stem}_{_timestamp()}{suffix}"
    if isinstance(content, str):
        target.write_text(content, encoding="utf-8")
    else:
        target.write_bytes(content)
    return target


def _slugify(value: str, default: str) -> str:
    text = (value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text[:48] or default


def _timestamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S")
