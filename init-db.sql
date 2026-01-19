-- Phase 5 RAG Foundation: pgvector Extension Setup
-- This script runs on PostgreSQL container startup to enable vector support
-- Reference: docs/PHASE5_QUICK_START.md, docs/02-architecture-phase5.md

-- Create pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify extension is loaded
SELECT * FROM pg_extension WHERE extname = 'vector';

-- Create IVFFlat index for future document chunks table
-- Note: Actual table created via Alembic migration
-- This index setup is documented for reference:
-- CREATE INDEX idx_embedding_cosine 
-- ON document_chunks 
-- USING ivfflat (embedding vector_cosine_ops) 
-- WITH (lists = 100);

-- Log: pgvector extension successfully initialized
