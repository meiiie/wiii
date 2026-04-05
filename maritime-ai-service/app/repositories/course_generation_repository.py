"""
CourseGenerationRepository — persists generation job state in PostgreSQL.

Follows existing pattern: dense_search_repository.py (asyncpg pool).
Replaces in-memory _generation_jobs dict.

Design spec v2.0 (2026-03-22), expert requirement for production-readiness.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class CourseGenerationRepository:
    """Persist course generation job state for crash recovery."""

    def __init__(self):
        self._pool = None

    async def _get_pool(self):
        if self._pool is None:
            try:
                import asyncpg
                self._pool = await asyncpg.create_pool(
                    settings.asyncpg_url,
                    min_size=1,
                    max_size=3,
                )
            except Exception as e:
                logger.error("Course gen repository pool creation failed: %s", e)
                raise
        return self._pool

    async def create_job(
        self,
        generation_id: str,
        teacher_id: str,
        file_path: str,
        language: str = "vi",
        teacher_prompt: str = "",
        target_chapters: Optional[int] = None,
        organization_id: Optional[str] = None,
        session_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        status_message: Optional[str] = None,
    ) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO course_generation_jobs
                    (id, teacher_id, phase, file_path, language, teacher_prompt,
                     target_chapters, organization_id, session_id, thread_id,
                     progress_percent, status_message)
                VALUES ($1, $2, 'CONVERTING', $3, $4, $5, $6, $7, $8, $9, 0, $10)
                """,
                generation_id, teacher_id, file_path, language,
                teacher_prompt, target_chapters, organization_id, session_id,
                thread_id, status_message,
            )

    async def update_phase(
        self,
        generation_id: str,
        phase: str,
        **kwargs,
    ) -> None:
        """Update job phase and optional fields (outline, course_id, error, etc.)."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            # Build dynamic SET clause for optional fields
            set_parts = ["phase = $2", "updated_at = $3"]
            values = [generation_id, phase, datetime.now(timezone.utc)]
            param_idx = 4

            for key in (
                "outline",
                "markdown",
                "section_map",
                "expand_request",
                "course_id",
                "error",
                "progress_percent",
                "status_message",
                "session_id",
                "thread_id",
                "started_at",
                "heartbeat_at",
                "completed_at",
                "cancel_requested",
                "cancelled_at",
            ):
                if key in kwargs:
                    val = kwargs[key]
                    if key in ("outline", "section_map", "expand_request", "completed_chapters", "failed_chapters"):
                        val = json.dumps(val, ensure_ascii=False) if val is not None else None
                    set_parts.append(f"{key} = ${param_idx}")
                    values.append(val)
                    param_idx += 1

            sql = f"UPDATE course_generation_jobs SET {', '.join(set_parts)} WHERE id = $1"
            await conn.execute(sql, *values)

    async def update_chapters(
        self,
        generation_id: str,
        completed_chapters: list[dict],
        failed_chapters: list[dict],
    ) -> None:
        """Update chapter completion status."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE course_generation_jobs
                SET completed_chapters = $2::jsonb,
                    failed_chapters = $3::jsonb,
                    updated_at = $4
                WHERE id = $1
                """,
                generation_id,
                json.dumps(completed_chapters, ensure_ascii=False),
                json.dumps(failed_chapters, ensure_ascii=False),
                datetime.now(timezone.utc),
            )

    async def update_progress(
        self,
        generation_id: str,
        progress_percent: int,
        *,
        status_message: Optional[str] = None,
        heartbeat_at: Optional[datetime] = None,
    ) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE course_generation_jobs
                SET progress_percent = $2,
                    status_message = COALESCE($3, status_message),
                    heartbeat_at = $4,
                    updated_at = $5
                WHERE id = $1
                """,
                generation_id,
                max(0, min(int(progress_percent), 100)),
                status_message,
                heartbeat_at or datetime.now(timezone.utc),
                datetime.now(timezone.utc),
            )

    async def mark_heartbeat(
        self,
        generation_id: str,
        *,
        status_message: Optional[str] = None,
    ) -> None:
        await self.update_progress(
            generation_id,
            progress_percent=(await self.get_job(generation_id) or {}).get("progress_percent", 0),
            status_message=status_message,
            heartbeat_at=datetime.now(timezone.utc),
        )

    async def request_cancel(
        self,
        generation_id: str,
        *,
        status_message: Optional[str] = None,
    ) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE course_generation_jobs
                SET cancel_requested = TRUE,
                    status_message = COALESCE($2, status_message),
                    updated_at = $3
                WHERE id = $1
                """,
                generation_id,
                status_message,
                datetime.now(timezone.utc),
            )

    async def clear_cancel_request(self, generation_id: str) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE course_generation_jobs
                SET cancel_requested = FALSE,
                    cancelled_at = NULL,
                    updated_at = $2
                WHERE id = $1
                """,
                generation_id,
                datetime.now(timezone.utc),
            )

    async def list_jobs(
        self,
        *,
        teacher_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict]:
        pool = await self._get_pool()

        filters: list[str] = []
        values: list[object] = []
        next_param = 1

        if teacher_id:
            filters.append(f"teacher_id = ${next_param}")
            values.append(teacher_id)
            next_param += 1
        if organization_id:
            filters.append(f"organization_id = ${next_param}")
            values.append(organization_id)
            next_param += 1

        values.append(limit)
        limit_param = next_param

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        sql = (
            "SELECT * FROM course_generation_jobs "
            f"{where_clause} "
            f"ORDER BY created_at DESC LIMIT ${limit_param}"
        )

        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *values)
        return [self._row_to_dict(row) for row in rows]

    async def get_job(self, generation_id: str) -> Optional[dict]:
        """Get job by ID. Returns dict or None."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM course_generation_jobs WHERE id = $1",
                generation_id,
            )
            if not row:
                return None
            return self._row_to_dict(row)

    async def claim_jobs_for_recovery(self, phases: list[str], limit: int = 100) -> list[dict]:
        """Atomically claim recoverable jobs so multiple workers do not duplicate work."""
        if not phases:
            return []

        pool = await self._get_pool()
        claimed_at = datetime.now(timezone.utc)
        stale_recovery_before = claimed_at.timestamp() - 60
        async with pool.acquire() as conn:
            async with conn.transaction():
                rows = await conn.fetch(
                    """
                    WITH claimed AS (
                        SELECT id, phase
                        FROM course_generation_jobs
                        WHERE (
                                phase = ANY($1::text[])
                                AND COALESCE(cancel_requested, FALSE) = FALSE
                                AND phase NOT IN ('RECOVERING_OUTLINE', 'RECOVERING_EXPANDING')
                            ) OR (
                                phase IN ('RECOVERING_OUTLINE', 'RECOVERING_EXPANDING')
                                AND COALESCE(cancel_requested, FALSE) = FALSE
                                AND EXTRACT(EPOCH FROM updated_at) <= $3
                            )
                        ORDER BY created_at ASC
                        FOR UPDATE SKIP LOCKED
                        LIMIT $2
                    )
                    UPDATE course_generation_jobs AS jobs
                    SET phase = CASE
                            WHEN claimed.phase IN ('CONVERTING', 'RECOVERING_OUTLINE')
                                THEN 'RECOVERING_OUTLINE'
                            WHEN claimed.phase IN ('EXPANDING', 'RECOVERING_EXPANDING')
                                THEN 'RECOVERING_EXPANDING'
                            ELSE jobs.phase
                        END,
                        updated_at = $4
                    FROM claimed
                    WHERE jobs.id = claimed.id
                    RETURNING jobs.*
                    """,
                    phases,
                    limit,
                    stale_recovery_before,
                    claimed_at,
                )
        return [self._row_to_dict(row) for row in rows]

    async def list_jobs_by_phases(self, phases: list[str], limit: int = 100) -> list[dict]:
        """List generation jobs by phase for recovery/sweeper flows."""
        if not phases:
            return []

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM course_generation_jobs
                WHERE phase = ANY($1::text[])
                ORDER BY created_at ASC
                LIMIT $2
                """,
                phases,
                limit,
            )
        return [self._row_to_dict(row) for row in rows]

    async def get_failed_chapter(
        self, generation_id: str, chapter_index: int
    ) -> Optional[dict]:
        """Get a specific failed chapter with cached content for retry."""
        job = await self.get_job(generation_id)
        if not job:
            return None
        failed = job.get("failed_chapters", [])
        for ch in failed:
            if ch.get("index") == chapter_index:
                return ch
        return None

    async def remove_failed_chapter(
        self, generation_id: str, chapter_index: int
    ) -> None:
        """Remove a chapter from failed list (before retry)."""
        job = await self.get_job(generation_id)
        if not job:
            return
        failed = [ch for ch in job.get("failed_chapters", [])
                  if ch.get("index") != chapter_index]
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE course_generation_jobs
                SET failed_chapters = $2::jsonb, updated_at = $3
                WHERE id = $1
                """,
                generation_id,
                json.dumps(failed, ensure_ascii=False),
                datetime.now(timezone.utc),
            )

    def _row_to_dict(self, row) -> dict:
        d = dict(row)
        # Parse JSONB fields that asyncpg returns as strings
        for key in ("outline", "section_map", "expand_request", "completed_chapters", "failed_chapters"):
            val = d.get(key)
            if isinstance(val, str):
                try:
                    d[key] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    pass
        return d

    async def close(self) -> None:
        """Close the repository asyncpg pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None


# Singleton
_repo: Optional[CourseGenerationRepository] = None


def get_course_gen_repo() -> CourseGenerationRepository:
    global _repo
    if _repo is None:
        _repo = CourseGenerationRepository()
    return _repo
