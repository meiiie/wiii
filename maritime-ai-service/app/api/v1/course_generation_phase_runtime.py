"""
Course generation phase executors.

Extracted from course_generation_runtime so the runtime shell can focus on job
dispatch, cancellation, heartbeat, and recovery orchestration.
"""

from __future__ import annotations

import asyncio
from typing import Optional


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
    repo = get_course_gen_repo_fn()
    try:
        parser = get_parser_fn(file_path)
        await repo.update_phase(
            generation_id,
            "CONVERTING",
            progress_percent=5,
            status_message="Đang chuyển đổi tài liệu nguồn",
            started_at=utcnow_fn(),
            heartbeat_at=utcnow_fn(),
            cancel_requested=False,
            cancelled_at=None,
            completed_at=None,
            error=None,
        )
        await raise_if_generation_cancelled_fn(repo, generation_id)

        state = await convert_node_fn(
            {
                "generation_id": generation_id,
                "file_path": file_path,
                "teacher_id": teacher_id,
                "teacher_prompt": teacher_prompt,
                "language": language,
                "target_chapters": target_chapters,
            },
            parser=parser,
        )

        await repo.update_progress(
            generation_id,
            18,
            status_message="Dang chuan bi nguon outline theo budget provider",
        )
        await raise_if_generation_cancelled_fn(repo, generation_id)

        prepared_source = prepare_outline_source_fn(
            markdown=state.get("markdown", ""),
            tier="deep",
        )
        state = {
            **state,
            "outline_source_markdown": prepared_source.rendered_markdown,
            "outline_source_mode": prepared_source.mode,
            "outline_source_metadata": prepared_source.to_metadata(),
        }
        logger.info(
            "Outline source prepared: generation=%s, mode=%s, providers=%s, original_tokens=%s, prepared_tokens=%s, token_budget=%s",
            generation_id,
            prepared_source.mode,
            ",".join(prepared_source.candidate_providers),
            prepared_source.original_tokens_estimate,
            prepared_source.prepared_tokens_estimate,
            prepared_source.token_budget,
        )
        outline_status_message = build_outline_status_message_fn(prepared_source.mode)

        await repo.update_progress(
            generation_id,
            25,
            heartbeat_at=utcnow_fn(),
            status_message="Đang tạo outline khóa học",
        )
        await raise_if_generation_cancelled_fn(repo, generation_id)

        heartbeat_task = start_generation_heartbeat_fn(
            repo,
            generation_id,
            progress_percent=25,
            status_message=outline_status_message,
        )
        try:
            state = await outline_node_fn(state)
        finally:
            await stop_generation_heartbeat_fn(heartbeat_task)

        await repo.update_phase(
            generation_id,
            "OUTLINE_READY",
            outline=state.get("outline"),
            markdown=state.get("markdown"),
            section_map=state.get("section_map"),
            progress_percent=40,
            status_message="Outline đã sẵn sàng để duyệt",
            completed_at=None,
            cancel_requested=False,
            heartbeat_at=utcnow_fn(),
            error=None,
        )
        logger.info("Outline ready: generation=%s", generation_id)
        cleanup_outline_source_file_fn(file_path)

    except (asyncio.CancelledError, cancelled_error_cls):
        logger.info("Outline cancelled: generation=%s", generation_id)
        await repo.update_phase(
            generation_id,
            "CANCELLED",
            cancel_requested=True,
            cancelled_at=utcnow_fn(),
            status_message="Đã hủy tác vụ tạo outline",
        )
        raise
    except Exception as exc:
        logger.exception("Outline failed: generation=%s", generation_id)
        await repo.update_phase(
            generation_id,
            "FAILED",
            error=str(exc),
            status_message="Tạo outline thất bại. Có thể thử resume sau khi kiểm tra môi trường.",
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
    repo = get_course_gen_repo_fn()
    try:
        await repo.update_phase(
            generation_id,
            "EXPANDING",
            expand_request=req.model_dump(),
            progress_percent=45,
            status_message="Đang chuẩn bị mở rộng nội dung khóa học",
            started_at=utcnow_fn(),
            heartbeat_at=utcnow_fn(),
            cancel_requested=False,
            cancelled_at=None,
            completed_at=None,
            error=None,
        )
        await raise_if_generation_cancelled_fn(repo, generation_id)

        push_service = get_push_service_fn()
        if not push_service:
            raise RuntimeError("LMS push service unavailable")

        course_id = req.course_id
        if not course_id:
            shell = await push_service.push_course_shell_async(
                teacher_id=req.teacher_id,
                category_id=req.category_id,
                title=req.course_title,
                description="",
            )
            if not shell:
                raise RuntimeError("Failed to create course shell")
            course_id = shell.get("courseId")
            if not course_id:
                raise RuntimeError(f"No courseId returned: {shell}")

        await repo.update_phase(
            generation_id,
            "EXPANDING",
            course_id=str(course_id),
            progress_percent=50,
            status_message="Đã tạo lớp vỏ khóa học, đang sinh nội dung chương",
            heartbeat_at=utcnow_fn(),
        )
        await raise_if_generation_cancelled_fn(repo, generation_id)

        job = await repo.get_job(generation_id)
        outline = job["outline"]
        chapters = outline["chapters"]
        approved_chapters = normalize_approved_chapters_fn(req.approved_chapters, len(chapters))
        existing_completed = merge_completed_chapters_fn(job.get("completed_chapters", []))
        existing_failed = dedupe_failed_chapters_fn(job.get("failed_chapters", []))
        completed_indexes = {
            item.get("index")
            for item in existing_completed
            if isinstance(item.get("index"), int)
        }
        pending_chapters = [idx for idx in approved_chapters if idx not in completed_indexes]
        existing_failed = without_failed_chapters_fn(existing_failed, pending_chapters)

        deps = {}
        for chapter in chapters:
            idx = chapter.get("orderIndex", 0)
            if chapter.get("dependsOn"):
                deps[idx] = chapter["dependsOn"]

        waves = compute_execution_waves_fn(pending_chapters, deps) if pending_chapters else []
        max_concurrent = getattr(settings_obj, "course_gen_max_concurrent_chapters", 3)
        semaphore = asyncio.Semaphore(max_concurrent)

        all_completed = list(existing_completed)
        all_failed = list(existing_failed)
        total_target = len(approved_chapters)

        if not waves:
            await repo.update_phase(
                generation_id,
                "COMPLETED",
                expand_request=req.model_dump(),
                progress_percent=100,
                status_message="Không còn chương nào cần chạy tiếp",
                completed_at=utcnow_fn(),
                error=build_partial_failure_summary_fn(all_failed),
            )
            return

        for wave_idx, wave in enumerate(waves, start=1):
            await raise_if_generation_cancelled_fn(repo, generation_id)
            await repo.update_progress(
                generation_id,
                compute_expand_progress_fn(total_target, len(all_completed)),
                status_message=f"Đang xử lý đợt {wave_idx}/{len(waves)} với {len(wave)} chương",
            )

            async def expand_limited(chapter_idx: int) -> dict:
                async with semaphore:
                    await raise_if_generation_cancelled_fn(repo, generation_id)
                    chapter = chapters[chapter_idx]
                    state = {
                        "generation_id": generation_id,
                        "teacher_id": req.teacher_id,
                        "language": req.language,
                        "course_id": str(course_id),
                        "markdown": job.get("markdown", ""),
                        "section_map": job.get("section_map") or {},
                        "current_chapter": chapter,
                        "current_chapter_idx": chapter_idx,
                        "completed_chapters": [],
                        "failed_chapters": [],
                    }
                    return await expand_single_chapter_fn(state)

            heartbeat_task = start_generation_heartbeat_fn(
                repo,
                generation_id,
                progress_percent=compute_expand_progress_fn(total_target, len(all_completed)),
                status_message=f"Dang xu ly dot {wave_idx}/{len(waves)} voi {len(wave)} chuong",
            )
            try:
                results = await asyncio.gather(
                    *[expand_limited(idx) for idx in wave],
                    return_exceptions=True,
                )
            finally:
                await stop_generation_heartbeat_fn(heartbeat_task)

            for chapter_idx, result in zip(wave, results):
                if isinstance(result, Exception):
                    logger.exception("Expand error: gen=%s, ch=%s", generation_id, chapter_idx)
                    all_failed = upsert_failed_chapter_fn(
                        all_failed,
                        {
                            "index": chapter_idx,
                            "error": str(result),
                            "phase": "EXPAND_FAILED",
                            "content_cache": None,
                        },
                    )
                    continue
                if isinstance(result, dict):
                    all_completed.extend(result.get("completed_chapters", []))
                    all_failed.extend(result.get("failed_chapters", []))

            all_completed = merge_completed_chapters_fn(all_completed)
            all_failed = dedupe_failed_chapters_fn(all_failed)

            await repo.update_chapters(generation_id, all_completed, all_failed)
            await repo.update_progress(
                generation_id,
                compute_expand_progress_fn(total_target, len(all_completed)),
                status_message=(
                    f"Đã hoàn thành {len(all_completed)}/{total_target} chương"
                    if total_target
                    else "Đã hoàn thành sinh nội dung chương"
                ),
            )

        await repo.update_phase(
            generation_id,
            "COMPLETED",
            expand_request=req.model_dump(),
            progress_percent=100,
            status_message=(
                "Đã hoàn tất tạo khóa học"
                if not all_failed
                else "Hoàn tất với một số chương cần chạy lại"
            ),
            completed_at=utcnow_fn(),
            error=build_partial_failure_summary_fn(all_failed),
        )
        logger.info(
            "Expand complete: gen=%s, ok=%d, fail=%d",
            generation_id,
            len(all_completed),
            len(all_failed),
        )

    except (asyncio.CancelledError, cancelled_error_cls):
        logger.info("Expand cancelled: gen=%s", generation_id)
        await repo.update_phase(
            generation_id,
            "CANCELLED",
            expand_request=req.model_dump(),
            cancel_requested=True,
            cancelled_at=utcnow_fn(),
            status_message="Đã hủy tác vụ mở rộng khóa học",
        )
        raise
    except Exception as exc:
        logger.exception("Expand failed: gen=%s", generation_id)
        await repo.update_phase(
            generation_id,
            "FAILED",
            error=str(exc),
            expand_request=req.model_dump(),
            status_message="Mở rộng nội dung khóa học thất bại. Có thể resume để tiếp tục.",
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
    repo = get_course_gen_repo_fn()
    try:
        job = await repo.get_job(generation_id)
        await repo.update_progress(
            generation_id,
            min((job or {}).get("progress_percent", 90), 95),
            status_message=f"Đang chạy lại chương {chapter_index + 1}",
        )
        if not job:
            raise RuntimeError("Generation job not found")
        if job.get("cancel_requested"):
            raise cancelled_error_cls(
                f"Generation job {generation_id} has been cancelled"
            )

        failed_ch = await repo.get_failed_chapter(generation_id, chapter_index)
        if not failed_ch:
            raise RuntimeError(f"Chapter {chapter_index} is no longer marked as failed")

        course_id = job.get("course_id")
        if not course_id:
            raise RuntimeError("No course_id — expand not started yet")

        content_cache = failed_ch.get("content_cache")

        if content_cache:
            push_service = get_push_service_fn()
            if not push_service:
                raise RuntimeError("Push service unavailable")

            response = await push_service.push_chapter_content_async(course_id, content_cache)
            await raise_if_generation_cancelled_fn(repo, generation_id)
            latest_job = await repo.get_job(generation_id) or job
            if response:
                completed = merge_completed_chapters_fn(
                    latest_job.get("completed_chapters", []) + [{
                        "index": chapter_index,
                        "chapterId": response.get("chapterId"),
                        "status": "COMPLETED",
                    }]
                )
                await repo.update_chapters(
                    generation_id,
                    completed,
                    without_failed_chapter_fn(latest_job.get("failed_chapters", []), chapter_index),
                )
                logger.info("Retry push success: gen=%s, ch=%d", generation_id, chapter_index)
            else:
                failed = upsert_failed_chapter_fn(
                    latest_job.get("failed_chapters", []),
                    {
                        "index": chapter_index,
                        "error": "Push retry failed",
                        "phase": "PUSH_FAILED",
                        "content_cache": content_cache,
                    },
                )
                await repo.update_chapters(
                    generation_id,
                    latest_job.get("completed_chapters", []),
                    failed,
                )
        else:
            outline = job["outline"]
            chapter = outline["chapters"][chapter_index]

            state = {
                "generation_id": generation_id,
                "teacher_id": job["teacher_id"],
                "language": job.get("language", "vi"),
                "course_id": course_id,
                "markdown": job.get("markdown", ""),
                "section_map": job.get("section_map") or {},
                "current_chapter": chapter,
                "current_chapter_idx": chapter_index,
                "completed_chapters": [],
                "failed_chapters": [],
            }

            result = await expand_single_chapter_fn(state)
            await raise_if_generation_cancelled_fn(repo, generation_id)

            latest_job = await repo.get_job(generation_id) or job
            completed = merge_completed_chapters_fn(
                latest_job.get("completed_chapters", []) + result.get("completed_chapters", [])
            )
            failed = without_failed_chapter_fn(latest_job.get("failed_chapters", []), chapter_index)
            for failed_item in result.get("failed_chapters", []):
                failed = upsert_failed_chapter_fn(failed, failed_item)
            await repo.update_chapters(generation_id, completed, failed)

            if result.get("completed_chapters"):
                logger.info("Retry full success: gen=%s, ch=%d", generation_id, chapter_index)
            else:
                logger.warning("Retry full failed: gen=%s, ch=%d", generation_id, chapter_index)

        latest = await repo.get_job(generation_id)
        if latest:
            failed = latest.get("failed_chapters", [])
            await repo.update_phase(
                generation_id,
                latest.get("phase", "COMPLETED"),
                progress_percent=100
                if not failed and latest.get("phase") == "COMPLETED"
                else latest.get("progress_percent", 95),
                status_message=(
                    f"Đã chạy lại thành công chương {chapter_index + 1}"
                    if not failed
                    else f"Đã cập nhật trạng thái sau khi chạy lại chương {chapter_index + 1}"
                ),
                error=build_partial_failure_summary_fn(failed),
            )

    except (asyncio.CancelledError, cancelled_error_cls):
        logger.info("Retry cancelled: gen=%s, ch=%d", generation_id, chapter_index)
        await repo.update_phase(
            generation_id,
            "CANCELLED",
            cancel_requested=True,
            cancelled_at=utcnow_fn(),
            status_message=f"Đã hủy chạy lại chương {chapter_index + 1}",
        )
        raise
    except Exception as exc:
        logger.exception("Retry failed: gen=%s, ch=%d", generation_id, chapter_index)
        latest_job = await repo.get_job(generation_id) or {}
        failed = upsert_failed_chapter_fn(
            latest_job.get("failed_chapters", []),
            {
                "index": chapter_index,
                "error": f"Retry error: {exc}",
                "phase": "RETRY_FAILED",
                "content_cache": (
                    failed_ch.get("content_cache")
                    if "failed_ch" in locals() and failed_ch is not None
                    else None
                ),
            },
        )
        await repo.update_chapters(
            generation_id,
            latest_job.get("completed_chapters", []),
            failed,
        )
        await repo.update_phase(
            generation_id,
            latest_job.get("phase", "COMPLETED"),
            error=build_partial_failure_summary_fn(failed),
            status_message=f"Chạy lại chương {chapter_index + 1} thất bại",
        )
