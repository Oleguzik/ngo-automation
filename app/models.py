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
from datetime import datetime, date
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
# PHASE 2 LITE: Expense Tracking (Active MVP)
# ============================================================================

class Expense(Base):
    """
    Expense entity representing organizational purchases and expenditures.
    
    PHASE 2 Lite Scope: MVP for expense data collection with itemization & audit trail
    - Itemized products/services with individual amounts
    - Purpose tracking (why the expense, source context)
    - Project linkage (which project/activity the expense belongs to)
    - Audit trail (who made payment, who received it)
    - Multiple document types (receipt, invoice, bank transfer, statement, etc.)
    - Structured validation (sum of items = total ±0.01€)
    - Foundation for analytics and reporting
    
    Attributes:
        id: Unique identifier (UUID)
        organization_id: Foreign key to Organization (required)
        project_id: Foreign key to Project (required for Phase 2 Lite)
        paid_by_id: User/member ID who made the payment (required, org member)
        paid_to_id: Volunteer or specialist ID who received payment (optional)
        products: Itemized products/services as JSON array [{name, amount, quantity, unit}]
        amount: Total purchase amount (DECIMAL for precision)
        purpose: Why this expense was made (required context field)
        purchase_date: Date of purchase (YYYY-MM-DD)
        shop_name: Name/location of seller (optional)
        payment_method: How it was paid ('cash', 'card', 'transfer', 'check', 'other')
        document_type: Source of expense data ('receipt', 'invoice', 'bank_transfer', 'kontoauszug', 'manual_entry', 'other')
        document_link: URL or path to PDF/image of receipt (optional)
        notes: Additional notes or AI-extracted details (optional)
        status: Record status ('active', 'archived', 'disputed', etc.)
        created_at: When expense was recorded
        updated_at: Last modification time
        organization: Relationship to parent Organization
        project: Relationship to Project (what the expense was for)
    
    Data Validation:
        - organization_id is required (foreign key constraint)
        - project_id is required (links to specific project)
        - paid_by_id is required (who authorized payment)
        - amount must be positive decimal (0.00 to 999,999.99)
        - amount MUST equal sum of products ±0.01€ (tolerance for rounding)
        - purchase_date format: ISO 8601 (YYYY-MM-DD)
        - payment_method from: 'cash', 'card', 'check', 'transfer', 'other'
        - document_type from: 'receipt', 'invoice', 'bank_transfer', 'kontoauszug', 'manual_entry', 'other'
        - products: JSON array of {name, amount, quantity, unit}
        - purpose: Required string (why this expense)
    
    Notes:
        - When organization deleted, all expenses are deleted (cascade)
        - When project deleted, expenses remain but project_id becomes NULL (SET NULL)
        - Indexed on organization_id for efficient filtering by org
        - Indexed on project_id for efficient filtering by project
        - Indexed on paid_to_id for filtering volunteer payments
        - Indexed on purchase_date for date-range queries
        - status field enables soft-delete and archiving
        - paid_by_id and paid_to_id provide audit trail (who was involved)
        
    Phase 2 Lite Additions:
        - ItemIZED products with individual amounts (not just names)
        - Purpose field (required context/reason)
        - Project linkage (not just organization)
        - Audit trail (paid_by_id, paid_to_id)
        - Multiple document types (not just links)
        - Amount validation (items sum must match total)
        - Volunteer payment tracking (paid_to_id)
    
    Example:
        expense = Expense(
            organization_id=1,
            project_id=3,
            paid_by_id=5,
            paid_to_id=None,
            products=[
                {"name": "Office Supplies - Pens", "amount": 25.50, "quantity": 1, "unit": "box"},
                {"name": "Printer Paper", "amount": 15.00, "quantity": 2, "unit": "ream"}
            ],
            amount=40.50,
            purpose="Quarterly office supplies purchase for project team",
            purchase_date=date(2026, 1, 6),
            shop_name="Staples",
            payment_method="card",
            document_type="receipt",
            document_link="https://storage.example.com/receipt123.pdf",
            notes="Q1 office supplies"
        )
    """
    
    __tablename__ = "expenses"
    
    # Unique identifier (UUID for distributed systems)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4, index=True)
    
    # Foreign keys (relationships)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Audit trail (NEW) - who was involved in this transaction
    paid_by_id = Column(Integer, nullable=False)  # Org member who made/authorized payment (REQUIRED)
    paid_to_id = Column(Integer, nullable=True, index=True)  # Volunteer/specialist who received payment (OPTIONAL)
    
    # Core expense data (itemized - NEW format)
    products = Column(JSONB, default=list, nullable=False)  # [{name, amount, quantity, unit}, ...]
    amount = Column(DECIMAL(12, 2), nullable=False)  # Total amount (must equal sum of products ±0.01€)
    
    # Context and purpose (NEW) - why this expense
    purpose = Column(String(500), nullable=False)  # WHY: reason, source, context (REQUIRED)
    purchase_date = Column(Date, nullable=False, index=True)  # When purchase occurred
    
    # Vendor/recipient information
    shop_name = Column(String(255), nullable=True)  # Store/vendor/recipient name (OPTIONAL for Phase 2 Lite)
    payment_method = Column(Enum(PaymentMethod), default=PaymentMethod.CARD, nullable=False)  # How paid
    
    # Document details (NEW types)
    document_type = Column(String(50), default="manual_entry", nullable=False)  # receipt, invoice, transfer, kontoauszug, manual_entry, other
    document_link = Column(String(500), nullable=True)  # URL or file path to document
    
    # Additional metadata
    notes = Column(Text, nullable=True)  # User notes or AI-extracted details
    status = Column(String(50), default="active", nullable=False)  # active, archived, disputed, etc.
    
    # Audit timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    organization = relationship("Organization", foreign_keys=[organization_id], backref="expenses")
    project = relationship("Project", foreign_keys=[project_id], backref="expenses")
    
    def __repr__(self):
        """String representation for debugging"""
        return f"<Expense(id={self.id}, org_id={self.organization_id}, project_id={self.project_id}, amount={self.amount}€, paid_by={self.paid_by_id})>"


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
