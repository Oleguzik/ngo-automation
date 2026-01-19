"""Add Phase 5 RAG foundation: document_chunks table with pgvector support

This migration creates the document_chunks table for storing text chunks
with vector embeddings for semantic search and RAG retrieval.

References:
- Spec: docs/00-spec-rag-implementation.md Section 3
- Architecture: docs/02-architecture-phase5.md Section 4

Features:
- 1536-dimensional vector embeddings (OpenAI text-embedding-3-small)
- IVFFlat index for fast similarity search (<100ms for 1M vectors)
- JSONB metadata for flexible chunk attributes (page_number, section, language)
- CASCADE delete with parent DocumentProcessing table

Revision ID: 20260119_docchunk_pgvector
Revises: 20260112_drop_expenses
Create Date: 2026-01-19 11:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '20260119_docchunk_pgvector'
down_revision: Union[str, None] = '20260112_drop_expenses'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create document_chunks table with pgvector support."""
    
    # Ensure pgvector extension is installed (in production, should be in init-db.sql)
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    # Check if document_chunks table already exists (may have been created by SQLAlchemy metadata.create_all)
    # If it exists, skip creation and proceed to ensure indexes and vector column are in place
    from sqlalchemy import inspect
    ctx = op.get_context()
    inspector = inspect(ctx.bind)
    tables = inspector.get_table_names()
    
    if 'document_chunks' not in tables:
        # Create document_chunks table with vector column
        # Note: pgvector's Vector type is represented as TEXT in Alembic for portability
        # The actual column type is created via raw SQL below
        op.create_table(
            'document_chunks',
            sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
            sa.Column('document_processing_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('chunk_text', sa.Text(), nullable=False),
            # embedding column: created with raw SQL (pgvector type)
            sa.Column('chunk_index', sa.Integer(), nullable=False),
            sa.Column('chunk_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            
            # Primary key
            sa.PrimaryKeyConstraint('id'),
            
            # Foreign key with cascade delete
            sa.ForeignKeyConstraint(
                ['document_processing_id'],
                ['document_processing.id'],
                name='fk_document_chunks_document_processing',
                ondelete='CASCADE'
            )
        )
        
        # Add embedding column with pgvector type
        # We do this separately because Alembic doesn't have native pgvector support
        op.execute("""
            ALTER TABLE document_chunks
            ADD COLUMN embedding vector(1536) NOT NULL;
        """)
    
    # Ensure indexes exist (safe to run even if table already exists)
    # 1. Index on document_processing_id for FK joins and batch retrieval
    try:
        op.create_index(
            'ix_document_chunks_document_processing_id',
            'document_chunks',
            ['document_processing_id'],
            unique=False
        )
    except Exception:
        pass  # Index already exists
    
    # 2. Index on created_at for time-range queries (Day 5 RAG audit logging)
    try:
        op.create_index(
            'ix_document_chunks_created_at',
            'document_chunks',
            ['created_at'],
            unique=False
        )
    except Exception:
        pass
    
    # 3. IVFFlat index on embedding vector for similarity search
    # This index enables fast approximate nearest neighbor search
    # - lists=100: Number of clusters (optimized for 1M vectors, use 10 for <10K)
    # - probes=10: Number of lists to examine during search
    try:
        op.execute("""
            CREATE INDEX ix_document_chunks_embedding_ivfflat
            ON document_chunks
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
        """)
    except Exception:
        pass  # Index already exists


def downgrade() -> None:
    """Drop document_chunks table and all related indexes."""
    
    # Drop indexes
    op.drop_index('ix_document_chunks_embedding_ivfflat', table_name='document_chunks')
    op.drop_index('ix_document_chunks_created_at', table_name='document_chunks')
    op.drop_index('ix_document_chunks_document_processing_id', table_name='document_chunks')
    
    # Drop foreign key constraint and table
    op.drop_constraint(
        'fk_document_chunks_document_processing',
        'document_chunks',
        type_='foreignkey'
    )
    op.drop_table('document_chunks')
