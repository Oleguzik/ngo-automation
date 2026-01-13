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
    
    IMPORTANT: Run migration script BEFORE this migration!
    python scripts/migrate_expenses_to_transactions.py
    """
    
    # Drop expenses table
    # Note: This will also drop the foreign key relationships automatically
    op.drop_table('expenses')


def downgrade() -> None:
    """
    Recreate expenses table structure (without data).
    
    WARNING: Data will NOT be restored! This only recreates the schema.
    Use database backup to restore data if needed.
    """
    
    # Recreate expenses table
    op.create_table(
        'expenses',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=True),
        sa.Column('paid_by_id', sa.Integer(), nullable=False),
        sa.Column('paid_to_id', sa.Integer(), nullable=True),
        sa.Column('products', postgresql.JSONB(), nullable=False),
        sa.Column('amount', sa.DECIMAL(12, 2), nullable=False),
        sa.Column('purpose', sa.String(500), nullable=False),
        sa.Column('purchase_date', sa.Date(), nullable=False),
        sa.Column('shop_name', sa.String(255), nullable=True),
        sa.Column('payment_method', sa.String(50), nullable=False),
        sa.Column('document_type', sa.String(50), nullable=False),
        sa.Column('document_link', sa.String(500), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        
        # Foreign keys
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
    )
    
    # Recreate indexes
    op.create_index('ix_expenses_id', 'expenses', ['id'])
    op.create_index('ix_expenses_organization_id', 'expenses', ['organization_id'])
    op.create_index('ix_expenses_project_id', 'expenses', ['project_id'])
    op.create_index('ix_expenses_paid_to_id', 'expenses', ['paid_to_id'])
    op.create_index('ix_expenses_purchase_date', 'expenses', ['purchase_date'])
    op.create_index('ix_expenses_created_at', 'expenses', ['created_at'])
