"""
Core Memory Block — Letta + Gemini hybrid structured user profile

Sprint 73: Living Memory System

Compiles stored user facts into a structured markdown profile block
that is always injected into every agent's system prompt.

SOTA Reference (Feb 2026):
  - Letta: Core Memory Blocks — structured, always in-context, 2K char limit
  - Gemini: Single structured user_context document with rationale
  - ChatGPT: 4-layer context injection with invisible user profiles

Design:
  - Compiled from DB facts using SemanticMemoryEngine.get_user_facts()
  - Sorted by effective importance (decay-aware)
  - Cached per user_id with configurable TTL, invalidated on fact write
  - Max ~800 tokens — truncation by section priority
  - Returns "" for unknown users (no hallucination)
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings

logger = logging.getLogger(__name__)

# Section labels in Vietnamese (display order)
_SECTION_LABELS: Dict[str, str] = {
    "name": "Tên",
    "age": "Tuổi",
    "location": "Nơi ở",
    "organization": "Tổ chức",
    "role": "Vai trò",
    "level": "Cấp bậc",
    "goal": "Mục tiêu",
    "weakness": "Điểm yếu",
    "strength": "Điểm mạnh",
    "learning_style": "Phong cách học",
    "preference": "Sở thích học",
    "hobby": "Sở thích",
    "interest": "Quan tâm",
    "pronoun_style": "Phong cách giao tiếp",
    "emotion": "Tâm trạng",
    "recent_topic": "Chủ đề gần đây",
}

# Identity fields never show staleness (stable facts)
_IDENTITY_FIELDS = ("name", "age", "location")

# Staleness threshold — facts older than this get age annotation
_STALENESS_DAYS = 7


def _format_age(updated_at: Optional[datetime]) -> str:
    """Format how old a fact is, for staleness indicator.

    Returns empty string for recent facts (<7 days).
    Returns Vietnamese age label for older facts.
    """
    if updated_at is None:
        return ""
    now = datetime.now(timezone.utc)
    # Ensure updated_at is timezone-aware
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    delta = now - updated_at
    days = delta.days
    if days < _STALENESS_DAYS:
        return ""
    if days < 30:
        return f" (cập nhật {days} ngày trước)"
    months = days // 30
    if months < 12:
        return f" (cập nhật {months} tháng trước)"
    return f" (cập nhật {days // 365} năm trước)"

# Section grouping for markdown rendering
_SECTION_GROUPS: List[Tuple[str, List[str]]] = [
    ("Học tập", ["goal", "weakness", "strength", "learning_style", "preference"]),
    ("Cá nhân", ["hobby", "interest", "pronoun_style"]),
    ("Ngữ cảnh", ["emotion", "recent_topic"]),
]


class CoreMemoryBlock:
    """
    Compiles and caches a structured user profile block.

    Thread-safe via simple dict cache with TTL.
    """

    def __init__(self):
        # Sprint 175b: Cache keyed by "org_id:user_id" for multi-tenant isolation
        # (was user_id only → cross-org cache leakage)
        self._cache: Dict[str, Tuple[str, float]] = {}

    def _cache_key(self, user_id: str, org_id: str = "") -> str:
        """Build org-scoped cache key."""
        return f"{org_id}:{user_id}" if org_id else user_id

    def invalidate(self, user_id: str, org_id: str = "") -> None:
        """Invalidate cached profile for a user (call on fact write)."""
        self._cache.pop(self._cache_key(user_id, org_id), None)

    def invalidate_all(self) -> None:
        """Clear all cached profiles."""
        self._cache.clear()

    async def get_block(
        self,
        user_id: str,
        facts_dict: Optional[Dict[str, Any]] = None,
        semantic_memory=None,
    ) -> str:
        """
        Get compiled profile block for a user.

        Args:
            user_id: User ID
            facts_dict: Pre-fetched facts dict (skip DB call if provided)
            semantic_memory: SemanticMemoryEngine for DB fetch

        Returns:
            Markdown profile string, or "" if no facts
        """
        if not settings.enable_core_memory_block:
            return ""

        if not user_id:
            return ""

        # Sprint 175b: Org-scoped cache key to prevent cross-org leakage
        from app.core.org_filter import get_effective_org_id
        org_id = get_effective_org_id() or ""
        cache_key = self._cache_key(user_id, org_id)

        # Check cache
        ttl = settings.core_memory_cache_ttl
        cached = self._cache.get(cache_key)
        if cached is not None:
            block, ts = cached
            if time.time() - ts < ttl:
                return block

        # Fetch facts
        if facts_dict is None:
            if semantic_memory is None:
                return ""
            try:
                facts_dict = await semantic_memory.get_user_facts(user_id)
            except Exception as e:
                logger.warning("[CORE_MEMORY] Failed to fetch facts for %s: %s", user_id, e)
                return ""

        if not facts_dict:
            self._cache[cache_key] = ("", time.time())
            return ""

        # Compile block
        block = self._compile(facts_dict)

        # Truncate if needed
        max_tokens = settings.core_memory_max_tokens
        block = self._truncate(block, max_tokens)

        # Cache
        self._cache[cache_key] = (block, time.time())
        return block

    def _compile(self, facts: Dict[str, Any]) -> str:
        """
        Compile facts dict into structured markdown profile.

        Returns:
            Markdown string like:
            ## Hồ sơ người dùng
            **Tên:** [User] | **Tuổi:** 25 | **Nơi ở:** TP.HCM
            **Vai trò:** Sinh viên | **Cấp bậc:** Đại học
            ...
        """
        lines: List[str] = [
            "## Hồ sơ người dùng (tham khảo nền — KHÔNG bịa đặt nếu thông tin này không khớp cuộc trò chuyện hiện tại)"
        ]

        # Identity line (inline)
        identity_parts = []
        for field in _IDENTITY_FIELDS:
            value = facts.get(field)
            if value:
                label = _SECTION_LABELS.get(field, field)
                identity_parts.append(f"**{label}:** {value}")
        if identity_parts:
            lines.append(" | ".join(identity_parts))

        # Professional line (role + level + org) — with staleness
        prof_parts = []
        for field in ("role", "level", "organization"):
            value = facts.get(field)
            if value:
                label = _SECTION_LABELS.get(field, field)
                age = _format_age(facts.get(f"{field}__updated_at"))
                prof_parts.append(f"**{label}:** {value}{age}")
        if prof_parts:
            lines.append(" | ".join(prof_parts))

        # Grouped sections — with staleness for non-identity fields
        for group_name, fields in _SECTION_GROUPS:
            items = []
            for field in fields:
                value = facts.get(field)
                if value:
                    label = _SECTION_LABELS.get(field, field)
                    age = _format_age(facts.get(f"{field}__updated_at"))
                    items.append(f"- {label}: {value}{age}")
            if items:
                lines.append(f"\n### {group_name}")
                lines.extend(items)

        # If only header, no facts worth showing
        if len(lines) <= 1:
            return ""

        return "\n".join(lines)

    def _truncate(self, block: str, max_tokens: int) -> str:
        """
        Truncate block to approximately max_tokens.

        Simple heuristic: 1 token ≈ 4 chars for Vietnamese.
        Truncation removes sections from bottom up (volatile first).
        """
        max_chars = max_tokens * 4
        if len(block) <= max_chars:
            return block

        # Split into lines and trim from bottom
        lines = block.split("\n")
        while len("\n".join(lines)) > max_chars and len(lines) > 2:
            lines.pop()

        return "\n".join(lines)


# Singleton
_core_memory_block: Optional[CoreMemoryBlock] = None


def get_core_memory_block() -> CoreMemoryBlock:
    """Get or create CoreMemoryBlock singleton."""
    global _core_memory_block
    if _core_memory_block is None:
        _core_memory_block = CoreMemoryBlock()
    return _core_memory_block
