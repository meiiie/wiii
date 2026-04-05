"""Support helpers for ChatOrchestrator side-effect orchestration."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Optional


logger = logging.getLogger(__name__)


def finalize_response_turn_impl(
    *,
    logger_obj: Any,
    session_manager: Any,
    persist_chat_message: Callable[..., None],
    upsert_thread_view: Callable[..., None],
    background_runner: Any,
    post_response_context_cls: Any,
    schedule_post_response_continuity_fn: Callable[..., Any],
    session_id: Any,
    user_id: str,
    user_role: Any,
    message: str,
    response_text: str,
    context: Any,
    domain_id: str | None,
    organization_id: str | None,
    current_agent: str,
    background_save: Optional[Callable],
    save_response_immediately: bool,
    include_lms_insights: bool,
    continuity_channel: str,
    transport_type: str,
) -> None:
    """Run post-response continuity, persistence, and thread sync."""
    used_name = (
        bool(context and context.user_name)
        and context.user_name.lower() in response_text.lower()
    ) if response_text else False
    opening = response_text[:50].strip() if response_text else None
    session_manager.update_state(
        session_id=session_id,
        phrase=opening,
        used_name=used_name,
    )

    persist_chat_message(
        session_id=session_id,
        role="assistant",
        content=response_text,
        user_id=user_id,
        background_save=background_save,
        immediate=save_response_immediately,
    )
    session_manager.append_message(
        session_id=session_id,
        role="assistant",
        content=response_text,
    )

    if response_text:
        upsert_thread_view(
            user_id=user_id,
            session_id=session_id,
            domain_id=domain_id,
            title=message,
            organization_id=organization_id,
        )

    if background_save and background_runner:
        background_runner.schedule_all(
            background_save=background_save,
            user_id=user_id,
            session_id=session_id,
            message=message,
            response=response_text,
            skip_fact_extraction=current_agent == "memory_agent",
            org_id=organization_id or "",
        )

    scheduled_hooks = schedule_post_response_continuity_fn(
        post_response_context_cls(
            user_id=user_id,
            user_role=user_role,
            message=message,
            response_text=response_text,
            domain_id=domain_id or "",
            organization_id=organization_id,
            channel=continuity_channel,
        ),
        include_lms_insights=include_lms_insights,
    )

    continuity_summary = {
        "session_id": str(session_id),
        "user_id": str(user_id),
        "domain_id": domain_id or "",
        "organization_id": organization_id or "",
        "transport_type": transport_type,
        "continuity_channel": continuity_channel,
        "include_lms_insights": include_lms_insights,
        "scheduled_hooks": list(scheduled_hooks),
        "background_tasks_scheduled": bool(background_save and background_runner),
        "response_persistence": (
            "immediate"
            if save_response_immediately or background_save is None
            else "background"
        ),
    }
    logger_obj.info(
        "[CONTINUITY] Finalized turn summary: %s",
        json.dumps(continuity_summary, sort_keys=True),
    )


def load_pronoun_style_from_facts_impl(
    *,
    semantic_memory: Any,
    session: Any,
    user_id: str,
) -> None:
    """Load persisted pronoun style from semantic memory."""
    try:
        if not semantic_memory or not semantic_memory.is_available():
            return

        from app.models.semantic_memory import MemoryType
        from app.repositories.semantic_memory_repository import (
            get_semantic_memory_repository,
        )

        repo = get_semantic_memory_repository()
        if not repo.is_available():
            return

        results = repo.get_memories_by_type(
            user_id=user_id,
            memory_type=MemoryType.USER_FACT,
            limit=10,
        )
        for memory in results:
            metadata = memory.metadata or {}
            if metadata.get("fact_type") != "pronoun_style":
                continue

            content = memory.content
            value = content.split(": ", 1)[-1] if ": " in content else content
            pronoun_dict = json.loads(value)
            session.state.update_pronoun_style(pronoun_dict)
            logger.debug("[SPRINT79] Loaded pronoun_style from facts for %s", user_id)
            return
    except Exception as exc:
        logger.debug("Failed to load pronoun style from facts: %s", exc)


def persist_pronoun_style_impl(
    *,
    background_save: Callable,
    user_id: str,
    pronoun_style: dict,
) -> None:
    """Store detected pronoun style as a semantic triple in the background."""
    pronoun_str = json.dumps(pronoun_style, ensure_ascii=False)

    def _store() -> None:
        try:
            from app.models.semantic_memory import Predicate, SemanticTriple
            from app.repositories.semantic_memory_repository import (
                get_semantic_memory_repository,
            )

            repo = get_semantic_memory_repository()
            if not repo.is_available():
                return

            triple = SemanticTriple(
                subject=user_id,
                predicate=Predicate.HAS_PRONOUN_STYLE,
                object=pronoun_str,
                object_type="personal",
                confidence=0.8,
            )
            repo.upsert_triple(triple)
            logger.debug("[SPRINT79] Persisted pronoun_style for %s", user_id)
        except Exception as exc:
            logger.debug("Failed to persist pronoun style: %s", exc)

    background_save(_store)


def maybe_summarize_previous_session_impl(
    *,
    background_save: Callable,
    user_id: str,
) -> None:
    """Schedule background summarization for the previous thread when needed."""
    try:
        from app.repositories.thread_repository import get_thread_repository
        from app.tasks.summarize_tasks import summarize_thread_background

        repo = get_thread_repository()
        threads = repo.list_threads(user_id=user_id, limit=2)
        if len(threads) < 2:
            return

        previous_thread = threads[1]
        extra = previous_thread.get("extra_data") or {}
        if extra.get("summary"):
            return

        background_save(
            summarize_thread_background,
            previous_thread["thread_id"],
            user_id,
        )
        logger.info(
            "[SPRINT79] Triggered auto-summarize of previous session %s",
            previous_thread["thread_id"],
        )
    except Exception as exc:
        logger.debug("Auto-summarize previous session failed: %s", exc)
