"""Add Phase 2 fields to transactions table

Revision ID: 20260112_phase2
Revises: ef039d0df15c
Create Date: 2026-01-12

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260112_phase2'
down_revision = 'ef039d0df15c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add paid_by_id, paid_to_id, and purpose fields from Phase 2 Expense model to transactions table
    
    NOTE: These fields are already defined in the Transaction model since Phase 4.
    This migration is a no-op to maintain migration history chain.
    The fields will be created by Phase 4 schema generation.
    """
    pass


def downgrade() -> None:
    """No-op downgrade for Phase 2 migration (see upgrade doc)"""
    pass
