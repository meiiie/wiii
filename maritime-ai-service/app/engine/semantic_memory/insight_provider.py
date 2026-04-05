"""
Insight Provider Module for Semantic Memory
CHI THI KY THUAT SO 25 - Project Restructure (Phase 2)

Handles insight extraction, validation, merging, evolution tracking,
and lifecycle management (consolidation, FIFO eviction).

Extracted from core.py for better modularity.

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 3.1, 5.1, 5.2, 5.3, 5.4
"""
import logging
from typing import List, Optional

from app.engine.embedding_runtime import EmbeddingBackendProtocol
from app.models.semantic_memory import (
    Insight,
    InsightCategory,
    MemoryType,
    SemanticMemoryCreate,
)
from app.repositories.semantic_memory_repository import SemanticMemoryRepository

logger = logging.getLogger(__name__)


class InsightProvider:
    """
    Handles insight extraction, validation, and lifecycle management.

    Responsibilities:
    - Extract behavioral insights from messages
    - Validate insights (duplicates, contradictions)
    - Merge/update existing insights with evolution tracking
    - Enforce hard limits via consolidation and FIFO eviction

    Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 3.1, 5.1, 5.2, 5.3, 5.4
    """

    # Insight Engine v0.5 Configuration (CHI THI 23 CAI TIEN)
    MAX_INSIGHTS = 50  # Hard limit for insights
    CONSOLIDATION_THRESHOLD = 40  # Trigger consolidation at this count
    PRESERVE_DAYS = 7  # Preserve memories accessed within 7 days

    def __init__(
        self,
        embeddings: EmbeddingBackendProtocol,
        repository: SemanticMemoryRepository,
    ):
        """
        Initialize InsightProvider.

        Args:
            embeddings: Semantic embedding backend instance
            repository: SemanticMemoryRepository instance
        """
        self._embeddings = embeddings
        self._repository = repository

        # Insight Engine v0.5 components (lazy initialization)
        self._insight_extractor = None
        self._insight_validator = None
        self._memory_consolidator = None

        logger.debug("InsightProvider initialized")

    async def update_last_accessed(self, insight_id: int) -> bool:
        """Update last_accessed timestamp for an insight."""
        try:
            return self._repository.update_last_accessed(insight_id)
        except Exception as e:
            logger.error("Failed to update last_accessed: %s", e)
            return False

    async def extract_and_store_insights(
        self,
        user_id: str,
        message: str,
        conversation_history: List[str] = None,
        session_id: Optional[str] = None,
    ) -> List[Insight]:
        """
        Extract behavioral insights from message and store them.

        v0.5 (CHI THI 23 CAI TIEN):
        1. Extract insights using InsightExtractor
        2. Validate each insight
        3. Handle duplicates (merge) and contradictions (update)
        4. Check consolidation threshold
        5. Store valid insights

        Args:
            user_id: User ID
            message: User message to extract insights from
            conversation_history: Previous messages for context
            session_id: Optional session ID

        Returns:
            List of stored insights

        **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 5.1, 5.2, 5.3, 5.4**
        """
        try:
            # Lazy init insight components
            if self._insight_extractor is None:
                try:
                    from app.engine.insight_extractor import InsightExtractor
                    self._insight_extractor = InsightExtractor()
                except ImportError:
                    logger.warning("InsightExtractor not available, skipping insight extraction")
                    return []

            if self._insight_validator is None:
                try:
                    from app.engine.insight_validator import InsightValidator
                    # SOTA: Pass embeddings for semantic similarity
                    self._insight_validator = InsightValidator(embeddings=self._embeddings)
                except ImportError:
                    logger.warning("InsightValidator not available")
                    self._insight_validator = None

            if self._memory_consolidator is None:
                try:
                    from app.engine.memory_consolidator import MemoryConsolidator
                    self._memory_consolidator = MemoryConsolidator()
                except ImportError:
                    logger.warning("MemoryConsolidator not available")
                    self._memory_consolidator = None

            # Step 1: Extract insights
            insights = await self._insight_extractor.extract_insights(
                user_id=user_id,
                message=message,
                conversation_history=conversation_history,
            )

            if not insights:
                return []

            # Step 2: Get existing insights for validation
            existing_insights = await self._get_user_insights(user_id)

            # Step 3: Validate and process each insight
            stored_insights = []
            for insight in insights:
                if self._insight_validator:
                    result = self._insight_validator.validate(insight, existing_insights)

                    if not result.is_valid:
                        logger.debug("Insight rejected: %s", result.reason)
                        continue

                    if result.action == "merge":
                        await self._merge_insight(insight, result.target_insight)
                        stored_insights.append(insight)

                    elif result.action == "update":
                        await self._update_insight_with_evolution(insight, result.target_insight)
                        stored_insights.append(insight)

                    elif result.action == "store":
                        await self._store_insight(insight, session_id)
                        stored_insights.append(insight)
                        existing_insights.append(insight)
                else:
                    # No validator, just store
                    await self._store_insight(insight, session_id)
                    stored_insights.append(insight)

            # Step 4: Check consolidation threshold
            if self._memory_consolidator:
                await self._check_and_consolidate(user_id)

            logger.info("Stored %d insights for user %s", len(stored_insights), user_id)
            return stored_insights

        except Exception as e:
            logger.error("Failed to extract and store insights: %s", e)
            return []

    async def _get_user_insights(self, user_id: str) -> List[Insight]:
        """
        Get all insights for a user.

        Sprint 26 FIX: Correctly queries INSIGHT type (not USER_FACT).
        Sprint 27 FIX: Uses get_user_insights() instead of search_similar()
        with zero-vector, which caused NaN in pgvector cosine distance
        (zero vector <=> any vector = NaN, so WHERE clause rejected all rows).
        """
        try:
            # Use dedicated get_user_insights() from InsightRepositoryMixin
            # which queries by memory_type without cosine similarity
            memories = self._repository.get_user_insights(
                user_id=user_id,
                limit=self.MAX_INSIGHTS,
            )

            insights = []
            for mem in memories:
                if mem.metadata.get("insight_category"):
                    try:
                        insight = Insight(
                            id=mem.id,
                            user_id=user_id,
                            content=mem.content,
                            category=InsightCategory(mem.metadata.get("insight_category")),
                            sub_topic=mem.metadata.get("sub_topic"),
                            confidence=mem.metadata.get("confidence", 0.8),
                            source_messages=mem.metadata.get("source_messages", []),
                            created_at=mem.created_at,
                            evolution_notes=mem.metadata.get("evolution_notes", []),
                        )
                        insights.append(insight)
                    except (ValueError, KeyError) as e:
                        logger.debug("Skipping invalid insight: %s", e)

            return insights

        except Exception as e:
            logger.error("Failed to get user insights: %s", e)
            return []

    async def _store_insight(self, insight: Insight, session_id: Optional[str] = None) -> bool:
        """Store a new insight."""
        try:
            # Sprint 27: Use async embedding to avoid blocking event loop
            embeddings = await self._embeddings.aembed_documents([insight.content])
            embedding = embeddings[0]

            memory = SemanticMemoryCreate(
                user_id=insight.user_id,
                content=insight.content,
                embedding=embedding,
                memory_type=MemoryType.INSIGHT,
                importance=insight.confidence,
                metadata=insight.to_metadata(),
                session_id=session_id,
            )

            self._repository.save_memory(memory)
            return True

        except Exception as e:
            logger.error("Failed to store insight: %s", e)
            return False

    async def _merge_insight(self, new_insight: Insight, existing_insight: Insight) -> bool:
        """
        Merge new insight with existing one - metadata only, preserve embedding.

        SOTA Fix: Use explicit update_metadata_only() API instead of
        passing embedding=None to update_fact().
        """
        try:
            new_confidence = (existing_insight.confidence + new_insight.confidence) / 2

            evolution_notes = existing_insight.evolution_notes.copy() if existing_insight.evolution_notes else []
            evolution_notes.append(f"Merged with similar insight: {new_insight.content[:50]}...")

            # SOTA FIX: Use correct API for metadata-only update
            return self._repository.update_metadata_only(
                fact_id=existing_insight.id,
                metadata={
                    **existing_insight.to_metadata(),
                    "confidence": new_confidence,
                    "evolution_notes": evolution_notes,
                },
                user_id=new_insight.user_id,  # Sprint 121 RC-7: defense-in-depth
            )

        except Exception as e:
            logger.error("Failed to merge insight: %s", e)
            return False

    async def _update_insight_with_evolution(self, new_insight: Insight, existing_insight: Insight) -> bool:
        """Update existing insight with evolution note (for contradictions)."""
        try:
            # Sprint 27: Use async embedding to avoid blocking event loop
            embeddings = await self._embeddings.aembed_documents([new_insight.content])
            embedding = embeddings[0]

            evolution_notes = existing_insight.evolution_notes.copy() if existing_insight.evolution_notes else []
            evolution_notes.append(f"Updated from: {existing_insight.content[:50]}...")

            return self._repository.update_fact(
                fact_id=existing_insight.id,
                content=new_insight.content,
                embedding=embedding,
                metadata={
                    **new_insight.to_metadata(),
                    "evolution_notes": evolution_notes,
                },
                user_id=new_insight.user_id,  # Sprint 121 RC-7: defense-in-depth
            )

        except Exception as e:
            logger.error("Failed to update insight with evolution: %s", e)
            return False

    async def enforce_hard_limit(self, user_id: str) -> bool:
        """
        Enforce hard limit of 50 insights.

        **Validates: Requirements 3.1**
        """
        try:
            current_count = self._repository.count_user_memories(
                user_id=user_id,
                memory_type=MemoryType.INSIGHT,
            )

            if current_count <= self.MAX_INSIGHTS:
                return True

            consolidated = await self._check_and_consolidate(user_id)

            if not consolidated:
                await self._fifo_eviction(user_id)

            return True

        except Exception as e:
            logger.error("Failed to enforce hard limit: %s", e)
            return False

    async def _check_and_consolidate(self, user_id: str) -> bool:
        """
        Check insight count and trigger LLM consolidation if threshold exceeded.

        Sprint 26: Wired to MemoryConsolidator (was a placeholder returning False).

        Flow:
        1. Count current insights
        2. If count >= CONSOLIDATION_THRESHOLD (40), fetch all insights
        3. Call MemoryConsolidator.consolidate() (LLM merges/deduplicates)
        4. Delete old insights, store consolidated ones
        5. Return True if consolidation happened
        """
        if not self._memory_consolidator:
            return False

        try:
            current_count = self._repository.count_user_memories(
                user_id=user_id,
                memory_type=MemoryType.INSIGHT,
            )

            should = await self._memory_consolidator.should_consolidate(current_count)
            if not should:
                return False

            logger.info(
                "[CONSOLIDATION] Triggering for user %s: %d insights >= %d",
                user_id, current_count, self.CONSOLIDATION_THRESHOLD
            )

            # Fetch all current insights
            existing_insights = await self._get_user_insights(user_id)
            if not existing_insights:
                return False

            # Run LLM consolidation
            result = await self._memory_consolidator.consolidate(existing_insights)

            if not result.success:
                logger.warning("[CONSOLIDATION] Failed: %s", result.error)
                return False

            # Replace old insights with consolidated ones:
            # 1. Delete all current insights
            deleted = self._repository.delete_oldest_insights(
                user_id, current_count
            )
            logger.info("[CONSOLIDATION] Deleted %d old insights", deleted)

            # 2. Store consolidated insights
            stored = 0
            for insight in result.consolidated_insights:
                insight.user_id = user_id  # Ensure correct user_id
                success = await self._store_insight(insight)
                if success:
                    stored += 1

            logger.info(
                "[CONSOLIDATION] Complete for user %s: %d -> %d insights",
                user_id, result.original_count, stored
            )
            return True

        except Exception as e:
            logger.error("[CONSOLIDATION] Error for user %s: %s", user_id, e)
            return False

    async def _fifo_eviction(self, user_id: str) -> int:
        """
        Evict oldest insights using FIFO.

        Sprint 26 FIX: Previously called delete_oldest_facts() which
        deletes USER_FACT entries. Now correctly calls delete_oldest_insights()
        which deletes INSIGHT entries.
        """
        try:
            current_count = self._repository.count_user_memories(
                user_id=user_id,
                memory_type=MemoryType.INSIGHT,
            )

            if current_count <= self.MAX_INSIGHTS:
                return 0

            excess = current_count - self.MAX_INSIGHTS
            deleted = self._repository.delete_oldest_insights(user_id, excess)

            logger.info("FIFO eviction for user %s: deleted %d insights", user_id, deleted)
            return deleted

        except Exception as e:
            logger.error("FIFO eviction failed: %s", e)
            return 0
