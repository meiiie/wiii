"""
Course Generation Workflow — 3-Node LangGraph Pipeline

CONVERT (Docling) → OUTLINE (DEEP tier) → EXPAND (LIGHT tier, parallel)

Design spec v2.0 (2026-03-22), expert-reviewed.
Pattern: Canvas IgniteAI iterative generation.
Philosophy: Anthropic "Building Effective Agents" — workflow over agent.

IMPORTANT: Uses platform LLM directly (get_llm_deep/get_llm_light).
NO custom LlmPort — platform already handles provider failover, thinking tiers.
"""

import asyncio
import logging
import re
from typing import Any, Optional, TypedDict
from uuid import uuid4

import structlog
from langchain_core.messages import HumanMessage

from app.engine.llm_pool import (
    get_llm_deep,
    get_llm_light,
    is_rate_limit_error,
)
from app.engine.workflows.course_generation_source_preparation import (
    prepare_outline_source,
)
from app.models.course_generation import CourseOutlineSchema, ChapterContentSchema
from app.ports.document_parser import DocumentParserPort
from app.prompts.course_generation.outline import build_outline_prompt
from app.prompts.course_generation.expand import build_expand_prompt

logger = structlog.get_logger()


# ── State Schema ──

class CourseGenState(TypedDict, total=False):
    # Input
    document_id: str
    file_path: str
    teacher_id: str
    teacher_prompt: str
    language: str
    target_chapters: Optional[int]

    # After CONVERT
    markdown: str
    section_map: dict
    metadata: dict
    page_count: int
    outline_source_markdown: str
    outline_source_mode: str
    outline_source_metadata: dict[str, Any]

    # After OUTLINE
    outline: Optional[dict]
    phase: str
    generation_id: str

    # After teacher approval (set externally)
    approved_chapters: list[int]
    course_id: Optional[str]

    # EXPAND tracking
    current_chapter: Optional[dict]
    current_chapter_idx: Optional[int]
    completed_chapters: list[dict]
    failed_chapters: list[dict]


# ── Node 0: CONVERT (Deterministic — Docling) ──

async def convert_node(
    state: CourseGenState,
    *,
    parser: DocumentParserPort,
) -> CourseGenState:
    """Convert document to structured Markdown via DocumentParserPort."""
    generation_id = state.get("generation_id", str(uuid4()))
    file_path = state["file_path"]

    logger.info("course_gen.convert_start",
                generation_id=generation_id, file_path=file_path)

    parsed = await parser.parse(
        file_path=file_path,
        options={"language": state.get("language", "vi")},
    )

    logger.info("course_gen.convert_complete",
                generation_id=generation_id,
                pages=parsed.page_count,
                sections=len(parsed.section_map),
                markdown_chars=len(parsed.markdown))

    return {
        **state,
        "generation_id": generation_id,
        "markdown": parsed.markdown,
        "section_map": parsed.section_map,
        "metadata": parsed.metadata,
        "page_count": parsed.page_count,
    }


# ── Node 1: OUTLINE (DEEP tier — reasoning-heavy) ──

async def outline_node(state: CourseGenState) -> CourseGenState:
    """Generate course outline — 1 LLM call, DEEP tier for structural reasoning."""
    generation_id = state.get("generation_id", "unknown")
    from app.services.structured_invoke_service import StructuredInvokeService

    prepared_markdown = state.get("outline_source_markdown") or state.get("markdown", "")
    source_mode = state.get("outline_source_mode", "full")
    if not prepared_markdown and state.get("markdown"):
        prepared = prepare_outline_source(markdown=state["markdown"], tier="deep")
        prepared_markdown = prepared.rendered_markdown
        source_mode = prepared.mode
        state = {
            **state,
            "outline_source_markdown": prepared.rendered_markdown,
            "outline_source_mode": prepared.mode,
            "outline_source_metadata": prepared.to_metadata(),
        }

    logger.info("course_gen.outline_start",
                generation_id=generation_id,
                markdown_chars=len(state.get("markdown", "")),
                outline_source_chars=len(prepared_markdown),
                outline_source_mode=source_mode)

    llm = get_llm_deep()

    messages = [HumanMessage(content=build_outline_prompt(
        markdown=prepared_markdown,
        language=state.get("language", "vi"),
        target_chapters=state.get("target_chapters"),
        teacher_prompt=state.get("teacher_prompt", ""),
        source_mode=source_mode,
    ))]

    outline = await StructuredInvokeService.ainvoke(
        llm=llm,
        schema=CourseOutlineSchema,
        payload=messages,
        tier="deep",
        timeout_profile="background",
    )

    logger.info("course_gen.outline_complete",
                generation_id=generation_id,
                title=outline.title,
                chapters=len(outline.chapters),
                outline_source_mode=source_mode)

    return {
        **state,
        "outline": outline.model_dump(),
        "phase": "OUTLINE_READY",
    }


# ── Node 2: EXPAND (LIGHT tier — transformation, per-chapter) ──

async def expand_single_chapter(state: CourseGenState) -> CourseGenState:
    """Generate full content for ONE chapter — LIGHT tier, retry logic."""
    generation_id = state.get("generation_id", "unknown")
    from app.services.structured_invoke_service import StructuredInvokeService
    chapter = state["current_chapter"]
    chapter_idx = state["current_chapter_idx"]
    course_id = state["course_id"]

    logger.info("course_gen.expand_start",
                generation_id=generation_id,
                chapter_idx=chapter_idx,
                chapter_title=chapter.get("title", ""))

    # Extract relevant markdown for this chapter
    relevant_content = extract_chapter_content(
        markdown=state["markdown"],
        source_pages=chapter.get("sourcePages", []),
        section_map=state.get("section_map", {}),
    )

    llm = get_llm_light()

    messages = [HumanMessage(content=build_expand_prompt(
        chapter=chapter,
        source_content=relevant_content,
        language=state.get("language", "vi"),
    ))]

    # LLM call with retry + automatic provider failover on 429
    max_retries = 2
    chapter_content = None
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            chapter_content = await StructuredInvokeService.ainvoke(
                llm=llm,
                schema=ChapterContentSchema,
                payload=messages,
                tier="light",
                timeout_profile="background",
            )
            break
        except Exception as e:
            last_error = e
            should_retry = isinstance(e, (TimeoutError, asyncio.TimeoutError)) or is_rate_limit_error(e)
            if attempt < max_retries and should_retry:
                wait = 2 ** attempt
                logger.warning("course_gen.expand_llm_retry",
                               generation_id=generation_id,
                               chapter_idx=chapter_idx,
                               attempt=attempt + 1,
                               wait_seconds=wait,
                               error=str(e))
                await asyncio.sleep(wait)
            else:
                break

    if chapter_content is None:
        logger.error("course_gen.expand_llm_failed",
                     generation_id=generation_id,
                     chapter_idx=chapter_idx,
                     error=str(last_error))
        return {
            **state,
            "failed_chapters": state.get("failed_chapters", []) + [{
                "index": chapter_idx,
                "error": str(last_error),
                "phase": "LLM_FAILED",
                "content_cache": None,
            }],
        }

    # Push to LMS — cache content before push for retry-push
    chapter_dict = chapter_content.model_dump()
    chapter_dict["teacherId"] = state.get("teacher_id", "")

    from app.integrations.lms.push_service import get_push_service
    push_service = get_push_service()

    if push_service is None:
        logger.error("course_gen.push_service_unavailable",
                     generation_id=generation_id)
        return {
            **state,
            "failed_chapters": state.get("failed_chapters", []) + [{
                "index": chapter_idx,
                "error": "LMS push service unavailable",
                "phase": "PUSH_FAILED",
                "content_cache": chapter_dict,
            }],
        }

    response = await push_service.push_chapter_content_async(course_id, chapter_dict)

    if response is None:
        logger.error("course_gen.push_failed",
                     generation_id=generation_id,
                     chapter_idx=chapter_idx)
        return {
            **state,
            "failed_chapters": state.get("failed_chapters", []) + [{
                "index": chapter_idx,
                "error": "LMS API push failed",
                "phase": "PUSH_FAILED",
                "content_cache": chapter_dict,
            }],
        }

    logger.info("course_gen.expand_complete",
                generation_id=generation_id,
                chapter_idx=chapter_idx,
                chapter_id=response.get("chapterId"))

    return {
        **state,
        "completed_chapters": state.get("completed_chapters", []) + [{
            "index": chapter_idx,
            "chapterId": response.get("chapterId"),
            "status": "COMPLETED",
        }],
    }


# ── Section Extraction (Expert Fix 2) ──

def extract_chapter_content(
    markdown: str,
    source_pages: list[int],
    section_map: dict[str, list[int]],
) -> str:
    """Extract relevant markdown for one chapter using page boundaries.

    Uses Docling page markers (<!-- page N -->) and heading boundaries
    to find the right portion of the document.
    """
    if not source_pages or not markdown:
        return markdown

    lines = markdown.split("\n")
    relevant_lines = []
    current_page_estimate = 1
    page_marker_pattern = re.compile(r"<!-- page (\d+) -->")

    in_relevant_section = False

    for line in lines:
        # Docling inserts page markers in markdown
        page_match = page_marker_pattern.search(line)
        if page_match:
            current_page_estimate = int(page_match.group(1))

        # On heading boundary, check if current page is in sourcePages
        if line.startswith("#"):
            in_relevant_section = current_page_estimate in source_pages

        if in_relevant_section:
            relevant_lines.append(line)

    result = "\n".join(relevant_lines)

    # Safety: if extracted too little (<5% of markdown), fallback to full
    if len(result) < len(markdown) * 0.05:
        logger.warning("course_gen.extraction_too_small",
                       source_pages=source_pages,
                       extracted_ratio=len(result) / max(len(markdown), 1))
        return markdown

    # Truncate to ~50K chars per chapter for LLM context
    max_chars = 50000
    if len(result) > max_chars:
        result = result[:max_chars] + "\n\n[... nội dung bị cắt do quá dài ...]"

    return result


# ── Parallel Execution Waves ──

def compute_execution_waves(
    approved: list[int],
    deps: dict[int, list[int]],
) -> list[list[int]]:
    """Topological sort into parallel waves respecting chapter dependencies."""
    if not deps:
        return [approved]

    waves = []
    completed = set()
    remaining = set(approved)

    while remaining:
        wave = [
            ch for ch in sorted(remaining)
            if all(d in completed for d in deps.get(ch, []))
        ]
        if not wave:
            logger.warning("course_gen.circular_dependency",
                           remaining=list(remaining))
            wave = [min(remaining)]
        waves.append(wave)
        completed.update(wave)
        remaining -= set(wave)

    return waves


# ── Main Orchestrator ──

async def run_course_generation(
    file_path: str,
    teacher_id: str,
    teacher_prompt: str = "",
    language: str = "vi",
    target_chapters: int | None = None,
    approved_chapters: list[int] | None = None,
    course_id: str | None = None,
    *,
    parser: DocumentParserPort,
    max_concurrent: int = 3,
    on_progress: Optional[callable] = None,
) -> dict:
    """Run course generation pipeline.

    Phase 1 (outline): CONVERT + OUTLINE → returns outline for teacher review
    Phase 2 (expand): EXPAND approved chapters → push to LMS

    Args:
        parser: DocumentParserPort (only abstraction needed — Docling is new dep)
        Other args: plain values, no DI needed — platform handles LLM/push
    """
    generation_id = str(uuid4())

    state: CourseGenState = {
        "file_path": file_path,
        "teacher_id": teacher_id,
        "teacher_prompt": teacher_prompt,
        "language": language,
        "target_chapters": target_chapters,
        "generation_id": generation_id,
        "completed_chapters": [],
        "failed_chapters": [],
    }

    # Phase 1: CONVERT + OUTLINE
    state = await convert_node(state, parser=parser)
    state = await outline_node(state)

    if on_progress:
        on_progress({"phase": "OUTLINE_READY", "outline": state["outline"]})

    if approved_chapters is None:
        return {
            "generation_id": generation_id,
            "phase": "OUTLINE_READY",
            "outline": state["outline"],
            "page_count": state.get("page_count", 0),
            "markdown": state.get("markdown", ""),
            "section_map": state.get("section_map", {}),
        }

    # Phase 2: EXPAND approved chapters
    state["approved_chapters"] = approved_chapters
    state["course_id"] = course_id

    outline_chapters = state["outline"]["chapters"]

    # Build dependency map
    deps = {}
    for ch in outline_chapters:
        idx = ch.get("orderIndex", 0)
        depends = ch.get("dependsOn", [])
        if depends:
            deps[idx] = depends

    waves = compute_execution_waves(approved_chapters, deps)
    semaphore = asyncio.Semaphore(max_concurrent)

    for wave_idx, wave in enumerate(waves):
        logger.info("course_gen.wave_start",
                    generation_id=generation_id,
                    wave=wave_idx + 1,
                    total_waves=len(waves),
                    chapters=wave)

        async def expand_with_limit(ch_idx: int) -> CourseGenState:
            async with semaphore:
                chapter = outline_chapters[ch_idx]
                expand_state = {
                    **state,
                    "current_chapter": chapter,
                    "current_chapter_idx": ch_idx,
                }
                return await expand_single_chapter(expand_state)

        results = await asyncio.gather(
            *[expand_with_limit(idx) for idx in wave],
            return_exceptions=True,
        )

        for result in results:
            if isinstance(result, Exception):
                logger.exception("course_gen.wave_error",
                                 generation_id=generation_id,
                                 error=str(result))
                continue
            if isinstance(result, dict):
                for ch in result.get("completed_chapters", []):
                    state["completed_chapters"].append(ch)
                    if on_progress:
                        on_progress({
                            "phase": "CHAPTER_GENERATED",
                            "courseId": course_id,
                            "chapterIndex": ch["index"],
                            "totalChapters": len(approved_chapters),
                        })
                for ch in result.get("failed_chapters", []):
                    state["failed_chapters"].append(ch)

    if on_progress:
        on_progress({"phase": "COMPLETED", "courseId": course_id})

    return {
        "generation_id": generation_id,
        "phase": "COMPLETED",
        "course_id": course_id,
        "completed_chapters": state["completed_chapters"],
        "failed_chapters": state["failed_chapters"],
    }
