"""Initial schema creation for NGO Automation MVP

This is the baseline migration that creates the complete database schema
from which all future migrations build.

Key Features:
- All core organizational tables (organizations, projects)
- Phase 4: Financial transactions with GoBD compliance
- Phase 5: RAG document processing with pgvector embeddings
- Phase 5C: Agent orchestration for agentic RAG

Database:
- PostgreSQL 15 with pgvector extension
- Array comparisons with custom operators
- JSONB for flexible metadata storage
- UUID for document tracking
- Timestamped audit columns

References:
- Spec: docs/00-spec-phase4.md
- Spec: docs/00-spec-rag-implementation.md
- Architecture: docs/02-architecture-phase4.md
- Architecture: docs/02-architecture-phase5.md

Assumptions:
- pgvector extension is already created via init-db.sql
- All foreign key constraints enabled
- Cascade delete on parent table deletions

Revision ID: 001_initial_schema
Create Date: 2026-02-07

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial database schema with all tables."""
    
    # ==================== CORE TABLES ====================
    
    # 1. Organizations (root entity)
    op.create_table(
        'organizations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('country', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_organizations_id', 'organizations', ['id'])
    op.create_index('ix_organizations_email', 'organizations', ['email'], unique=True)
    
    # 2. Cost Categories (for transaction categorization)
    op.create_table(
        'cost_categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_cost_categories_id', 'cost_categories', ['id'])
    
    # 3. Projects (organizational activities)
    op.create_table(
        'projects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='active'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name='fk_projects_organization', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_projects_id', 'projects', ['id'])
    op.create_index('ix_projects_organization_id', 'projects', ['organization_id'])
    
    # ==================== PHASE 4: FINANCIAL TABLES ====================
    
    # 4. Transactions (core financial records - GoBD compliant)
    op.create_table(
        'transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=True),
        sa.Column('transaction_hash', sa.String(64), nullable=True),  # For deduplication
        sa.Column('transaction_type', sa.String(50), nullable=False),  # donation, expense, grant, etc.
        sa.Column('transaction_date', sa.Date(), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, server_default='EUR'),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('vendor_name', sa.String(255), nullable=True),
        sa.Column('vat_rate', sa.Numeric(5, 2), nullable=True),  # 0.00, 7.00, 19.00
        sa.Column('vat_amount', sa.Numeric(12, 2), nullable=True),
        sa.Column('net_amount', sa.Numeric(12, 2), nullable=True),
        sa.Column('source_type', sa.String(50), nullable=False),  # manual, bank_statement, invoice, etc.
        sa.Column('payment_method', sa.String(50), nullable=True),
        sa.Column('is_duplicate', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name='fk_transactions_organization', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name='fk_transactions_project', ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_transactions_id', 'transactions', ['id'])
    op.create_index('ix_transactions_organization_id', 'transactions', ['organization_id'])
    op.create_index('ix_transactions_project_id', 'transactions', ['project_id'])
    op.create_index('ix_transactions_transaction_date', 'transactions', ['transaction_date'])
    op.create_index('ix_transactions_transaction_hash', 'transactions', ['transaction_hash'], unique=True, postgresql_where=sa.text("transaction_hash IS NOT NULL"))
    
    # 5. Transaction Duplicates (tracking for data quality)
    op.create_table(
        'transaction_duplicates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('original_transaction_id', sa.Integer(), nullable=False),
        sa.Column('duplicate_transaction_id', sa.Integer(), nullable=False),
        sa.Column('similarity_score', sa.Numeric(5, 4), nullable=False),  # 0.0000 to 1.0000
        sa.Column('detected_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['original_transaction_id'], ['transactions.id'], name='fk_duplicate_original', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['duplicate_transaction_id'], ['transactions.id'], name='fk_duplicate_duplicate', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_transaction_duplicates_id', 'transaction_duplicates', ['id'])
    op.create_index('ix_transaction_duplicates_original', 'transaction_duplicates', ['original_transaction_id'])
    op.create_index('ix_transaction_duplicates_duplicate', 'transaction_duplicates', ['duplicate_transaction_id'])
    
    # 6. Profit Records (organization profit tracking)
    op.create_table(
        'profit_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('total_income', sa.Numeric(15, 2), nullable=False, server_default='0.00'),
        sa.Column('total_expenses', sa.Numeric(15, 2), nullable=False, server_default='0.00'),
        sa.Column('net_profit', sa.Numeric(15, 2), nullable=False),  # income - expenses
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name='fk_profit_records_organization', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_profit_records_id', 'profit_records', ['id'])
    op.create_index('ix_profit_records_organization_id', 'profit_records', ['organization_id'])
    op.create_index('ix_profit_records_period', 'profit_records', ['period_start', 'period_end'])
    
    # 7. Fee Records (fee tracking for transactions)
    op.create_table(
        'fee_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('transaction_id', sa.Integer(), nullable=False),
        sa.Column('fee_type', sa.String(100), nullable=False),  # bank_fee, payment_processor_fee, etc.
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id'], name='fk_fee_records_transaction', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_fee_records_id', 'fee_records', ['id'])
    op.create_index('ix_fee_records_transaction_id', 'fee_records', ['transaction_id'])
    
    # 8. Event Costs (track costs for specific events/projects)
    op.create_table(
        'event_costs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('event_name', sa.String(255), nullable=False),
        sa.Column('cost_amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('cost_date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name='fk_event_costs_project', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_event_costs_id', 'event_costs', ['id'])
    op.create_index('ix_event_costs_project_id', 'event_costs', ['project_id'])
    op.create_index('ix_event_costs_cost_date', 'event_costs', ['cost_date'])
    
    # ==================== PHASE 5: RAG DOCUMENT TABLES ====================
    
    # 9. Document Processing (document intake and status tracking)
    op.create_table(
        'document_processing',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('file_name', sa.String(255), nullable=False),
        sa.Column('file_type', sa.String(50), nullable=False),  # pdf, docx, xlsx, csv, etc.
        sa.Column('file_size', sa.Integer(), nullable=False),  # bytes
        sa.Column('raw_text', sa.Text(), nullable=True),
        sa.Column('extracted_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('processing_status', sa.String(50), nullable=False, server_default='pending'),  # pending, processing, completed, failed
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('chunks_created', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('embedding_status', sa.String(50), nullable=False, server_default='pending'),  # pending, processing, completed, failed
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name='fk_document_processing_organization', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_document_processing_id', 'document_processing', ['id'])
    op.create_index('ix_document_processing_organization_id', 'document_processing', ['organization_id'])
    op.create_index('ix_document_processing_processing_status', 'document_processing', ['processing_status'])
    op.create_index('ix_document_processing_embedding_status', 'document_processing', ['embedding_status'])
    
    # 10. Document Chunks (text chunks with pgvector embeddings)
    op.create_table(
        'document_chunks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_processing_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('chunk_text', sa.Text(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('chunk_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['document_processing_id'], ['document_processing.id'], name='fk_document_chunks_document_processing', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    
    # Add pgvector column via raw SQL (Alembic doesn't natively support pgvector)
    op.execute("""
        ALTER TABLE document_chunks
        ADD COLUMN embedding vector(1536) NOT NULL;
    """)
    
    op.create_index('ix_document_chunks_id', 'document_chunks', ['id'])
    op.create_index('ix_document_chunks_document_processing_id', 'document_chunks', ['document_processing_id'])
    op.create_index('ix_document_chunks_created_at', 'document_chunks', ['created_at'])
    
    # Create vector similarity index for fast semantic search
    op.execute("""
        CREATE INDEX ix_document_chunks_embedding_ivfflat
        ON document_chunks
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
    """)
    
    # 11. Conversations (multi-turn RAG conversation history)
    op.create_table(
        'conversations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('messages', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),  # Array of {role, content}
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name='fk_conversations_organization', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_conversations_id', 'conversations', ['id'])
    op.create_index('ix_conversations_organization_id', 'conversations', ['organization_id'])
    op.create_index('ix_conversations_created_at', 'conversations', ['created_at'])
    
    # ==================== PHASE 5C: AGENT ORCHESTRATION TABLES ====================
    
    # 12. Agent Tasks (autonomous task execution tracking)
    op.create_table(
        'agent_tasks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('task_type', sa.String(100), nullable=False),  # document_processing, rag_query, extraction, etc.
        sa.Column('input_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('output_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),  # pending, running, completed, failed
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name='fk_agent_tasks_organization', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_agent_tasks_id', 'agent_tasks', ['id'])
    op.create_index('ix_agent_tasks_organization_id', 'agent_tasks', ['organization_id'])
    op.create_index('ix_agent_tasks_status', 'agent_tasks', ['status'])
    op.create_index('ix_agent_tasks_created_at', 'agent_tasks', ['created_at'])
    
    # 13. Agent Steps (individual steps within a task - for detailed tracing)
    op.create_table(
        'agent_steps',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('agent_task_id', sa.Integer(), nullable=False),
        sa.Column('step_number', sa.Integer(), nullable=False),
        sa.Column('step_name', sa.String(255), nullable=False),
        sa.Column('step_type', sa.String(100), nullable=False),  # search, retrieve, generate, etc.
        sa.Column('input_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('output_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),  # Execution time in milliseconds
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['agent_task_id'], ['agent_tasks.id'], name='fk_agent_steps_agent_task', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_agent_steps_id', 'agent_steps', ['id'])
    op.create_index('ix_agent_steps_agent_task_id', 'agent_steps', ['agent_task_id'])
    op.create_index('ix_agent_steps_step_number', 'agent_steps', ['agent_task_id', 'step_number'], unique=True)


def downgrade() -> None:
    """Drop all tables (complete schema rollback)."""
    
    # Drop in reverse order of creation to handle foreign keys
    op.drop_table('agent_steps')
    op.drop_table('agent_tasks')
    op.drop_table('conversations')
    op.drop_table('document_chunks')
    op.drop_table('document_processing')
    op.drop_table('event_costs')
    op.drop_table('fee_records')
    op.drop_table('profit_records')
    op.drop_table('transaction_duplicates')
    op.drop_table('transactions')
    op.drop_table('projects')
    op.drop_table('cost_categories')
    op.drop_table('organizations')
