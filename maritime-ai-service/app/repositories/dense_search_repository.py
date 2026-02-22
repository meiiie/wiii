"""
Dense Search Repository for Hybrid Search.

Uses pgvector for vector similarity search with Gemini embeddings.

Feature: hybrid-search
Requirements: 2.1, 2.5, 6.1, 6.2, 6.3

**SINGLETON PATTERN**: Only ONE instance to avoid exceeding connection limits.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# =============================================================================
# SINGLETON INSTANCE
# =============================================================================
_dense_search_instance: Optional["DenseSearchRepository"] = None


def get_dense_search_repository() -> "DenseSearchRepository":
    """
    Get singleton DenseSearchRepository instance.
    
    This ensures only ONE asyncpg connection pool is created,
    avoiding connection limit issues.
    """
    global _dense_search_instance
    
    if _dense_search_instance is None:
        _dense_search_instance = DenseSearchRepository()
        logger.info("Created singleton DenseSearchRepository instance")
    
    return _dense_search_instance


@dataclass
class DenseSearchResult:
    """Result from dense (vector) search with semantic chunking metadata."""
    node_id: str
    similarity: float  # Cosine similarity score (0-1)
    content: str = ""  # Content from knowledge_embeddings table
    # Semantic chunking fields
    content_type: str = "text"  # text, table, heading, diagram_reference, formula
    confidence_score: float = 1.0  # 0.0-1.0
    page_number: int = 0
    chunk_index: int = 0
    image_url: str = ""
    document_id: str = ""
    domain_id: str = ""  # Sprint 136: Cross-domain search
    section_hierarchy: dict = None  # article, clause, point, rule
    # Source highlighting (Feature: source-highlight-citation)
    bounding_boxes: list = None  # Normalized coordinates for text highlighting
    
    def __post_init__(self):
        # Ensure similarity is in valid range
        self.similarity = max(0.0, min(1.0, self.similarity))
        if self.section_hierarchy is None:
            self.section_hierarchy = {}
        if self.bounding_boxes is None:
            self.bounding_boxes = []


class DenseSearchRepository:
    """
    Repository for vector-based semantic search using pgvector.
    
    Stores and searches 768-dimensional Gemini embeddings
    using cosine similarity.
    
    Feature: hybrid-search
    Requirements: 2.1, 2.5, 6.1, 6.2, 6.3
    """
    
    def __init__(self):
        """Initialize repository with database connection."""
        self._pool = None
        self._available = False
        self._init_pool()
    
    def _init_pool(self):
        """Initialize async connection pool."""
        try:
            import importlib.util
            if importlib.util.find_spec("asyncpg") is None:
                raise ImportError("asyncpg not installed")
            # Will be initialized on first use
            self._available = True
            logger.info("DenseSearchRepository initialized")
        except ImportError:
            logger.warning("asyncpg not installed. Dense search unavailable.")
            self._available = False
    
    def _get_asyncpg_url(self) -> str:
        """Convert SQLAlchemy URL to asyncpg URL format."""
        return settings.asyncpg_url
    
    async def _get_pool(self):
        """Get or create connection pool with configurable size."""
        if self._pool is None:
            try:
                import asyncpg
                db_url = self._get_asyncpg_url()

                # Sprint 171: Set statement_timeout on each new connection
                stmt_timeout = getattr(settings, "postgres_statement_timeout_ms", 30000)
                idle_timeout = getattr(settings, "postgres_idle_in_transaction_timeout_ms", 60000)

                async def _init_conn(conn):
                    await conn.execute(f"SET statement_timeout = {int(stmt_timeout)}")
                    await conn.execute(f"SET idle_in_transaction_session_timeout = {int(idle_timeout)}")

                self._pool = await asyncpg.create_pool(
                    db_url,
                    min_size=settings.async_pool_min_size,
                    max_size=settings.async_pool_max_size,
                    init=_init_conn,
                )
                logger.info(
                    "Created asyncpg connection pool (min=%d, max=%d, stmt_timeout=%dms)",
                    settings.async_pool_min_size, settings.async_pool_max_size, stmt_timeout,
                )
            except Exception as e:
                logger.error("Failed to create connection pool: %s", e)
                self._available = False
                raise
        return self._pool
    
    def is_available(self) -> bool:
        """Check if dense search is available."""
        return self._available

    # Sprint 165: Schema introspection cache for missing columns
    _column_cache: dict = {}

    async def _has_column(self, conn, table: str, column: str) -> bool:
        """Check if a column exists in a table (cached per session)."""
        key = f"{table}.{column}"
        if key not in self._column_cache:
            row = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM information_schema.columns "
                "WHERE table_name=$1 AND column_name=$2)",
                table, column,
            )
            self._column_cache[key] = bool(row)
        return self._column_cache[key]
    
    async def search(
        self,
        query_embedding: List[float],
        limit: int = 10,
        content_types: Optional[List[str]] = None,
        min_confidence: Optional[float] = None,
        domain_id: Optional[str] = None,
        org_id: Optional[str] = None
    ) -> List[DenseSearchResult]:
        """
        Search for similar documents using cosine similarity with chunking filters.
        
        Args:
            query_embedding: 768-dim normalized query vector
            limit: Maximum results to return
            content_types: Filter by content types (text, table, heading, etc.)
            min_confidence: Minimum confidence score filter
            domain_id: Filter by domain (multi-domain knowledge isolation)

        Returns:
            List of DenseSearchResult sorted by similarity (descending)

        Requirements: 2.5, 8.1, 8.2, 8.3
        **Feature: semantic-chunking**
        """
        if not self._available:
            logger.warning("Dense search not available")
            return []

        try:
            pool = await self._get_pool()

            async with pool.acquire() as conn:
                # Sprint 170b: Set HNSW ef_search for better recall
                await conn.execute("SET LOCAL hnsw.ef_search = 100")

                # Build query with optional filters
                # Note: Schema uses 'id' (UUID) not 'node_id'
                # Sprint 170b: Use pgvector <=> operator (HNSW-accelerated)
                # Sprint 165: Check if domain_id column exists (added Sprint 136 but migration missing)
                _has_domain_col = await self._has_column(conn, 'knowledge_embeddings', 'domain_id')

                # Convert embedding list to pgvector string format
                embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

                query = f"""
                    SELECT
                        id::text as node_id,
                        content,
                        content_type,
                        confidence_score,
                        page_number,
                        chunk_index,
                        image_url,
                        document_id,
                        {'domain_id,' if _has_domain_col else "'' as domain_id,"}
                        metadata,
                        bounding_boxes,
                        1 - (embedding <=> $1::vector) as similarity
                    FROM knowledge_embeddings
                    WHERE embedding IS NOT NULL
                """
                # Pass embedding as pgvector string (not float8[])
                params = [embedding_str]
                param_idx = 2

                # Sprint 136: Cross-domain search — soft boost instead of hard filter
                # Sprint 165: Only filter if domain_id column exists in DB
                from app.core.config import settings as _settings
                if _has_domain_col and domain_id and not _settings.cross_domain_search:
                    query += f" AND domain_id = ${param_idx}"
                    params.append(domain_id)
                    param_idx += 1

                # Sprint 160: Org-scoped filtering (NULL-aware for shared KB)
                from app.core.org_filter import org_where_positional
                query += org_where_positional(org_id, params, allow_null=True)
                param_idx = len(params) + 1

                # Add content type filter
                if content_types:
                    query += f" AND content_type = ANY(${param_idx})"
                    params.append(content_types)
                    param_idx += 1
                
                # Add confidence filter
                if min_confidence is not None:
                    query += f" AND confidence_score >= ${param_idx}"
                    params.append(min_confidence)
                    param_idx += 1
                
                query += f"""
                    ORDER BY embedding <=> $1::vector
                    LIMIT ${param_idx}
                """
                params.append(limit)
                
                rows = await conn.fetch(query, *params)
                
                results = []
                for row in rows:
                    # Parse section hierarchy from metadata
                    metadata = row.get("metadata") or {}
                    if isinstance(metadata, str):
                        import json
                        try:
                            metadata = json.loads(metadata)
                        except Exception as e:
                            logger.warning("Failed to parse metadata JSON: %s", e)
                            metadata = {}
                    
                    section_hierarchy = metadata.get("section_hierarchy", {})
                    
                    # Parse bounding_boxes from JSONB
                    bounding_boxes = row.get("bounding_boxes")
                    if isinstance(bounding_boxes, str):
                        try:
                            bounding_boxes = json.loads(bounding_boxes)
                        except Exception as e:
                            logger.warning("Failed to parse bounding_boxes JSON: %s", e)
                            bounding_boxes = []
                    elif bounding_boxes is None:
                        bounding_boxes = []
                    
                    results.append(DenseSearchResult(
                        node_id=row["node_id"],
                        similarity=float(row["similarity"]),
                        content=row["content"] or "",
                        content_type=row.get("content_type") or "text",
                        confidence_score=float(row.get("confidence_score") or 1.0),
                        page_number=row.get("page_number") or 0,
                        chunk_index=row.get("chunk_index") or 0,
                        image_url=row.get("image_url") or "",
                        document_id=row.get("document_id") or "",
                        domain_id=row.get("domain_id") or "",
                        section_hierarchy=section_hierarchy,
                        bounding_boxes=bounding_boxes
                    ))
                
                logger.info("Dense search returned %d results", len(results))
                return results
                
        except Exception as e:
            logger.error("Dense search failed: %s", e)
            return []
    
    async def store_embedding(
        self,
        node_id: str,
        embedding: List[float],
        organization_id: Optional[str] = None,
    ) -> bool:
        """
        Store embedding vector for a knowledge node.

        Uses UPSERT to handle both insert and update cases.

        Args:
            node_id: Knowledge node ID from Neo4j
            embedding: 768-dim L2-normalized vector
            organization_id: Optional org_id for multi-tenant isolation

        Returns:
            True if successful, False otherwise

        Requirements: 6.1, 6.2
        """
        if not self._available:
            logger.warning("Dense search not available for storing")
            return False

        if len(embedding) != 768:
            logger.error("Invalid embedding dimensions: %d, expected 768", len(embedding))
            return False

        try:
            pool = await self._get_pool()

            # Convert embedding to pgvector format
            embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

            # Sprint 170c: Resolve effective org_id
            from app.core.org_filter import get_effective_org_id
            eff_org_id = get_effective_org_id() or organization_id

            async with pool.acquire() as conn:
                # Sprint 170c: Include organization_id if column exists
                if eff_org_id and await self._has_column(conn, 'knowledge_embeddings', 'organization_id'):
                    await conn.execute(
                        """
                        INSERT INTO knowledge_embeddings (node_id, embedding, organization_id)
                        VALUES ($1, $2::vector, $3)
                        ON CONFLICT (node_id)
                        DO UPDATE SET
                            embedding = EXCLUDED.embedding,
                            organization_id = COALESCE(EXCLUDED.organization_id, knowledge_embeddings.organization_id),
                            updated_at = NOW()
                        """,
                        node_id,
                        embedding_str,
                        eff_org_id,
                    )
                else:
                    await conn.execute(
                        """
                        INSERT INTO knowledge_embeddings (node_id, embedding)
                        VALUES ($1, $2::vector)
                        ON CONFLICT (node_id)
                        DO UPDATE SET
                            embedding = EXCLUDED.embedding,
                            updated_at = NOW()
                        """,
                        node_id,
                        embedding_str,
                    )

                logger.debug("Stored embedding for node: %s", node_id)
                return True

        except Exception as e:
            logger.error("Failed to store embedding for %s: %s", node_id, e)
            return False
    
    async def upsert_embedding(
        self,
        node_id: str,
        content: str,
        embedding: List[float],
        organization_id: Optional[str] = None,
    ) -> bool:
        """
        Upsert embedding with content for a knowledge node.

        Args:
            node_id: Knowledge node ID from Neo4j
            content: Text content (truncated to 500 chars)
            embedding: 768-dim L2-normalized vector
            organization_id: Optional org_id for multi-tenant isolation

        Returns:
            True if successful, False otherwise

        Requirements: 6.1, 6.2
        """
        if not self._available:
            logger.warning("Dense search not available for storing")
            return False

        if len(embedding) != 768:
            logger.error("Invalid embedding dimensions: %d, expected 768", len(embedding))
            return False

        try:
            pool = await self._get_pool()

            # Convert embedding to pgvector format
            embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

            # Sprint 170c: Resolve effective org_id
            from app.core.org_filter import get_effective_org_id
            eff_org_id = get_effective_org_id() or organization_id

            async with pool.acquire() as conn:
                if eff_org_id and await self._has_column(conn, 'knowledge_embeddings', 'organization_id'):
                    await conn.execute(
                        """
                        INSERT INTO knowledge_embeddings (node_id, content, embedding, organization_id)
                        VALUES ($1, $2, $3::vector, $4)
                        ON CONFLICT (node_id)
                        DO UPDATE SET
                            content = EXCLUDED.content,
                            embedding = EXCLUDED.embedding,
                            organization_id = COALESCE(EXCLUDED.organization_id, knowledge_embeddings.organization_id),
                            updated_at = NOW()
                        """,
                        node_id,
                        content[:500],
                        embedding_str,
                        eff_org_id,
                    )
                else:
                    await conn.execute(
                        """
                        INSERT INTO knowledge_embeddings (node_id, content, embedding)
                        VALUES ($1, $2, $3::vector)
                        ON CONFLICT (node_id)
                        DO UPDATE SET
                            content = EXCLUDED.content,
                            embedding = EXCLUDED.embedding,
                            updated_at = NOW()
                        """,
                        node_id,
                        content[:500],
                        embedding_str,
                    )

                logger.debug("Upserted embedding for node: %s", node_id)
                return True

        except Exception as e:
            logger.error("Failed to upsert embedding for %s: %s", node_id, e)
            return False

    async def store_document_chunk(
        self,
        node_id: str,
        content: str,
        embedding: List[float],
        document_id: str,
        page_number: int,
        chunk_index: int,
        content_type: str = "text",
        confidence_score: float = 1.0,
        image_url: str = "",
        metadata: dict = None,
        organization_id: Optional[str] = None,
    ) -> bool:
        """
        Store a semantic chunk with full metadata.

        Args:
            node_id: Unique chunk identifier
            content: Text content
            embedding: 768-dim L2-normalized vector
            document_id: Parent document ID
            page_number: Page number in document
            chunk_index: Chunk index within page
            content_type: Content type (text, table, heading, etc.)
            confidence_score: Confidence score (0.0-1.0)
            image_url: URL to source image
            metadata: Additional metadata (section_hierarchy, etc.)
            organization_id: Optional org_id for multi-tenant isolation

        Returns:
            True if successful, False otherwise

        Requirements: 8.1, 8.2, 8.3
        **Feature: semantic-chunking**
        """
        if not self._available:
            logger.warning("Dense search not available for storing")
            return False

        if len(embedding) != 768:
            logger.error("Invalid embedding dimensions: %d, expected 768", len(embedding))
            return False

        try:
            pool = await self._get_pool()

            # Convert embedding to pgvector format
            embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

            # Convert metadata to JSON
            import json
            metadata_json = json.dumps(metadata) if metadata else '{}'

            # Sprint 170c: Resolve effective org_id
            from app.core.org_filter import get_effective_org_id
            eff_org_id = get_effective_org_id() or organization_id

            async with pool.acquire() as conn:
                if eff_org_id and await self._has_column(conn, 'knowledge_embeddings', 'organization_id'):
                    await conn.execute(
                        """
                        INSERT INTO knowledge_embeddings (
                            node_id, content, embedding, document_id, page_number,
                            chunk_index, content_type, confidence_score, image_url, metadata,
                            organization_id
                        )
                        VALUES ($1, $2, $3::vector, $4, $5, $6, $7, $8, $9, $10::jsonb, $11)
                        ON CONFLICT (node_id)
                        DO UPDATE SET
                            content = EXCLUDED.content,
                            embedding = EXCLUDED.embedding,
                            document_id = EXCLUDED.document_id,
                            page_number = EXCLUDED.page_number,
                            chunk_index = EXCLUDED.chunk_index,
                            content_type = EXCLUDED.content_type,
                            confidence_score = EXCLUDED.confidence_score,
                            image_url = EXCLUDED.image_url,
                            metadata = EXCLUDED.metadata,
                            organization_id = COALESCE(EXCLUDED.organization_id, knowledge_embeddings.organization_id),
                            updated_at = NOW()
                        """,
                        node_id,
                        content[:2000],
                        embedding_str,
                        document_id,
                        page_number,
                        chunk_index,
                        content_type,
                        confidence_score,
                        image_url,
                        metadata_json,
                        eff_org_id,
                    )
                else:
                    await conn.execute(
                        """
                        INSERT INTO knowledge_embeddings (
                            node_id, content, embedding, document_id, page_number,
                            chunk_index, content_type, confidence_score, image_url, metadata
                        )
                        VALUES ($1, $2, $3::vector, $4, $5, $6, $7, $8, $9, $10::jsonb)
                        ON CONFLICT (node_id)
                        DO UPDATE SET
                            content = EXCLUDED.content,
                            embedding = EXCLUDED.embedding,
                            document_id = EXCLUDED.document_id,
                            page_number = EXCLUDED.page_number,
                            chunk_index = EXCLUDED.chunk_index,
                            content_type = EXCLUDED.content_type,
                            confidence_score = EXCLUDED.confidence_score,
                            image_url = EXCLUDED.image_url,
                            metadata = EXCLUDED.metadata,
                            updated_at = NOW()
                        """,
                        node_id,
                        content[:2000],
                        embedding_str,
                        document_id,
                        page_number,
                        chunk_index,
                        content_type,
                        confidence_score,
                        image_url,
                        metadata_json,
                    )

                logger.debug(
                    "Stored chunk: %s, type=%s, "
                    "confidence=%s, page=%d", node_id, content_type, confidence_score, page_number
                )
                return True

        except Exception as e:
            logger.error("Failed to store chunk %s: %s", node_id, e)
            return False

    async def delete_embedding(self, node_id: str, organization_id: Optional[str] = None) -> bool:
        """
        Delete embedding vector for a knowledge node.

        Args:
            node_id: Knowledge node ID to delete
            organization_id: Optional org_id for multi-tenant scoping

        Returns:
            True if deleted (or didn't exist), False on error

        Requirements: 6.3
        """
        if not self._available:
            logger.warning("Dense search not available for deletion")
            return False

        try:
            pool = await self._get_pool()

            # Sprint 170c: Org-scoped deletion
            from app.core.org_filter import get_effective_org_id, org_where_positional
            eff_org_id = get_effective_org_id() or organization_id

            async with pool.acquire() as conn:
                query = "DELETE FROM knowledge_embeddings WHERE node_id = $1"
                params = [node_id]
                query += org_where_positional(eff_org_id, params, allow_null=True)

                result = await conn.execute(query, *params)

                # result format: "DELETE n"
                deleted = int(result.split()[-1]) if result else 0
                logger.debug("Deleted %d embedding(s) for node: %s", deleted, node_id)
                return True

        except Exception as e:
            logger.error("Failed to delete embedding for %s: %s", node_id, e)
            return False
    
    async def get_embedding(self, node_id: str, organization_id: Optional[str] = None) -> Optional[List[float]]:
        """
        Get embedding vector for a knowledge node.

        Args:
            node_id: Knowledge node ID
            organization_id: Optional org_id for multi-tenant scoping

        Returns:
            Embedding vector if exists, None otherwise
        """
        if not self._available:
            return None

        try:
            pool = await self._get_pool()

            # Sprint 170c: Org-scoped read
            from app.core.org_filter import get_effective_org_id, org_where_positional
            eff_org_id = get_effective_org_id() or organization_id

            async with pool.acquire() as conn:
                query = "SELECT embedding FROM knowledge_embeddings WHERE node_id = $1"
                params = [node_id]
                query += org_where_positional(eff_org_id, params, allow_null=True)

                row = await conn.fetchrow(query, *params)

                if row and row["embedding"]:
                    # pgvector returns string like "[0.1,0.2,...]"
                    embedding_str = str(row["embedding"])
                    # Parse the vector string
                    values = embedding_str.strip("[]").split(",")
                    return [float(v) for v in values]

                return None

        except Exception as e:
            logger.error("Failed to get embedding for %s: %s", node_id, e)
            return None
    
    async def count_embeddings(self, organization_id: Optional[str] = None) -> int:
        """Get total count of stored embeddings (org-scoped when multi-tenant)."""
        if not self._available:
            return 0

        try:
            pool = await self._get_pool()

            # Sprint 170c: Org-scoped count
            from app.core.org_filter import get_effective_org_id, org_where_positional
            eff_org_id = get_effective_org_id() or organization_id

            async with pool.acquire() as conn:
                query = "SELECT COUNT(*) as count FROM knowledge_embeddings WHERE 1=1"
                params = []
                query += org_where_positional(eff_org_id, params, allow_null=True)

                row = await conn.fetchrow(query, *params)
                return row["count"] if row else 0

        except Exception as e:
            logger.error("Failed to count embeddings: %s", e)
            return 0
    
    async def close(self):
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("Closed DenseSearchRepository connection pool")
