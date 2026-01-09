"""
Pydantic schemas for request/response validation.
Defines data structures for API endpoints with automatic validation.

PHASE 1: Organization, Project schemas (✅ Active)
PHASE 2 Lite: Expense schemas (✅ Active MVP)
PHASE 2 Full: Document, Beneficiary, Case schemas (⏸️ Deferred - commented out below)
"""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, validator, field_validator
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


class ExpenseBase(BaseModel):
    """Base expense fields"""
    # Items & amount
    products: List[ProductLineItem] = Field(..., min_items=1, description="Itemized products/services")
    amount: Decimal = Field(..., gt=0, description="Total amount")
    
    # Context & purpose
    purpose: str = Field(..., min_length=1, max_length=500, description="Why this expense")
    purchase_date: date = Field(..., description="Transaction date")
    
    # Vendor/recipient
    shop_name: Optional[str] = Field(default=None, max_length=255, description="Vendor/recipient name")
    
    # Payment method & document
    payment_method: PaymentMethodEnum = Field(..., description="How paid")
    document_type: DocumentTypeEnum = Field(default=DocumentTypeEnum.MANUAL_ENTRY, description="Document source")
    document_link: Optional[str] = Field(default=None, max_length=500, description="File path/URL")
    
    # Notes
    notes: Optional[str] = Field(default=None, max_length=1000, description="Additional context")
    
    @field_validator('amount')
    @classmethod
    def validate_amount_matches_items(cls, v, info):
        """Validate total matches sum of line items (±0.01€ tolerance)"""
        if 'products' in info.data:
            products = info.data['products']
            if isinstance(products, list) and len(products) > 0:
                # Handle both ProductLineItem objects and dicts
                line_total = Decimal('0')
                for p in products:
                    if isinstance(p, dict):
                        line_total += Decimal(str(p.get('amount', 0)))
                    else:
                        line_total += p.amount
                
                tolerance = Decimal('0.01')
                if abs(v - line_total) > tolerance:
                    raise ValueError(
                        f'Total amount {v}€ does not match sum of items {line_total}€ '
                        f'(tolerance: ±0.01€)'
                    )
        return v


class ExpenseCreate(ExpenseBase):
    """Schema for creating new expense"""
    organization_id: int = Field(..., gt=0, description="Organization ID")
    project_id: int = Field(..., gt=0, description="Project ID")
    paid_by_id: Optional[int] = Field(default=None, gt=0, description="Org member who made payment (default: auth user)")
    paid_to_id: Optional[int] = Field(default=None, gt=0, description="Volunteer/specialist ID")


class ExpenseUpdate(BaseModel):
    """Schema for updating expense (all fields optional)"""
    products: Optional[List[ProductLineItem]] = None
    amount: Optional[Decimal] = Field(default=None, gt=0)
    purpose: Optional[str] = Field(default=None, min_length=1, max_length=500)
    purchase_date: Optional[date] = None
    project_id: Optional[int] = Field(default=None, gt=0)
    shop_name: Optional[str] = Field(default=None, max_length=255)
    payment_method: Optional[PaymentMethodEnum] = None
    document_type: Optional[DocumentTypeEnum] = None
    document_link: Optional[str] = Field(default=None, max_length=500)
    paid_to_id: Optional[int] = Field(default=None, gt=0)
    notes: Optional[str] = Field(default=None, max_length=1000)
    status: Optional[str] = Field(default=None, pattern="^(active|archived|disputed)$")


class ExpenseResponse(ExpenseBase):
    """Response with system-generated fields"""
    id: UUID = Field(..., description="Expense UUID")
    organization_id: int
    project_id: int
    paid_by_id: int
    paid_to_id: Optional[int]
    status: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ExpenseListResponse(BaseModel):
    """
    Schema for paginated expense list response.
    
    Example:
        {
            "items": [
                {
                    "id": "uuid-1",
                    "organization_id": 1,
                    ...
                },
                {
                    "id": "uuid-2",
                    "organization_id": 1,
                    ...
                }
            ],
            "total": 42,
            "skip": 0,
            "limit": 10
        }
    """
    items: List[ExpenseResponse] = []
    total: int = Field(..., description="Total number of expenses (across all pages)")
    skip: int = Field(default=0, description="Number of records skipped")
    limit: int = Field(default=10, description="Number of records returned")


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
    amount: Decimal = Field(..., gt=0, decimal_places=2, description="Revenue amount")
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
