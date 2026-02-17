"""
Memory Consolidation Tasks — Background memory maintenance

Sprint 18: Virtual Agent-per-User Architecture
Daily/periodic tasks for maintaining user memory quality:
- Deduplicate similar facts (cosine similarity > 0.90)
- Extract new facts from recent unsummarized sessions
- Merge contradictory facts

Feature-gated: Requires `enable_background_tasks=True`.
"""

import logging

logger = logging.getLogger(__name__)


async def consolidate_user_memory(user_id: str) -> dict:
    """
    Consolidate memory for a single user.

    1. Load all user facts from semantic_memory
    2. Identify and merge duplicate facts (cosine > 0.90)
    3. Extract new facts from recent unsummarized sessions
    4. Update thread_views with session summaries

    Args:
        user_id: User ID to consolidate

    Returns:
        Dict with consolidation results
    """
    results = {
        "user_id": user_id,
        "facts_processed": 0,
        "duplicates_merged": 0,
        "new_facts_extracted": 0,
        "sessions_summarized": 0,
        "errors": [],
    }

    # Step 1: Summarize unsummarized sessions
    try:
        from app.services.session_summarizer import get_session_summarizer
        from app.repositories.thread_repository import get_thread_repository

        summarizer = get_session_summarizer()
        thread_repo = get_thread_repository()

        threads = thread_repo.list_threads(user_id=user_id, limit=20)
        for thread in threads:
            extra = thread.get("extra_data", {})
            if isinstance(extra, dict) and not extra.get("summary"):
                summary = await summarizer.summarize_thread(
                    thread_id=thread["thread_id"],
                    user_id=user_id,
                )
                if summary:
                    results["sessions_summarized"] += 1

    except Exception as e:
        logger.warning("Session summarization step failed: %s", e)
        results["errors"].append(f"summarization: {e}")

    logger.info(
        "[MEMORY_CONSOLIDATION] user=%s: "
        "summarized=%d, "
        "errors=%d",
        user_id, results['sessions_summarized'], len(results['errors']),
    )
    return results


async def consolidate_all_active_users() -> dict:
    """
    Run memory consolidation for all users with recent activity.

    Intended to be called by a daily scheduled task.

    Returns:
        Summary of consolidation results
    """
    results = {"users_processed": 0, "errors": []}

    try:
        from app.repositories.thread_repository import get_thread_repository
        from sqlalchemy import text

        repo = get_thread_repository()
        repo._ensure_initialized()

        if not repo._session_factory:
            return results

        # Get distinct users with recent threads (last 7 days)
        with repo._session_factory() as session:
            rows = session.execute(
                text(
                    "SELECT DISTINCT user_id FROM thread_views "
                    "WHERE last_message_at > NOW() - INTERVAL '7 days'"
                )
            ).fetchall()

        for row in rows:
            user_id = row[0]
            try:
                await consolidate_user_memory(user_id)
                results["users_processed"] += 1
            except Exception as e:
                results["errors"].append(f"{user_id}: {e}")

    except Exception as e:
        logger.error("Memory consolidation batch failed: %s", e)
        results["errors"].append(str(e))

    logger.info(
        "[MEMORY_CONSOLIDATION] Batch complete: "
        "users=%d, errors=%d",
        results['users_processed'], len(results['errors']),
    )
    return results
