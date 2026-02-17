"""
Memory Updater — Mem0-style ADD/UPDATE/DELETE/NOOP pipeline

Sprint 73: Living Memory System

Two-phase update pipeline replacing simple upsert:
  Phase 1: CLASSIFY — determine action (ADD/UPDATE/DELETE/NOOP)
  Phase 2: EXECUTE — apply action with revision tracking

SOTA Reference (Feb 2026):
  - Mem0: Two-phase extract→evaluate pipeline with revision history
  - OpenClaw: Conflict resolution with explicit ADD/UPDATE/DELETE/NOOP
  - LangMem: Semantic dedup with contradiction detection
"""

import json
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MemoryAction(str, Enum):
    """Actions for memory updates."""
    ADD = "add"         # New fact, no existing match
    UPDATE = "update"   # Same type, different value → replace + track revision
    DELETE = "delete"    # Contradicted/invalidated
    NOOP = "noop"       # Already known, identical


class MemoryDecision:
    """Result of classifying a fact against existing memory."""

    __slots__ = ("action", "fact_type", "new_value", "old_value", "confidence", "reason")

    def __init__(
        self,
        action: MemoryAction,
        fact_type: str,
        new_value: str,
        old_value: Optional[str] = None,
        confidence: float = 1.0,
        reason: str = "",
    ):
        self.action = action
        self.fact_type = fact_type
        self.new_value = new_value
        self.old_value = old_value
        self.confidence = confidence
        self.reason = reason

    def __repr__(self) -> str:
        return f"MemoryDecision({self.action.value}, {self.fact_type}={self.new_value!r})"


# Negation patterns in Vietnamese
_NEGATION_PATTERNS = [
    "không còn", "không phải", "hết rồi", "bỏ rồi",
    "không nữa", "thôi rồi", "đã bỏ", "không làm",
]


class MemoryUpdater:
    """
    Mem0-style memory update pipeline.

    Classifies each extracted fact into ADD/UPDATE/DELETE/NOOP,
    then executes with revision tracking in metadata JSONB.
    """

    def __init__(self, similarity_threshold: float = 0.92):
        """
        Args:
            similarity_threshold: Cosine similarity above which facts are
                considered semantically identical (NOOP).
        """
        self._sim_threshold = similarity_threshold

    def classify(
        self,
        fact_type: str,
        new_value: str,
        existing_facts: Dict[str, Any],
        confidence: float = 0.9,
    ) -> MemoryDecision:
        """
        Classify a single fact against existing memory.

        Rule-based decision (no LLM needed for common cases):
          1. Same fact_type not in existing → ADD
          2. Same fact_type + identical value → NOOP
          3. Same fact_type + different value → UPDATE
          4. Negation pattern in new_value → DELETE

        Args:
            fact_type: Fact type string (e.g. "name", "role")
            new_value: Newly extracted value
            existing_facts: Dict of existing facts {type: value}
            confidence: Extraction confidence

        Returns:
            MemoryDecision
        """
        new_value_clean = new_value.strip()

        # Check for negation (DELETE)
        if self._is_negation(new_value_clean):
            if fact_type in existing_facts:
                return MemoryDecision(
                    action=MemoryAction.DELETE,
                    fact_type=fact_type,
                    new_value=new_value_clean,
                    old_value=existing_facts[fact_type],
                    confidence=confidence,
                    reason="Negation detected",
                )
            # Negation for non-existing fact → NOOP
            return MemoryDecision(
                action=MemoryAction.NOOP,
                fact_type=fact_type,
                new_value=new_value_clean,
                confidence=confidence,
                reason="Negation for non-existing fact",
            )

        old_value = existing_facts.get(fact_type)

        if old_value is None:
            # New fact type → ADD
            return MemoryDecision(
                action=MemoryAction.ADD,
                fact_type=fact_type,
                new_value=new_value_clean,
                confidence=confidence,
                reason="New fact type",
            )

        # Same type exists — compare values
        if self._values_match(str(old_value), new_value_clean):
            return MemoryDecision(
                action=MemoryAction.NOOP,
                fact_type=fact_type,
                new_value=new_value_clean,
                old_value=str(old_value),
                confidence=confidence,
                reason="Identical value",
            )

        # Different value → UPDATE
        return MemoryDecision(
            action=MemoryAction.UPDATE,
            fact_type=fact_type,
            new_value=new_value_clean,
            old_value=str(old_value),
            confidence=confidence,
            reason="Value changed",
        )

    def classify_batch(
        self,
        extracted_facts: List[Dict[str, Any]],
        existing_facts: Dict[str, Any],
    ) -> List[MemoryDecision]:
        """
        Classify a batch of extracted facts.

        Args:
            extracted_facts: List of {"fact_type": str, "value": str, "confidence": float}
            existing_facts: Dict of existing facts {type: value}

        Returns:
            List of MemoryDecisions
        """
        decisions = []
        for fact in extracted_facts:
            decision = self.classify(
                fact_type=fact.get("fact_type", ""),
                new_value=fact.get("value", ""),
                existing_facts=existing_facts,
                confidence=fact.get("confidence", 0.9),
            )
            decisions.append(decision)
        return decisions

    def build_revision_metadata(
        self,
        decision: MemoryDecision,
        existing_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Build metadata dict with revision tracking.

        For UPDATE actions, appends to revision_history.
        For ADD actions, initializes first_seen.

        Args:
            decision: Classification result
            existing_metadata: Current metadata from DB row

        Returns:
            Updated metadata dict for JSONB storage
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        meta = dict(existing_metadata) if existing_metadata else {}

        meta["fact_type"] = decision.fact_type
        meta["confidence"] = decision.confidence

        if decision.action == MemoryAction.ADD:
            meta["first_seen"] = now_iso
            meta["access_count"] = 0
            meta.setdefault("revision_history", [])

        elif decision.action == MemoryAction.UPDATE:
            # Track revision
            history = meta.get("revision_history", [])
            if isinstance(history, str):
                try:
                    history = json.loads(history)
                except (json.JSONDecodeError, TypeError):
                    history = []
            history.append({
                "old": decision.old_value,
                "new": decision.new_value,
                "at": now_iso,
            })
            meta["revision_history"] = history
            # Preserve first_seen
            meta.setdefault("first_seen", now_iso)

        return meta

    def summarize_changes(self, decisions: List[MemoryDecision]) -> str:
        """
        Create a Vietnamese summary of memory changes for the response.

        Returns:
            Summary string like "Đã ghi nhớ: tên Minh. Cập nhật: từ SG → HN."
            Or "" if no actionable changes.
        """
        added = [d for d in decisions if d.action == MemoryAction.ADD]
        updated = [d for d in decisions if d.action == MemoryAction.UPDATE]
        deleted = [d for d in decisions if d.action == MemoryAction.DELETE]

        parts = []

        if added:
            items = ", ".join(f"{d.fact_type}: {d.new_value}" for d in added[:5])
            parts.append(f"Đã ghi nhớ: {items}")

        if updated:
            items = []
            for d in updated[:3]:
                items.append(f"{d.fact_type}: {d.old_value} → {d.new_value}")
            parts.append(f"Đã cập nhật: {', '.join(items)}")

        if deleted:
            items = ", ".join(f"{d.fact_type}" for d in deleted[:3])
            parts.append(f"Đã xóa: {items}")

        return ". ".join(parts)

    def _is_negation(self, value: str) -> bool:
        """Check if value contains negation patterns."""
        value_lower = value.lower()
        return any(pattern in value_lower for pattern in _NEGATION_PATTERNS)

    def _values_match(self, old_value: str, new_value: str) -> bool:
        """
        Check if two values are semantically identical.

        Uses normalized string comparison (case-insensitive, stripped).
        For more complex matching, could add embedding similarity.
        """
        return old_value.strip().lower() == new_value.strip().lower()
