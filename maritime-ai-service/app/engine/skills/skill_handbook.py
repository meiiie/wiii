"""
Explicit skill handbook for Wiii.

This is a lightweight projection inspired by SkillOrchestra / AgentSkillOS:
- capability tree comes from CapabilityRegistry
- competence/cost come from SkillMetricsTracker + living-agent mastery
- retrieval is query-aware but cheap enough to run at runtime

The handbook is intentionally read-only for now. It gives the rest of the
system one place to ask:
  "What can this tool/skill do, how good is Wiii at it, and what does it cost?"
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from app.engine.skills.capability_registry import ToolCapability, get_capability_registry

_INTENT_ALIAS_MAP = {
    "lookup": {"rag", "knowledge", "retrieval", "legal", "maritime"},
    "learning": {"rag", "learning", "assessment", "character", "knowledge", "analysis"},
    "web_search": {"utility", "web", "news", "legal", "maritime"},
    "product_search": {"product_search", "commerce", "shopping", "product", "comparison", "sourcing", "vision"},
    "personal": {"memory", "relationship", "character"},
    "social": {"relationship", "character", "utility"},
}


@dataclass(frozen=True)
class SkillHandbookEntry:
    """Projected handbook entry for a single tool capability."""

    tool_name: str
    skill_domain: Optional[str]
    selector_category: Optional[str]
    capability_path: tuple[str, ...]
    description: str
    tags: tuple[str, ...]
    execution_mode: str = "single"
    success_rate: float = 0.0
    competence_score: float = 0.0
    mastery_score: float = 0.0
    avg_latency_ms: float = 0.0
    avg_cost_usd: float = 0.0
    invocation_count: int = 0

    def searchable_text(self) -> str:
        return " ".join(
            part for part in (
                self.tool_name,
                self.description,
                " ".join(self.capability_path),
                " ".join(self.tags),
                self.skill_domain or "",
                self.selector_category or "",
            ) if part
        ).strip()

    def tradeoff_summary(self) -> str:
        latency = f"{int(self.avg_latency_ms)}ms" if self.avg_latency_ms > 0 else "latency chưa rõ"
        cost = f"${self.avg_cost_usd:.4f}" if self.avg_cost_usd > 0 else "cost chưa rõ"
        competence = f"{self.competence_score:.2f}"
        return f"competence={competence}, latency={latency}, cost={cost}"

    def prompt_hint(self) -> str:
        path = " > ".join(self.capability_path)
        guidance = self.description.rstrip(".")
        return (
            f"- {self.tool_name}: {guidance}. "
            f"Capability path: {path}. "
            f"Trade-off: {self.tradeoff_summary()}."
        )


class SkillHandbook:
    """Projection layer over capabilities + metrics + mastery."""

    @staticmethod
    def _safe_float(value, default: float = 0.0) -> float:
        try:
            return float(value)
        except Exception:
            return default

    @staticmethod
    def _safe_int(value, default: int = 0) -> int:
        try:
            return int(value)
        except Exception:
            return default

    def _build_entry(self, capability: ToolCapability) -> SkillHandbookEntry:
        success_rate = 0.0
        competence_score = 0.0
        mastery_score = 0.0
        avg_latency_ms = 0.0
        avg_cost_usd = 0.0
        invocation_count = 0

        try:
            from app.engine.skills.skill_metrics import get_skill_metrics_tracker

            metrics = get_skill_metrics_tracker().get_metrics(f"tool:{capability.tool_name}")
            if metrics is not None:
                success_rate = self._safe_float(getattr(metrics, "success_rate", 0.0))
                avg_latency_ms = self._safe_float(getattr(metrics, "avg_latency_ms", 0.0))
                avg_cost_usd = self._safe_float(getattr(metrics, "avg_cost_per_invocation", 0.0))
                invocation_count = self._safe_int(getattr(metrics, "total_invocations", 0))
        except Exception:
            pass

        try:
            from app.engine.skills.skill_tool_bridge import get_mastery_score

            mastery_score = self._safe_float(get_mastery_score(capability.tool_name))
        except Exception:
            mastery_score = 0.0

        competence_score = min(
            1.0,
            (success_rate * 0.65)
            + (mastery_score * 0.25)
            + (min(invocation_count, 20) / 20.0 * 0.10),
        )

        return SkillHandbookEntry(
            tool_name=capability.tool_name,
            skill_domain=capability.skill_domain,
            selector_category=capability.selector_category,
            capability_path=capability.capability_path,
            description=capability.description,
            tags=capability.tags,
            execution_mode=capability.execution_mode,
            success_rate=success_rate,
            competence_score=competence_score,
            mastery_score=mastery_score,
            avg_latency_ms=avg_latency_ms,
            avg_cost_usd=avg_cost_usd,
            invocation_count=invocation_count,
        )

    def get_tool_entry(self, tool_name: str) -> Optional[SkillHandbookEntry]:
        capability = get_capability_registry().get(tool_name)
        if capability is None:
            return None
        return self._build_entry(capability)

    def list_entries(self) -> list[SkillHandbookEntry]:
        registry = get_capability_registry()
        return [
            self._build_entry(capability)
            for capability in registry.all()
        ]

    def suggest_for_query(
        self,
        query: str,
        *,
        intent: Optional[str] = None,
        max_entries: int = 5,
    ) -> list[SkillHandbookEntry]:
        """Retrieve the best matching handbook entries for a query."""

        query_words = {word.strip().lower() for word in (query or "").split() if word.strip()}
        normalized_intent = (intent or "").strip().lower()
        candidates: list[tuple[float, SkillHandbookEntry]] = []

        for entry in self.list_entries():
            if entry.execution_mode == "internal":
                continue
            search_text = entry.searchable_text().lower()
            overlap = sum(1 for word in query_words if word in search_text)
            intent_aliases = _INTENT_ALIAS_MAP.get(normalized_intent, set())
            intent_match = bool(
                normalized_intent
                and (
                    entry.selector_category == normalized_intent
                    or normalized_intent in entry.capability_path
                    or bool(intent_aliases.intersection(entry.capability_path))
                    or (
                        entry.selector_category is not None
                        and entry.selector_category in intent_aliases
                    )
                )
            )
            if overlap <= 0 and not intent_match:
                continue
            score = float(overlap)
            if intent_match:
                score += 1.0
            if normalized_intent and entry.selector_category == normalized_intent:
                score += 2.0
            if normalized_intent and normalized_intent in entry.capability_path:
                score += 1.5
            score += entry.competence_score
            if entry.avg_cost_usd > 0:
                score += 1.0 / (1.0 + entry.avg_cost_usd * 100)
            if entry.avg_latency_ms > 0:
                score += 1.0 / (1.0 + entry.avg_latency_ms / 1000.0)
            candidates.append((score, entry))

        candidates.sort(key=lambda item: item[0], reverse=True)
        return [entry for score, entry in candidates[:max_entries] if score > 0]

    def summarize_for_query(
        self,
        query: str,
        *,
        intent: Optional[str] = None,
        max_entries: int = 3,
    ) -> str:
        """Build a compact capability summary for prompts/telemetry."""

        entries = self.suggest_for_query(query, intent=intent, max_entries=max_entries)
        if not entries:
            return ""
        lines = [
            "Capability handbook phù hợp lúc này:",
            "Chỉ xem đây là định hướng chọn kỹ năng/công cụ, không phải chỉ thị cứng.",
        ]
        for entry in entries:
            lines.append(entry.prompt_hint())
        return "\n".join(lines)


_HANDBOOK = SkillHandbook()


def get_skill_handbook() -> SkillHandbook:
    """Return the shared read-only skill handbook."""

    return _HANDBOOK
