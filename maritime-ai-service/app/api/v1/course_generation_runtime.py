"""
Course generation background runtime helpers.

This module owns the long-running job shell so the API router can stay focused
on HTTP concerns. Phase executors live in a dedicated module while this file
keeps public wrapper names stable for existing imports and monkeypatch seams.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Awaitable, Callable, Optional

from app.api.v1.course_generation_phase_runtime import (
    run_expand_phase_impl as _run_expand_phase_impl,
    run_outline_phase_impl as _run_outline_phase_impl,
    run_retry_chapter_impl as _run_retry_chapter_impl,
)


def dispatch_course_generation_task(
    coroutine: Awaitable[None],
    *,
    label: str,
    generation_id: str,
    active_tasks: set[asyncio.Task],
    active_tasks_by_job: dict[str, set[asyncio.Task]],
    logger,
    cancelled_error_cls: type[Exception],
) -> asyncio.Task:
    task = asyncio.create_task(coroutine, name=label)
    active_tasks.add(task)
    active_tasks_by_job.setdefault(generation_id, set()).add(task)

    def _cleanup(done: asyncio.Task) -> None:
        active_tasks.discard(done)
        tasks = active_tasks_by_job.get(generation_id)
        if tasks is not None:
            tasks.discard(done)
            if not tasks:
                active_tasks_by_job.pop(generation_id, None)
        if done.cancelled():
            return
        exc = done.exception()
        if isinstance(exc, cancelled_error_cls):
            return
        if exc is not None:
            logger.exception("Course generation task crashed: %s", label, exc_info=exc)

    task.add_done_callback(_cleanup)
    return task


def cancel_active_generation_tasks(
    generation_id: str,
    *,
    active_tasks_by_job: dict[str, set[asyncio.Task]],
) -> int:
    tasks = list(active_tasks_by_job.get(generation_id, set()))
    for task in tasks:
        task.cancel()
    return len(tasks)


def build_outline_status_message(source_mode: str) -> str:
    if source_mode == "full":
        return "Dang tao outline khoa hoc"
    if source_mode == "chunk_compact":
        return "Dang tao outline tu ban do tai lieu da co dong"
    if source_mode == "heading_index":
        return "Dang tao outline tu muc luc tai lieu da nen"
    return "Dang tao outline khoa hoc"


def heartbeat_interval_seconds(settings_obj) -> float:
    interval = getattr(settings_obj, "llm_stream_keepalive_interval_seconds", 15.0)
    try:
        return max(float(interval), 5.0)
    except (TypeError, ValueError):
        return 15.0


def start_generation_heartbeat(
    repo,
    generation_id: str,
    *,
    progress_percent: int,
    status_message: str,
    interval_seconds: float,
    generation_heartbeat_loop_fn,
) -> asyncio.Task:
    return asyncio.create_task(
        generation_heartbeat_loop_fn(
            repo,
            generation_id,
            progress_percent=progress_percent,
            status_message=status_message,
            interval_seconds=interval_seconds,
        ),
        name=f"course-gen:heartbeat:{generation_id}",
    )


async def stop_generation_heartbeat(task: Optional[asyncio.Task]) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        return


async def generation_heartbeat_loop(
    repo,
    generation_id: str,
    *,
    progress_percent: int,
    status_message: str,
    interval_seconds: float,
    terminal_generation_phases: set[str],
    utcnow_fn,
) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        job = await repo.get_job(generation_id)
        if not job:
            return
        if job.get("phase") in terminal_generation_phases:
            return
        if job.get("cancel_requested"):
            return
        await repo.update_progress(
            generation_id,
            progress_percent,
            status_message=status_message,
            heartbeat_at=utcnow_fn(),
        )


async def raise_if_generation_cancelled(
    repo,
    generation_id: str,
    *,
    cancelled_error_cls: type[Exception],
) -> None:
    job = await repo.get_job(generation_id)
    if job and job.get("cancel_requested"):
        raise cancelled_error_cls(
            f"Generation job {generation_id} has been cancelled"
        )


async def recover_course_generation_jobs_impl(
    *,
    limit: int,
    get_course_gen_repo_fn,
    recoverable_phases: tuple[str, ...],
    dispatch_task_fn,
    run_outline_phase_fn,
    run_expand_phase_fn,
    expand_request_cls,
    logger,
    file_exists_fn=os.path.exists,
) -> int:
    repo = get_course_gen_repo_fn()
    claim_jobs = getattr(repo, "claim_jobs_for_recovery", None)
    if callable(claim_jobs):
        jobs = await claim_jobs(list(recoverable_phases), limit=limit)
    else:
        jobs = await repo.list_jobs_by_phases(list(recoverable_phases), limit=limit)
    recovered = 0

    for job in jobs:
        generation_id = job["id"]
        phase = job.get("phase")

        if phase in {"CONVERTING", "RECOVERING_OUTLINE"}:
            file_path = job.get("file_path")
            if not file_path or not file_exists_fn(file_path):
                await repo.update_phase(
                    generation_id,
                    "FAILED",
                    error="Recovery failed: source document is no longer available",
                )
                continue

            dispatch_task_fn(
                run_outline_phase_fn(
                    generation_id,
                    file_path,
                    job["teacher_id"],
                    job.get("teacher_prompt", ""),
                    job.get("language", "vi"),
                    job.get("target_chapters"),
                ),
                label=f"course-gen:recover:outline:{generation_id}",
                generation_id=generation_id,
            )
            recovered += 1
            continue

        if phase in {"EXPANDING", "RECOVERING_EXPANDING"}:
            expand_request = job.get("expand_request")
            if not expand_request:
                await repo.update_phase(
                    generation_id,
                    "FAILED",
                    error="Recovery failed: expand request snapshot is missing",
                )
                continue

            req = expand_request_cls(**expand_request)
            dispatch_task_fn(
                run_expand_phase_fn(generation_id, req),
                label=f"course-gen:recover:expand:{generation_id}",
                generation_id=generation_id,
            )
            recovered += 1

    if recovered:
        logger.info("Recovered %d course generation job(s)", recovered)
    return recovered


async def run_outline_phase_impl(
    generation_id: str,
    file_path: str,
    teacher_id: str,
    teacher_prompt: str,
    language: str,
    target_chapters: Optional[int],
    *,
    get_course_gen_repo_fn,
    convert_node_fn,
    outline_node_fn,
    prepare_outline_source_fn,
    get_parser_fn,
    raise_if_generation_cancelled_fn,
    build_outline_status_message_fn,
    start_generation_heartbeat_fn,
    stop_generation_heartbeat_fn,
    utcnow_fn,
    cleanup_outline_source_file_fn,
    logger,
    cancelled_error_cls: type[Exception],
) -> None:
    return await _run_outline_phase_impl(
        generation_id,
        file_path,
        teacher_id,
        teacher_prompt,
        language,
        target_chapters,
        get_course_gen_repo_fn=get_course_gen_repo_fn,
        convert_node_fn=convert_node_fn,
        outline_node_fn=outline_node_fn,
        prepare_outline_source_fn=prepare_outline_source_fn,
        get_parser_fn=get_parser_fn,
        raise_if_generation_cancelled_fn=raise_if_generation_cancelled_fn,
        build_outline_status_message_fn=build_outline_status_message_fn,
        start_generation_heartbeat_fn=start_generation_heartbeat_fn,
        stop_generation_heartbeat_fn=stop_generation_heartbeat_fn,
        utcnow_fn=utcnow_fn,
        cleanup_outline_source_file_fn=cleanup_outline_source_file_fn,
        logger=logger,
        cancelled_error_cls=cancelled_error_cls,
    )


async def run_expand_phase_impl(
    generation_id: str,
    req,
    *,
    get_course_gen_repo_fn,
    get_push_service_fn,
    raise_if_generation_cancelled_fn,
    utcnow_fn,
    normalize_approved_chapters_fn,
    merge_completed_chapters_fn,
    dedupe_failed_chapters_fn,
    without_failed_chapters_fn,
    compute_expand_progress_fn,
    settings_obj,
    expand_single_chapter_fn,
    compute_execution_waves_fn,
    start_generation_heartbeat_fn,
    stop_generation_heartbeat_fn,
    build_partial_failure_summary_fn,
    upsert_failed_chapter_fn,
    logger,
    cancelled_error_cls: type[Exception],
) -> None:
    return await _run_expand_phase_impl(
        generation_id,
        req,
        get_course_gen_repo_fn=get_course_gen_repo_fn,
        get_push_service_fn=get_push_service_fn,
        raise_if_generation_cancelled_fn=raise_if_generation_cancelled_fn,
        utcnow_fn=utcnow_fn,
        normalize_approved_chapters_fn=normalize_approved_chapters_fn,
        merge_completed_chapters_fn=merge_completed_chapters_fn,
        dedupe_failed_chapters_fn=dedupe_failed_chapters_fn,
        without_failed_chapters_fn=without_failed_chapters_fn,
        compute_expand_progress_fn=compute_expand_progress_fn,
        settings_obj=settings_obj,
        expand_single_chapter_fn=expand_single_chapter_fn,
        compute_execution_waves_fn=compute_execution_waves_fn,
        start_generation_heartbeat_fn=start_generation_heartbeat_fn,
        stop_generation_heartbeat_fn=stop_generation_heartbeat_fn,
        build_partial_failure_summary_fn=build_partial_failure_summary_fn,
        upsert_failed_chapter_fn=upsert_failed_chapter_fn,
        logger=logger,
        cancelled_error_cls=cancelled_error_cls,
    )


async def run_retry_chapter_impl(
    generation_id: str,
    chapter_index: int,
    *,
    get_course_gen_repo_fn,
    get_push_service_fn,
    raise_if_generation_cancelled_fn,
    merge_completed_chapters_fn,
    without_failed_chapter_fn,
    upsert_failed_chapter_fn,
    build_partial_failure_summary_fn,
    expand_single_chapter_fn,
    utcnow_fn,
    logger,
    cancelled_error_cls: type[Exception],
) -> None:
    return await _run_retry_chapter_impl(
        generation_id,
        chapter_index,
        get_course_gen_repo_fn=get_course_gen_repo_fn,
        get_push_service_fn=get_push_service_fn,
        raise_if_generation_cancelled_fn=raise_if_generation_cancelled_fn,
        merge_completed_chapters_fn=merge_completed_chapters_fn,
        without_failed_chapter_fn=without_failed_chapter_fn,
        upsert_failed_chapter_fn=upsert_failed_chapter_fn,
        build_partial_failure_summary_fn=build_partial_failure_summary_fn,
        expand_single_chapter_fn=expand_single_chapter_fn,
        utcnow_fn=utcnow_fn,
        logger=logger,
        cancelled_error_cls=cancelled_error_cls,
    )
