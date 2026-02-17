"""
Learning Graph Service
Knowledge Graph Implementation Phase 3

Manages learning relationships between Users, Modules, and Topics.
Orchestrates between Neon (facts) and Neo4j (relationships).

Pattern: MemoriLabs Hybrid Retrieval
"""

import logging
from typing import Optional, Dict, Any

from app.repositories.user_graph_repository import (
    UserGraphRepository,
    get_user_graph_repository
)
from app.repositories.semantic_memory_repository import (
    SemanticMemoryRepository,
    get_semantic_memory_repository
)

logger = logging.getLogger(__name__)


class LearningGraphService:
    """
    Service for managing learning graph relationships.
    
    Bridges Neon (semantic facts) and Neo4j (relationships).
    
    Use Cases:
    - Track what user has studied (STUDIED)
    - Detect knowledge gaps (WEAK_AT)
    - Map module prerequisites (PREREQUISITE)
    """
    
    def __init__(
        self,
        user_graph: Optional[UserGraphRepository] = None,
        semantic_repo: Optional[SemanticMemoryRepository] = None
    ):
        """Initialize with repositories."""
        self._user_graph = user_graph or get_user_graph_repository()
        self._semantic_repo = semantic_repo or get_semantic_memory_repository()
    
    def is_available(self) -> bool:
        """Check if both Neon and Neo4j are available."""
        return self._user_graph.is_available()
    
    # =========================================================================
    # STUDIED RELATIONSHIP
    # =========================================================================
    
    async def record_study_session(
        self,
        user_id: str,
        module_id: str,
        module_title: str,
        progress: float = 0.0
    ) -> bool:
        """
        Record that user studied a module.
        
        Called when user:
        - Asks questions about a module
        - Completes exercises
        - Views module content
        
        Args:
            user_id: User ID from LMS
            module_id: Module identifier
            module_title: Module title
            progress: Progress percentage (0.0 - 1.0)
        """
        if not self._user_graph.is_available():
            logger.warning("[LEARNING GRAPH] Neo4j unavailable, skipping study record")
            return False
        
        try:
            # Ensure module node exists
            self._user_graph.ensure_module_node(
                module_id=module_id,
                title=module_title
            )
            
            # Create/update STUDIED relationship
            success = self._user_graph.mark_studied(
                user_id=user_id,
                module_id=module_id,
                progress=progress
            )
            
            if success:
                logger.info("[LEARNING GRAPH] Recorded: %s studied %s", user_id, module_id)
            
            return success
            
        except Exception as e:
            logger.error("[LEARNING GRAPH] Failed to record study: %s", e)
            return False
    
    async def mark_module_completed(
        self,
        user_id: str,
        module_id: str
    ) -> bool:
        """Mark module as completed by user."""
        if not self._user_graph.is_available():
            return False
        
        return self._user_graph.mark_completed(user_id, module_id)
    
    # =========================================================================
    # WEAK_AT RELATIONSHIP (Knowledge Gaps)
    # =========================================================================
    
    async def detect_and_record_weakness(
        self,
        user_id: str,
        topic_id: str,
        topic_name: str,
        confidence: float = 0.5
    ) -> bool:
        """
        Record a detected knowledge gap.
        
        Called when:
        - User answers incorrectly multiple times
        - User explicitly says they don't understand
        - AI detects confusion in conversation
        
        Args:
            user_id: User ID
            topic_id: Topic identifier (e.g., "colregs_rule_15")
            topic_name: Human-readable topic name
            confidence: How confident we are about the weakness (0-1)
        """
        if not self._user_graph.is_available():
            logger.warning("[LEARNING GRAPH] Neo4j unavailable, skipping weakness record")
            return False
        
        try:
            # Ensure topic node exists
            self._user_graph.ensure_topic_node(
                topic_id=topic_id,
                name=topic_name
            )
            
            # Create/update WEAK_AT relationship
            success = self._user_graph.mark_weak_at(
                user_id=user_id,
                topic_id=topic_id,
                confidence=confidence
            )
            
            if success:
                logger.info(
                    "[LEARNING GRAPH] Knowledge gap: %s weak at %s "
                    "(confidence: %.0f%%)",
                    user_id, topic_name, confidence * 100,
                )
            
            return success
            
        except Exception as e:
            logger.error("[LEARNING GRAPH] Failed to record weakness: %s", e)
            return False
    
    # =========================================================================
    # PREREQUISITE RELATIONSHIP
    # =========================================================================
    
    async def add_module_prerequisite(
        self,
        module_id: str,
        requires_module_id: str
    ) -> bool:
        """
        Add prerequisite relationship between modules.
        
        Example: "Navigation Rules" requires "Basic Seamanship"
        """
        if not self._user_graph.is_available():
            return False
        
        return self._user_graph.add_prerequisite(module_id, requires_module_id)
    
    # =========================================================================
    # QUERY OPERATIONS (Hybrid Retrieval)
    # =========================================================================
    
    async def get_user_learning_context(self, user_id: str) -> Dict[str, Any]:
        """
        Get full learning context for user.
        
        Combines:
        - Learning path from Neo4j
        - Knowledge gaps from Neo4j
        - User facts from Neon
        
        Returns:
            {
                "learning_path": [...],
                "knowledge_gaps": [...],
                "recommendations": [...]
            }
        """
        context = {
            "learning_path": [],
            "knowledge_gaps": [],
            "recommendations": []
        }
        
        if not self._user_graph.is_available():
            return context
        
        try:
            # Get from Neo4j
            context["learning_path"] = self._user_graph.get_learning_path(user_id)
            context["knowledge_gaps"] = self._user_graph.get_knowledge_gaps(user_id)
            
            # Generate recommendations based on gaps
            for gap in context["knowledge_gaps"]:
                context["recommendations"].append(
                    f"Cần ôn tập: {gap.get('topic_name', 'Unknown')}"
                )
            
            logger.debug(
                "[LEARNING GRAPH] Context for %s: "
                "%d modules, "
                "%d gaps",
                user_id, len(context['learning_path']), len(context['knowledge_gaps']),
            )
            
        except Exception as e:
            logger.error("[LEARNING GRAPH] Failed to get context: %s", e)
        
        return context


# ============================================================================
# SINGLETON PATTERN
# ============================================================================

_learning_graph_service: Optional[LearningGraphService] = None


def get_learning_graph_service() -> LearningGraphService:
    """Get or create singleton LearningGraphService instance."""
    global _learning_graph_service
    
    if _learning_graph_service is None:
        _learning_graph_service = LearningGraphService()
    
    return _learning_graph_service
