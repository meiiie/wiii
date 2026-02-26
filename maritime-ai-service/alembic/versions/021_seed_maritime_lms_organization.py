"""Seed maritime-lms organization for LMS integration

Revision ID: 021
Revises: 020
Create Date: 2026-02-23

Sprint 175: "Cắm Phích Cắm" — Wiii x Maritime LMS Integration
- Creates the 'maritime-lms' organization record
- Domain: maritime only (LMS students study maritime subjects)
- Settings: branding + AI persona overlay for LMS context
"""
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '021'
down_revision = '020'
branch_labels = None
depends_on = None


def table_exists(table_name: str) -> bool:
    """Check if table exists."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    """Seed maritime-lms organization."""
    if not table_exists('organizations'):
        return

    op.execute("""
        INSERT INTO organizations (id, name, display_name, description, allowed_domains, default_domain, settings)
        VALUES (
            'maritime-lms',
            'LMS Hang Hai',
            'Trường Đại học Hàng Hải',
            'Hệ thống quản lý học tập Hàng Hải — tích hợp Wiii AI',
            ARRAY['maritime'],
            'maritime',
            '{"branding": {"name": "Wiii Hàng Hải", "welcome_message": "Chào bạn! Tôi là Wiii — trợ lý AI của Trường Hàng Hải. Tôi có thể giúp bạn với bài tập, ôn thi, và tra cứu kiến thức hàng hải."}, "features": {"enable_product_search": false, "enable_browser_scraping": false, "enable_living_agent": false}, "ai_config": {"persona_prompt_overlay": "Bạn đang hỗ trợ sinh viên Trường Đại học Hàng Hải. Ưu tiên kiến thức hàng hải (COLREG, SOLAS, MARPOL). Khi sinh viên hỏi về bài tập, dùng phương pháp Socratic — hướng dẫn chứ không cho đáp án trực tiếp."}}'
        )
        ON CONFLICT (id) DO UPDATE SET
            display_name = EXCLUDED.display_name,
            description = EXCLUDED.description,
            settings = EXCLUDED.settings,
            updated_at = NOW()
    """)


def downgrade() -> None:
    """Remove maritime-lms organization."""
    if table_exists('organizations'):
        op.execute("DELETE FROM organizations WHERE id = 'maritime-lms'")
