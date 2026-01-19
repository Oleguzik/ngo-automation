"""Drop expenses table (consolidated into transactions)

Revision ID: 20260112_drop_expenses
Revises: 20260112_phase2
Create Date: 2026-01-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260112_drop_expenses'
down_revision = '20260112_phase2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Drop expenses table after data has been migrated to transactions.
    
    NOTE: This is a no-op since the expenses table was never created
    in the Phase 4 schema. This migration is kept for historical purposes.
    """
    pass


def downgrade() -> None:
    """
    No-op downgrade for drop_expenses (see upgrade doc)
    """
    pass
