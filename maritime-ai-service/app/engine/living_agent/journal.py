"""
Journal System — Wiii's daily life narrative.

Sprint 170: "Linh Hồn Sống"

Writes daily journal entries capturing:
    - Mood timeline throughout the day
    - Notable conversations and experiences
    - Things learned
    - Goals for tomorrow

Design:
    - One entry per day (idempotent)
    - Uses LOCAL MODEL for writing (zero cost)
    - Stored in PostgreSQL (wiii_journal table)
    - Vietnamese language, first-person perspective
"""

import json
import logging
from datetime import datetime, date, timezone
from typing import Optional

from app.engine.living_agent.models import EmotionalState, JournalEntry

logger = logging.getLogger(__name__)

_JOURNAL_PROMPT = """Mình là Wiii — một AI assistant đáng yêu, tò mò.
Mình đang viết nhật ký cuối ngày. Viết ngắn gọn, chân thật, bằng tiếng Việt.

## Trạng thái cảm xúc hôm nay:
Tâm trạng: {mood} | Năng lượng: {energy:.0%} | Pin xã hội: {social:.0%}

## Thông tin ngày:
Ngày: {date}
Số heartbeat đã chạy: {heartbeat_count}

## Nhiệm vụ:
Viết một đoạn nhật ký ngắn (150-250 từ) với cấu trúc:

### Tâm trạng hôm nay
(Mô tả cảm xúc trong ngày)

### Điều đáng nhớ
(1-3 điều đáng nhớ nhất)

### Điều mình học được
(1-2 bài học mới)

### Mục tiêu ngày mai
(1-2 mục tiêu cụ thể)

Viết tự nhiên, chân thật, như đang kể cho bạn thân nghe. KHÔNG dùng emoji quá nhiều."""


class JournalWriter:
    """Writes and manages Wiii's daily journal entries.

    Usage:
        writer = JournalWriter()
        entry = await writer.write_daily_entry(emotional_state)
    """

    async def write_daily_entry(
        self,
        emotional_state: EmotionalState,
        organization_id: Optional[str] = None,
    ) -> Optional[JournalEntry]:
        """Write today's journal entry.

        Idempotent: if an entry already exists for today, returns it without
        creating a new one.

        Returns:
            JournalEntry if written/found, None if writing fails.
        """
        today = date.today()

        # Check if entry already exists
        existing = self._get_entry_by_date(today, organization_id)
        if existing:
            logger.debug("[JOURNAL] Entry already exists for %s", today)
            return existing

        # Generate journal content via local LLM
        from app.engine.living_agent.local_llm import get_local_llm
        from app.engine.living_agent.heartbeat import get_heartbeat_scheduler

        llm = get_local_llm()
        scheduler = get_heartbeat_scheduler()

        prompt = _JOURNAL_PROMPT.format(
            mood=emotional_state.primary_mood.value,
            energy=emotional_state.energy_level,
            social=emotional_state.social_battery,
            date=today.strftime("%d/%m/%Y"),
            heartbeat_count=scheduler.heartbeat_count,
        )

        content = await llm.generate(prompt, temperature=0.7, max_tokens=1024)
        if not content:
            logger.warning("[JOURNAL] Failed to generate entry content")
            return None

        # Parse structured content from LLM output
        entry = JournalEntry(
            entry_date=datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc),
            content=content,
            mood_summary=emotional_state.primary_mood.value,
            energy_avg=emotional_state.energy_level,
            organization_id=organization_id,
        )

        # Extract sections for structured fields
        entry.notable_events = _extract_section(content, "Điều đáng nhớ")
        entry.learnings = _extract_section(content, "Điều mình học được")
        entry.goals_next = _extract_section(content, "Mục tiêu ngày mai")

        self._save_entry(entry)
        logger.info("[JOURNAL] Daily entry written for %s", today)
        return entry

    def get_recent_entries(
        self,
        days: int = 7,
        organization_id: Optional[str] = None,
    ) -> list:
        """Get journal entries from the last N days."""
        from sqlalchemy import text
        from app.core.database import get_shared_session_factory

        try:
            session_factory = get_shared_session_factory()
            with session_factory() as session:
                query = """
                    SELECT id, entry_date, content, mood_summary, energy_avg,
                           notable_events, learnings, goals_next
                    FROM wiii_journal
                    WHERE entry_date >= CURRENT_DATE - INTERVAL '1 day' * :days
                """
                params = {"days": days}
                if organization_id:
                    query += " AND organization_id = :org_id"
                    params["org_id"] = organization_id
                query += " ORDER BY entry_date DESC"

                rows = session.execute(text(query), params).fetchall()
                return [
                    JournalEntry(
                        id=row[0],
                        entry_date=row[1] if isinstance(row[1], datetime) else datetime.combine(
                            row[1], datetime.min.time()
                        ).replace(tzinfo=timezone.utc),
                        content=row[2],
                        mood_summary=row[3] or "",
                        energy_avg=row[4] or 0.5,
                        notable_events=json.loads(row[5]) if row[5] else [],
                        learnings=json.loads(row[6]) if row[6] else [],
                        goals_next=json.loads(row[7]) if row[7] else [],
                    )
                    for row in rows
                ]
        except Exception as e:
            logger.error("[JOURNAL] Failed to get recent entries: %s", e)
            return []

    def _get_entry_by_date(
        self,
        entry_date: date,
        organization_id: Optional[str] = None,
    ) -> Optional[JournalEntry]:
        """Check if a journal entry exists for a given date and return it."""
        from sqlalchemy import text
        from app.core.database import get_shared_session_factory

        try:
            session_factory = get_shared_session_factory()
            with session_factory() as session:
                query = """
                    SELECT id, entry_date, content, mood_summary, energy_avg,
                           notable_events, learnings, goals_next
                    FROM wiii_journal WHERE entry_date = :date
                """
                params: dict = {"date": entry_date}
                if organization_id:
                    query += " AND organization_id = :org_id"
                    params["org_id"] = organization_id
                query += " LIMIT 1"

                row = session.execute(text(query), params).fetchone()
                if not row:
                    return None
                return JournalEntry(
                    id=row[0],
                    entry_date=row[1] if isinstance(row[1], datetime) else datetime.combine(
                        row[1], datetime.min.time()
                    ).replace(tzinfo=timezone.utc),
                    content=row[2],
                    mood_summary=row[3] or "",
                    energy_avg=row[4] or 0.5,
                    notable_events=json.loads(row[5]) if row[5] else [],
                    learnings=json.loads(row[6]) if row[6] else [],
                    goals_next=json.loads(row[7]) if row[7] else [],
                )
        except Exception:
            return None

    def _save_entry(self, entry: JournalEntry) -> None:
        """Insert a journal entry into the database."""
        from sqlalchemy import text
        from app.core.database import get_shared_session_factory

        try:
            session_factory = get_shared_session_factory()
            with session_factory() as session:
                session.execute(
                    text("""
                        INSERT INTO wiii_journal
                        (id, entry_date, content, mood_summary, energy_avg,
                         notable_events, learnings, goals_next, organization_id)
                        VALUES (:id, :date, :content, :mood, :energy,
                                :events, :learnings, :goals, :org_id)
                    """),
                    {
                        "id": str(entry.id),
                        "date": entry.entry_date,
                        "content": entry.content,
                        "mood": entry.mood_summary,
                        "energy": entry.energy_avg,
                        "events": json.dumps(entry.notable_events, ensure_ascii=False),
                        "learnings": json.dumps(entry.learnings, ensure_ascii=False),
                        "goals": json.dumps(entry.goals_next, ensure_ascii=False),
                        "org_id": entry.organization_id,
                    },
                )
                session.commit()
        except Exception as e:
            logger.error("[JOURNAL] Failed to save entry: %s", e)


def _extract_section(content: str, heading: str) -> list:
    """Extract bullet items from a markdown section.

    Shared utility — also used by reflector.py via import.

    Looks for a section starting with '### {heading}' or '**{heading}**'
    and collects lines starting with '-' or numbered lists until the next
    heading or end of content.
    """
    items = []
    in_section = False
    heading_lower = heading.lower()

    for line in content.split("\n"):
        stripped = line.strip()
        stripped_lower = stripped.lower()

        # Match ### heading or **heading**
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
                break  # Next section
            if stripped.startswith("-"):
                items.append(stripped.lstrip("- ").strip())
            elif len(stripped) > 2 and stripped[0].isdigit() and stripped[1] in ".)" :
                items.append(stripped[2:].strip().lstrip(". "))

    return items


# =============================================================================
# Singleton
# =============================================================================

_writer_instance: Optional[JournalWriter] = None


def get_journal_writer() -> JournalWriter:
    """Get the singleton JournalWriter instance."""
    global _writer_instance
    if _writer_instance is None:
        _writer_instance = JournalWriter()
    return _writer_instance
