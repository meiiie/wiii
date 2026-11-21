"""Shared validation state and primitive field and path checks."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from .constants import (
    DOT_PATH_RE,
    WILDCARD_DOT_PATH_RE,
)


class ValidationChecks:
    def __init__(self, *, repo_root: Path, registry_path: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.registry_path = registry_path.resolve()
        self.errors: list[str] = []
        self.passed_checks = 0

    def pass_check(self) -> None:
        self.passed_checks += 1

    def error(self, message: str) -> None:
        self.errors.append(message)

    def resolve_repo_path(self, raw_path: Any, *, context: str) -> Path | None:
        if not isinstance(raw_path, str) or not raw_path.strip():
            self.error(f"{context}: path must be a non-empty string")
            return None
        normalized = raw_path.replace("\\", "/").strip()
        posix_path = PurePosixPath(normalized)
        parts = posix_path.parts
        if (
            Path(normalized).is_absolute()
            or posix_path.is_absolute()
            or ".." in parts
            or (parts and ":" in parts[0])
        ):
            self.error(f"{context}: path must be repo-relative: {raw_path!r}")
            return None

        relative_path = Path(*parts)
        raw_candidate = self.repo_root / relative_path
        candidate = raw_candidate.resolve()
        try:
            candidate.relative_to(self.repo_root)
        except ValueError:
            self.error(f"{context}: path escapes repo root: {raw_path!r}")
            return None
        if _repo_relative_path_contains_symlink(self.repo_root, relative_path):
            self.error(f"{context}: path must not contain symlinks: {raw_path!r}")
            return None
        self.pass_check()
        return candidate

    def require_string(self, value: Any, field: str, *, context: str) -> str:
        if not isinstance(value, str) or not value.strip():
            self.error(f"{context}: `{field}` must be a non-empty string")
            return ""
        self.pass_check()
        return value.strip()

    def require_string_list(self, value: Any, field: str, *, context: str) -> list[str]:
        if (
            not isinstance(value, list)
            or not value
            or not all(isinstance(item, str) and item.strip() for item in value)
        ):
            self.error(f"{context}: `{field}` must be a non-empty string list")
            return []
        self.pass_check()
        values = [item.strip() for item in value]
        self.require_unique_string_values(values, field=field, context=context)
        return values

    def require_string_list_allow_empty(self, value: Any, field: str, *, context: str) -> list[str]:
        if not isinstance(value, list) or not all(
            isinstance(item, str) and item.strip() for item in value
        ):
            self.error(f"{context}: `{field}` must be a string list")
            return []
        self.pass_check()
        return [item.strip() for item in value]

    def require_dot_path(
        self,
        value: str,
        field: str,
        *,
        context: str,
        allow_wildcard: bool = False,
    ) -> None:
        pattern = WILDCARD_DOT_PATH_RE if allow_wildcard else DOT_PATH_RE
        if pattern.match(value):
            self.pass_check()
            return
        wildcard_hint = " with `*` wildcard segments" if allow_wildcard else ""
        self.error(f"{context}: `{field}` must be dot-path syntax{wildcard_hint}")

    def require_json_scalar(self, value: Any, field: str, *, context: str) -> None:
        if value is None or isinstance(value, (dict, list)):
            self.error(f"{context}: {field} must be a non-null JSON scalar")
            return
        self.pass_check()

    def reject_unknown_keys(
        self,
        item: dict[str, Any],
        *,
        allowed_keys: set[str],
        context: str,
    ) -> None:
        unknown_keys = sorted(set(item) - allowed_keys)
        if unknown_keys:
            self.error(f"{context}: unknown field(s): {', '.join(unknown_keys)}")
            return
        self.pass_check()

    def require_unique_string_values(
        self,
        values: list[str],
        *,
        field: str,
        context: str,
    ) -> None:
        seen_values: set[str] = set()
        duplicate_values: list[str] = []
        for value in values:
            if value in seen_values and value not in duplicate_values:
                duplicate_values.append(value)
            seen_values.add(value)
        if duplicate_values:
            rendered = ", ".join(repr(value) for value in duplicate_values)
            self.error(f"{context}: `{field}` must not contain duplicate values: {rendered}")
            return
        self.pass_check()

    def require_unique_repo_path_values(
        self,
        values: list[str],
        *,
        field: str,
        context: str,
    ) -> None:
        seen_paths: dict[str, str] = {}
        duplicate_paths: list[tuple[str, str]] = []
        for value in values:
            normalized = _normalized_registry_path_key(value)
            previous = seen_paths.get(normalized)
            if previous is not None and (previous, value) not in duplicate_paths:
                duplicate_paths.append((previous, value))
                continue
            seen_paths[normalized] = value
        if duplicate_paths:
            rendered = ", ".join(
                f"{first!r} and {second!r}" for first, second in duplicate_paths
            )
            self.error(
                f"{context}: `{field}` must not contain duplicate normalized paths: "
                f"{rendered}"
            )
            return
        self.pass_check()

    def require_file_text(self, raw_path: Any, *, context: str) -> tuple[Path | None, str]:
        path = self.resolve_repo_path(raw_path, context=context)
        if path is None:
            return None, ""
        if not path.exists():
            self.error(f"{context}: file does not exist: {raw_path}")
            return path, ""
        if not path.is_file():
            self.error(f"{context}: path must be a file: {raw_path}")
            return path, ""
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            self.error(f"{context}: file is not UTF-8: {raw_path} ({exc})")
            return path, ""
        self.pass_check()
        return path, text

    def require_tokens(self, text: str, tokens: list[str], *, context: str) -> None:
        for token in tokens:
            if token not in text:
                self.error(f"{context}: missing token {token!r}")
            else:
                self.pass_check()


def _normalized_registry_path_key(raw_path: str) -> str:
    return str(PurePosixPath(raw_path.replace("\\", "/").strip()))


def _repo_relative_path_contains_symlink(repo_root: Path, relative_path: Path) -> bool:
    current = repo_root
    for part in relative_path.parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def _is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1
