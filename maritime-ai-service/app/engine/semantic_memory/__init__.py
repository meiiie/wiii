"""
Semantic Memory Module
CHI THI KY THUAT SO 25 - Project Restructure

This module provides semantic memory capabilities for the Wiii.
Refactored from monolithic semantic_memory.py into modular components:

- core.py: SemanticMemoryEngine (Facade)
- context.py: ContextRetriever (context/insights retrieval)
- extraction.py: FactExtractor (fact extraction/storage)
- insight_provider.py: InsightProvider (insight extraction, validation, lifecycle)

Usage:
    from app.engine.semantic_memory import SemanticMemoryEngine
    engine = SemanticMemoryEngine()
"""

from .core import SemanticMemoryEngine, get_semantic_memory_engine
from .context import ContextRetriever
from .extraction import FactExtractor
from .insight_provider import InsightProvider

__all__ = [
    "SemanticMemoryEngine",
    "get_semantic_memory_engine",
    "ContextRetriever",
    "FactExtractor",
    "InsightProvider",
]
