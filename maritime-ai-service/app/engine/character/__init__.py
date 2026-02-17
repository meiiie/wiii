"""
Character Engine — Wiii's Living Character System.

Sprint 93: Self-evolving character architecture inspired by Letta/MemGPT.

Architecture:
    Layer 1 (YAML):  Immutable DNA — core identity, backstory, quirks
    Layer 2 (DB):    Living State — learned lessons, opinions, experiences
    Layer 3 (Tools): Self-editing — AI can update its own living state
"""

from app.engine.character.models import (
    BlockLabel,
    CharacterBlock,
    CharacterBlockCreate,
    CharacterBlockUpdate,
    CharacterExperience,
    CharacterExperienceCreate,
    ExperienceType,
)

__all__ = [
    "BlockLabel",
    "CharacterBlock",
    "CharacterBlockCreate",
    "CharacterBlockUpdate",
    "CharacterExperience",
    "CharacterExperienceCreate",
    "ExperienceType",
]
