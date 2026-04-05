"""Cache-generation token for LLM selectability snapshots."""

from __future__ import annotations

_selectability_cache_generation = 0


def get_llm_selectability_cache_generation() -> int:
    return _selectability_cache_generation


def bump_llm_selectability_cache_generation() -> int:
    global _selectability_cache_generation
    _selectability_cache_generation += 1
    return _selectability_cache_generation
