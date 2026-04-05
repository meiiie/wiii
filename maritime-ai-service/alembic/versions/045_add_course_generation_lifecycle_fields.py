"""045: Add lifecycle fields to course_generation_jobs

Hardens AI course generation into a durable background/session workflow with:
- progress tracking
- heartbeat timestamps
- cooperative cancellation
- session/thread correlation
- resumable lifecycle metadata
"""

from alembic import op
import sqlalchemy as sa


revision = "045"
down_revision = "044"
branch_labels = None
depends_on = None


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

    columns = (
        ("session_id", sa.String(length=255), {"nullable": True}),
        ("thread_id", sa.Text(), {"nullable": True}),
        (
            "progress_percent",
            sa.Integer(),
            {"nullable": False, "server_default": sa.text("0")},
        ),
        ("status_message", sa.Text(), {"nullable": True}),
        ("started_at", sa.DateTime(timezone=True), {"nullable": True}),
        ("heartbeat_at", sa.DateTime(timezone=True), {"nullable": True}),
        ("completed_at", sa.DateTime(timezone=True), {"nullable": True}),
        (
            "cancel_requested",
            sa.Boolean(),
            {"nullable": False, "server_default": sa.text("false")},
        ),
        ("cancelled_at", sa.DateTime(timezone=True), {"nullable": True}),
    )

    for column_name, column_type, kwargs in columns:
        if not _column_exists(conn, "course_generation_jobs", column_name):
            op.add_column(
                "course_generation_jobs",
                sa.Column(column_name, column_type, **kwargs),
            )

    if not _index_exists(conn, "idx_course_gen_jobs_teacher_created"):
        op.create_index(
            "idx_course_gen_jobs_teacher_created",
            "course_generation_jobs",
            ["teacher_id", "created_at"],
        )

    if not _index_exists(conn, "idx_course_gen_jobs_org_created"):
        op.create_index(
            "idx_course_gen_jobs_org_created",
            "course_generation_jobs",
            ["organization_id", "created_at"],
        )

    if not _index_exists(conn, "idx_course_gen_jobs_thread"):
        op.create_index(
            "idx_course_gen_jobs_thread",
            "course_generation_jobs",
            ["thread_id"],
        )


def downgrade() -> None:
    for index_name in (
        "idx_course_gen_jobs_thread",
        "idx_course_gen_jobs_org_created",
        "idx_course_gen_jobs_teacher_created",
    ):
        op.drop_index(index_name, table_name="course_generation_jobs")

    for column_name in (
        "cancelled_at",
        "cancel_requested",
        "completed_at",
        "heartbeat_at",
        "started_at",
        "status_message",
        "progress_percent",
        "thread_id",
        "session_id",
    ):
        op.drop_column("course_generation_jobs", column_name)
