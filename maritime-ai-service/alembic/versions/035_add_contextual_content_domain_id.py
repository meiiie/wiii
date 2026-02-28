"""Add contextual_content and domain_id columns to knowledge_embeddings.

These columns were added directly via ALTER TABLE during the multimodal RAG
audit but need a proper migration for reproducible deployments.

- contextual_content: stores context-enriched text for retrieval augmentation
- domain_id: tracks which domain plugin produced the embedding (org isolation)

Revision ID: 035
Revises: 034
"""
from alembic import op


# revision identifiers
revision = "035"
down_revision = "034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE knowledge_embeddings "
        "ADD COLUMN IF NOT EXISTS contextual_content TEXT"
    )
    op.execute(
        "ALTER TABLE knowledge_embeddings "
        "ADD COLUMN IF NOT EXISTS domain_id VARCHAR(100)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE knowledge_embeddings DROP COLUMN IF EXISTS domain_id"
    )
    op.execute(
        "ALTER TABLE knowledge_embeddings DROP COLUMN IF EXISTS contextual_content"
    )
