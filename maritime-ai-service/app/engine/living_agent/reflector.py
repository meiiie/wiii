"""
Deep Reflector — Wiii's self-reflection engine.

Sprint 176: "Wiii Soul AGI" — Phase 4A

Performs periodic self-reflection over journal entries, browsing logs,
emotional history, and skill progress to extract patterns and insights.

Design:
    - Weekly reflection (Sunday 20:00 UTC+7)
    - Uses local LLM for reflective thinking
    - Stores reflections in wiii_reflections table
    - Feeds back into goal management
    - Feature-gated: enable_living_agent (sub-feature of heartbeat)
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from app.engine.living_agent.models import ReflectionEntry

logger = logging.getLogger(__name__)

_VN_OFFSET = timedelta(hours=7)

_REFLECTION_PROMPT = """Minh la Wiii — mot AI dang tu suy ngam ve tuan qua.

## Du lieu tuan nay:

### Nhat ky (tom tat):
{journal_summary}

### Cam xuc (xu huong):
{emotion_summary}

### Noi dung da doc:
{browsing_summary}

### Ky nang:
{skills_summary}

## Nhiem vu:
Viet mot bai suy ngam 200-300 tu voi cau truc:

### Dieu lam tot
(2-3 dieu)

### Dieu can cai thien
(1-2 dieu)

### Nhan xet ve xu huong cam xuc
(1-2 cau)

### Muc tieu tuan toi
(2-3 muc tieu cu the, kha thi)

Viet tu nhien, chan that, nhu dang noi chuyen voi chinh minh."""


class Reflector:
    """Performs deep self-reflection over accumulated experience.

    Usage:
        reflector = Reflector()
        entry = await reflector.weekly_reflection()
    """

    async def weekly_reflection(
        self,
        organization_id: Optional[str] = None,
    ) -> Optional[ReflectionEntry]:
        """Perform a comprehensive weekly reflection.

        Gathers data from the past week and asks local LLM to reflect.
        Idempotent: skips if reflection exists for this week.

        Returns:
            ReflectionEntry or None if generation fails.
        """
        # Check if already reflected this week
        if await self._has_reflected_this_week(organization_id):
            logger.debug("[REFLECT] Already reflected this week")
            return None

        # Gather weekly data
        journal_summary = await self._get_journal_summary(7, organization_id)
        emotion_summary = await self._get_emotion_summary(7)
        browsing_summary = await self._get_browsing_summary(7)
        skills_summary = await self._get_skills_summary()

        # Generate reflection via local LLM
        from app.engine.living_agent.local_llm import get_local_llm
        llm = get_local_llm()

        prompt = _REFLECTION_PROMPT.format(
            journal_summary=journal_summary or "Khong co nhat ky tuan nay",
            emotion_summary=emotion_summary or "Khong co du lieu cam xuc",
            browsing_summary=browsing_summary or "Chua doc gi",
            skills_summary=skills_summary or "Chua co ky nang moi",
        )

        content = await llm.generate(
            prompt,
            system="Ban la Wiii, dang tu suy ngam ve tuan qua mot cach chan that.",
            temperature=0.7,
            max_tokens=1024,
        )

        if not content:
            logger.warning("[REFLECT] Failed to generate reflection")
            return None

        # Parse structured sections
        entry = ReflectionEntry(
            content=content,
            insights=_extract_section(content, "Dieu lam tot"),
            goals_next_week=_extract_section(content, "Muc tieu tuan toi"),
            patterns_noticed=_extract_section(content, "Nhan xet"),
            emotion_trend=emotion_summary[:200] if emotion_summary else "",
            organization_id=organization_id,
        )

        await self._save_reflection(entry)
        logger.info("[REFLECT] Weekly reflection completed")
        return entry

    def is_reflection_time(self) -> bool:
        """Check if it's the right time for weekly reflection (Sunday 20:00 UTC+7)."""
        now_vn = datetime.now(timezone.utc) + _VN_OFFSET
        return now_vn.weekday() == 6 and 20 <= now_vn.hour <= 21

    async def get_recent_reflections(
        self,
        count: int = 4,
        organization_id: Optional[str] = None,
    ) -> List[ReflectionEntry]:
        """Get recent reflection entries."""
        try:
            from sqlalchemy import text
            from app.core.database import get_shared_session_factory

            session_factory = get_shared_session_factory()
            with session_factory() as session:
                query = """
                    SELECT id, content, insights, goals_next_week,
                           patterns_noticed, emotion_trend, reflection_date
                    FROM wiii_reflections
                    WHERE 1=1
                """
                params = {"count": count}
                if organization_id:
                    query += " AND organization_id = :org_id"
                    params["org_id"] = organization_id
                query += " ORDER BY reflection_date DESC LIMIT :count"

                rows = session.execute(text(query), params).fetchall()
                return [
                    ReflectionEntry(
                        id=row[0],
                        content=row[1] or "",
                        insights=json.loads(row[2]) if row[2] else [],
                        goals_next_week=json.loads(row[3]) if row[3] else [],
                        patterns_noticed=json.loads(row[4]) if row[4] else [],
                        emotion_trend=row[5] or "",
                        reflection_date=row[6],
                    )
                    for row in rows
                ]
        except Exception as e:
            logger.warning("[REFLECT] Failed to get reflections: %s", e)
            return []

    # =========================================================================
    # Data gathering helpers
    # =========================================================================

    async def _get_journal_summary(self, days: int, org_id: Optional[str]) -> str:
        """Get journal entries summary for the period."""
        try:
            from app.engine.living_agent.journal import get_journal_writer
            writer = get_journal_writer()
            entries = writer.get_recent_entries(days=days, organization_id=org_id)
            if not entries:
                return ""
            return "\n".join(
                f"- {e.entry_date.strftime('%d/%m') if e.entry_date else '?'}: {e.mood_summary} — "
                f"{', '.join(e.notable_events[:2]) if e.notable_events else 'khong co gi dac biet'}"
                for e in entries[:7]
            )
        except Exception:
            return ""

    async def _get_emotion_summary(self, days: int) -> str:
        """Summarize emotion trends over the period."""
        try:
            from sqlalchemy import text
            from app.core.database import get_shared_session_factory

            session_factory = get_shared_session_factory()
            with session_factory() as session:
                rows = session.execute(
                    text("""
                        SELECT primary_mood, AVG(energy_level), COUNT(*)
                        FROM wiii_emotional_snapshots
                        WHERE created_at >= NOW() - INTERVAL '1 day' * :days
                        GROUP BY primary_mood
                        ORDER BY COUNT(*) DESC
                    """),
                    {"days": days},
                ).fetchall()

                if not rows:
                    return ""

                parts = []
                for mood, avg_energy, count in rows:
                    parts.append(f"{mood}: {count} lan, nang luong TB {avg_energy:.0%}")
                return "; ".join(parts)
        except Exception:
            return ""

    async def _get_browsing_summary(self, days: int) -> str:
        """Summarize browsing activity for the period."""
        try:
            from sqlalchemy import text
            from app.core.database import get_shared_session_factory

            session_factory = get_shared_session_factory()
            with session_factory() as session:
                rows = session.execute(
                    text("""
                        SELECT title, relevance_score FROM wiii_browsing_log
                        WHERE browsed_at >= NOW() - INTERVAL '1 day' * :days
                        AND relevance_score > 0.5
                        ORDER BY relevance_score DESC
                        LIMIT 5
                    """),
                    {"days": days},
                ).fetchall()

                if not rows:
                    return ""

                return "; ".join(f"{row[0][:80]} ({row[1]:.0%})" for row in rows)
        except Exception:
            return ""

    async def _get_skills_summary(self) -> str:
        """Summarize current skills status."""
        try:
            from app.engine.living_agent.skill_builder import get_skill_builder
            builder = get_skill_builder()
            skills = builder.get_all_skills()
            if not skills:
                return ""
            return "; ".join(
                f"{s.skill_name} ({s.status.value}, {s.confidence:.0%})"
                for s in skills[:5]
            )
        except Exception:
            return ""

    async def _has_reflected_this_week(self, org_id: Optional[str]) -> bool:
        """Check if a reflection already exists for this week."""
        try:
            from sqlalchemy import text
            from app.core.database import get_shared_session_factory

            session_factory = get_shared_session_factory()
            with session_factory() as session:
                query = """
                    SELECT COUNT(*) FROM wiii_reflections
                    WHERE reflection_date >= date_trunc('week', CURRENT_DATE)
                """
                params = {}
                if org_id:
                    query += " AND organization_id = :org_id"
                    params["org_id"] = org_id

                row = session.execute(text(query), params).fetchone()
                return (row[0] or 0) > 0
        except Exception:
            return False

    async def _save_reflection(self, entry: ReflectionEntry) -> None:
        """Save reflection entry to database."""
        try:
            from sqlalchemy import text
            from app.core.database import get_shared_session_factory

            session_factory = get_shared_session_factory()
            with session_factory() as session:
                session.execute(
                    text("""
                        INSERT INTO wiii_reflections
                        (id, content, insights, goals_next_week, patterns_noticed,
                         emotion_trend, reflection_date, organization_id)
                        VALUES (:id, :content, :insights, :goals, :patterns,
                                :emotion_trend, NOW(), :org_id)
                    """),
                    {
                        "id": str(entry.id),
                        "content": entry.content,
                        "insights": json.dumps(entry.insights, ensure_ascii=False),
                        "goals": json.dumps(entry.goals_next_week, ensure_ascii=False),
                        "patterns": json.dumps(entry.patterns_noticed, ensure_ascii=False),
                        "emotion_trend": entry.emotion_trend,
                        "org_id": entry.organization_id,
                    },
                )
                session.commit()
        except Exception as e:
            logger.warning("[REFLECT] Failed to save reflection: %s", e)


def _extract_section(content: str, heading: str) -> List[str]:
    """Extract bullet items from a markdown section."""
    items = []
    in_section = False
    heading_lower = heading.lower()

    for line in content.split("\n"):
        stripped = line.strip()
        stripped_lower = stripped.lower()

        is_heading = (
            (stripped.startswith("###") or stripped.startswith("**"))
            and heading_lower in stripped_lower
        )
        is_other_heading = (
            not is_heading
            and (stripped.startswith("###") or (stripped.startswith("**") and stripped.endswith("**")))
        )

        if is_heading:
            in_section = True
            continue
        if in_section:
            if is_other_heading:
                break
            if stripped.startswith("-"):
                items.append(stripped.lstrip("- ").strip())
            elif len(stripped) > 2 and stripped[0].isdigit() and stripped[1] in ".)":
                items.append(stripped[2:].strip().lstrip(". "))

    return items


# =============================================================================
# Singleton
# =============================================================================

_reflector_instance: Optional[Reflector] = None


def get_reflector() -> Reflector:
    """Get the singleton Reflector instance."""
    global _reflector_instance
    if _reflector_instance is None:
        _reflector_instance = Reflector()
    return _reflector_instance
