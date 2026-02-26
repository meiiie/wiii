"""
Knowledge Visualization Service — Sprint 191: "Mắt Tri Thức"

Provides 3 core functions:
1. compute_scatter — PCA/t-SNE dimensionality reduction on embeddings
2. compute_knowledge_graph — Document/chunk graph with cross-doc similarity
3. simulate_rag_flow — RAG retrieval simulation with grading

In-memory TTL cache (30 min) keyed by (org_id, function, params).
"""

import hashlib
import json
import logging
import time
from typing import Any, Optional

import numpy as np
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# =============================================================================
# Response Models
# =============================================================================


class ScatterPoint(BaseModel):
    x: float
    y: float
    z: Optional[float] = None
    document_id: str
    document_name: str
    content_preview: str
    content_type: Optional[str] = None
    page_number: Optional[int] = None


class ScatterDocument(BaseModel):
    id: str
    name: str
    color: str


class ScatterResponse(BaseModel):
    points: list[ScatterPoint]
    documents: list[ScatterDocument]
    method: str
    dimensions: int
    computation_ms: int


class KnowledgeGraphNode(BaseModel):
    id: str
    label: str
    node_type: str  # "document" | "chunk"
    document_id: Optional[str] = None
    page_number: Optional[int] = None


class KnowledgeGraphEdge(BaseModel):
    source: str
    target: str
    edge_type: str  # "contains" | "similar_to"
    weight: Optional[float] = None


class KnowledgeGraphResponse(BaseModel):
    nodes: list[KnowledgeGraphNode]
    edges: list[KnowledgeGraphEdge]
    mermaid_code: str
    computation_ms: int


class RagFlowStep(BaseModel):
    name: str
    duration_ms: int
    detail: Optional[str] = None


class RagFlowChunk(BaseModel):
    chunk_id: str
    document_id: str
    document_name: str
    content_preview: str
    page_number: Optional[int] = None
    similarity: float
    grade: str  # "relevant" | "partial" | "irrelevant"
    content_type: Optional[str] = None


class RagFlowResponse(BaseModel):
    query: str
    steps: list[RagFlowStep]
    chunks: list[RagFlowChunk]
    computation_ms: int


# =============================================================================
# Cache — in-memory TTL (30 min)
# =============================================================================

_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_TTL = 1800  # 30 minutes


def _cache_key(org_id: str, func: str, params: dict) -> str:
    raw = f"{org_id}:{func}:{json.dumps(params, sort_keys=True)}"
    return hashlib.md5(raw.encode()).hexdigest()


def _cache_get(key: str) -> Optional[Any]:
    entry = _CACHE.get(key)
    if entry is None:
        return None
    ts, value = entry
    if time.time() - ts > _CACHE_TTL:
        del _CACHE[key]
        return None
    return value


def _cache_set(key: str, value: Any) -> None:
    # Evict expired entries if cache grows large
    if len(_CACHE) > 200:
        now = time.time()
        expired = [k for k, (ts, _) in _CACHE.items() if now - ts > _CACHE_TTL]
        for k in expired:
            del _CACHE[k]
    _CACHE[key] = (time.time(), value)


# =============================================================================
# Color Palette
# =============================================================================

DOC_COLORS = [
    "#3B82F6",  # blue
    "#EF4444",  # red
    "#10B981",  # emerald
    "#F59E0B",  # amber
    "#8B5CF6",  # violet
    "#EC4899",  # pink
    "#06B6D4",  # cyan
    "#F97316",  # orange
    "#14B8A6",  # teal
    "#6366F1",  # indigo
]


# =============================================================================
# Core Functions
# =============================================================================

async def _get_pool():
    from app.core.database import get_asyncpg_pool
    return await get_asyncpg_pool()


async def compute_scatter(
    org_id: str,
    method: str = "pca",
    dimensions: int = 2,
    limit: int = 500,
) -> ScatterResponse:
    """Compute PCA or t-SNE scatter from org embeddings."""
    start = time.time()

    # Check cache
    cache_params = {"method": method, "dimensions": dimensions, "limit": limit}
    key = _cache_key(org_id, "scatter", cache_params)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    pool = await _get_pool()

    # Fetch embeddings with document info
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT ke.id, ke.embedding, ke.document_id, ke.content,
                   ke.content_type, ke.page_number,
                   COALESCE(od.filename, ke.document_id) AS document_name
            FROM knowledge_embeddings ke
            LEFT JOIN organization_documents od
                ON ke.document_id = od.document_id
                AND ke.organization_id = od.organization_id
            WHERE ke.organization_id = $1
            ORDER BY ke.created_at DESC
            LIMIT $2
            """,
            org_id, limit,
        )

    if not rows:
        result = ScatterResponse(
            points=[], documents=[], method=method,
            dimensions=dimensions, computation_ms=0,
        )
        _cache_set(key, result)
        return result

    # Parse embeddings
    embeddings = []
    metadata = []
    for row in rows:
        emb_str = row["embedding"]
        # pgvector returns string like "[0.1,0.2,...]"
        if isinstance(emb_str, str):
            vec = np.fromstring(emb_str.strip("[]"), sep=",")
        else:
            vec = np.array(emb_str)
        if vec.shape[0] > 0:
            embeddings.append(vec)
            metadata.append(dict(row))

    if not embeddings:
        result = ScatterResponse(
            points=[], documents=[], method=method,
            dimensions=dimensions, computation_ms=0,
        )
        _cache_set(key, result)
        return result

    X = np.vstack(embeddings)

    # Auto-fallback: t-SNE on >500 points → PCA
    actual_method = method
    if method == "tsne" and X.shape[0] > 500:
        actual_method = "pca"
        logger.info("t-SNE fallback to PCA: %d points > 500", X.shape[0])

    # t-SNE perplexity must be < n_samples
    if actual_method == "tsne" and X.shape[0] < 5:
        actual_method = "pca"

    # Dimensionality reduction
    if actual_method == "tsne":
        from sklearn.manifold import TSNE
        perplexity = min(30, max(2, X.shape[0] - 1))
        reducer = TSNE(n_components=dimensions, perplexity=perplexity, random_state=42)
        coords = reducer.fit_transform(X)
    else:
        from sklearn.decomposition import PCA
        n_components = min(dimensions, X.shape[0], X.shape[1])
        reducer = PCA(n_components=n_components, random_state=42)
        coords = reducer.fit_transform(X)
        # Pad if fewer components than requested
        if coords.shape[1] < dimensions:
            pad = np.zeros((coords.shape[0], dimensions - coords.shape[1]))
            coords = np.hstack([coords, pad])

    # Build document map for colors
    doc_ids = list(dict.fromkeys(m["document_id"] for m in metadata))
    doc_color_map = {did: DOC_COLORS[i % len(DOC_COLORS)] for i, did in enumerate(doc_ids)}

    # Build points
    points = []
    for i, m in enumerate(metadata):
        content = m.get("content") or ""
        preview = content[:150] + ("..." if len(content) > 150 else "")
        pt = ScatterPoint(
            x=round(float(coords[i, 0]), 4),
            y=round(float(coords[i, 1]), 4),
            z=round(float(coords[i, 2]), 4) if dimensions == 3 else None,
            document_id=m["document_id"],
            document_name=m["document_name"],
            content_preview=preview,
            content_type=m.get("content_type"),
            page_number=m.get("page_number"),
        )
        points.append(pt)

    # Build document list
    doc_name_map = {}
    for m in metadata:
        doc_name_map[m["document_id"]] = m["document_name"]
    documents = [
        ScatterDocument(id=did, name=doc_name_map.get(did, did), color=doc_color_map[did])
        for did in doc_ids
    ]

    elapsed_ms = int((time.time() - start) * 1000)
    result = ScatterResponse(
        points=points, documents=documents,
        method=actual_method, dimensions=dimensions,
        computation_ms=elapsed_ms,
    )
    _cache_set(key, result)
    return result


async def compute_knowledge_graph(
    org_id: str,
    max_nodes: int = 50,
) -> KnowledgeGraphResponse:
    """Build knowledge graph from org documents and chunks. Works without Graph RAG."""
    start = time.time()

    cache_params = {"max_nodes": max_nodes}
    key = _cache_key(org_id, "graph", cache_params)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    pool = await _get_pool()
    nodes: list[KnowledgeGraphNode] = []
    edges: list[KnowledgeGraphEdge] = []

    # Get documents
    async with pool.acquire() as conn:
        doc_rows = await conn.fetch(
            """
            SELECT document_id, filename
            FROM organization_documents
            WHERE organization_id = $1 AND status = 'ready'
            ORDER BY created_at DESC
            """,
            org_id,
        )

    doc_ids = []
    doc_names = {}
    for dr in doc_rows:
        did = dr["document_id"]
        doc_ids.append(did)
        doc_names[did] = dr["filename"]
        nodes.append(KnowledgeGraphNode(
            id=f"doc_{did[:8]}",
            label=dr["filename"][:40],
            node_type="document",
            document_id=did,
        ))

    if not doc_ids:
        result = KnowledgeGraphResponse(
            nodes=[], edges=[], mermaid_code="graph LR\n  empty[Chưa có tài liệu]",
            computation_ms=0,
        )
        _cache_set(key, result)
        return result

    # Top chunks per doc (limited)
    chunk_limit = max(2, max_nodes // max(len(doc_ids), 1))
    async with pool.acquire() as conn:
        chunk_rows = await conn.fetch(
            """
            WITH ranked AS (
                SELECT id, document_id, content, page_number, embedding,
                       ROW_NUMBER() OVER (PARTITION BY document_id ORDER BY confidence_score DESC NULLS LAST, id) AS rn
                FROM knowledge_embeddings
                WHERE organization_id = $1 AND document_id = ANY($2::text[])
            )
            SELECT id, document_id, content, page_number, embedding
            FROM ranked
            WHERE rn <= $3
            ORDER BY document_id, rn
            LIMIT $4
            """,
            org_id, doc_ids, chunk_limit, max_nodes,
        )

    # Add chunk nodes + document→chunk edges
    chunk_embeddings = {}
    for cr in chunk_rows:
        cid = str(cr["id"])
        content = cr["content"] or ""
        short = content[:50] + ("..." if len(content) > 50 else "")
        chunk_node_id = f"chunk_{cid[:8]}"
        nodes.append(KnowledgeGraphNode(
            id=chunk_node_id,
            label=short,
            node_type="chunk",
            document_id=cr["document_id"],
            page_number=cr["page_number"],
        ))
        doc_node_id = f"doc_{cr['document_id'][:8]}"
        edges.append(KnowledgeGraphEdge(
            source=doc_node_id,
            target=chunk_node_id,
            edge_type="contains",
        ))
        # Store embedding for cross-doc similarity
        emb_str = cr["embedding"]
        if isinstance(emb_str, str):
            vec = np.fromstring(emb_str.strip("[]"), sep=",")
        else:
            vec = np.array(emb_str) if emb_str is not None else None
        if vec is not None and vec.shape[0] > 0:
            chunk_embeddings[chunk_node_id] = (vec, cr["document_id"])

    # Cross-doc similarity edges (cosine > 0.85)
    chunk_ids_list = list(chunk_embeddings.keys())
    for i in range(len(chunk_ids_list)):
        for j in range(i + 1, len(chunk_ids_list)):
            cid_a = chunk_ids_list[i]
            cid_b = chunk_ids_list[j]
            vec_a, doc_a = chunk_embeddings[cid_a]
            vec_b, doc_b = chunk_embeddings[cid_b]
            # Only cross-document edges
            if doc_a == doc_b:
                continue
            cos_sim = float(np.dot(vec_a, vec_b) / (np.linalg.norm(vec_a) * np.linalg.norm(vec_b) + 1e-10))
            if cos_sim > 0.85:
                edges.append(KnowledgeGraphEdge(
                    source=cid_a,
                    target=cid_b,
                    edge_type="similar_to",
                    weight=round(cos_sim, 3),
                ))

    # Generate Mermaid syntax
    mermaid_lines = ["graph LR"]
    mermaid_lines.append("  classDef doc fill:#3B82F6,stroke:#1D4ED8,color:#fff")
    mermaid_lines.append("  classDef chunk fill:#F59E0B,stroke:#D97706,color:#fff")
    for n in nodes:
        safe_label = n.label.replace('"', "'").replace("\n", " ")
        if n.node_type == "document":
            mermaid_lines.append(f'  {n.id}["{safe_label}"]:::doc')
        else:
            mermaid_lines.append(f'  {n.id}("{safe_label}"):::chunk')
    for e in edges:
        if e.edge_type == "contains":
            mermaid_lines.append(f"  {e.source} --> {e.target}")
        else:
            w = f"|{e.weight}|" if e.weight else ""
            mermaid_lines.append(f"  {e.source} -.{w}.- {e.target}")

    mermaid_code = "\n".join(mermaid_lines)

    elapsed_ms = int((time.time() - start) * 1000)
    result = KnowledgeGraphResponse(
        nodes=nodes, edges=edges, mermaid_code=mermaid_code,
        computation_ms=elapsed_ms,
    )
    _cache_set(key, result)
    return result


async def simulate_rag_flow(
    org_id: str,
    query: str,
    top_k: int = 10,
) -> RagFlowResponse:
    """Simulate RAG retrieval: embed → search → grade."""
    start = time.time()
    steps: list[RagFlowStep] = []

    # Step 1: Embed query
    t0 = time.time()
    try:
        from app.engine.llm_providers.gemini_embedding import GeminiOptimizedEmbeddings
        embedder = GeminiOptimizedEmbeddings()
        query_embedding = await embedder.aembed_query(query)
    except Exception as e:
        logger.error("Failed to embed query: %s", e)
        return RagFlowResponse(
            query=query, steps=[RagFlowStep(name="Embedding", duration_ms=0, detail=f"Error: {e}")],
            chunks=[], computation_ms=int((time.time() - start) * 1000),
        )
    steps.append(RagFlowStep(name="Embedding", duration_ms=int((time.time() - t0) * 1000),
                              detail=f"{len(query_embedding)} dimensions"))

    # Step 2: Vector search
    t1 = time.time()
    pool = await _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT ke.id, ke.document_id, ke.content, ke.page_number,
                   ke.content_type,
                   COALESCE(od.filename, ke.document_id) AS document_name,
                   1 - (ke.embedding <=> $1::vector) AS similarity
            FROM knowledge_embeddings ke
            LEFT JOIN organization_documents od
                ON ke.document_id = od.document_id
                AND ke.organization_id = od.organization_id
            WHERE ke.organization_id = $2
            ORDER BY ke.embedding <=> $1::vector
            LIMIT $3
            """,
            str(query_embedding), org_id, top_k,
        )
    steps.append(RagFlowStep(name="Retrieval", duration_ms=int((time.time() - t1) * 1000),
                              detail=f"{len(rows)} chunks from vector search"))

    # Step 3: Grade
    t2 = time.time()
    chunks: list[RagFlowChunk] = []
    for row in rows:
        sim = float(row["similarity"]) if row["similarity"] is not None else 0.0
        if sim >= 0.75:
            grade = "relevant"
        elif sim >= 0.60:
            grade = "partial"
        else:
            grade = "irrelevant"

        content = row["content"] or ""
        preview = content[:200] + ("..." if len(content) > 200 else "")
        chunks.append(RagFlowChunk(
            chunk_id=str(row["id"]),
            document_id=row["document_id"],
            document_name=row["document_name"],
            content_preview=preview,
            page_number=row["page_number"],
            similarity=round(sim, 4),
            grade=grade,
            content_type=row.get("content_type"),
        ))
    steps.append(RagFlowStep(name="Grading", duration_ms=int((time.time() - t2) * 1000),
                              detail=f"{sum(1 for c in chunks if c.grade == 'relevant')} relevant, "
                                     f"{sum(1 for c in chunks if c.grade == 'partial')} partial"))

    elapsed_ms = int((time.time() - start) * 1000)
    return RagFlowResponse(
        query=query, steps=steps, chunks=chunks, computation_ms=elapsed_ms,
    )
