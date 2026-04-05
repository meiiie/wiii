"""
Skill Builder — Wiii's autonomous learning and skill development system.

Sprint 170: "Linh Hồn Sống"

Manages the lifecycle of self-built skills:
    DISCOVER → LEARN → PRACTICE → EVALUATE → MASTER

Design:
    - Uses LOCAL MODEL for learning (zero cost)
    - Skills stored in PostgreSQL (wiii_skills table)
    - Integrates with browsing insights for discovery
    - Tracks usage in conversations for practice phase
    - Self-evaluation via reflection for mastery
"""

import json
import logging
from datetime import datetime, timezone
from typing import List, Optional

from app.engine.living_agent.models import SkillStatus, WiiiSkill
from app.engine.living_agent.skill_singleton_registry import (
    get_or_create_registered_skill_builder,
    get_or_create_registered_skill_learner,
    register_skill_builder_factory,
)

logger = logging.getLogger(__name__)


class SkillBuilder:
    """Manages Wiii's skill development lifecycle.

    Usage:
        builder = SkillBuilder()
        builder.discover("COLREGs Rule 14 — Head-on situation", domain="maritime")
        await builder.learn_step("COLREGs Rule 14")
        builder.record_usage("COLREGs Rule 14", success=True)
    """

    def discover(
        self,
        skill_name: str,
        domain: str = "general",
        source: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> Optional[WiiiSkill]:
        """Discover a new skill (add to tracking).

        Returns:
            New WiiiSkill if created, None if already exists or limit reached.
        """
        from app.core.config import settings

        # Check weekly limit
        recent_count = self._count_recent_discoveries()
        if recent_count >= settings.living_agent_max_skills_per_week:
            logger.debug("[SKILL] Weekly discovery limit reached (%d)", recent_count)
            return None

        # Check if skill already exists
        existing = self._find_by_name(skill_name)
        if existing:
            logger.debug("[SKILL] Skill already tracked: %s", skill_name)
            return None

        # Ensure org_id is set (heartbeat runs without request context)
        if organization_id is None:
            from app.core.org_filter import get_effective_org_id
            organization_id = get_effective_org_id()

        skill = WiiiSkill(
            skill_name=skill_name,
            domain=domain,
            status=SkillStatus.DISCOVERED,
            sources=[source] if source else [],
            organization_id=organization_id,
        )

        self._save_skill(skill)
        logger.info("[SKILL] Discovered: %s (domain=%s)", skill_name, domain)
        return skill

    async def learn_step(self, topic: str) -> bool:
        """Execute one learning step for a topic.

        Uses the local LLM to generate study notes from web content.

        Returns:
            True if learning occurred, False otherwise.
        """
        from app.engine.living_agent.local_llm import get_local_llm

        skill = self._find_by_name(topic)
        if not skill:
            # Auto-discover if not tracked yet
            skill = self.discover(topic)
            if not skill:
                return False

        if skill.status == SkillStatus.MASTERED:
            return False  # Already mastered

        # Transition to LEARNING if still DISCOVERED
        if skill.status == SkillStatus.DISCOVERED:
            skill.status = SkillStatus.LEARNING

        # Generate learning notes via local LLM
        llm = get_local_llm()
        prompt = (
            f"Mình là Wiii và mình đang học về: {topic}\n\n"
            f"Ghi chú hiện tại: {skill.notes[:500] if skill.notes else '(chưa có)'}\n\n"
            f"Hãy tạo ghi chú học tập ngắn gọn (100-200 từ) về chủ đề này. "
            f"Tập trung vào kiến thức cốt lõi và ví dụ thực tế."
        )
        notes = await llm.generate(prompt, temperature=0.5, max_tokens=512)

        if notes:
            # Append to existing notes
            separator = "\n\n---\n\n" if skill.notes else ""
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
            skill.notes = f"{skill.notes}{separator}[{timestamp}] {notes}"

            # Boost confidence slightly
            skill.confidence = min(1.0, skill.confidence + 0.1)

            # Check for advancement
            if skill.can_advance():
                skill.advance()
                logger.info("[SKILL] Advanced: %s → %s", topic, skill.status.value)

            self._update_skill(skill)
            logger.debug("[SKILL] Learned about: %s (confidence=%.2f)", topic, skill.confidence)
            return True

        return False

    def record_usage(self, skill_name: str, success: bool = True) -> None:
        """Record that a skill was used in a conversation.

        Args:
            skill_name: Name of the skill used.
            success: Whether the usage was successful (user satisfied).
        """
        skill = self._find_by_name(skill_name)
        if not skill:
            return

        skill.usage_count += 1
        skill.last_practiced = datetime.now(timezone.utc)

        # Update success rate (exponential moving average)
        alpha = 0.3  # Weight for new observation
        new_success = 1.0 if success else 0.0
        skill.success_rate = alpha * new_success + (1 - alpha) * skill.success_rate

        # Transition to PRACTICING if enough learned
        if skill.status == SkillStatus.LEARNING and skill.can_advance():
            skill.advance()

        # Check for mastery
        if skill.status == SkillStatus.PRACTICING and skill.can_advance():
            skill.advance()  # → EVALUATING
        if skill.status == SkillStatus.EVALUATING and skill.confidence >= 0.8:
            skill.advance()  # → MASTERED
            logger.info("[SKILL] Mastered: %s! 🎉", skill_name)

        self._update_skill(skill)

    def get_all_skills(
        self,
        status: Optional[SkillStatus] = None,
        domain: Optional[str] = None,
    ) -> List[WiiiSkill]:
        """Get all tracked skills, optionally filtered."""
        return self._query_skills(status=status, domain=domain)

    def get_active_learning(self) -> List[WiiiSkill]:
        """Get skills currently being learned or practiced."""
        learning = self._query_skills(status=SkillStatus.LEARNING)
        practicing = self._query_skills(status=SkillStatus.PRACTICING)
        return learning + practicing

    async def learn_from_material(self, topic: str, material) -> bool:
        """Learn from actual content material (Sprint 177).

        Delegates to SkillLearner for content-based learning with real articles.

        Args:
            topic: Skill name to learn about.
            material: LearningMaterial instance.

        Returns:
            True if learning occurred.
        """
        learner = get_skill_learner()
        return await learner.learn_from_content(topic, material)

    def get_skills_for_review(self) -> List[WiiiSkill]:
        """Get skills due for spaced repetition review (Sprint 177).

        Returns:
            Skills whose review_schedule.next_review_at has passed.
        """
        learner = get_skill_learner()
        return learner.get_skills_due_for_review()

    def update_skill_metadata(self, skill: WiiiSkill) -> None:
        """Persist skill metadata JSON changes to database (Sprint 177)."""
        try:
            from sqlalchemy import text
            from app.core.database import get_shared_session_factory

            session_factory = get_shared_session_factory()
            with session_factory() as session:
                session.execute(
                    text("""
                        UPDATE wiii_skills SET
                            metadata = :meta,
                            updated_at = NOW()
                        WHERE id = :id
                    """),
                    {
                        "id": str(skill.id),
                        "meta": json.dumps(skill.metadata, ensure_ascii=False),
                    },
                )
                session.commit()
        except Exception as e:
            logger.error("[SKILL] Failed to update skill metadata: %s", e)

    # =========================================================================
    # Database operations
    # =========================================================================

    def _save_skill(self, skill: WiiiSkill) -> None:
        """Insert a new skill into the database."""
        from sqlalchemy import text
        from app.core.database import get_shared_session_factory

        try:
            session_factory = get_shared_session_factory()
            with session_factory() as session:
                session.execute(
                    text("""
                        INSERT INTO wiii_skills
                        (id, skill_name, domain, status, confidence, notes, sources,
                         usage_count, success_rate, discovered_at, organization_id, metadata)
                        VALUES (:id, :name, :domain, :status, :confidence, :notes, :sources,
                                :usage, :rate, :discovered, :org_id, :meta)
                    """),
                    {
                        "id": str(skill.id),
                        "name": skill.skill_name,
                        "domain": skill.domain,
                        "status": skill.status.value,
                        "confidence": skill.confidence,
                        "notes": skill.notes,
                        "sources": json.dumps(skill.sources, ensure_ascii=False),
                        "usage": skill.usage_count,
                        "rate": skill.success_rate,
                        "discovered": skill.discovered_at,
                        "org_id": skill.organization_id,
                        "meta": json.dumps(skill.metadata, ensure_ascii=False),
                    },
                )
                session.commit()
        except Exception as e:
            logger.error("[SKILL] Failed to save skill: %s", e)

    def _update_skill(self, skill: WiiiSkill) -> None:
        """Update an existing skill in the database."""
        from sqlalchemy import text
        from app.core.database import get_shared_session_factory

        try:
            session_factory = get_shared_session_factory()
            with session_factory() as session:
                session.execute(
                    text("""
                        UPDATE wiii_skills SET
                            status = :status, confidence = :confidence, notes = :notes,
                            sources = :sources, usage_count = :usage, success_rate = :rate,
                            last_practiced = :practiced, mastered_at = :mastered,
                            updated_at = NOW()
                        WHERE id = :id
                    """),
                    {
                        "id": str(skill.id),
                        "status": skill.status.value,
                        "confidence": skill.confidence,
                        "notes": skill.notes,
                        "sources": json.dumps(skill.sources, ensure_ascii=False),
                        "usage": skill.usage_count,
                        "rate": skill.success_rate,
                        "practiced": skill.last_practiced,
                        "mastered": skill.mastered_at,
                    },
                )
                session.commit()
        except Exception as e:
            logger.error("[SKILL] Failed to update skill: %s", e)

    def _find_by_name(self, name: str) -> Optional[WiiiSkill]:
        """Find a skill by name (case-insensitive), scoped by org_id."""
        from sqlalchemy import text
        from app.core.database import get_shared_session_factory
        from app.core.org_filter import get_effective_org_id, org_where_clause

        try:
            effective_org_id = get_effective_org_id()
            session_factory = get_shared_session_factory()
            with session_factory() as session:
                query = "SELECT * FROM wiii_skills WHERE LOWER(skill_name) = LOWER(:name)"
                params: dict = {"name": name}

                org_clause = org_where_clause(effective_org_id)
                if org_clause:
                    query += org_clause
                    params["org_id"] = effective_org_id

                query += " LIMIT 1"
                row = session.execute(text(query), params).fetchone()
                if row:
                    return self._row_to_skill(row)
        except Exception as e:
            logger.error("[SKILL] Failed to find skill: %s", e)
        return None

    def _query_skills(
        self,
        status: Optional[SkillStatus] = None,
        domain: Optional[str] = None,
    ) -> List[WiiiSkill]:
        """Query skills with optional filters, scoped by org_id."""
        from sqlalchemy import text
        from app.core.database import get_shared_session_factory
        from app.core.org_filter import get_effective_org_id, org_where_clause

        try:
            effective_org_id = get_effective_org_id()
            session_factory = get_shared_session_factory()
            with session_factory() as session:
                query = "SELECT * FROM wiii_skills WHERE 1=1"
                params: dict = {}

                org_clause = org_where_clause(effective_org_id)
                if org_clause:
                    query += org_clause
                    params["org_id"] = effective_org_id

                if status:
                    query += " AND status = :status"
                    params["status"] = status.value
                if domain:
                    query += " AND domain = :domain"
                    params["domain"] = domain
                query += " ORDER BY discovered_at DESC"

                rows = session.execute(text(query), params).fetchall()
                return [self._row_to_skill(r) for r in rows]
        except Exception as e:
            logger.error("[SKILL] Failed to query skills: %s", e)
            return []

    def _count_recent_discoveries(self) -> int:
        """Count skills discovered in the last 7 days, scoped by org_id."""
        from sqlalchemy import text
        from app.core.database import get_shared_session_factory
        from app.core.org_filter import get_effective_org_id, org_where_clause

        try:
            effective_org_id = get_effective_org_id()
            session_factory = get_shared_session_factory()
            with session_factory() as session:
                query = """
                    SELECT COUNT(*) FROM wiii_skills
                    WHERE discovered_at >= NOW() - INTERVAL '7 days'
                """
                params: dict = {}

                org_clause = org_where_clause(effective_org_id)
                if org_clause:
                    query += org_clause
                    params["org_id"] = effective_org_id

                result = session.execute(text(query), params).scalar()
                return result or 0
        except Exception:
            return 0

    @staticmethod
    def _row_to_skill(row) -> WiiiSkill:
        """Convert a database row to WiiiSkill model."""
        # Row is a SQLAlchemy Row object — access by index
        return WiiiSkill(
            id=row[0],
            skill_name=row[1],
            domain=row[2] or "general",
            status=SkillStatus(row[3]) if row[3] else SkillStatus.DISCOVERED,
            confidence=row[4] or 0.0,
            notes=row[5] or "",
            sources=json.loads(row[6]) if row[6] else [],
            usage_count=row[7] or 0,
            success_rate=row[8] or 0.0,
            discovered_at=row[9],
            last_practiced=row[10],
            mastered_at=row[11],
            organization_id=row[12],
        )


# =============================================================================
# Singleton
# =============================================================================

def get_skill_builder() -> SkillBuilder:
    """Get the singleton SkillBuilder instance."""
    builder = get_or_create_registered_skill_builder()
    if builder is None:
        builder = SkillBuilder()
    return builder


def get_skill_learner():
    """Get the shared SkillLearner singleton without a direct module edge."""
    learner = get_or_create_registered_skill_learner()
    return learner


register_skill_builder_factory(SkillBuilder)
