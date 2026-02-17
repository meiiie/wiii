"""
Memory Lifecycle — Active Pruning of Decayed Memories

Sprint 123 (P4): Stanford Generative Agents pattern.
`should_prune()` existed in importance_decay.py since Sprint 73 but was
never called.  This module wires it into the extraction flow as an
inline pre-extraction step (avoids a separate background task).

Feature-gated via `settings.enable_memory_pruning` (default True).
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def prune_stale_memories(user_id: str) -> int:
    """
    Active garbage collection for decayed memories.

    Called inline before `extract_and_store_facts()` to keep the memory
    store clean.  Deletes facts whose effective importance has dropped
    below `settings.memory_prune_threshold`.

    Returns:
        Number of facts pruned
    """
    try:
        from app.core.config import settings
        if not settings.enable_memory_pruning:
            return 0

        from app.repositories.semantic_memory_repository import get_semantic_memory_repository
        from app.engine.semantic_memory.importance_decay import (
            calculate_effective_importance_from_timestamps,
        )

        repo = get_semantic_memory_repository()
        all_facts = repo.get_all_user_facts(user_id)

        if not all_facts:
            return 0

        prune_threshold = settings.memory_prune_threshold
        now = datetime.now(timezone.utc)
        pruned = 0

        for fact in all_facts:
            meta = fact.metadata or {}
            fact_type = meta.get("fact_type", "unknown")
            access_count = meta.get("access_count", 0)

            effective = calculate_effective_importance_from_timestamps(
                base_importance=fact.importance,
                fact_type=fact_type,
                last_accessed=meta.get("last_accessed"),
                created_at=fact.created_at,
                access_count=access_count,
                now=now,
            )

            if effective < prune_threshold:
                success = repo.delete_memory(user_id, str(fact.id))
                if success:
                    pruned += 1
                    logger.info(
                        "Pruned stale fact for user %s: type=%s, "
                        "effective_importance=%.3f, content='%s'",
                        user_id, fact_type, effective, fact.content[:50],
                    )

        if pruned > 0:
            logger.info(
                "Memory pruning complete for user %s: removed %d/%d stale facts",
                user_id, pruned, len(all_facts),
            )
        return pruned

    except Exception as e:
        logger.warning("Memory pruning failed for user %s: %s", user_id, e)
        return 0
