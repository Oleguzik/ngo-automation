"""
Pydantic schemas for request/response validation.
Defines data structures for API endpoints with automatic validation.

PHASE 1: Organization, Project schemas (✅ Active)
PHASE 2 Lite: Expense schemas (✅ Active MVP)
PHASE 2 Full: Document, Beneficiary, Case schemas (⏸️ Deferred - commented out below)
"""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, validator, field_validator, ConfigDict
from datetime import datetime, date
from typing import Optional, List, Literal
from decimal import Decimal
from enum import Enum
from uuid import UUID
import re


# ========== Organization Schemas ==========

class OrganizationBase(BaseModel):
    """Base schema with common organization fields"""
    name: str = Field(..., min_length=1, max_length=255, description="Organization name")
    email: EmailStr = Field(..., description="Contact email address")
    country: Optional[str] = Field(None, max_length=100, description="Country of operation")
    description: Optional[str] = Field(None, description="Detailed description")


class OrganizationCreate(OrganizationBase):
    """
    Schema for creating new organization.
    
    Example:
        {
            "name": "Climate Action NGO",
            "email": "contact@climateaction.org",
            "country": "Germany",
            "description": "Working on climate change solutions"
        }
    """
    pass


class OrganizationUpdate(BaseModel):
    """
    Schema for updating organization (all fields optional).
    
    Example:
        {
            "country": "France",
            "description": "Updated description"
        }
    """
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    country: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None


class OrganizationResponse(OrganizationBase):
    """
    Schema for organization response (includes generated fields).
    
    Example:
        {
            "id": 1,
            "name": "Climate Action NGO",
            "email": "contact@climateaction.org",
            "country": "Germany",
            "description": "Working on climate change solutions",
            "is_active": true,
            "created_at": "2025-12-23T10:00:00",
            "updated_at": "2025-12-23T10:00:00"
        }
    """
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        """Enable conversion from ORM models to Pydantic models"""
        from_attributes = True


class OrganizationWithProjects(OrganizationResponse):
    """
    Schema for organization with all related projects.
    
    Example:
        {
            "id": 1,
            "name": "Climate Action NGO",
            ...
            "projects": [
                {"id": 1, "name": "Solar Panel Project", ...},
                {"id": 2, "name": "Tree Planting", ...}
            ]
        }
    """
    projects: List["ProjectResponse"] = []


# ========== Project Schemas ==========

class ProjectBase(BaseModel):
    """Base schema with common project fields"""
    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    description: Optional[str] = Field(None, description="Project description")
    organization_id: int = Field(..., gt=0, description="ID of parent organization")
    status: str = Field(default="active", max_length=50, description="Project status")


class ProjectCreate(ProjectBase):
    """
    Schema for creating new project.
    
    Example:
        {
            "name": "Solar Panel Installation",
            "description": "Installing solar panels in rural areas",
            "organization_id": 1,
            "status": "active"
        }
    """
    pass


class ProjectUpdate(BaseModel):
    """
    Schema for updating project (all fields optional).
    
    Example:
        {
            "status": "completed",
            "description": "Successfully completed"
        }
    """
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    organization_id: Optional[int] = Field(None, gt=0)
    status: Optional[str] = Field(None, max_length=50)


class ProjectResponse(ProjectBase):
    """
    Schema for project response (includes generated fields).
    
    Example:
        {
            "id": 1,
            "name": "Solar Panel Installation",
            "description": "Installing solar panels in rural areas",
            "organization_id": 1,
            "status": "active",
            "is_active": true,
            "created_at": "2025-12-23T10:00:00",
            "updated_at": "2025-12-23T10:00:00"
        }
    """
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        """Enable conversion from ORM models to Pydantic models"""
        from_attributes = True


class ProjectWithOrganization(ProjectResponse):
    """
    Schema for project with parent organization details.
    
    Example:
        {
            "id": 1,
            "name": "Solar Panel Installation",
            ...
            "organization": {
                "id": 1,
                "name": "Climate Action NGO",
                "email": "contact@climateaction.org",
                ...
            }
        }
    """
    organization: OrganizationResponse


# ============================================================================
# PHASE 2 LITE: Expense Schemas (MVP - Expenditure Tracking)
# ============================================================================

class PaymentMethodEnum(str, Enum):
    """Payment method enumeration"""
    CASH = "cash"
    CARD = "card"
    CHECK = "check"
    TRANSFER = "transfer"
    OTHER = "other"


class DocumentTypeEnum(str, Enum):
    """Type of source document for expense"""
    RECEIPT = "receipt"                # Store receipt
    INVOICE = "invoice"                # Service invoice
    BANK_TRANSFER = "bank_transfer"    # Bank transaction
    KONTOAUSZUG = "kontoauszug"        # German bank statement
    MANUAL_ENTRY = "manual_entry"      # No document
    OTHER = "other"


class ProductLineItem(BaseModel):
    """Single line item in itemized expense"""
    name: str = Field(..., min_length=1, max_length=255, description="Product/service name")
    amount: Decimal = Field(..., gt=0, description="Unit price")
    quantity: Optional[int] = Field(default=1, ge=1, description="Quantity")
    unit: Optional[str] = Field(default=None, max_length=50, description="Unit (kg, hours, etc.)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Office Supplies - Pens",
                "amount": 25.50,
                "quantity": 1,
                "unit": "box"
            }
        }


# ============================================================================
# PHASE 2 LITE: Expense Schemas (DEPRECATED - Use Transaction schemas)
# ============================================================================
# NOTE: Expense schemas have been removed and consolidated into Transaction schemas
# See TransactionCreate, TransactionResponse, etc. with transaction_type='expense'


# ============================================================================
# PHASE 2 FULL: Deferred Schemas (COMMENTED OUT)
# ============================================================================
# When implementing Phase 2 Full, uncomment and expand:
# - DocumentBase, DocumentCreate, DocumentResponse
# - BeneficiaryBase, BeneficiaryCreate, BeneficiaryResponse
# - CaseBase, CaseCreate, CaseResponse
# See docs/PHASE2_COMPLETE_SPECIFICATION.md for full details

# ============================================================================
# Pydantic v2 Forward Reference Resolution
# ============================================================================
# Rebuild models after all classes are defined to resolve forward references
OrganizationWithProjects.model_rebuild()
# ============================================================================


# ============================================================================
# PHASE 3: Cost & Profit MVP Schemas
# ============================================================================

# ========== Cost Category Schemas ==========

class CostCategoryBase(BaseModel):
    """Base schema for cost categories"""
    name: str = Field(..., min_length=1, max_length=255, description="Category name")
    description: Optional[str] = Field(None, description="Category description")


class CostCategoryCreate(CostCategoryBase):
    """Schema for creating cost category"""
    pass


class CostCategoryResponse(CostCategoryBase):
    """Schema for cost category response"""
    id: int
    organization_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ========== Profit Record Schemas ==========

class DonorInfo(BaseModel):
    """Donor/payer information"""
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    organization: Optional[str] = None
    country: Optional[str] = None


class ProfitRecordBase(BaseModel):
    """Base schema for profit records"""
    source: str = Field(..., max_length=100, description="Revenue source (donation, grant, sales, etc.)")
    amount: Decimal = Field(..., gt=0, description="Revenue amount")
    currency: str = Field(default="EUR", max_length=3, description="Currency code")
    received_date: date = Field(..., description="Date revenue was received")
    description: str = Field(..., min_length=1, max_length=500, description="Revenue description")
    reference: Optional[str] = Field(None, max_length=255, description="External reference/transaction ID")
    donor_info: Optional[DonorInfo] = Field(None, description="Donor/payer information")
    notes: Optional[str] = Field(None, description="Additional notes")


class ProfitRecordCreate(ProfitRecordBase):
    """Schema for creating profit record"""
    project_id: Optional[int] = Field(None, description="Optional project linkage")


class ProfitRecordUpdate(BaseModel):
    """Schema for updating profit record"""
    source: Optional[str] = None
    amount: Optional[Decimal] = None
    received_date: Optional[date] = None
    description: Optional[str] = None
    reference: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class ProfitRecordResponse(ProfitRecordBase):
    """Schema for profit record response"""
    id: UUID
    organization_id: int
    project_id: Optional[int]
    status: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ========== Document Processing Schemas ==========

class ExtractedCostData(BaseModel):
    """Extracted cost data from document via OpenAI"""
    date: Optional[str] = None
    vendor: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = "EUR"
    items: Optional[List["ExtractedItem"]] = None
    confidence: Optional[float] = Field(None, ge=0, le=1)  # 0.0 to 1.0


class TransactionItem(BaseModel):
    """Individual transaction for bank statements/multi-transaction documents"""
    date: Optional[str] = None
    description: Optional[str] = None
    amount: Optional[Decimal] = None

    @field_validator("amount", mode="before")
    @classmethod
    def _coerce_amount(cls, v):
        """Coerce amounts into Decimal."""
        if v is None:
            return v
        if isinstance(v, (int, float, Decimal)):
            return Decimal(str(v))
        s = str(v).strip()
        s = s.replace("€", "").replace(",", ".")
        s = re.sub(r"[^0-9.\-]", "", s)
        if s == "":
            return Decimal("0")
        return Decimal(s)


class ExtractedProfitData(BaseModel):
    """Extracted revenue/profit data from document via OpenAI"""
    date: Optional[str] = None
    source: Optional[str] = None  # donation, grant, sales, service_fee, bank_transfer, etc.
    amount: Optional[Decimal] = None
    currency: Optional[str] = "EUR"
    donor_name: Optional[str] = None
    description: Optional[str] = None
    reference: Optional[str] = None
    transaction_items: Optional[List["TransactionItem"]] = None  # For bank statements
    confidence: Optional[float] = Field(None, ge=0, le=1)


class ExtractedItem(BaseModel):
    """Typed line item for extracted cost data."""
    name: str = Field(..., min_length=1, max_length=255)
    amount: Decimal = Field(..., description="Line total (not unit price)")
    quantity: Optional[Decimal] = Field(default=None)
    unit: Optional[str] = Field(default=None, max_length=50)

    @field_validator("amount", mode="before")
    @classmethod
    def _coerce_amount(cls, v):
        """Coerce amounts like '€8.00', '8,00', ' 8.0 ' into Decimal."""
        if v is None:
            return v
        if isinstance(v, (int, float, Decimal)):
            return Decimal(str(v))
        s = str(v).strip()
        s = s.replace("€", "").replace(",", ".")
        s = re.sub(r"[^0-9.\-]", "", s)
        if s == "":
            return Decimal("0")
        return Decimal(s)

    @field_validator("quantity", mode="before")
    @classmethod
    def _coerce_quantity(cls, v):
        """Coerce quantities like '2.5', '1' to Decimal if provided."""
        if v is None:
            return v
        if isinstance(v, (int, float, Decimal)):
            return Decimal(str(v))
        s = str(v).strip()
        s = s.replace(",", ".")
        s = re.sub(r"[^0-9.\-]", "", s)
        if s == "":
            return None
        return Decimal(s)


# Rebuild forward references now that ExtractedItem and TransactionItem exist
ExtractedCostData.model_rebuild()
ExtractedProfitData.model_rebuild()


class DocumentProcessingBase(BaseModel):
    """Base schema for document processing"""
    file_name: str = Field(..., description="Original filename")
    file_type: str = Field(..., max_length=50, description="File type (pdf, image, xlsx, csv)")
    file_size: int = Field(..., gt=0, description="File size in bytes")


class DocumentProcessingCreate(DocumentProcessingBase):
    """Schema for creating document processing record"""
    pass


class DocumentProcessingResponse(DocumentProcessingBase):
    """Schema for document processing response"""
    id: UUID
    organization_id: int
    raw_text: Optional[str]
    extracted_data: Optional[dict]  # Can contain cost or profit data
    processing_status: str  # pending, processing, completed, failed
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ========== PHASE 5: DocumentChunk Schemas (RAG Foundation) ==========

class DocumentChunkBase(BaseModel):
    """
    Base schema for document chunk (text with embedding).
    
    From spec (00-spec-rag-implementation.md):
    - chunk_text: ~500 tokens (tunable, ~2000 chars)
    - embedding: 1536-dimensional vector (OpenAI text-embedding-3-small)
    - chunk_metadata: flexible JSON (page_number, section, language)
    - chunk_index: sequential position in document
    """
    chunk_text: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Text content of chunk (~500 tokens max)"
    )
    chunk_index: int = Field(
        ...,
        ge=0,
        description="Sequential position of chunk within document (0, 1, 2, ...)"
    )
    chunk_metadata: Optional[dict] = Field(
        default=None,
        description="Optional metadata (page_number, section, language, etc.)"
    )


class DocumentChunkCreate(DocumentChunkBase):
    """
    Schema for creating document chunk with embedding.
    
    Note: embedding is generated by EmbeddingService, not provided by client.
    Use this schema when creating chunks from uploaded document.
    
    Example:
        {
            "chunk_text": "This is the first chunk of text extracted from a document...",
            "chunk_index": 0,
            "chunk_metadata": {"page_number": 1, "section": "Introduction"}
        }
    """
    embedding: Optional[List[float]] = Field(
        default=None,
        description="Pre-generated embedding (1536 dims). If None, will be generated by service."
    )


class DocumentChunkRead(BaseModel):
    """
    Schema for reading document chunk from database.
    
    Note: embedding is omitted for API responses (too large).
    Use /search endpoint for semantic queries with embedding-based retrieval.
    
    Example:
        {
            "id": 42,
            "document_processing_id": "550e8400-e29b-41d4-a716-446655440000",
            "chunk_text": "This is the first chunk...",
            "chunk_index": 0,
            "chunk_metadata": {"page_number": 1},
            "created_at": "2026-01-19T10:30:00",
            "updated_at": "2026-01-19T10:30:00"
        }
    """
    id: int
    document_processing_id: UUID
    chunk_text: str
    chunk_index: int
    chunk_metadata: Optional[dict]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class DocumentChunkWithSimilarity(DocumentChunkRead):
    """
    Schema for chunk with similarity score (from semantic search).
    
    Used in search results to show relevance score.
    
    Example:
        {
            "id": 42,
            "document_processing_id": "550e8400-e29b-41d4-a716-446655440000",
            "chunk_text": "This is the first chunk...",
            "chunk_index": 0,
            "metadata": {"page_number": 1},
            "similarity_score": 0.85,
            "created_at": "2026-01-19T10:30:00",
            "updated_at": "2026-01-19T10:30:00"
        }
    """
    similarity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Cosine similarity score (0.0 = dissimilar, 1.0 = identical)"
    )


class DocumentChunkListResponse(BaseModel):
    """Response for listing chunks (paginated)"""
    items: List[DocumentChunkRead]
    total: int
    skip: int
    limit: int


# ========== PHASE 5: TextChunk Schemas (Chunking Service) ==========

class TextChunk(BaseModel):
    """
    Schema for text chunks produced by ChunkingService.
    
    Used for chunking long documents into embeddings-ready pieces with metadata.
    
    Attributes:
        chunk_index: Position in document (0, 1, 2, ...)
        chunk_text: The actual text content (10-2000 chars)
        token_count: Approximate token count for this chunk
        metadata: Strategy used, page number, language, etc.
    
    Example:
        {
            "chunk_index": 0,
            "chunk_text": "Long text content here...",
            "token_count": 487,
            "metadata": {
                "strategy": "fixed",
                "chunk_size_config": 500,
                "overlap_config": 50
            }
        }
    """
    chunk_index: int = Field(..., ge=0, description="Position in document (0-based)")
    chunk_text: str = Field(..., min_length=10, max_length=2000, description="Chunk text content")
    token_count: int = Field(..., gt=0, description="Approximate OpenAI token count")
    metadata: dict = Field(default_factory=dict, description="Strategy and configuration metadata")
    
    class Config:
        from_attributes = True
        json_encoders = {
            dict: lambda v: v if isinstance(v, dict) else dict(v)
        }


class ChunkingRequest(BaseModel):
    """
    Request for chunking service endpoint.
    
    Attributes:
        text: Document text to chunk (required)
        chunk_size: Target tokens per chunk (default 500, max 8191)
        overlap: Overlap between chunks in tokens (default 50)
        strategy: Chunking strategy - "fixed", "sentence", or "semantic"
        metadata: Optional metadata to include in all chunks
    
    Example:
        {
            "text": "Long document text...",
            "chunk_size": 500,
            "overlap": 50,
            "strategy": "fixed",
            "metadata": {"source": "receipt.pdf", "page": 1}
        }
    """
    text: str = Field(..., min_length=1, description="Document text to chunk")
    chunk_size: int = Field(default=500, ge=10, le=8191, description="Target chunk size in tokens")
    overlap: int = Field(default=50, ge=0, le=500, description="Token overlap between chunks")
    strategy: Literal["fixed", "sentence", "semantic"] = Field(
        default="fixed",
        description="Chunking strategy"
    )
    metadata: Optional[dict] = Field(None, description="Optional metadata for all chunks")


class ChunkingResponse(BaseModel):
    """
    Response from chunking service endpoint.
    
    Attributes:
        chunks: List of TextChunk objects
        total_chunks: Total number of chunks created
        strategy_used: Which chunking strategy was applied
        total_tokens: Total tokens across all chunks
    
    Example:
        {
            "chunks": [
                {
                    "chunk_index": 0,
                    "chunk_text": "...",
                    "token_count": 487,
                    "metadata": {...}
                },
                ...
            ],
            "total_chunks": 5,
            "strategy_used": "fixed",
            "total_tokens": 2345
        }
    """
    chunks: List[TextChunk] = Field(..., description="List of text chunks")
    total_chunks: int = Field(..., ge=0, description="Number of chunks created")
    strategy_used: str = Field(..., description="Chunking strategy applied")
    total_tokens: int = Field(..., ge=0, description="Total tokens across all chunks")


# ========== Phase 5B: RAG Query Schemas ==========

class SearchChunkResult(BaseModel):
    """
    Single chunk result from semantic search.
    
    Attributes:
        chunk_id: Unique chunk identifier
        chunk_text: Text content of the chunk
        similarity_score: Cosine similarity score (0-1)
        document_name: Name of source document
        metadata: Optional chunk metadata
    
    Example:
        {
            "chunk_id": "uuid-1",
            "chunk_text": "Invoice from Tech Solutions...",
            "similarity_score": 0.95,
            "document_name": "invoice_2025-12-15.pdf",
            "metadata": {"page": 1}
        }
    """
    chunk_id: UUID = Field(..., description="Unique chunk identifier")
    chunk_text: str = Field(..., min_length=1, description="Chunk text content")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Cosine similarity (0-1)")
    document_name: str = Field(..., description="Source document filename")
    metadata: Optional[dict] = Field(None, description="Chunk metadata (page, section, etc.)")
    
    class Config:
        from_attributes = True


class SearchRequest(BaseModel):
    """
    Request for semantic document search.
    
    Attributes:
        query: Search query in natural language
        top_k: Maximum number of results to return
        min_similarity: Minimum similarity threshold (0-1)
    
    Example:
        {
            "query": "tech expenses Q4",
            "top_k": 5,
            "min_similarity": 0.7
        }
    """
    query: str = Field(..., min_length=1, max_length=1000, description="Search query")
    top_k: int = Field(default=5, ge=1, le=20, description="Max results")
    min_similarity: float = Field(default=0.7, ge=0.0, le=1.0, description="Min similarity score")


class SearchResponse(BaseModel):
    """
    Response from semantic search endpoint.
    
    Attributes:
        query: Original search query
        chunks: List of matching chunks with scores
        total_results: Number of results returned
        query_time_ms: Query execution time in milliseconds
    
    Example:
        {
            "query": "tech expenses Q4",
            "chunks": [
                {
                    "chunk_id": "uuid-1",
                    "chunk_text": "...",
                    "similarity_score": 0.95,
                    "document_name": "invoice.pdf",
                    "metadata": {}
                }
            ],
            "total_results": 1,
            "query_time_ms": 1234
        }
    """
    query: str = Field(..., description="Original search query")
    chunks: List[SearchChunkResult] = Field(..., description="Matching chunks")
    total_results: int = Field(..., ge=0, description="Number of results")
    query_time_ms: Optional[float] = Field(None, description="Query time in milliseconds")


# ============================================================================
# PHASE 5B: RAG Query System - Request/Response Schemas
# ============================================================================

class SourceCitation(BaseModel):
    """Citation source for RAG answer"""
    document_name: str = Field(..., description="Name of source document")
    chunk_id: UUID = Field(..., description="ID of chunk used")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Vector similarity score")
    page_number: Optional[int] = Field(None, ge=1, description="Page number if available")
    
    class Config:
        from_attributes = True


class RAGRequest(BaseModel):
    """
    Request for RAG query endpoint.
    
    Attributes:
        question: Natural language question
        top_k: Number of chunks to retrieve
        min_similarity: Minimum similarity threshold
        temperature: LLM temperature (0.0-1.0, lower=more factual)
    
    Example:
        {
            "question": "How much did we spend on consulting in Q4?",
            "top_k": 10,
            "min_similarity": 0.7,
            "temperature": 0.1
        }
    """
    question: str = Field(..., min_length=1, max_length=1000, description="Natural language question")
    top_k: int = Field(default=10, ge=1, le=50, description="Chunks to retrieve")
    min_similarity: float = Field(default=0.7, ge=0.0, le=1.0, description="Similarity threshold")
    temperature: float = Field(default=0.1, ge=0.0, le=1.0, description="LLM temperature")


class RAGResponse(BaseModel):
    """
    Response from RAG query endpoint.
    
    Attributes:
        question: Original question
        answer: Generated answer with citations
        sources: List of source citations
        confidence: Confidence score (0-1)
        chunks_used: Number of chunks used in generation
        query_time_ms: Total query time
    
    Example:
        {
            "question": "How much did we spend on consulting in Q4?",
            "answer": "Based on uploaded documents, consulting costs were €15,000 in Q4 2025 [Source: invoice_2025-12-15.pdf, page 1]",
            "sources": [
                {
                    "document_name": "invoice_2025-12-15.pdf",
                    "chunk_id": "uuid-1",
                    "similarity_score": 0.95,
                    "page_number": 1
                }
            ],
            "confidence": 0.92,
            "chunks_used": 3,
            "query_time_ms": 2847
        }
    """
    question: str = Field(..., description="Original question")
    answer: str = Field(..., description="Generated answer with citations")
    sources: List[SourceCitation] = Field(..., description="Source citations")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Answer confidence score")
    chunks_used: int = Field(..., ge=0, description="Number of chunks used")
    query_time_ms: Optional[float] = Field(None, ge=0, description="Query time in ms")
    
    class Config:
        from_attributes = True


# ============================================================================
# PHASE 5B: Conversation History & Multi-Turn Schemas
# ============================================================================

class ConversationMessage(BaseModel):
    """
    Single message in a conversation.
    
    Attributes:
        role: "user" or "assistant"
        content: Message text
        timestamp: ISO 8601 timestamp
        sources: List of source citations (for assistant messages only)
        confidence: Confidence score (for assistant messages only)
    
    Example:
        {
            "role": "assistant",
            "content": "Q4 consulting costs were €15,000...",
            "timestamp": "2026-01-19T10:30:00Z",
            "sources": [...],
            "confidence": 0.92
        }
    """
    role: Literal["user", "assistant"] = Field(..., description="Message sender role")
    content: str = Field(..., min_length=1, description="Message text")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="ISO 8601 timestamp")
    sources: Optional[List[SourceCitation]] = Field(None, description="Source citations (assistant only)")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confidence score (assistant only)")
    
    class Config:
        from_attributes = True


class ConversationCreate(BaseModel):
    """
    Request to create a new conversation.
    
    Attributes:
        title: Conversation title/topic
    
    Example:
        {
            "title": "Q4 2025 Spending Analysis"
        }
    """
    title: str = Field(..., min_length=1, max_length=255, description="Conversation title")


class ConversationResponse(BaseModel):
    """
    Conversation with full message history.
    
    Attributes:
        id: Conversation UUID
        organization_id: Organization ID
        title: Conversation title
        messages: List of all messages in conversation
        created_at: Creation timestamp
        updated_at: Last update timestamp
    
    Example:
        {
            "id": "uuid-1",
            "organization_id": 1,
            "title": "Q4 Spending Analysis",
            "messages": [
                {
                    "role": "user",
                    "content": "How much did we spend on tech in Q4?",
                    "timestamp": "2026-01-19T10:30:00Z"
                },
                {
                    "role": "assistant",
                    "content": "Based on documents, €15,500...",
                    "timestamp": "2026-01-19T10:30:30Z",
                    "sources": [...],
                    "confidence": 0.92
                }
            ],
            "created_at": "2026-01-19T10:30:00Z",
            "updated_at": "2026-01-19T10:30:30Z"
        }
    """
    id: UUID = Field(..., description="Conversation ID")
    organization_id: int = Field(..., description="Organization ID")
    title: str = Field(..., description="Conversation title")
    messages: List[ConversationMessage] = Field(..., description="All messages")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True


class ConversationListItem(BaseModel):
    """
    Conversation summary for listing (without full message history).
    
    Attributes:
        id: Conversation UUID
        title: Conversation title
        message_count: Number of messages
        created_at: Creation timestamp
        updated_at: Last message timestamp
    
    Example:
        {
            "id": "uuid-1",
            "title": "Q4 Spending Analysis",
            "message_count": 5,
            "created_at": "2026-01-19T10:30:00Z",
            "updated_at": "2026-01-19T10:32:00Z"
        }
    """
    id: UUID = Field(..., description="Conversation ID")
    title: str = Field(..., description="Conversation title")
    message_count: int = Field(..., ge=0, description="Number of messages")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class MessageAddRequest(BaseModel):
    """
    Request to add message to conversation (user question).
    
    The endpoint will:
    1. Add user message to conversation
    2. Use RAGService to generate answer
    3. Add assistant message with answer + sources
    4. Return updated conversation
    
    Attributes:
        question: User's natural language question
        top_k: Max chunks to retrieve (optional)
        min_similarity: Similarity threshold (optional)
    
    Example:
        {
            "question": "Which vendor was the largest?",
            "top_k": 10,
            "min_similarity": 0.7
        }
    """
    question: str = Field(..., min_length=1, max_length=1000, description="User question")
    top_k: int = Field(default=10, ge=1, le=50, description="Chunks to retrieve")
    min_similarity: float = Field(default=0.7, ge=0.0, le=1.0, description="Similarity threshold")


class CostProfitSummary(BaseModel):
    """Summary of cost and profit data for analysis"""
    organization_id: int
    total_costs: Decimal
    total_profits: Decimal
    net_balance: Decimal  # profits - costs
    cost_count: int
    profit_count: int
    period_start: Optional[date]
    period_end: Optional[date]
    by_category: Optional[dict] = None  # {category: total_amount}
    top_cost_categories: Optional[List[dict]] = None
    by_project: Optional[dict] = None
    analysis: Optional[str] = None  # AI-generated analysis


class AIAnalysisRequest(BaseModel):
    """Request for AI analysis of cost/profit data"""
    project_id: Optional[int] = None
    period_days: int = Field(default=30, ge=1, le=365)
    analysis_type: Literal["summary", "detailed", "forecast", "anomaly"] = Field(
        default="summary",
        description="Type of analysis to perform"
    )
    custom_prompt: Optional[str] = None


class AIAnalysisResponse(BaseModel):
    """AI analysis response"""
    organization_id: int
    analysis_type: str
    summary: str  # Main findings
    details: dict  # Detailed breakdown
    recommendations: List[str]  # Suggested actions
    timestamp: datetime


# ============================================================================
# PHASE 4: Financial Reporting - Transaction Schemas
# ============================================================================

class TransactionLineItem(BaseModel):
    """
    Line item for transaction details (stored as JSONB).
    
    Used for itemized transaction details:
    - Receipt items (bread 2x €3.50, milk 1x €2.00)
    - Invoice lines (service €500, materials €200)
    - Purchase orders with multiple items
    
    Example:
        {
            "description": "Workshop materials",
            "quantity": 1,
            "unit": "set",
            "unit_price": Decimal("150.00"),
            "amount": Decimal("150.00")
        }
    """
    description: str = Field(..., min_length=1, max_length=255)
    quantity: Decimal = Field(..., ge=Decimal("0.01"))
    unit: Optional[str] = Field(None, max_length=50, description="Unit of measure (pcs, kg, hours, etc.)")
    unit_price: Decimal = Field(..., ge=Decimal("0.00"))
    amount: Decimal = Field(..., ge=Decimal("0.00"))
    
    @field_validator("amount")
    @classmethod
    def validate_amount_matches_quantity_price(cls, v, info):
        """Ensure amount = quantity × unit_price (with rounding tolerance)"""
        data = info.data
        if "quantity" in data and "unit_price" in data:
            calculated = data["quantity"] * data["unit_price"]
            if abs(v - calculated) > Decimal("0.01"):  # Allow 1 cent rounding
                raise ValueError(f"amount ({v}) must equal quantity × unit_price ({calculated})")
        return v


class TransactionBase(BaseModel):
    """Base schema with common transaction fields"""
    transaction_type: Literal["expense", "revenue"] = Field(default="expense", description="Type of transaction", alias="type")
    transaction_date: Optional[date] = Field(default=None, description="Date of transaction (ISO 8601), defaults to today", alias="date")
    amount: Decimal = Field(..., gt=Decimal("0"), description="Transaction amount (2 decimal places)")
    currency: str = Field(default="EUR", max_length=3, description="Currency code (ISO 4217)")
    category: Optional[str] = Field(None, max_length=100, description="GoBD category (Büromaterial, Lebensmittel, Honorare, etc.)")
    vendor_name: Optional[str] = Field(None, max_length=255, description="Payee/payer name (will be normalized)", alias="vendor")
    vat_rate: Optional[Decimal] = Field(None, ge=Decimal("0"), le=Decimal("1"), description="VAT rate (0.19 for 19%, 0.07 for 7%, 0.00 for exempt)")
    vat_amount: Optional[Decimal] = Field(None, ge=Decimal("0"), description="Calculated VAT amount")
    net_amount: Optional[Decimal] = Field(None, ge=Decimal("0"), description="Amount before VAT")
    source_type: Literal["receipt_photo", "bank_statement", "invoice_pdf", "manual_entry"] = Field(default="manual_entry", description="Source of transaction data", alias="source")
    payment_method: Optional[Literal["cash", "card", "transfer", "check", "other"]] = None
    notes: Optional[str] = Field(None, max_length=1000, description="Additional context or notes")
    line_items: Optional[List[TransactionLineItem]] = Field(None, description="Itemized transaction details")
    
    model_config = ConfigDict(populate_by_name=True)
    
    @field_validator("transaction_date", mode="before")
    @classmethod
    def set_default_date(cls, v):
        """Set default to today if not provided"""
        if v is None:
            from datetime import date as date_type
            return date_type.today()
        return v
    
    @field_validator("amount", "vat_amount", "net_amount")
    @classmethod
    def validate_decimal_precision(cls, v):
        """Ensure monetary values have max 2 decimal places"""
        if v is not None and v.as_tuple().exponent < -2:
            raise ValueError("Monetary values can have maximum 2 decimal places")
        return v
    
    @field_validator("currency")
    @classmethod
    def validate_currency_code(cls, v):
        """Ensure currency is valid ISO 4217 code"""
        valid_currencies = {"EUR", "USD", "GBP", "CHF", "PLN", "CZK", "HUF"}  # Common in Germany region
        if v.upper() not in valid_currencies:
            raise ValueError(f"Currency {v} not supported. Valid: {valid_currencies}")
        return v.upper()


class TransactionCreate(TransactionBase):
    """
    Schema for creating new transaction.
    
    Can accept organization_id and project_id in request body (convenience endpoints)
    or they can be set by the endpoint via path/query parameters.
    
    Example:
        {
            "transaction_type": "expense",
            "transaction_date": "2025-01-15",
            "amount": "43.55",
            "currency": "EUR",
            "category": "Lebensmittel",
            "vendor_name": "REWE",
            "vat_rate": "0.07",
            "vat_amount": "2.85",
            "net_amount": "40.70",
            "source_type": "receipt_photo",
            "payment_method": "card",
            "organization_id": 1,
            "project_id": 1,
            "line_items": [
                {
                    "description": "Brot Vollkorn",
                    "quantity": "2.0",
                    "unit": "pcs",
                    "unit_price": "3.50",
                    "amount": "7.00"
                }
            ]
        }
    """
    organization_id: Optional[int] = Field(None, gt=0, description="Organization ID (optional if set in endpoint)")
    project_id: Optional[int] = Field(None, gt=0, description="Project ID (optional if not required)")
    transaction_hash: Optional[str] = Field(None, min_length=16, max_length=16, description="SHA-256 fingerprint (optional, calculated if omitted)")
    document_processing_id: Optional[str] = Field(None, description="UUID of source document processing record")
    project_id: Optional[int] = Field(None, description="Project ID (optional, for project-specific expenses)")


class TransactionUpdate(BaseModel):
    """
    Schema for updating transaction (all fields optional for PATCH requests).
    
    Only fields provided will be updated.
    """
    transaction_type: Optional[Literal["expense", "revenue"]] = None
    transaction_date: Optional[date] = None
    amount: Optional[Decimal] = Field(None, gt=Decimal("0"))
    currency: Optional[str] = Field(None, max_length=3)
    category: Optional[str] = Field(None, max_length=100)
    vendor_name: Optional[str] = Field(None, max_length=255)
    vat_rate: Optional[Decimal] = Field(None, ge=Decimal("0"), le=Decimal("1"))
    vat_amount: Optional[Decimal] = Field(None, ge=Decimal("0"))
    net_amount: Optional[Decimal] = Field(None, ge=Decimal("0"))
    source_type: Optional[Literal["receipt_photo", "bank_statement", "invoice_pdf", "manual_entry"]] = None
    payment_method: Optional[Literal["cash", "card", "transfer", "check", "other"]] = None
    notes: Optional[str] = Field(None, max_length=1000)
    line_items: Optional[List[TransactionLineItem]] = None
    is_duplicate: Optional[bool] = Field(None, description="Mark as duplicate if manually detected")
    duplicate_of: Optional[int] = Field(None, description="ID of original transaction if duplicate")


class TransactionResponse(TransactionBase):
    """
    Schema for transaction API response.
    
    Includes all database fields including IDs, timestamps, and deduplication info.
    """
    id: int
    organization_id: int
    project_id: Optional[int]
    transaction_hash: str
    is_duplicate: bool = Field(default=False, description="Whether this is a duplicate transaction")
    duplicate_of: Optional[int] = Field(None, description="ID of original transaction (if duplicate)")
    is_active: bool = Field(default=True, description="Soft delete flag")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: lambda v: float(v)
        }


# ============================================================================
# PHASE 4: Transaction Duplicate Detection Schemas
# ============================================================================

class TransactionDuplicateBase(BaseModel):
    """Base schema for duplicate detection records"""
    similarity_score: Decimal = Field(..., ge=Decimal("0"), le=Decimal("1"), description="Similarity score (0.0 to 1.0)")
    resolution_strategy: Optional[Literal["auto_ignored", "manual_review", "merged", "false_positive"]] = Field(None, description="How duplicate was handled")


class TransactionDuplicateCreate(TransactionDuplicateBase):
    """
    Schema for creating duplicate detection record.
    
    Used when OCR/AI pipeline detects a potential duplicate transaction.
    
    Example:
        {
            "original_transaction_id": 123,
            "duplicate_transaction_id": 456,
            "similarity_score": "1.0",
            "resolution_strategy": "auto_ignored"
        }
    """
    original_transaction_id: int = Field(..., description="ID of original transaction")
    duplicate_transaction_id: int = Field(..., description="ID of duplicate transaction")


class TransactionDuplicateUpdate(BaseModel):
    """Schema for updating duplicate detection record (resolution only)"""
    resolution_strategy: Optional[Literal["auto_ignored", "manual_review", "merged", "false_positive"]] = None
    resolved_by: Optional[int] = Field(None, description="User ID who resolved (future use)")


class TransactionDuplicateResponse(TransactionDuplicateBase):
    """Response schema with database IDs and timestamps"""
    id: int
    original_transaction_id: int
    duplicate_transaction_id: int
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[int] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============================================================================
# PHASE 4: Fee Record Schemas (German Contractor Payments)
# ============================================================================

class FeeRecordBase(BaseModel):
    """Base schema for fee records"""
    contractor_name: str = Field(..., min_length=1, max_length=255, description="Contractor/volunteer name")
    contractor_id_hash: Optional[str] = Field(None, max_length=64, description="SHA-256 hashed personal ID (GDPR anonymized)")
    service_description: str = Field(..., min_length=1, max_length=1000, description="Description of service provided")
    gross_amount: Decimal = Field(..., gt=Decimal("0"), description="Payment amount before tax")
    tax_withheld: Decimal = Field(default=Decimal("0"), ge=Decimal("0"), description="Tax deducted (German tax compliance)")
    net_amount: Decimal = Field(..., ge=Decimal("0"), description="Payment after tax deduction")
    payment_date: date = Field(..., description="Date of payment (ISO 8601)")
    invoice_number: Optional[str] = Field(None, max_length=100, description="Invoice/receipt reference number")
    
    @field_validator("net_amount")
    @classmethod
    def validate_net_amount(cls, v, info):
        """Ensure net_amount = gross_amount - tax_withheld"""
        data = info.data
        if "gross_amount" in data and "tax_withheld" in data:
            expected = data["gross_amount"] - data["tax_withheld"]
            if abs(v - expected) > Decimal("0.01"):  # Allow 1 cent rounding
                raise ValueError(f"net_amount ({v}) must equal gross_amount - tax_withheld ({expected})")
        return v


class FeeRecordCreate(FeeRecordBase):
    """
    Schema for creating fee record.
    
    Used for German contractor/volunteer payments (Honorare).
    
    Example:
        {
            "contractor_name": "Max Mustermann",
            "contractor_id_hash": "a7f3b2c4...",
            "service_description": "Workshop facilitation - 3 hours @100€/hour",
            "gross_amount": "300.00",
            "tax_withheld": "0.00",
            "net_amount": "300.00",
            "payment_date": "2025-01-20",
            "invoice_number": "HON-2025-001",
            "organization_id": 1
        }
    """
    organization_id: Optional[int] = Field(None, gt=0, description="Organization ID (optional if set in endpoint)")
    transaction_id: Optional[int] = Field(None, description="Reference to payment transaction")


class FeeRecordUpdate(BaseModel):
    """Schema for updating fee record (all fields optional)"""
    contractor_name: Optional[str] = Field(None, min_length=1, max_length=255)
    contractor_id_hash: Optional[str] = Field(None, max_length=64)
    service_description: Optional[str] = Field(None, min_length=1, max_length=1000)
    gross_amount: Optional[Decimal] = Field(None, gt=Decimal("0"))
    tax_withheld: Optional[Decimal] = Field(None, ge=Decimal("0"))
    net_amount: Optional[Decimal] = Field(None, ge=Decimal("0"))
    payment_date: Optional[date] = None
    invoice_number: Optional[str] = Field(None, max_length=100)


class FeeRecordResponse(FeeRecordBase):
    """Response schema with database IDs and timestamps"""
    id: int
    organization_id: int
    transaction_id: Optional[int]
    is_active: bool = Field(default=True, description="Soft delete flag")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ============================================================================
# PHASE 4: Event Cost Schemas
# ============================================================================

class CostBreakdown(BaseModel):
    """
    Detailed cost breakdown for an event (stored as JSONB).
    
    Flexible structure for different event types:
    - venue, catering, materials, transport, equipment, etc.
    
    Example:
        {
            "venue": 300.00,
            "catering": 250.00,
            "materials": 200.00,
            "transport": 100.00,
            "equipment_rental": 50.00
        }
    """
    venue: Optional[Decimal] = Field(None, ge=Decimal("0"))
    catering: Optional[Decimal] = Field(None, ge=Decimal("0"))
    materials: Optional[Decimal] = Field(None, ge=Decimal("0"))
    transport: Optional[Decimal] = Field(None, ge=Decimal("0"))
    equipment_rental: Optional[Decimal] = Field(None, ge=Decimal("0"))
    staff: Optional[Decimal] = Field(None, ge=Decimal("0"))
    permits: Optional[Decimal] = Field(None, ge=Decimal("0"))
    other: Optional[Decimal] = Field(None, ge=Decimal("0"), description="Other miscellaneous costs")
    
    def get_total(self) -> Decimal:
        """Calculate total from all breakdown items"""
        total = Decimal("0")
        for field, value in self.__dict__.items():
            if value is not None:
                total += value
        return total


class EventCostBase(BaseModel):
    """Base schema for event cost tracking"""
    event_name: str = Field(..., min_length=1, max_length=255, description="Event or workshop name")
    event_date: date = Field(..., description="Date of event (ISO 8601)")
    total_cost: Decimal = Field(..., gt=Decimal("0"), description="Total event expenditure")
    attendee_count: Optional[int] = Field(None, ge=1, description="Number of participants (if tracked)")
    cost_per_person: Optional[Decimal] = Field(None, ge=Decimal("0"), description="Auto-calculated: total_cost / attendee_count")
    cost_breakdown: Optional[CostBreakdown] = Field(None, description="Itemized cost breakdown")
    
    @field_validator("cost_per_person")
    @classmethod
    def validate_cost_per_person(cls, v, info):
        """Ensure cost_per_person = total_cost / attendee_count"""
        data = info.data
        if "total_cost" in data and "attendee_count" in data and data["attendee_count"]:
            expected = data["total_cost"] / Decimal(str(data["attendee_count"]))
            if v is not None and abs(v - expected) > Decimal("0.01"):
                raise ValueError(f"cost_per_person ({v}) must equal total_cost / attendee_count ({expected})")
        return v


class EventCostCreate(EventCostBase):
    """
    Schema for creating event cost record.
    
    Used for tracking workshop, event, and activity expenses.
    
    Example:
        {
            "event_name": "Youth Workshop - Digital Skills",
            "event_date": "2025-01-25",
            "total_cost": "850.00",
            "attendee_count": 25,
            "cost_per_person": "34.00",
            "cost_breakdown": {
                "venue": 300.00,
                "catering": 250.00,
                "materials": 200.00,
                "transport": 100.00
            },
            "project_id": 2,
            "organization_id": 1
        }
    """
    organization_id: Optional[int] = Field(None, gt=0, description="Organization ID (optional if set in endpoint)")
    project_id: Optional[int] = Field(None, description="Project that funded this event (optional)")


class EventCostUpdate(BaseModel):
    """Schema for updating event cost (all fields optional)"""
    event_name: Optional[str] = Field(None, min_length=1, max_length=255)
    event_date: Optional[date] = None
    total_cost: Optional[Decimal] = Field(None, gt=Decimal("0"))
    attendee_count: Optional[int] = Field(None, ge=1)
    cost_per_person: Optional[Decimal] = Field(None, ge=Decimal("0"))
    cost_breakdown: Optional[CostBreakdown] = None


class EventCostResponse(EventCostBase):
    """Response schema with database IDs and timestamps"""
    id: int
    organization_id: int
    project_id: Optional[int]
    is_active: bool = Field(default=True, description="Soft delete flag")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ============================================================================
# PHASE 4: Summary and Aggregate Schemas
# ============================================================================

class FinancialSummaryByCategory(BaseModel):
    """Summary of transactions grouped by category"""
    category: str
    transaction_count: int
    total_amount: Decimal
    average_amount: Decimal
    min_amount: Decimal
    max_amount: Decimal


class FinancialSummaryResponse(BaseModel):
    """
    Comprehensive financial summary for organization.
    
    Used for dashboard and reporting endpoints.
    """
    organization_id: int
    period_start: Optional[date]
    period_end: Optional[date]
    
    # Transaction summary
    total_expenses: Decimal
    total_revenue: Decimal
    net_balance: Decimal  # revenue - expenses
    expense_count: int
    revenue_count: int
    duplicate_count: int
    
    # Category breakdown
    by_category: List[FinancialSummaryByCategory]
    
    # Project breakdown
    by_project: Optional[dict] = None  # {project_id: total_amount}
    
    # Fee summary
    total_fees_paid: Decimal = Field(default=Decimal("0"))
    total_tax_withheld: Decimal = Field(default=Decimal("0"))
    fee_records_count: int = Field(default=0)
    
    # Event summary
    total_event_cost: Decimal = Field(default=Decimal("0"))
    events_count: int = Field(default=0)
    total_event_attendees: int = Field(default=0)
    
    # Metadata
    generated_at: datetime
    
    class Config:
        from_attributes = True
