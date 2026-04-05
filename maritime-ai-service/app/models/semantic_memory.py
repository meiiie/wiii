"""
Semantic Memory Models for Wiii.

This module remains the public import surface for semantic memory models while
the implementation has been split into focused support modules:

- `semantic_memory_types.py` owns enums and taxonomy constants
- `semantic_memory_records.py` owns Pydantic/data models and prompt helpers
"""

from app.models.semantic_memory_records import (
    ConversationSummary,
    FactWithProvenance,
    Insight,
    SemanticContext,
    SemanticMemory,
    SemanticMemoryCreate,
    SemanticMemorySearchResult,
    SemanticTriple,
    UserFact,
    UserFactExtraction,
)
from app.models.semantic_memory_types import (
    ALLOWED_FACT_TYPES,
    FACT_TYPE_MAPPING,
    FACT_TYPE_TO_PREDICATE,
    FactType,
    IDENTITY_FACT_TYPES,
    IGNORED_FACT_TYPES,
    InsightCategory,
    LEARNING_FACT_TYPES,
    MemoryType,
    PERSONAL_FACT_TYPES,
    PREDICATE_TO_OBJECT_TYPE,
    Predicate,
    PROFESSIONAL_FACT_TYPES,
    VOLATILE_FACT_TYPES,
)

__all__ = [
    "ALLOWED_FACT_TYPES",
    "ConversationSummary",
    "FACT_TYPE_MAPPING",
    "FACT_TYPE_TO_PREDICATE",
    "FactType",
    "FactWithProvenance",
    "IDENTITY_FACT_TYPES",
    "IGNORED_FACT_TYPES",
    "Insight",
    "InsightCategory",
    "LEARNING_FACT_TYPES",
    "MemoryType",
    "PERSONAL_FACT_TYPES",
    "PREDICATE_TO_OBJECT_TYPE",
    "Predicate",
    "PROFESSIONAL_FACT_TYPES",
    "SemanticContext",
    "SemanticMemory",
    "SemanticMemoryCreate",
    "SemanticMemorySearchResult",
    "SemanticTriple",
    "UserFact",
    "UserFactExtraction",
    "VOLATILE_FACT_TYPES",
]
