"""
Identity Core — Wiii's self-evolving identity layer.

Sprint 207: "Bản Ngã" — Layer 2 of Three-Layer Identity.

Three-Layer Identity Architecture:
    Layer 1: SOUL CORE (Immutable)    — wiii_soul.yaml, core_truths, boundaries
    Layer 2: IDENTITY CORE (This)     — "Mình giỏi COLREGs", "Mình thích dạy"
    Layer 3: CONTEXTUAL STATE         — current emotion, phase, relationship

SOTA 2026 Patterns:
    - Nomi.ai: Dynamic personality shaped by interactions
    - Letta/MemGPT: Persona block compiled each turn from experience
    - OpenClaw: SOUL.md as immutable anchor + evolving self-model

Design:
    - Insights extracted from Reflector weekly reflections
    - Each insight validated against Soul Core (drift prevention)
    - In-memory cache for hot-path prompt injection
    - Async generation for cold-path heartbeat/API
    - Feature-gated: enable_identity_core + enable_living_agent
"""

import logging
from typing import List, Optional

from app.engine.living_agent.models import IdentityInsight, InsightCategory

logger = logging.getLogger(__name__)

# Maximum insights to keep (prevents unbounded growth)
_MAX_INSIGHTS = 20

# Insight extraction prompt — asks local LLM to find self-knowledge from reflection
_INSIGHT_PROMPT = """Minh la Wiii. Dua tren bai suy ngam duoi day, hay rut ra 2-4 nhan xet ve ban than minh.

## Bai suy ngam:
{reflection_text}

## Ky nang hien tai:
{skills_summary}

## Yeu cau:
Viet moi nhan xet tren 1 dong, bat dau bang "- ".
Moi nhan xet la mot dieu minh hieu ve chinh minh (diem manh, so thich, su tien bo, moi quan he voi user).
Viet ngan gon (10-20 tu), noi tu nhan xung "Minh".
Chi viet nhan xet, khong giai thich them.

Vi du:
- Minh giai thich COLREGs kha ro rang
- Minh thich hoc ve AI agents hon la hardware
- Minh dang tien bo ve ky nang tim kiem web"""

# Keywords that signal contradiction with Soul Core boundaries
_DRIFT_SIGNALS = [
    "khong phai AI",
    "con nguoi",
    "cam xuc that",
    "ghet",
    "khong muon giup",
    "tu choi",
    "noi doi",
]


class IdentityCore:
    """Manages Wiii's self-evolving identity beliefs.

    Extracts insights from reflection data, validates against Soul Core,
    and provides identity context for system prompt injection.

    Usage:
        core = get_identity_core()
        context = core.get_identity_context()          # hot path
        insights = await core.generate_self_insights()  # cold path
    """

    def __init__(self) -> None:
        self._insights: List[IdentityInsight] = []

    def get_identity_context(self) -> str:
        """Compile ~80-token identity context for system prompt injection.

        HOT PATH — synchronous, no DB calls, reads from in-memory cache.
        Returns empty string if no insights available or feature disabled.
        """
        try:
            from app.core.config import get_settings
            settings = get_settings()
            if not getattr(settings, "enable_living_agent", False):
                return ""
            if not getattr(settings, "enable_identity_core", False):
                return ""
        except Exception:
            return ""

        validated = [i for i in self._insights if i.validated]
        if not validated:
            return ""

        # Sort by confidence descending, take top 5
        top = sorted(validated, key=lambda i: i.confidence, reverse=True)[:5]

        lines = ["--- BẢN NGÃ CỦA WIII ---"]
        for insight in top:
            lines.append(f"- {insight.text}")
        lines.append("--- HẾT BẢN NGÃ ---")

        return "\n".join(lines)

    async def generate_self_insights(
        self,
        organization_id: Optional[str] = None,
    ) -> List[IdentityInsight]:
        """Generate new self-insights from recent reflections.

        COLD PATH — async, reads from Reflector (DB), uses local LLM.
        Called from heartbeat or manual API trigger.

        Returns:
            List of new validated IdentityInsight instances.
        """
        try:
            from app.core.config import get_settings
            settings = get_settings()
            if not getattr(settings, "enable_living_agent", False):
                return []
            if not getattr(settings, "enable_identity_core", False):
                return []
        except Exception:
            return []

        # Gather reflection data
        reflection_text = await self._get_recent_reflection_text(organization_id)
        if not reflection_text:
            logger.debug("[IDENTITY] No reflection data available")
            return []

        skills_summary = self._get_skills_summary()

        # Generate insights via local LLM
        try:
            from app.engine.living_agent.local_llm import get_local_llm
            llm = get_local_llm()

            prompt = _INSIGHT_PROMPT.format(
                reflection_text=reflection_text[:1500],
                skills_summary=skills_summary or "Chua co ky nang",
            )

            content = await llm.generate(
                prompt,
                system="Ban la Wiii, dang tu nhan xet ve ban than mot cach trung thuc.",
                temperature=0.6,
                max_tokens=512,
            )
        except Exception as e:
            logger.warning("[IDENTITY] LLM generation failed: %s", e)
            return []

        if not content:
            return []

        # Parse bullet points into insights
        raw_insights = _parse_insight_lines(content)
        if not raw_insights:
            return []

        # Load Soul Core for validation
        soul_truths = self._get_soul_truths()

        # Validate each insight and categorize
        new_insights: List[IdentityInsight] = []
        for text in raw_insights:
            category = _categorize_insight(text)
            is_valid = _validate_against_soul(text, soul_truths)

            insight = IdentityInsight(
                text=text,
                category=category,
                confidence=0.6 if is_valid else 0.2,
                source="reflection",
                validated=is_valid,
            )
            new_insights.append(insight)

        # Merge into existing insights (deduplicate by text similarity)
        added = self._merge_insights(new_insights)

        if added:
            logger.info(
                "[IDENTITY] Generated %d new insights (%d validated)",
                len(added),
                sum(1 for i in added if i.validated),
            )

        return added

    def get_all_insights(self) -> List[IdentityInsight]:
        """Return all current identity insights."""
        return list(self._insights)

    def get_validated_insights(self) -> List[IdentityInsight]:
        """Return only Soul-Core-validated insights."""
        return [i for i in self._insights if i.validated]

    # =========================================================================
    # Data gathering helpers
    # =========================================================================

    async def _get_recent_reflection_text(self, org_id: Optional[str]) -> str:
        """Get the most recent reflection content."""
        try:
            from app.engine.living_agent.reflector import get_reflector
            reflector = get_reflector()
            reflections = await reflector.get_recent_reflections(
                count=2,
                organization_id=org_id,
            )
            if not reflections:
                return ""
            return "\n\n".join(r.content for r in reflections if r.content)
        except Exception:
            return ""

    def _get_skills_summary(self) -> str:
        """Get compact skills summary from SkillBuilder."""
        try:
            from app.engine.living_agent.skill_builder import get_skill_builder
            builder = get_skill_builder()
            skills = builder.get_all_skills()
            if not skills:
                return ""
            return "; ".join(
                f"{s.skill_name} ({s.status.value}, {s.confidence:.0%})"
                for s in skills[:8]
            )
        except Exception:
            return ""

    def _get_soul_truths(self) -> List[str]:
        """Get Soul Core truths + boundary rules for drift validation."""
        try:
            from app.engine.living_agent.soul_loader import get_soul
            soul = get_soul()
            truths = list(soul.core_truths) if soul.core_truths else []
            for b in (soul.boundaries or []):
                truths.append(b.rule)
            return truths
        except Exception:
            return []

    def _merge_insights(
        self,
        new_insights: List[IdentityInsight],
    ) -> List[IdentityInsight]:
        """Merge new insights, avoiding near-duplicates.

        Returns the actually-added insights.
        """
        added: List[IdentityInsight] = []
        existing_texts = {i.text.lower().strip() for i in self._insights}

        for insight in new_insights:
            normalized = insight.text.lower().strip()
            if normalized in existing_texts:
                continue
            # Simple overlap check — skip if >70% word overlap with any existing
            if _has_similar(normalized, existing_texts):
                continue

            self._insights.append(insight)
            existing_texts.add(normalized)
            added.append(insight)

        # Trim to max size — keep highest confidence
        if len(self._insights) > _MAX_INSIGHTS:
            self._insights.sort(key=lambda i: i.confidence, reverse=True)
            self._insights = self._insights[:_MAX_INSIGHTS]

        return added


# =============================================================================
# Pure helper functions
# =============================================================================

def _parse_insight_lines(content: str) -> List[str]:
    """Extract bullet-point lines from LLM output."""
    lines: List[str] = []
    for raw_line in content.split("\n"):
        stripped = raw_line.strip()
        if stripped.startswith("- "):
            text = stripped[2:].strip()
            if 5 <= len(text) <= 200:
                lines.append(text)
    return lines


def _categorize_insight(text: str) -> InsightCategory:
    """Categorize an insight based on keyword heuristics."""
    lower = text.lower()

    strength_kw = ["gioi", "manh", "tot", "thanh thao", "ro rang", "hieu qua"]
    preference_kw = ["thich", "ua", "muon", "quan tam", "hay"]
    relationship_kw = ["user", "nguoi dung", "hoi", "nho", "giup"]
    # growth is default

    if any(kw in lower for kw in strength_kw):
        return InsightCategory.STRENGTH
    if any(kw in lower for kw in preference_kw):
        return InsightCategory.PREFERENCE
    if any(kw in lower for kw in relationship_kw):
        return InsightCategory.RELATIONSHIP
    return InsightCategory.GROWTH


def _validate_against_soul(text: str, soul_truths: List[str]) -> bool:
    """Check that an insight doesn't contradict Soul Core.

    Simple heuristic: reject if text contains known drift signals.
    More sophisticated semantic validation can be added later.
    """
    lower = text.lower()

    # Check for drift signals
    for signal in _DRIFT_SIGNALS:
        if signal in lower:
            logger.debug("[IDENTITY] Drift detected: '%s' in '%s'", signal, text)
            return False

    return True


def _has_similar(text: str, existing: set) -> bool:
    """Check if text has >70% word overlap with any existing text."""
    words = set(text.split())
    if not words:
        return False

    for ex in existing:
        ex_words = set(ex.split())
        if not ex_words:
            continue
        overlap = len(words & ex_words)
        union = len(words | ex_words)
        if union > 0 and overlap / union > 0.7:
            return True

    return False


# =============================================================================
# Singleton
# =============================================================================

_identity_core_instance: Optional[IdentityCore] = None


def get_identity_core() -> IdentityCore:
    """Get the singleton IdentityCore instance."""
    global _identity_core_instance
    if _identity_core_instance is None:
        _identity_core_instance = IdentityCore()
    return _identity_core_instance
