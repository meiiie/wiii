"""MemoryConfig — memory system: core memory, facts, character, emotion."""
from pydantic import BaseModel


class MemoryConfig(BaseModel):
    """Memory system — core memory, facts, character, emotion."""
    enable_core_memory_block: bool = True
    core_memory_max_tokens: int = 800
    core_memory_cache_ttl: int = 300
    max_user_facts: int = 50
    max_injected_facts: int = 5
    fact_injection_min_confidence: float = 0.5
    enable_memory_decay: bool = True
    enable_memory_pruning: bool = True
    enable_semantic_fact_retrieval: bool = True
    fact_retrieval_alpha: float = 0.3
    fact_retrieval_beta: float = 0.5
    fact_retrieval_gamma: float = 0.2
