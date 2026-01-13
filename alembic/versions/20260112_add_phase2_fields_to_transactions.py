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
    """Add paid_by_id, paid_to_id, and purpose fields from Phase 2 Expense model to transactions table"""
    
    # Add audit trail fields
    op.add_column('transactions', sa.Column('paid_by_id', sa.Integer(), nullable=True, comment='User/volunteer who authorized the payment'))
    op.add_column('transactions', sa.Column('paid_to_id', sa.Integer(), nullable=True, comment='User/volunteer who received payment (for honoraria)'))
    
    # Add purpose field
    op.add_column('transactions', sa.Column('purpose', sa.String(500), nullable=True, comment='Purpose/context of transaction (from Phase 2 Expense model)'))
    
    # Create indexes for better query performance
    op.create_index('ix_transactions_paid_by_id', 'transactions', ['paid_by_id'])
    op.create_index('ix_transactions_paid_to_id', 'transactions', ['paid_to_id'])


def downgrade() -> None:
    """Remove Phase 2 fields from transactions table"""
    
    # Drop indexes first
    op.drop_index('ix_transactions_paid_by_id', table_name='transactions')
    op.drop_index('ix_transactions_paid_to_id', table_name='transactions')
    
    # Drop columns
    op.drop_column('transactions', 'purpose')
    op.drop_column('transactions', 'paid_to_id')
    op.drop_column('transactions', 'paid_by_id')
