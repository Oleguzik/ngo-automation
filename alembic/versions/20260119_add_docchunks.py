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
down_revision: Union[str, None] = '20260112_add_phase2_fields_to_transactions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create document_chunks table with pgvector support."""
    
    # pgvector extension must be created in init-db.sql BEFORE migrations run
    # Alembic migrations run transactionally, so we cannot create extensions here
    
    # Create document_chunks table with vector column
    op.create_table(
        'document_chunks',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('document_processing_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('chunk_text', sa.Text(), nullable=False),
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
        ),
        
        # Create indexes
        sa.Index('ix_document_chunks_document_processing_id', 'document_processing_id'),
        sa.Index('ix_document_chunks_created_at', 'created_at'),
    )
    
    # Add embedding column with pgvector type in separate command
    # Using raw SQL because Alembic doesn't have native pgvector support
    op.execute("""
        ALTER TABLE document_chunks
        ADD COLUMN embedding vector(1536) NOT NULL;
    """)
    
    # Create vector similarity index
    op.execute("""
        CREATE INDEX ix_document_chunks_embedding_ivfflat
        ON document_chunks
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
    """)


def downgrade() -> None:
    """Drop document_chunks table and all related indexes."""
    
    # Drop the table (indexes are dropped automatically)
    op.drop_table('document_chunks')
