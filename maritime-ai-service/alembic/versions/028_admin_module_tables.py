"""028: Create admin module tables

Sprint 178: "Admin Toàn Diện" — Comprehensive Admin Module

Tables: admin_audit_log, admin_feature_flags, llm_usage_log
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # -------------------------------------------------------------------------
    # Table 1: admin_audit_log
    # -------------------------------------------------------------------------
    result = conn.execute(sa.text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_name = 'admin_audit_log'"
    ))
    if result.fetchone() is None:
        op.create_table(
            "admin_audit_log",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("actor_id", sa.Text(), nullable=False),
            sa.Column("actor_role", sa.Text(), nullable=False, server_default="admin"),
            sa.Column("actor_name", sa.Text(), nullable=True),
            sa.Column("action", sa.Text(), nullable=False),
            sa.Column("http_method", sa.Text(), nullable=True),
            sa.Column("http_path", sa.Text(), nullable=True),
            sa.Column("http_status", sa.Integer(), nullable=True),
            sa.Column("target_type", sa.Text(), nullable=True),
            sa.Column("target_id", sa.Text(), nullable=True),
            sa.Column("target_name", sa.Text(), nullable=True),
            sa.Column("old_value", sa.JSON(), nullable=True),
            sa.Column("new_value", sa.JSON(), nullable=True),
            sa.Column("ip_address", sa.Text(), nullable=True),
            sa.Column("user_agent", sa.Text(), nullable=True),
            sa.Column("request_id", sa.Text(), nullable=True),
            sa.Column("organization_id", sa.Text(), nullable=True),
            sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        )
        op.create_index("ix_admin_audit_actor", "admin_audit_log", ["actor_id"])
        op.create_index("ix_admin_audit_action", "admin_audit_log", ["action"])
        op.create_index("ix_admin_audit_target", "admin_audit_log", ["target_type", "target_id"])
        op.create_index("ix_admin_audit_occurred", "admin_audit_log", ["occurred_at"])
        op.create_index("ix_admin_audit_org", "admin_audit_log", ["organization_id"])

    # -------------------------------------------------------------------------
    # Table 2: admin_feature_flags
    # -------------------------------------------------------------------------
    result = conn.execute(sa.text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_name = 'admin_feature_flags'"
    ))
    if result.fetchone() is None:
        op.create_table(
            "admin_feature_flags",
            sa.Column("key", sa.Text(), nullable=False),
            sa.Column("value", sa.Boolean(), nullable=False),
            sa.Column("flag_type", sa.Text(), nullable=False, server_default="release"),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("owner", sa.Text(), nullable=True),
            sa.Column("organization_id", sa.Text(), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
            sa.UniqueConstraint("key", "organization_id", name="uq_feature_flag_key_org"),
        )
        op.create_index("ix_feature_flags_org", "admin_feature_flags", ["organization_id"])
        op.create_index("ix_feature_flags_expires", "admin_feature_flags", ["expires_at"])

    # -------------------------------------------------------------------------
    # Table 3: llm_usage_log
    # -------------------------------------------------------------------------
    result = conn.execute(sa.text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_name = 'llm_usage_log'"
    ))
    if result.fetchone() is None:
        op.execute(sa.text("""
            CREATE TABLE llm_usage_log (
                id BIGSERIAL PRIMARY KEY,
                request_id TEXT,
                user_id TEXT,
                session_id TEXT,
                organization_id TEXT,
                model TEXT NOT NULL,
                provider TEXT,
                tier TEXT,
                component TEXT,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                total_tokens INTEGER GENERATED ALWAYS AS (input_tokens + output_tokens) STORED,
                duration_ms FLOAT DEFAULT 0,
                estimated_cost_usd FLOAT DEFAULT 0,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))
        op.create_index("ix_llm_usage_user", "llm_usage_log", ["user_id"])
        op.create_index("ix_llm_usage_org", "llm_usage_log", ["organization_id"])
        op.create_index("ix_llm_usage_model", "llm_usage_log", ["model"])
        op.create_index("ix_llm_usage_created", "llm_usage_log", ["created_at"])
        op.create_index("ix_llm_usage_request", "llm_usage_log", ["request_id"])

    # Autovacuum tuning for high-write tables
    op.execute(sa.text(
        "ALTER TABLE admin_audit_log SET (autovacuum_vacuum_scale_factor = 0.05, "
        "autovacuum_analyze_scale_factor = 0.02)"
    ))
    op.execute(sa.text(
        "ALTER TABLE llm_usage_log SET (autovacuum_vacuum_scale_factor = 0.05, "
        "autovacuum_analyze_scale_factor = 0.02)"
    ))


def downgrade():
    op.drop_table("llm_usage_log")
    op.drop_index("ix_feature_flags_expires", table_name="admin_feature_flags")
    op.drop_index("ix_feature_flags_org", table_name="admin_feature_flags")
    op.drop_table("admin_feature_flags")
    op.drop_index("ix_admin_audit_org", table_name="admin_audit_log")
    op.drop_index("ix_admin_audit_occurred", table_name="admin_audit_log")
    op.drop_index("ix_admin_audit_target", table_name="admin_audit_log")
    op.drop_index("ix_admin_audit_action", table_name="admin_audit_log")
    op.drop_index("ix_admin_audit_actor", table_name="admin_audit_log")
    op.drop_table("admin_audit_log")
