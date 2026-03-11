"""CacheConfig — semantic cache settings."""
from pydantic import BaseModel


class CacheConfig(BaseModel):
    """Semantic cache settings."""
    enabled: bool = True
    similarity_threshold: float = 0.92
    response_ttl: int = 7200
    retrieval_ttl: int = 1800
    max_entries: int = 10000
    adaptive_ttl: bool = True
