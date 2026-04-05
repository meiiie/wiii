"""Create course_generation_jobs table for AI course generation persistence.

Persists generation state across server restarts.
Design spec v2.0 (2026-03-22), expert requirement.

Revision ID: 040
Revises: 039
Create Date: 2026-03-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "040"
down_revision = "039"
branch_labels = None
depends_on = None


def _table_exists(conn, table_name: str) -> bool:
    return bool(
        conn.execute(
            sa.text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = current_schema() AND table_name = :table_name"
            ),
            {"table_name": table_name},
        ).fetchone()
    )


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    return bool(
        conn.execute(
            sa.text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = current_schema() "
                "AND table_name = :table_name AND column_name = :column_name"
            ),
            {"table_name": table_name, "column_name": column_name},
        ).fetchone()
    )


def _index_exists(conn, index_name: str) -> bool:
    return bool(
        conn.execute(
            sa.text(
                "SELECT 1 FROM pg_indexes "
                "WHERE schemaname = current_schema() AND indexname = :index_name"
            ),
            {"index_name": index_name},
        ).fetchone()
    )


def upgrade() -> None:
    conn = op.get_bind()

    if not _table_exists(conn, "course_generation_jobs"):
        op.create_table(
            "course_generation_jobs",
            sa.Column("id", sa.String(36), primary_key=True),  # UUID as string
            sa.Column("teacher_id", sa.String(36), nullable=False),
            sa.Column("phase", sa.String(50), nullable=False, server_default="CONVERTING"),
            sa.Column("file_path", sa.Text(), nullable=True),
            sa.Column("language", sa.String(5), server_default="vi"),
            sa.Column("teacher_prompt", sa.Text(), server_default=""),
            sa.Column("target_chapters", sa.Integer(), nullable=True),
            sa.Column("outline", postgresql.JSONB(), nullable=True),
            sa.Column("markdown", sa.Text(), nullable=True),  # Cached for expand phase
            sa.Column("section_map", postgresql.JSONB(), nullable=True),
            sa.Column("expand_request", postgresql.JSONB(), nullable=True),
            sa.Column("course_id", sa.String(36), nullable=True),  # LMS courseId after shell created
            sa.Column("completed_chapters", postgresql.JSONB(), server_default="[]"),
            sa.Column("failed_chapters", postgresql.JSONB(), server_default="[]"),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("organization_id", sa.String(100), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
    else:
        if not _column_exists(conn, "course_generation_jobs", "expand_request"):
            op.add_column(
                "course_generation_jobs",
                sa.Column("expand_request", postgresql.JSONB(), nullable=True),
            )

    if not _index_exists(conn, "idx_course_gen_jobs_teacher"):
        op.create_index("idx_course_gen_jobs_teacher", "course_generation_jobs", ["teacher_id"])
    if not _index_exists(conn, "idx_course_gen_jobs_phase"):
        op.create_index("idx_course_gen_jobs_phase", "course_generation_jobs", ["phase"])
    if not _index_exists(conn, "idx_course_gen_jobs_created"):
        op.create_index("idx_course_gen_jobs_created", "course_generation_jobs", ["created_at"])


def downgrade() -> None:
    op.drop_table("course_generation_jobs")
