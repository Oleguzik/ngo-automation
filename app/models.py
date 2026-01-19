"""
SQLAlchemy ORM models for database tables.

PHASE 1: Organizations and Projects (Core NGO Management) ✅ ACTIVE
PHASE 2 Lite: Expenses (Current - Expenditure Tracking MVP) ✅ ACTIVE
PHASE 2 Full: Documents, Beneficiaries, and Cases (AI Document Processing) ⏸️ DEFERRED
  - All Phase 2 Full code is commented out below for future implementation
  - Can be uncommented when expanding to full document intelligence
  - See docs/PHASE2_COMPLETE_SPECIFICATION.md for full details

All models use proper indexing, relationships, and audit fields (created_at, updated_at).
Vector embeddings (pgvector) will be used for semantic search once Phase 2 Full is implemented.
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Date, ForeignKey, JSON, DECIMAL, Table, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector
from datetime import datetime, date
from decimal import Decimal
from uuid import uuid4
import enum
from app.database import Base

# ============================================================================
# Enumerations
# ============================================================================
class PaymentMethod(str, enum.Enum):
    """Payment method enumeration"""
    CASH = "cash"
    CARD = "card"
    CHECK = "check"
    TRANSFER = "transfer"
    OTHER = "other"


# ============================================================================
# PHASE 2 FULL: Junction Table (COMMENTED OUT - DEFERRED)
# ============================================================================
# document_cases = Table(
#     'document_cases',
#     Base.metadata,
#     Column('document_id', UUID(as_uuid=True), ForeignKey('documents.id', ondelete='CASCADE'), primary_key=True),
#     Column('case_id', UUID(as_uuid=True), ForeignKey('cases.id', ondelete='CASCADE'), primary_key=True),
#     Column('linked_at', DateTime, default=datetime.utcnow)
# )


class Organization(Base):
    """
    Organization entity representing an NGO.
    
    Attributes:
        id: Unique identifier (auto-generated)
        name: Organization name (must be unique)
        email: Contact email (must be unique)
        country: Country of operation (optional)
        description: Detailed description (optional)
        is_active: Soft delete flag (True = active, False = deleted)
        created_at: Creation timestamp (UTC)
        updated_at: Last modification timestamp (UTC, auto-updates)
        projects: Relationship to associated Project objects
    
    Note:
        When organization is deleted, all related projects are deleted too (cascade)
    """
    
    __tablename__ = "organizations"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Required fields with unique constraints
    name = Column(String(255), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    
    # Optional fields
    country = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    
    # Soft delete flag (don't actually delete, just mark inactive)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Timestamps (auto-managed)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationship: 1 Organization → Many Projects
    # cascade="all,delete": When org deleted, delete all projects automatically
    # back_populates: Bidirectional relationship (org.projects ↔ project.organization)
    projects = relationship("Project", back_populates="organization", cascade="all,delete")
    
    def __repr__(self):
        """String representation for debugging"""
        return f"<Organization(id={self.id}, name='{self.name}', email='{self.email}')>"


class Project(Base):
    """
    Project entity representing a project owned by an organization.
    
    Attributes:
        id: Unique identifier (auto-generated)
        name: Project name
        description: Project description (optional)
        organization_id: Foreign key to Organizations table (required)
        status: Current project status (default: 'active')
        is_active: Soft delete flag (True = active, False = deleted)
        created_at: Creation timestamp (UTC)
        updated_at: Last modification timestamp (UTC, auto-updates)
        organization: Relationship to parent Organization object
    
    Note:
        Cannot create project without valid organization_id
    """
    
    __tablename__ = "projects"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Required fields
    name = Column(String(255), index=True, nullable=False)
    
    # Optional description
    description = Column(Text, nullable=True)
    
    # Foreign key to organizations table (required, not null)
    # If organization deleted, project is deleted too (cascade handled in Organization model)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    
    # Project status (active, paused, completed, etc.)
    status = Column(String(50), default="active", nullable=False)
    
    # Soft delete flag
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Timestamps (auto-managed)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationship: Many Projects → 1 Organization
    # back_populates: Bidirectional relationship (project.organization ↔ org.projects)
    organization = relationship("Organization", back_populates="projects")
    
    def __repr__(self):
        """String representation for debugging"""
        return f"<Project(id={self.id}, name='{self.name}', org_id={self.organization_id})>"


# ============================================================================
# PHASE 3: Cost & Profit MVP with AI Integration
# ============================================================================

class CostCategory(Base):
    """
    Cost category for organizing and analyzing expenses.
    
    Attributes:
        id: Unique identifier
        organization_id: Foreign key to Organization
        name: Category name (e.g., 'Salaries', 'Rent', 'Supplies', 'Transport')
        description: Category description (optional)
        is_active: Soft delete flag
        created_at: Creation timestamp
        updated_at: Last modification timestamp
    """
    
    __tablename__ = "cost_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationship
    organization = relationship("Organization", foreign_keys=[organization_id], backref="cost_categories")
    
    def __repr__(self):
        return f"<CostCategory(id={self.id}, name='{self.name}', org_id={self.organization_id})>"


class ProfitRecord(Base):
    """
    Profit/Revenue record for tracking income and donations.
    
    PHASE 3 MVP: Income tracking to balance against expenses for cost/profit analysis
    
    Attributes:
        id: Unique identifier (UUID)
        organization_id: Foreign key to Organization (required)
        project_id: Foreign key to Project (optional)
        source: Revenue source (e.g., 'donation', 'grant', 'sales', 'service', 'fundraiser')
        amount: Revenue amount (DECIMAL for precision)
        currency: Currency code (default: 'EUR')
        received_date: Date revenue was received
        donor_info: Donor/payer information (name, email, etc.) as JSON (optional)
        description: Detailed description of revenue source
        reference: External reference (transaction ID, invoice number, etc.)
        status: Record status ('received', 'pending', 'disputed', 'cancelled')
        notes: Additional notes or AI-extracted details
        created_at: When record was created
        updated_at: Last modification time
    """
    
    __tablename__ = "profit_records"
    
    # Unique identifier
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4, index=True)
    
    # Foreign keys
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Revenue details
    source = Column(String(100), nullable=False, index=True)  # donation, grant, sales, service, fundraiser, other
    amount = Column(DECIMAL(12, 2), nullable=False)
    currency = Column(String(3), default="EUR", nullable=False)
    received_date = Column(Date, nullable=False, index=True)
    
    # Donor/payer information (flexible JSON)
    donor_info = Column(JSONB, default={}, nullable=True)  # {name, email, phone, organization, ...}
    
    # Context
    description = Column(String(500), nullable=False)
    reference = Column(String(255), nullable=True)  # External transaction ID, invoice #, etc.
    
    # Status and metadata
    status = Column(String(50), default="received", nullable=False)  # received, pending, disputed, cancelled
    notes = Column(Text, nullable=True)  # User notes or AI-extracted details
    
    # Audit timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    organization = relationship("Organization", foreign_keys=[organization_id], backref="profit_records")
    project = relationship("Project", foreign_keys=[project_id], backref="profit_records")
    
    def __repr__(self):
        return f"<ProfitRecord(id={self.id}, org_id={self.organization_id}, amount={self.amount}€, source='{self.source}')>"


# ============================================================================
# PHASE 3: AI Document Processing for Cost/Profit (Not yet vectorized)
# ============================================================================

class DocumentProcessing(Base):
    """
    Track documents uploaded for AI-powered cost/profit extraction.
    
    PHASE 3 MVP: Store extracted cost/profit data from files (receipts, invoices, etc.)
    - NOT YET using vector embeddings (RAG deferred to Phase 3.5)
    - Focus on structured data extraction via OpenAI
    - Support for receipts, invoices, bank statements, Excel exports
    
    Attributes:
        id: Unique identifier (UUID)
        organization_id: Foreign key to Organization
        file_name: Original filename
        file_type: File type (pdf, image, xlsx, csv, etc.)
        file_size: Size in bytes
        raw_text: Extracted text from document (via OCR or native)
        extracted_data: Structured extraction results from OpenAI as JSON
        processing_status: 'pending', 'processing', 'completed', 'failed'
        error_message: If processing failed, error details
        created_at: Upload timestamp
        updated_at: Last processing time
    """
    
    __tablename__ = "document_processing"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # File metadata
    file_name = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)  # pdf, image, xlsx, csv, etc.
    file_size = Column(Integer, nullable=False)  # bytes
    
    # Extraction results
    raw_text = Column(Text, nullable=True)  # Extracted text from OCR/native
    extracted_data = Column(JSONB, default={}, nullable=True)  # Structured extraction from OpenAI
    
    # Processing status
    processing_status = Column(String(50), default="pending", nullable=False)
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationship
    organization = relationship("Organization", foreign_keys=[organization_id], backref="document_processing")
    
    def __repr__(self):
        return f"<DocumentProcessing(id={self.id}, file='{self.file_name}', status='{self.processing_status}')>"


# ============================================================================
# PHASE 5: RAG Foundation - Vector Search & Semantic Q&A
# ============================================================================

class DocumentChunk(Base):
    """
    Text chunk with vector embedding for semantic search.
    
    PHASE 5 RAG Foundation: Split documents into chunks, embed with OpenAI,
    store vectors for similarity search and RAG retrieval.
    
    From spec (00-spec-rag-implementation.md):
    - 500 tokens per chunk (tunable, default recommended)
    - 50 token overlap for context continuity
    - 1536-dimensional embeddings (OpenAI text-embedding-3-small)
    - Cosine similarity search via pgvector
    
    Attributes:
        id: Unique identifier (auto-increment)
        document_processing_id: Foreign key to DocumentProcessing (source document)
        chunk_text: Text content of chunk (up to ~2000 characters ~ 500 tokens)
        embedding: Vector embedding (1536 dimensions) for semantic search
        chunk_index: Position of chunk within document (0, 1, 2, ...)
        metadata: Additional metadata as JSON (page_number, section, language, etc.)
        created_at: Chunk creation timestamp
        updated_at: Last modification timestamp
        
    Relationships:
        - document_processing: The source document this chunk came from
        
    Indexing:
        - IVFFlat index on embedding column for fast similarity search
        - Index on document_processing_id for batch retrieval
        
    Vector Search Usage:
        - Query: SELECT * FROM document_chunks 
                 ORDER BY embedding <=> query_vector
                 LIMIT 5
        - Min similarity threshold: 0.7 (cosine similarity)
        - Retrieval time: <100ms for 1M vectors with IVFFlat
        
    Reference:
        - Spec: docs/00-spec-rag-implementation.md Section 3
        - Architecture: docs/02-architecture-phase5.md Section 4
        - Implementation: docs/PHASE5_IMPLEMENTATION_GUIDE.md
    """
    
    __tablename__ = "document_chunks"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign key to source document
    document_processing_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document_processing.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Chunk content
    chunk_text = Column(Text, nullable=False)  # Up to ~2000 chars (500 tokens)
    
    # Vector embedding (1536 dimensions for text-embedding-3-small)
    embedding = Column(Vector(1536), nullable=False)
    
    # Chunk position in document
    chunk_index = Column(Integer, nullable=False)
    
    # Optional chunk metadata (page number, section, language, etc.)
    # Named chunk_metadata (not 'metadata') because 'metadata' is reserved by SQLAlchemy
    chunk_metadata = Column(JSONB, default={}, nullable=True)
    
    # Timestamps for audit trail
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationship to source document
    document_processing = relationship(
        "DocumentProcessing",
        foreign_keys=[document_processing_id],
        backref="chunks"
    )
    
    def __repr__(self):
        return (
            f"<DocumentChunk(id={self.id}, doc_id={self.document_processing_id}, "
            f"chunk_idx={self.chunk_index}, text_len={len(self.chunk_text) if self.chunk_text else 0})>"
        )


# ============================================================================
# PHASE 5B: RAG Query System - Conversation History & Multi-Turn Support
# ============================================================================

class Conversation(Base):
    """
    Multi-turn conversation history for RAG queries.
    
    PHASE 5B RAG Query System: Store conversation threads with multiple user
    questions and AI answers, enabling context-aware follow-up questions.
    
    From spec (00-spec-rag-implementation.md):
    - Conversation = collection of messages (user questions + AI answers)
    - Each message includes: role (user/assistant), content, timestamp, sources
    - Messages stored in JSONB for flexibility (can add metadata)
    - Context window: last 5 messages used for follow-up prompts
    - Enables: "Which vendor was the largest?" → refers to previous question
    
    Attributes:
        id: Unique conversation ID (UUID)
        organization_id: Organization this conversation belongs to
        title: Conversation title/topic (e.g., "Q4 Spending Analysis")
        messages: JSONB array of messages with structure:
            [
                {
                    "role": "user|assistant",
                    "content": "Question or answer text",
                    "timestamp": "2026-01-19T10:30:00Z",
                    "sources": [  # For assistant messages only
                        {
                            "document_name": "invoice.pdf",
                            "chunk_id": "uuid",
                            "similarity_score": 0.94,
                            "page_number": 1
                        }
                    ],
                    "confidence": 0.92  # For assistant messages only
                }
            ]
        created_at: Conversation creation timestamp
        updated_at: Last message timestamp
        
    Relationships:
        - organization: The organization this conversation belongs to
        
    Indexing:
        - Index on (organization_id, created_at) for list queries
        - Index on updated_at for recent conversations
        
    Multi-Turn Context:
        - When answering follow-up, last 5 messages included in prompt
        - Helps GPT understand pronouns and context
        - Max 5 messages limit to manage token usage
        
    Reference:
        - Spec: docs/00-spec-rag-implementation.md Section 5B
        - Architecture: docs/02-architecture-phase5.md Section 3
    """
    
    __tablename__ = "conversations"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Organization this conversation belongs to
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    
    # Conversation title/topic
    title = Column(String(255), nullable=False)
    
    # Messages as JSONB array
    # Structure: [{"role": "user|assistant", "content": "...", "timestamp": "...", ...}]
    messages = Column(JSONB, default=list, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationship to organization
    organization = relationship(
        "Organization",
        foreign_keys=[organization_id],
        backref="conversations"
    )
    
    def __repr__(self):
        msg_count = len(self.messages) if self.messages else 0
        return f"<Conversation(id={self.id}, org={self.organization_id}, title='{self.title}', msgs={msg_count})>"
    
    def get_context_messages(self, limit: int = 5) -> list:
        """
        Get last N messages for context injection into prompts.
        
        Args:
            limit: Max messages to return (default 5)
        
        Returns:
            List of last N messages (or all if fewer than limit)
        
        Example:
            >>> conv.messages = [msg1, msg2, msg3, msg4, msg5, msg6]
            >>> conv.get_context_messages(5)
            [msg2, msg3, msg4, msg5, msg6]  # Last 5
        """
        if not self.messages:
            return []
        return list(self.messages[-limit:]) if len(self.messages) > limit else list(self.messages)


# ============================================================================
# PHASE 4: Financial Reporting System with AI-Powered Transaction Extraction
# ============================================================================

class Transaction(Base):
    """
    Transaction entity for comprehensive financial tracking and GoBD compliance.
    
    PHASE 4: AI-powered multi-source transaction processing
    - OCR extraction from receipt photos (Tesseract)
    - AI-powered text parsing (OpenAI GPT-4o-mini)
    - Bank statement parsing (rule-based)
    - Invoice processing with line items
    - Hash-based deduplication (SHA-256)
    - GoBD-compliant audit trail
    
    Attributes:
        id: Unique identifier (auto-generated)
        organization_id: Foreign key to Organization (required)
        project_id: Foreign key to Project (optional, for project-specific expenses)
        transaction_hash: SHA-256 fingerprint for deduplication (unique, 16 chars)
        transaction_type: 'expense' or 'revenue'
        transaction_date: Date of transaction (ISO 8601 YYYY-MM-DD)
        amount: Total transaction amount (DECIMAL for precision)
        currency: Currency code (default: 'EUR')
        category: GoBD-compliant category (Büromaterial, Lebensmittel, Honorare, etc.)
        vendor_name: Payee/payer name (normalized for deduplication)
        vat_rate: VAT/MwSt rate (0.19 for 19%, 0.07 for 7%, 0.00 for exempt)
        vat_amount: Calculated VAT amount (auto-calculated)
        net_amount: Amount before VAT (auto-calculated)
        source_type: 'receipt_photo', 'bank_statement', 'invoice_pdf', 'manual_entry'
        document_processing_id: Foreign key to DocumentProcessing (source file)
        payment_method: 'cash', 'card', 'transfer', 'check', 'other'
        notes: Additional notes or context
        line_items: Itemized details as JSONB array [{description, amount, quantity}]
        is_duplicate: Flag indicating if this is a duplicate transaction
        duplicate_of: Self-referencing FK to original transaction (if duplicate)
        is_active: Soft delete flag (GoBD compliance - never hard delete)
        created_at: Creation timestamp (audit trail)
        updated_at: Last modification timestamp (audit trail)
        
    AI Engineering Notes:
        - transaction_hash enables O(1) duplicate detection
        - Hash formula: SHA256(date|amount|normalized_vendor|currency)[:16]
        - Vendor normalization: lowercase, remove "GmbH", "AG", "e.V.", special chars
        - OCR → GPT-4 extraction → hash check → insert (deduplication saves ~30% API calls)
        - line_items JSONB enables flexible itemization without schema changes
        
    GoBD Compliance:
        - is_active (soft delete) - never hard delete transactions
        - created_at, updated_at - immutable audit trail
        - transaction_hash - ensures uniqueness and traceability
        - All fields nullable=False where required (data integrity)
        
    Example:
        transaction = Transaction(
            organization_id=1,
            project_id=3,
            transaction_hash="a3f5b89c12d4e6f7",
            transaction_type="expense",
            transaction_date=date(2025, 1, 15),
            amount=Decimal("43.55"),
            currency="EUR",
            category="Lebensmittel",
            vendor_name="REWE",
            vat_rate=Decimal("0.07"),
            vat_amount=Decimal("2.85"),
            net_amount=Decimal("40.70"),
            source_type="receipt_photo",
            payment_method="card",
            line_items=[
                {"description": "Brot", "amount": 3.50, "quantity": 2},
                {"description": "Milch", "amount": 1.20, "quantity": 1}
            ]
        )
    """
    
    __tablename__ = "transactions"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign keys
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    document_processing_id = Column(UUID(as_uuid=True), ForeignKey("document_processing.id", ondelete="SET NULL"), nullable=True)
    
    # Audit trail fields (from Phase 2 Expense model)
    paid_by_id = Column(Integer, nullable=True, index=True, comment="User/volunteer who authorized the payment")
    paid_to_id = Column(Integer, nullable=True, index=True, comment="User/volunteer who received payment (for honoraria)")
    
    # Deduplication fingerprint (SHA-256 truncated to 16 chars)
    transaction_hash = Column(String(16), unique=True, nullable=False, index=True)
    
    # Core transaction data
    transaction_type = Column(String(20), nullable=False, index=True)  # 'expense' or 'revenue'
    transaction_date = Column(Date, nullable=False, index=True)
    amount = Column(DECIMAL(12, 2), nullable=False)
    currency = Column(String(3), default="EUR", nullable=False)
    
    # German GoBD categories
    category = Column(String(100), nullable=True, index=True)  # Büromaterial, Lebensmittel, Honorare, etc.
    
    # Vendor/payer information
    vendor_name = Column(String(255), nullable=True, index=True)  # Normalized for deduplication
    
    # German VAT (Mehrwertsteuer) tracking
    vat_rate = Column(DECIMAL(5, 2), nullable=True)  # 0.19, 0.07, 0.00
    vat_amount = Column(DECIMAL(12, 2), nullable=True)
    net_amount = Column(DECIMAL(12, 2), nullable=True)
    
    # Source tracking (AI pipeline metadata)
    source_type = Column(String(50), nullable=False, index=True)  # receipt_photo, bank_statement, invoice_pdf, manual_entry
    payment_method = Column(String(50), nullable=True)  # cash, card, transfer, check, other
    
    # Additional context
    notes = Column(Text, nullable=True)
    purpose = Column(String(500), nullable=True, comment="Purpose/context of transaction (from Phase 2 Expense model)")
    line_items = Column(JSONB, default=list, nullable=True)  # [{description, amount, quantity, unit}, ...]
    
    # Deduplication tracking
    is_duplicate = Column(Boolean, default=False, nullable=False)
    duplicate_of = Column(Integer, ForeignKey("transactions.id"), nullable=True)  # Self-referencing FK
    
    # GoBD compliance (soft delete only)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Audit timestamps (immutable)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    organization = relationship("Organization", foreign_keys=[organization_id], backref="transactions")
    project = relationship("Project", foreign_keys=[project_id], backref="transactions")
    document = relationship("DocumentProcessing", foreign_keys=[document_processing_id], backref="transactions")
    
    # Self-referencing relationship for duplicates
    original_transaction = relationship("Transaction", remote_side=[id], foreign_keys=[duplicate_of], backref="duplicates")
    
    def __repr__(self):
        return f"<Transaction(id={self.id}, hash='{self.transaction_hash}', type='{self.transaction_type}', amount={self.amount}€, vendor='{self.vendor_name}')>"


class TransactionDuplicate(Base):
    """
    Track potential duplicate transactions with similarity scoring.
    
    PHASE 4: Duplicate detection and resolution tracking
    - Links original transaction to potential duplicates
    - Stores similarity score (0.0 to 1.0)
    - Tracks resolution strategy (auto_ignored, manual_review, merged, etc.)
    
    Attributes:
        id: Unique identifier
        original_transaction_id: FK to original transaction
        duplicate_transaction_id: FK to duplicate transaction
        similarity_score: Similarity metric (1.0 = exact match, 0.8 = fuzzy match)
        resolution_strategy: How duplicate was handled
        resolved_at: When resolution was made
        resolved_by: User/system that resolved (optional)
        created_at: When duplicate was detected
        
    AI Engineering Notes:
        - similarity_score 1.0: Exact hash match (same date, amount, vendor)
        - similarity_score 0.8-0.99: Fuzzy match (similar but not identical)
        - Used for manual review queue in dashboard
        
    Example:
        dup = TransactionDuplicate(
            original_transaction_id=123,
            duplicate_transaction_id=456,
            similarity_score=Decimal("1.0"),
            resolution_strategy="auto_ignored"
        )
    """
    
    __tablename__ = "transaction_duplicates"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign keys to transactions
    original_transaction_id = Column(Integer, ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False, index=True)
    duplicate_transaction_id = Column(Integer, ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Similarity metrics
    similarity_score = Column(DECIMAL(3, 2), nullable=False)  # 0.00 to 1.00
    
    # Resolution tracking
    resolution_strategy = Column(String(50), nullable=True)  # auto_ignored, manual_review, merged, false_positive
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(Integer, nullable=True)  # User ID who resolved (future: FK to User table)
    
    # Audit timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    original = relationship("Transaction", foreign_keys=[original_transaction_id])
    duplicate = relationship("Transaction", foreign_keys=[duplicate_transaction_id])
    
    def __repr__(self):
        return f"<TransactionDuplicate(original_id={self.original_transaction_id}, duplicate_id={self.duplicate_transaction_id}, score={self.similarity_score})>"


class FeeRecord(Base):
    """
    Fee record for German contractor/freelancer payments (Honorare).
    
    PHASE 4: German tax compliance for contractor payments
    - Tracks payments to volunteers, speakers, specialists
    - GDPR-compliant anonymization (contractor_id_hash)
    - Tax withholding tracking (Steuerabzug)
    - Links to transaction for audit trail
    
    Attributes:
        id: Unique identifier
        organization_id: Foreign key to Organization
        transaction_id: Foreign key to Transaction (payment record)
        contractor_name: Name of contractor/volunteer (visible)
        contractor_id_hash: SHA-256 hashed personal ID (GDPR anonymized)
        service_description: What service was provided
        gross_amount: Total payment before tax
        tax_withheld: Tax deducted (if applicable)
        net_amount: Payment after tax deduction
        payment_date: Date of payment
        invoice_number: Invoice/receipt reference
        is_active: Soft delete flag
        created_at: Creation timestamp
        updated_at: Last modification timestamp
        
    GDPR Compliance:
        - contractor_id_hash: Personal ID hashed (one-way, cannot reverse)
        - contractor_name: Kept for business purposes (allowed under GDPR)
        - Right to erasure: Cascade delete when organization deleted
        
    German Tax Law:
        - Tracks Honorare (contractor fees) separately from regular expenses
        - tax_withheld: Required for tax filing (Lohnsteuer, Sozialversicherung)
        - Used for annual tax reports and contractor summaries
        
    Example:
        fee = FeeRecord(
            organization_id=1,
            transaction_id=789,
            contractor_name="Max Mustermann",
            contractor_id_hash="a7f3b2c4...",  # SHA-256 of personal ID
            service_description="Workshop facilitation - 3 hours",
            gross_amount=Decimal("300.00"),
            tax_withheld=Decimal("0.00"),
            net_amount=Decimal("300.00"),
            payment_date=date(2025, 1, 20),
            invoice_number="HON-2025-001"
        )
    """
    
    __tablename__ = "fee_records"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign keys
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True)
    
    # Contractor information
    contractor_name = Column(String(255), nullable=False, index=True)
    contractor_id_hash = Column(String(64), nullable=True)  # SHA-256 hashed personal ID (GDPR)
    
    # Service details
    service_description = Column(Text, nullable=False)
    
    # Payment amounts
    gross_amount = Column(DECIMAL(10, 2), nullable=False)
    tax_withheld = Column(DECIMAL(10, 2), default=Decimal("0.00"), nullable=False)
    net_amount = Column(DECIMAL(10, 2), nullable=False)
    
    # Payment metadata
    payment_date = Column(Date, nullable=False, index=True)
    invoice_number = Column(String(100), nullable=True)
    
    # Soft delete
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Audit timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    organization = relationship("Organization", foreign_keys=[organization_id], backref="fee_records")
    transaction = relationship("Transaction", foreign_keys=[transaction_id], backref="fee_records")
    
    def __repr__(self):
        return f"<FeeRecord(id={self.id}, contractor='{self.contractor_name}', amount={self.gross_amount}€, date={self.payment_date})>"


class EventCost(Base):
    """
    Event cost tracking for NGO activities and workshops.
    
    PHASE 4: Activity-based cost tracking
    - Links events to projects
    - Calculates cost per attendee
    - Detailed cost breakdown (venue, catering, materials, etc.)
    - Useful for budget planning and impact reporting
    
    Attributes:
        id: Unique identifier
        organization_id: Foreign key to Organization
        project_id: Foreign key to Project (which project funded the event)
        event_name: Name of event/workshop
        event_date: Date of event
        total_cost: Total expenditure for event
        attendee_count: Number of participants
        cost_per_person: Auto-calculated (total_cost / attendee_count)
        cost_breakdown: Itemized costs as JSONB {venue: 500, catering: 300, ...}
        is_active: Soft delete flag
        created_at: Creation timestamp
        updated_at: Last modification timestamp
        
    Use Cases:
        - Budget planning: "How much does a workshop cost on average?"
        - Impact reporting: "We served 150 people at €12 per person"
        - Donor reports: "Your donation funded 3 workshops reaching 75 youth"
        
    Example:
        event = EventCost(
            organization_id=1,
            project_id=2,
            event_name="Youth Workshop - Digital Skills",
            event_date=date(2025, 1, 25),
            total_cost=Decimal("850.00"),
            attendee_count=25,
            cost_per_person=Decimal("34.00"),  # Auto-calculated
            cost_breakdown={
                "venue": 300.00,
                "catering": 250.00,
                "materials": 200.00,
                "transport": 100.00
            }
        )
    """
    
    __tablename__ = "event_costs"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign keys
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Event details
    event_name = Column(String(255), nullable=False)
    event_date = Column(Date, nullable=False, index=True)
    
    # Cost tracking
    total_cost = Column(DECIMAL(10, 2), nullable=False)
    attendee_count = Column(Integer, nullable=True)  # Optional if not tracked
    cost_per_person = Column(DECIMAL(8, 2), nullable=True)  # Auto-calculated or NULL
    
    # Detailed breakdown
    cost_breakdown = Column(JSONB, default={}, nullable=True)  # {venue: 500, catering: 300, materials: 200, ...}
    
    # Soft delete
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Audit timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    organization = relationship("Organization", foreign_keys=[organization_id], backref="event_costs")
    project = relationship("Project", foreign_keys=[project_id], backref="event_costs")
    
    def __repr__(self):
        return f"<EventCost(id={self.id}, event='{self.event_name}', total={self.total_cost}€, attendees={self.attendee_count})>"


# ============================================================================
# END OF PHASE 4 MODELS
# ============================================================================

# Uncomment the following when implementing Phase 2 Full features:
# - Document text extraction (PDF, Excel, Word, Image)
# - OCR processing  
# - Email integration
# - LLM classification
# - Semantic search via embeddings
# - See docs/PHASE2_COMPLETE_SPECIFICATION.md for full details
# ============================================================================
#
# class Document(Base):
#     """
#     Document entity representing uploaded/ingested files with AI processing metadata.
#     """
#     __tablename__ = "documents"
#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
#     file_name = Column(String(255), nullable=False)
#     file_type = Column(String(50), nullable=False)
#     source = Column(String(50), nullable=False)
#     raw_text = Column(Text, nullable=True)
#     embedding = Column(String, nullable=True)
#     processing_status = Column(String(50), default="pending", nullable=False)
#     metadata_json = Column(JSONB, default={}, nullable=True)
#     created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
#     updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
#     # cases = relationship("Case", secondary=document_cases, back_populates="documents")
#
# 
# class Beneficiary(Base):
#     """
#     Beneficiary entity representing individuals receiving aid/services.
#     """
#     __tablename__ = "beneficiaries"
#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
#     full_name = Column(String(255), nullable=False, index=True)
#     contact_info = Column(JSONB, default={}, nullable=True)
#     embedding = Column(String, nullable=True)
#     created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
#     updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
#     # cases = relationship("Case", back_populates="beneficiary", cascade="all,delete")
#
#
# class Case(Base):
#     """
#     Case entity representing processed documents linked to beneficiaries.
#     """
#     __tablename__ = "cases"
#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
#     beneficiary_id = Column(UUID(as_uuid=True), ForeignKey("beneficiaries.id", ondelete="CASCADE"), nullable=False)
#     case_type = Column(String(100), nullable=True)
#     amount = Column(DECIMAL(10, 2), nullable=True)
#     case_date = Column(DateTime, nullable=True)
#     summary = Column(Text, nullable=True)
#     status = Column(String(50), default="open", nullable=False)
#     embedding = Column(String, nullable=True)
#     created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
#     updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
#     # beneficiary = relationship("Beneficiary", back_populates="cases")
#     # documents = relationship("Document", secondary=document_cases, back_populates="cases")
#
# ============================================================================
# END OF PHASE 2 FULL MODELS (DEFERRED)
# ============================================================================
