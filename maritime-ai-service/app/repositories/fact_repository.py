"""
Fact repository facade for semantic memory.

Keeps the public mixin name stable while delegating concrete behavior to
specialized runtime mixins:
- query runtime: fact lookup, semantic search, deduped retrieval
- mutation runtime: updates, metadata-only changes, eviction
- triple runtime: semantic triple persistence and lookup
"""

from app.repositories.fact_repository_mutation_runtime import (
    FactRepositoryMutationRuntimeMixin,
)
from app.repositories.fact_repository_query_runtime import (
    FactRepositoryQueryRuntimeMixin,
)
from app.repositories.fact_repository_triples import FactRepositoryTripleMixin


class FactRepositoryMixin(
    FactRepositoryQueryRuntimeMixin,
    FactRepositoryMutationRuntimeMixin,
    FactRepositoryTripleMixin,
):
    """
    Compatibility shell for fact-oriented semantic memory operations.

    The host repository keeps session/bootstrap ownership while read, write,
    and triple-specific behavior live in dedicated mixins so this module
    stays small and easier to evolve.
    """

    pass
