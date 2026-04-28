"""Wiii memory contract helpers.

This module keeps memory layers explicit before prompt construction.  The goal
is small but important: Wiii should distinguish durable user facts from recent
relationship context and from Wiii's own persona, then answer honestly when a
user asks whether Wiii remembers them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

MEMORY_BLOCKS: tuple[str, ...] = (
    "persona",
    "human",
    "relationship",
    "goals",
    "craft",
    "world",
)

FACT_TYPE_TO_BLOCK: dict[str, str] = {
    "name": "human",
    "age": "human",
    "location": "human",
    "organization": "human",
    "role": "human",
    "level": "human",
    "pronoun_style": "human",
    "preference": "human",
    "learning_style": "human",
    "hobby": "human",
    "interest": "human",
    "strength": "human",
    "weakness": "human",
    "emotion": "relationship",
    "recent_topic": "relationship",
    "relationship": "relationship",
    "relationship_note": "relationship",
    "goal": "goals",
    "learning_goal": "goals",
    "project_goal": "goals",
    "craft_note": "craft",
    "world_context": "world",
    "persona": "persona",
}


@dataclass(frozen=True)
class MemoryContractSnapshot:
    """Prompt-ready memory availability snapshot for one turn."""

    has_long_term_memory: bool
    has_recent_context: bool
    active_blocks: tuple[str, ...]

    @property
    def should_claim_recent_memory(self) -> bool:
        """True when Wiii can acknowledge the current thread even without facts."""

        return self.has_recent_context and not self.has_long_term_memory


def classify_fact_type(fact_type: str | None) -> str:
    """Classify a fact type into one Wiii memory block."""

    normalized = str(fact_type or "").strip().lower()
    return FACT_TYPE_TO_BLOCK.get(normalized, "human")


def _iter_fact_types(user_facts: Iterable[Any] | None) -> Iterable[str]:
    for fact in user_facts or []:
        if isinstance(fact, dict):
            yield str(
                fact.get("fact_type")
                or fact.get("type")
                or fact.get("memory_type")
                or ""
            )
            continue

        raw_fact_type = getattr(fact, "fact_type", None)
        if raw_fact_type is not None:
            yield str(getattr(raw_fact_type, "value", raw_fact_type) or "")
            continue

        raw_type = getattr(fact, "type", None)
        if raw_type is not None:
            yield str(raw_type or "")


def build_memory_snapshot(
    *,
    core_memory_block: str | None = None,
    user_facts: Iterable[Any] | None = None,
    recent_conversation: str | None = None,
    conversation_summary: str | None = None,
) -> MemoryContractSnapshot:
    """Build a lightweight availability snapshot for the current turn."""

    active = {"persona"}
    fact_types = list(_iter_fact_types(user_facts))
    for fact_type in fact_types:
        block = classify_fact_type(fact_type)
        if block in MEMORY_BLOCKS:
            active.add(block)

    has_core = bool(str(core_memory_block or "").strip())
    has_facts = bool(fact_types)
    has_recent = bool(
        str(recent_conversation or "").strip()
        or str(conversation_summary or "").strip()
    )
    if has_core or has_facts:
        active.add("human")
    if has_recent:
        active.add("relationship")

    ordered_blocks = tuple(block for block in MEMORY_BLOCKS if block in active)
    return MemoryContractSnapshot(
        has_long_term_memory=has_core or has_facts,
        has_recent_context=has_recent,
        active_blocks=ordered_blocks,
    )


def build_memory_contract_policy_prompt() -> str:
    """Return stable policy text for Wiii memory behavior."""

    return "\n".join(
        [
            "--- WIII MEMORY CONTRACT ---",
            "Keep Wiii memory layers separate:",
            "- persona: Wiii's own identity, voice, and selfhood. Never store user facts here.",
            "- human: durable facts about the user, such as name, role, preferences, and learning style.",
            "- relationship: recent shared context, trust, rhythm, and what just happened in this thread.",
            "- goals: durable user goals, learning goals, and project direction.",
            "- craft: how Wiii should teach, explain, build visuals, and collaborate better.",
            "- world: stable external context that remains useful beyond one turn.",
            "Memory honesty rules:",
            "- Do not invent user facts.",
            "- If long-term facts are absent but recent conversation exists, say Wiii remembers the recent thread instead of claiming it knows nothing about the user.",
            "- If both long-term facts and recent context are absent, say that clearly and invite the user to share what should be remembered.",
            "- When referencing old facts, phrase them as prior memory, not as something the user just said.",
        ]
    )


def build_wiii_memory_contract_prompt(
    *,
    core_memory_block: str | None = None,
    user_facts: Iterable[Any] | None = None,
    recent_conversation: str | None = None,
    conversation_summary: str | None = None,
) -> str:
    """Build the prompt block injected into agent prompts."""

    snapshot = build_memory_snapshot(
        core_memory_block=core_memory_block,
        user_facts=user_facts,
        recent_conversation=recent_conversation,
        conversation_summary=conversation_summary,
    )
    lines = [
        build_memory_contract_policy_prompt(),
        f"Active memory blocks this turn: {', '.join(snapshot.active_blocks)}.",
    ]
    if snapshot.has_long_term_memory:
        lines.append("Long-term memory status: available.")
    elif snapshot.has_recent_context:
        lines.append("Long-term memory status: empty, but recent relationship context is available.")
    else:
        lines.append("Long-term memory status: empty.")

    core = str(core_memory_block or "").strip()
    if core:
        lines.extend(["", "--- CORE MEMORY BLOCK ---", core])

    return "\n".join(lines)
