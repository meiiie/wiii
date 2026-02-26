"""Sprint 193b: Rename default organization to 'Tổ Chức Wiii'.

Revision ID: 033
Revises: 032
"""
from alembic import op


# revision identifiers
revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """UPDATE organizations
           SET display_name = 'Tổ Chức Wiii',
               name = 'Tổ Chức Wiii'
           WHERE id = 'default'
             AND display_name = 'Wiii Default Organization'"""
    )


def downgrade() -> None:
    op.execute(
        """UPDATE organizations
           SET display_name = 'Wiii Default Organization',
               name = 'Wiii Default Organization'
           WHERE id = 'default'
             AND display_name = 'Tổ Chức Wiii'"""
    )
