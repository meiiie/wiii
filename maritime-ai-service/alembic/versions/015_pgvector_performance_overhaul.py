"""pgvector performance overhaul: vector(768) column, HNSW index, B-tree indexes

Revision ID: 015
Revises: 014
Create Date: 2026-02-22

Sprint 170b: "Nền Tảng Vững" — PostgreSQL Performance Overhaul.

Critical fixes:
1. Enable pgvector extension
2. Convert embedding FLOAT[] → vector(768)
3. Create HNSW index (100-1000x speedup for vector search)
4. Add 7 missing B-tree indexes on frequently queried columns

Idempotent: checks column type and index existence before DDL.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '015'
down_revision = '014'
branch_labels = None
depends_on = None


def _index_exists(index_name: str) -> bool:
    """Check if an index exists."""
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM pg_indexes WHERE indexname = :name)"
        ),
        {"name": index_name},
    )
    return result.scalar()


def _column_type(table: str, column: str) -> str:
    """Get the UDT name of a column (e.g. 'vector', '_float8')."""
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            "SELECT udt_name FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :column"
        ),
        {"table": table, "column": column},
    )
    row = result.fetchone()
    return row[0] if row else ""


def _column_exists(table: str, column: str) -> bool:
    """Check if a column exists in a table."""
    return _column_type(table, column) != ""


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1a. Enable pgvector extension
    # ------------------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ------------------------------------------------------------------
    # 1b. Convert embedding FLOAT[] → vector(768)
    # Only if column is still a native array (udt_name = '_float8')
    # ------------------------------------------------------------------
    col_type = _column_type("knowledge_embeddings", "embedding")
    if col_type != "vector":
        op.execute("""
            ALTER TABLE knowledge_embeddings
              ALTER COLUMN embedding TYPE vector(768)
              USING CASE
                WHEN embedding IS NULL THEN NULL
                WHEN array_length(embedding, 1) = 768 THEN embedding::vector(768)
                ELSE NULL
              END
        """)

    # ------------------------------------------------------------------
    # 1c. HNSW index — THE critical fix (100-1000x speedup)
    # ------------------------------------------------------------------
    if not _index_exists("idx_knowledge_embeddings_hnsw"):
        op.execute("""
            CREATE INDEX idx_knowledge_embeddings_hnsw
              ON knowledge_embeddings
              USING hnsw (embedding vector_cosine_ops)
              WITH (m = 16, ef_construction = 128)
        """)

    # ------------------------------------------------------------------
    # 1d. Missing B-tree indexes on user_id columns
    # ------------------------------------------------------------------
    btree_indexes = [
        ("idx_chat_messages_user_id", "chat_messages", ["user_id"]),
        ("idx_character_blocks_user_id", "wiii_character_blocks", ["user_id"]),
        ("idx_semantic_memories_user_id", "semantic_memories", ["user_id"]),
        ("idx_chat_history_user_id", "chat_history", ["user_id"]),
        ("idx_experiences_user_id", "wiii_experiences", ["user_id"]),
    ]
    for idx_name, table, columns in btree_indexes:
        # Only create index if the table and column actually exist
        if not _index_exists(idx_name) and _column_exists(table, columns[0]):
            op.create_index(idx_name, table, columns)

    # ------------------------------------------------------------------
    # 1e. Composite indexes for org-filtered and user+label queries
    # ------------------------------------------------------------------
    composite_indexes = [
        ("idx_knowledge_embeddings_org_domain", "knowledge_embeddings", ["organization_id", "domain_id"]),
        ("idx_character_blocks_user_label", "wiii_character_blocks", ["user_id", "label"]),
    ]
    for idx_name, table, columns in composite_indexes:
        # Only create if all columns exist
        if not _index_exists(idx_name) and all(_column_exists(table, c) for c in columns):
            op.create_index(idx_name, table, columns)


def downgrade() -> None:
    # Drop indexes in reverse order
    indexes_to_drop = [
        ("idx_character_blocks_user_label", "wiii_character_blocks"),
        ("idx_knowledge_embeddings_org_domain", "knowledge_embeddings"),
        ("idx_experiences_user_id", "wiii_experiences"),
        ("idx_chat_history_user_id", "chat_history"),
        ("idx_semantic_memories_user_id", "semantic_memories"),
        ("idx_character_blocks_user_id", "wiii_character_blocks"),
        ("idx_chat_messages_user_id", "chat_messages"),
        ("idx_knowledge_embeddings_hnsw", "knowledge_embeddings"),
    ]
    for idx_name, table in indexes_to_drop:
        if _index_exists(idx_name):
            op.drop_index(idx_name, table_name=table)

    # Revert vector(768) → FLOAT[] if currently vector
    col_type = _column_type("knowledge_embeddings", "embedding")
    if col_type == "vector":
        op.execute("""
            ALTER TABLE knowledge_embeddings
              ALTER COLUMN embedding TYPE float8[]
              USING embedding::float8[]
        """)
