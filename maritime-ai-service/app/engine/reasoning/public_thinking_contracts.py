"""Contracts for curated public thinking surfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ThinkingBeatKind(str, Enum):
    OBSERVE = "observe"
    INTERPRET = "interpret"
    DOUBT = "doubt"
    DECISION = "decision"
    STRATEGY = "strategy"


class ThinkingToneMode(str, Enum):
    TECHNICAL_RESTRAINED = "technical_restrained"
    ANALYTICAL_COMPANION = "analytical_companion"
    INSTRUCTIONAL_COMPANION = "instructional_companion"
    RELATIONAL_COMPANION = "relational_companion"


@dataclass(slots=True)
class ThinkingBeat:
    kind: ThinkingBeatKind
    text: str
    subject: str = ""


@dataclass(slots=True)
class ThinkingSurfacePlan:
    header_label: str = ""
    header_summary: str = ""
    beats: list[ThinkingBeat] = field(default_factory=list)
    tone_mode: ThinkingToneMode = ThinkingToneMode.RELATIONAL_COMPANION

    def visible_fragments(self) -> list[str]:
        return [beat.text.strip() for beat in self.beats if beat.text and beat.text.strip()]
