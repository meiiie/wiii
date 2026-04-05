"""
Semantic memory enums and constants.

Extracted from app.models.semantic_memory so the public module can remain a
stable compatibility facade while this file owns the memory type taxonomy.
"""

from enum import Enum


class MemoryType(str, Enum):
    """Types of semantic memories."""

    MESSAGE = "message"
    SUMMARY = "summary"
    RUNNING_SUMMARY = "running_summary"
    USER_FACT = "user_fact"
    INSIGHT = "insight"
    IMAGE_MEMORY = "image_memory"
    EPISODE = "episode"


class InsightCategory(str, Enum):
    """Categories for behavioral insights."""

    LEARNING_STYLE = "learning_style"
    KNOWLEDGE_GAP = "knowledge_gap"
    GOAL_EVOLUTION = "goal_evolution"
    HABIT = "habit"
    PREFERENCE = "preference"


class FactType(str, Enum):
    """
    Types of user facts that can be extracted.

    v0.6 Update:
    - Expanded for richer user profiles
    - Volatile types decay fast via importance_decay
    """

    NAME = "name"
    AGE = "age"
    HOMETOWN = "hometown"
    ROLE = "role"
    LEVEL = "level"
    LOCATION = "location"
    ORGANIZATION = "organization"
    GOAL = "goal"
    PREFERENCE = "preference"
    WEAKNESS = "weakness"
    STRENGTH = "strength"
    LEARNING_STYLE = "learning_style"
    HOBBY = "hobby"
    INTEREST = "interest"
    PRONOUN_STYLE = "pronoun_style"
    EMOTION = "emotion"
    RECENT_TOPIC = "recent_topic"
    BACKGROUND = "background"
    WEAK_AREA = "weak_area"
    STRONG_AREA = "strong_area"


ALLOWED_FACT_TYPES = {
    "name",
    "age",
    "hometown",
    "role",
    "level",
    "location",
    "organization",
    "goal",
    "preference",
    "weakness",
    "strength",
    "learning_style",
    "hobby",
    "interest",
    "emotion",
    "recent_topic",
    "pronoun_style",
}

FACT_TYPE_MAPPING = {
    "background": "role",
    "weak_area": "weakness",
    "strong_area": "strength",
}

IGNORED_FACT_TYPES: set = set()

IDENTITY_FACT_TYPES = {"name", "age", "hometown"}
PROFESSIONAL_FACT_TYPES = {"role", "level", "location", "organization"}
LEARNING_FACT_TYPES = {"goal", "preference", "weakness", "strength", "learning_style"}
PERSONAL_FACT_TYPES = {"hobby", "interest", "pronoun_style"}
VOLATILE_FACT_TYPES = {"emotion", "recent_topic"}


class Predicate(str, Enum):
    """Predicate types for semantic triples."""

    HAS_NAME = "has_name"
    HAS_AGE = "has_age"
    HAS_HOMETOWN = "has_hometown"
    HAS_ROLE = "has_role"
    HAS_LEVEL = "has_level"
    LOCATED_AT = "located_at"
    BELONGS_TO = "belongs_to"
    HAS_GOAL = "has_goal"
    PREFERS = "prefers"
    WEAK_AT = "weak_at"
    STRONG_AT = "strong_at"
    LEARNS_VIA = "learns_via"
    HAS_HOBBY = "has_hobby"
    INTERESTED_IN = "interested_in"
    HAS_PRONOUN_STYLE = "has_pronoun_style"
    FEELS = "feels"
    RECENTLY_DISCUSSED = "recently_discussed"
    STUDIED = "studied"
    COMPLETED = "completed"


FACT_TYPE_TO_PREDICATE = {
    "name": Predicate.HAS_NAME,
    "age": Predicate.HAS_AGE,
    "hometown": Predicate.HAS_HOMETOWN,
    "role": Predicate.HAS_ROLE,
    "level": Predicate.HAS_LEVEL,
    "location": Predicate.LOCATED_AT,
    "organization": Predicate.BELONGS_TO,
    "goal": Predicate.HAS_GOAL,
    "preference": Predicate.PREFERS,
    "weakness": Predicate.WEAK_AT,
    "strength": Predicate.STRONG_AT,
    "learning_style": Predicate.LEARNS_VIA,
    "hobby": Predicate.HAS_HOBBY,
    "interest": Predicate.INTERESTED_IN,
    "pronoun_style": Predicate.HAS_PRONOUN_STYLE,
    "emotion": Predicate.FEELS,
    "recent_topic": Predicate.RECENTLY_DISCUSSED,
    "background": Predicate.HAS_ROLE,
    "weak_area": Predicate.WEAK_AT,
    "strong_area": Predicate.STRONG_AT,
}

PREDICATE_TO_OBJECT_TYPE = {
    Predicate.HAS_NAME: "identity",
    Predicate.HAS_AGE: "identity",
    Predicate.HAS_HOMETOWN: "identity",
    Predicate.HAS_ROLE: "identity",
    Predicate.HAS_LEVEL: "identity",
    Predicate.LOCATED_AT: "professional",
    Predicate.BELONGS_TO: "professional",
    Predicate.HAS_GOAL: "learning",
    Predicate.PREFERS: "learning",
    Predicate.WEAK_AT: "learning",
    Predicate.STRONG_AT: "learning",
    Predicate.LEARNS_VIA: "learning",
    Predicate.HAS_HOBBY: "personal",
    Predicate.INTERESTED_IN: "personal",
    Predicate.HAS_PRONOUN_STYLE: "personal",
    Predicate.FEELS: "volatile",
    Predicate.RECENTLY_DISCUSSED: "volatile",
    Predicate.STUDIED: "progress",
    Predicate.COMPLETED: "progress",
}


__all__ = [
    "ALLOWED_FACT_TYPES",
    "FACT_TYPE_MAPPING",
    "FACT_TYPE_TO_PREDICATE",
    "FactType",
    "IDENTITY_FACT_TYPES",
    "IGNORED_FACT_TYPES",
    "InsightCategory",
    "LEARNING_FACT_TYPES",
    "MemoryType",
    "PERSONAL_FACT_TYPES",
    "PREDICATE_TO_OBJECT_TYPE",
    "Predicate",
    "PROFESSIONAL_FACT_TYPES",
    "VOLATILE_FACT_TYPES",
]
