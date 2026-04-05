"""Support helpers for course generation API wrappers."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException

from app.core.security import AuthenticatedUser, is_platform_admin
from app.core.thread_utils import build_thread_id


def utcnow_impl() -> datetime:
    return datetime.now(timezone.utc)


def derive_generation_thread_id_impl(auth: AuthenticatedUser) -> Optional[str]:
    if not auth.session_id:
        return None
    try:
        return build_thread_id(auth.user_id, auth.session_id, auth.organization_id)
    except ValueError:
        return None


def compute_expand_progress_impl(total_target: int, completed_count: int) -> int:
    if total_target <= 0:
        return 50
    ratio = max(0.0, min(completed_count / total_target, 1.0))
    return min(99, 50 + int(round(ratio * 49)))


def without_failed_chapters_impl(chapters: list[dict], chapter_indices: list[int]) -> list[dict]:
    if not chapter_indices:
        return list(chapters)
    blocked = set(chapter_indices)
    return [chapter for chapter in chapters if chapter.get("index") not in blocked]


def cleanup_outline_source_file_impl(file_path: str) -> None:
    try:
        os.unlink(file_path)
    except OSError:
        pass


def ensure_teacher_matches_auth_impl(teacher_id: str, auth: AuthenticatedUser) -> None:
    if is_platform_admin(auth):
        return
    if auth.user_id != teacher_id:
        raise HTTPException(
            403,
            "You do not have permission to manage this course generation job",
        )


def require_generation_job_access_impl(job: dict, auth: AuthenticatedUser) -> None:
    if not is_platform_admin(auth) and auth.user_id != job.get("teacher_id"):
        raise HTTPException(
            403,
            "You do not have permission to access this course generation job",
        )

    job_org = job.get("organization_id")
    if job_org and not is_platform_admin(auth) and auth.organization_id != job_org:
        raise HTTPException(
            403,
            "You do not have permission to access this organization job",
        )


def normalize_approved_chapters_impl(indices: list[int], chapter_count: int) -> list[int]:
    normalized: list[int] = []
    seen: set[int] = set()
    for idx in indices:
        if idx < 0 or idx >= chapter_count:
            raise HTTPException(
                400,
                f"approved_chapters contains invalid index {idx}; outline has {chapter_count} chapters",
            )
        if idx in seen:
            continue
        seen.add(idx)
        normalized.append(idx)
    if not normalized:
        raise HTTPException(400, "approved_chapters must not be empty")
    return normalized


def merge_completed_chapters_impl(chapters: list[dict]) -> list[dict]:
    by_index: dict[int, dict] = {}
    for chapter in chapters:
        idx = chapter.get("index")
        if isinstance(idx, int):
            by_index[idx] = chapter
    return [by_index[idx] for idx in sorted(by_index)]


def without_failed_chapter_impl(chapters: list[dict], chapter_index: int) -> list[dict]:
    return [chapter for chapter in chapters if chapter.get("index") != chapter_index]


def dedupe_failed_chapters_impl(chapters: list[dict]) -> list[dict]:
    by_index: dict[int, dict] = {}
    for chapter in chapters:
        idx = chapter.get("index")
        if isinstance(idx, int):
            by_index[idx] = chapter
    return [by_index[idx] for idx in sorted(by_index)]


def upsert_failed_chapter_impl(chapters: list[dict], failed: dict) -> list[dict]:
    merged = without_failed_chapter_impl(chapters, failed.get("index"))
    merged.append(failed)
    return dedupe_failed_chapters_impl(merged)


def build_partial_failure_summary_impl(failed_chapters: list[dict]) -> Optional[str]:
    if not failed_chapters:
        return None
    return f"{len(failed_chapters)} chapter(s) failed during expansion"
