"""029: Create organization_documents table

Sprint 190: "Kho Tri Thức" — Org Admin Knowledge Base Management

Tracks document lifecycle: uploading → processing → ready | failed
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    result = conn.execute(sa.text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_name = 'organization_documents'"
    ))
    if result.fetchone() is None:
        op.create_table(
            "organization_documents",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("document_id", sa.Text(), nullable=False, unique=True),
            sa.Column("organization_id", sa.Text(), nullable=False),
            sa.Column("filename", sa.Text(), nullable=False),
            sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
            sa.Column("status", sa.Text(), nullable=False, server_default="uploading"),
            sa.Column("page_count", sa.Integer(), nullable=True),
            sa.Column("chunk_count", sa.Integer(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("uploaded_by", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        )
        op.create_index("ix_org_docs_org_status", "organization_documents", ["organization_id", "status"])
        op.create_index("ix_org_docs_org_id", "organization_documents", ["organization_id"])
        op.create_index("ix_org_docs_uploaded_by", "organization_documents", ["uploaded_by"])

    # Autovacuum tuning
    op.execute(sa.text(
        "ALTER TABLE organization_documents SET (autovacuum_vacuum_scale_factor = 0.05, "
        "autovacuum_analyze_scale_factor = 0.02)"
    ))


def downgrade():
    op.drop_index("ix_org_docs_uploaded_by", table_name="organization_documents")
    op.drop_index("ix_org_docs_org_id", table_name="organization_documents")
    op.drop_index("ix_org_docs_org_status", table_name="organization_documents")
    op.drop_table("organization_documents")
