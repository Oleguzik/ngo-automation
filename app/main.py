"""
FastAPI application with REST API endpoints for NGO management.
Provides CRUD operations for Organizations and Projects.
"""

from fastapi import FastAPI, Depends, HTTPException, Query, Header, Path, Body, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
import logging

from app import models, schemas, crud
from app.database import engine, get_db, Base
from app.pdf_utils import extract_text_from_pdf
from app.ai_service import AIService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize AI Service
ai_service = AIService()

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title="NGO Automation MVP",
    description="REST API for managing organizations and projects",
    version="1.0.0",
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc"  # ReDoc documentation
)

# Configure CORS (allow frontend to connect)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== Health Check ==========

@app.get("/health", tags=["Utilities"])
def health_check():
    """
    Health check endpoint to verify API is running.
    
    Returns:
        {"status": "ok"}
    """
    return {"status": "ok"}


# ========== Organization Endpoints ==========

@app.post(
    "/organizations",
    response_model=schemas.OrganizationResponse,
    status_code=201,
    tags=["Organizations"]
)
def create_organization(
    organization: schemas.OrganizationCreate,
    db: Session = Depends(get_db)
):
    """
    Create new organization.
    
    Request body:
        - name: Organization name (unique)
        - email: Contact email (unique)
        - country: Country (optional)
        - description: Description (optional)
    
    Returns:
        Created organization with id and timestamps
        
    Raises:
        409 Conflict: If email or name already exists
    """
    return crud.create_organization(db=db, organization=organization)


@app.get(
    "/organizations",
    response_model=List[schemas.OrganizationResponse],
    tags=["Organizations"]
)
def list_organizations(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(10, ge=1, le=100, description="Maximum records to return"),
    db: Session = Depends(get_db)
):
    """
    List all organizations with pagination.
    
    Query parameters:
        - skip: Number of records to skip (default: 0)
        - limit: Maximum records to return (default: 10, max: 100)
    
    Returns:
        List of organizations
    """
    return crud.get_all_organizations(db=db, skip=skip, limit=limit)


@app.get(
    "/organizations/{organization_id}",
    response_model=schemas.OrganizationWithProjects,
    tags=["Organizations"]
)
def get_organization(
    organization_id: int,
    db: Session = Depends(get_db)
):
    """
    Get organization by ID with all related projects.
    
    Path parameters:
        - organization_id: Organization ID
    
    Returns:
        Organization with list of all projects
        
    Raises:
        404 Not Found: If organization doesn't exist
    """
    db_org = crud.get_organization(db=db, organization_id=organization_id)
    if db_org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return db_org


@app.put(
    "/organizations/{organization_id}",
    response_model=schemas.OrganizationResponse,
    tags=["Organizations"]
)
def update_organization(
    organization_id: int,
    organization_update: schemas.OrganizationUpdate,
    db: Session = Depends(get_db)
):
    """
    Update organization by ID (partial update).
    
    Path parameters:
        - organization_id: Organization ID
    
    Request body:
        All fields optional - only provided fields are updated
    
    Returns:
        Updated organization
        
    Raises:
        404 Not Found: If organization doesn't exist
        409 Conflict: If updated email/name conflicts with existing record
    """
    db_org = crud.update_organization(
        db=db,
        organization_id=organization_id,
        organization_update=organization_update
    )
    if db_org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return db_org


@app.delete(
    "/organizations/{organization_id}",
    tags=["Organizations"]
)
def delete_organization(
    organization_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete organization by ID (cascade deletes all projects).
    
    Path parameters:
        - organization_id: Organization ID
    
    Returns:
        Success message
        
    Raises:
        404 Not Found: If organization doesn't exist
        
    Warning:
        All projects belonging to this organization will be deleted!
    """
    success = crud.delete_organization(db=db, organization_id=organization_id)
    if not success:
        raise HTTPException(status_code=404, detail="Organization not found")
    return {"message": f"Organization {organization_id} deleted successfully"}


# ========== Project Endpoints ==========

@app.post(
    "/projects",
    response_model=schemas.ProjectResponse,
    status_code=201,
    tags=["Projects"]
)
def create_project(
    project: schemas.ProjectCreate,
    db: Session = Depends(get_db)
):
    """
    Create new project.
    
    Request body:
        - name: Project name
        - description: Description (optional)
        - organization_id: Parent organization ID (required)
        - status: Project status (default: 'active')
    
    Returns:
        Created project with id and timestamps
        
    Raises:
        404 Not Found: If organization_id doesn't exist
    """
    return crud.create_project(db=db, project=project)


@app.get(
    "/projects",
    response_model=List[schemas.ProjectResponse],
    tags=["Projects"]
)
def list_projects(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(10, ge=1, le=100, description="Maximum records to return"),
    db: Session = Depends(get_db)
):
    """
    List all projects with pagination.
    
    Query parameters:
        - skip: Number of records to skip (default: 0)
        - limit: Maximum records to return (default: 10, max: 100)
    
    Returns:
        List of projects
    """
    return crud.get_all_projects(db=db, skip=skip, limit=limit)


@app.get(
    "/projects/{project_id}",
    response_model=schemas.ProjectWithOrganization,
    tags=["Projects"]
)
def get_project(
    project_id: int,
    db: Session = Depends(get_db)
):
    """
    Get project by ID with parent organization details.
    
    Path parameters:
        - project_id: Project ID
    
    Returns:
        Project with organization details
        
    Raises:
        404 Not Found: If project doesn't exist
    """
    db_project = crud.get_project(db=db, project_id=project_id)
    if db_project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return db_project


@app.get(
    "/organizations/{organization_id}/projects",
    response_model=List[schemas.ProjectResponse],
    tags=["Projects"]
)
def list_organization_projects(
    organization_id: int,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(10, ge=1, le=100, description="Maximum records to return"),
    db: Session = Depends(get_db)
):
    """
    List all projects for specific organization.
    
    Path parameters:
        - organization_id: Organization ID
    
    Query parameters:
        - skip: Number of records to skip (default: 0)
        - limit: Maximum records to return (default: 10, max: 100)
    
    Returns:
        List of projects for this organization
        
    Raises:
        404 Not Found: If organization doesn't exist
    """
    # Verify organization exists
    org = crud.get_organization(db=db, organization_id=organization_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    return crud.get_projects_by_organization(
        db=db,
        organization_id=organization_id,
        skip=skip,
        limit=limit
    )


@app.put(
    "/projects/{project_id}",
    response_model=schemas.ProjectResponse,
    tags=["Projects"]
)
def update_project(
    project_id: int,
    project_update: schemas.ProjectUpdate,
    db: Session = Depends(get_db)
):
    """
    Update project by ID (partial update).
    
    Path parameters:
        - project_id: Project ID
    
    Request body:
        All fields optional - only provided fields are updated
    
    Returns:
        Updated project
        
    Raises:
        404 Not Found: If project or organization_id doesn't exist
    """
    db_project = crud.update_project(
        db=db,
        project_id=project_id,
        project_update=project_update
    )
    if db_project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return db_project


@app.delete(
    "/projects/{project_id}",
    tags=["Projects"]
)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete project by ID.
    
    Path parameters:
        - project_id: Project ID
    
    Returns:
        Success message
        
    Raises:
        404 Not Found: If project doesn't exist
    """
    success = crud.delete_project(db=db, project_id=project_id)
    if not success:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"message": f"Project {project_id} deleted successfully"}


# ============= EXPENSES ENDPOINTS (Phase 2 Lite) =============

@app.post(
    "/expenses",
    response_model=schemas.ExpenseResponse,
    status_code=201,
    tags=["Expenses"]
)
async def create_expense(
    expense: schemas.ExpenseCreate,
    current_user_id: int = Header(..., description="Authenticated user ID"),
    db: Session = Depends(get_db)
) -> schemas.ExpenseResponse:
    """
    Create new expense with itemized products and audit trail.
    
    Request body:
        - products: List of {name, amount, quantity, unit}
        - amount: Total amount (must equal sum of products ±0.01€)
        - purpose: Why this expense (1-500 chars)
        - purchase_date: Transaction date
        - payment_method: cash, card, transfer, check, other
        - organization_id: Parent organization ID
        - project_id: Project ID (must belong to same org)
        - paid_by_id: Org member who made payment (default: current_user_id)
        - paid_to_id: Volunteer/specialist ID (optional)
        - document_type: receipt, invoice, bank_transfer, kontoauszug, manual_entry, other
        - shop_name: Vendor/recipient name (optional)
        - document_link: File path/URL (optional)
        - notes: Additional context (optional)
    
    Headers:
        - current-user-id: Authenticated user ID (used for paid_by_id if not provided)
    
    Returns:
        Created expense with UUID and timestamps
        
    Raises:
        404 Not Found: If organization or project doesn't exist
        422 Unprocessable Entity: If amount doesn't match sum of items (±0.01€) or validation fails
        400 Bad Request: If database constraint violated
    """
    # Set paid_by_id from authenticated user if not provided
    if not expense.paid_by_id:
        expense.paid_by_id = current_user_id
    
    db_expense = crud.create_expense(db, expense)
    return db_expense


@app.get(
    "/expenses",
    response_model=schemas.ExpenseListResponse,
    tags=["Expenses"]
)
async def list_expenses(
    skip: int = Query(0, ge=0, description="Number to skip"),
    limit: int = Query(10, ge=1, le=100, description="Number to return"),
    organization_id: Optional[int] = Query(None, description="Filter by organization"),
    project_id: Optional[int] = Query(None, description="Filter by project"),
    document_type: Optional[str] = Query(None, description="Filter by document type"),
    paid_to_id: Optional[int] = Query(None, description="Filter by volunteer/specialist"),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db)
) -> schemas.ExpenseListResponse:
    """
    List expenses with optional filtering and pagination.
    
    Query parameters:
        - skip: Number of records to skip (default: 0)
        - limit: Maximum records to return (default: 10, max: 100)
        - organization_id: Filter by organization ID (optional)
        - project_id: Filter by project ID (optional)
        - document_type: Filter by document type (optional)
        - paid_to_id: Filter by volunteer/specialist ID (optional)
        - status: Filter by status - active/archived/disputed (optional)
    
    Returns:
        Paginated list of expenses matching filters
        
    Example:
        GET /expenses?skip=0&limit=10&organization_id=1
        GET /expenses?project_id=3&document_type=receipt
    """
    expenses, total = crud.get_all_expenses(
        db,
        skip=skip,
        limit=limit,
        organization_id=organization_id,
        project_id=project_id,
        document_type=document_type,
        paid_to_id=paid_to_id,
        status=status
    )
    
    return schemas.ExpenseListResponse(
        items=expenses,
        total=total,
        skip=skip,
        limit=limit
    )


@app.get(
    "/expenses/{expense_id}",
    response_model=schemas.ExpenseResponse,
    tags=["Expenses"]
)
async def get_expense(
    expense_id: str = Path(..., description="Expense UUID"),
    db: Session = Depends(get_db)
) -> schemas.ExpenseResponse:
    """
    Get expense by ID.
    
    Path parameters:
        - expense_id: Expense UUID
    
    Returns:
        Expense object with all details and audit trail
        
    Raises:
        400 Bad Request: If UUID format is invalid
        404 Not Found: If expense doesn't exist
    """
    # Convert string to UUID
    try:
        expense_uuid = UUID(expense_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")
    
    db_expense = crud.get_expense(db, expense_uuid)
    if not db_expense:
        raise HTTPException(status_code=404, detail=f"Expense {expense_id} not found")
    
    return db_expense


@app.put("/expenses/{expense_id}", response_model=schemas.ExpenseResponse, tags=["Expenses"])
async def update_expense(
    expense_id: str = Path(..., description="Expense UUID"),
    expense_update: schemas.ExpenseUpdate = Body(...),
    db: Session = Depends(get_db)
) -> schemas.ExpenseResponse:
    """Update expense (partial update, only provided fields changed)"""
    
    # Convert string to UUID
    try:
        expense_uuid = UUID(expense_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")
    
    db_expense = crud.update_expense(db, expense_uuid, expense_update)
    if not db_expense:
        raise HTTPException(status_code=404, detail=f"Expense {expense_id} not found")
    
    return db_expense


@app.delete("/expenses/{expense_id}", status_code=204, tags=["Expenses"])
async def delete_expense(
    expense_id: str = Path(..., description="Expense UUID"),
    db: Session = Depends(get_db)
) -> None:
    """Delete expense by ID"""
    
    # Convert string to UUID
    try:
        expense_uuid = UUID(expense_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")
    
    deleted = crud.delete_expense(db, expense_uuid)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Expense {expense_id} not found")


@app.get("/organizations/{organization_id}/expenses", response_model=schemas.ExpenseListResponse, tags=["Expenses"])
async def get_organization_expenses(
    organization_id: int = Path(..., gt=0),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    project_id: Optional[int] = Query(None),
    document_type: Optional[str] = Query(None),
    paid_to_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db)
) -> schemas.ExpenseListResponse:
    """Get expenses for specific organization"""
    
    # Verify organization exists
    org = crud.get_organization(db, organization_id)
    if not org:
        raise HTTPException(status_code=404, detail=f"Organization {organization_id} not found")
    
    expenses, total = crud.get_all_expenses(
        db,
        skip=skip,
        limit=limit,
        organization_id=organization_id,
        project_id=project_id,
        document_type=document_type,
        paid_to_id=paid_to_id,
        status=status
    )
    
    return schemas.ExpenseListResponse(
        items=expenses,
        total=total,
        skip=skip,
        limit=limit
    )


# ========== Root Endpoint ==========

@app.get("/", tags=["Utilities"])
def root():
    """
    Root endpoint with API information.
    
    Returns:
        API metadata and links to documentation
    """
    return {
        "message": "NGO Automation MVP - Backend API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health"
    }

# ============================================================================
# PHASE 3: Cost & Profit MVP Endpoints with AI Integration
# ============================================================================

# ========== Cost Category Endpoints ==========

@app.post(
    "/organizations/{organization_id}/cost-categories",
    response_model=schemas.CostCategoryResponse,
    status_code=201,
    tags=["Cost Management"]
)
def create_cost_category(
    organization_id: int,
    category: schemas.CostCategoryCreate,
    db: Session = Depends(get_db)
):
    """
    Create cost category for organization.
    
    Example categories: Salaries, Rent, Utilities, Supplies, Transport, Services
    """
    # Verify organization exists
    org = crud.get_organization(db, organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    return crud.create_cost_category(db, category, organization_id)


@app.get(
    "/organizations/{organization_id}/cost-categories",
    response_model=List[schemas.CostCategoryResponse],
    tags=["Cost Management"]
)
def get_cost_categories(
    organization_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get all cost categories for organization"""
    org = crud.get_organization(db, organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    return crud.get_cost_categories(db, organization_id, skip, limit)


# ========== Profit Record Endpoints ==========

@app.post(
    "/organizations/{organization_id}/profits",
    response_model=schemas.ProfitRecordResponse,
    status_code=201,
    tags=["Profit & Revenue"]
)
def create_profit_record(
    organization_id: int,
    profit: schemas.ProfitRecordCreate,
    db: Session = Depends(get_db)
):
    """
    Create profit/revenue record.
    
    Tracks donations, grants, sales, and other income sources.
    """
    org = crud.get_organization(db, organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    return crud.create_profit_record(db, profit, organization_id)


@app.get(
    "/organizations/{organization_id}/profits",
    response_model=List[schemas.ProfitRecordResponse],
    tags=["Profit & Revenue"]
)
def get_profit_records(
    organization_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status: received, pending, disputed, cancelled"),
    db: Session = Depends(get_db)
):
    """Get all profit records for organization"""
    org = crud.get_organization(db, organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    return crud.get_profit_records(db, organization_id, skip, limit, status)


@app.get(
    "/organizations/{organization_id}/profits/{profit_id}",
    response_model=schemas.ProfitRecordResponse,
    tags=["Profit & Revenue"]
)
def get_profit_record(
    organization_id: int,
    profit_id: UUID,
    db: Session = Depends(get_db)
):
    """Get specific profit record"""
    org = crud.get_organization(db, organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    profit = crud.get_profit_record(db, profit_id, organization_id)
    if not profit:
        raise HTTPException(status_code=404, detail="Profit record not found")
    
    return profit


@app.put(
    "/organizations/{organization_id}/profits/{profit_id}",
    response_model=schemas.ProfitRecordResponse,
    tags=["Profit & Revenue"]
)
def update_profit_record(
    organization_id: int,
    profit_id: UUID,
    profit_update: schemas.ProfitRecordUpdate,
    db: Session = Depends(get_db)
):
    """Update profit record"""
    org = crud.get_organization(db, organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    profit = crud.update_profit_record(db, profit_id, profit_update, organization_id)
    if not profit:
        raise HTTPException(status_code=404, detail="Profit record not found")
    
    return profit


@app.delete(
    "/organizations/{organization_id}/profits/{profit_id}",
    status_code=204,
    tags=["Profit & Revenue"]
)
def delete_profit_record(
    organization_id: int,
    profit_id: UUID,
    db: Session = Depends(get_db)
):
    """Delete profit record"""
    org = crud.get_organization(db, organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    if not crud.delete_profit_record(db, profit_id, organization_id):
        raise HTTPException(status_code=404, detail="Profit record not found")


# ========== Cost/Profit Analysis Endpoints ==========

@app.get(
    "/organizations/{organization_id}/cost-profit-summary",
    response_model=schemas.CostProfitSummary,
    tags=["Analysis"]
)
def get_cost_profit_summary(
    organization_id: int,
    period_days: int = Query(30, ge=1, le=365, description="Period in days to analyze"),
    db: Session = Depends(get_db)
):
    """
    Get cost and profit summary for organization.
    
    Returns:
        - total_costs: Sum of all expenses in period
        - total_profits: Sum of all revenue in period
        - net_balance: profits - costs
        - cost_count: Number of expense records
        - profit_count: Number of revenue records
    """
    org = crud.get_organization(db, organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    return crud.get_cost_profit_summary(db, organization_id, period_days)


@app.post(
    "/organizations/{organization_id}/cost-profit-analysis",
    response_model=schemas.AIAnalysisResponse,
    tags=["Analysis"]
)
def analyze_cost_profit_data(
    organization_id: int,
    analysis_request: schemas.AIAnalysisRequest,
    db: Session = Depends(get_db)
):
    """
    Get AI-powered analysis of cost and profit data.
    
    Analysis types:
        - summary: Quick overview (default)
        - detailed: In-depth analysis with patterns
        - forecast: Forecast next 30 days
        - anomaly: Identify unusual spending
    
    Requires OpenAI API key configured in environment.
    """
    from app.ai_service import ai_service
    from datetime import datetime
    
    org = crud.get_organization(db, organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Get summary data
    summary = crud.get_cost_profit_summary(db, organization_id, analysis_request.period_days)
    summary_text = f"""
Cost & Profit Summary (Last {analysis_request.period_days} days):
- Total Costs: €{summary.total_costs}
- Total Profits: €{summary.total_profits}
- Net Balance: €{summary.net_balance}
- Expense Records: {summary.cost_count}
- Revenue Records: {summary.profit_count}
Period: {summary.period_start} to {summary.period_end}
"""
    
    # Generate AI analysis
    analysis_text = ai_service.analyze_cost_profit_data(
        summary_text,
        analysis_type=analysis_request.analysis_type,
        custom_prompt=analysis_request.custom_prompt
    )
    
    # Generate recommendations
    recommendations = ai_service.identify_cost_optimization(summary_text)
    
    return schemas.AIAnalysisResponse(
        organization_id=organization_id,
        analysis_type=analysis_request.analysis_type,
        summary=analysis_text,
        details={
            "total_costs": float(summary.total_costs),
            "total_profits": float(summary.total_profits),
            "net_balance": float(summary.net_balance),
            "period_days": analysis_request.period_days
        },
        recommendations=recommendations,
        timestamp=datetime.utcnow()
    )


# ========== Document Processing Endpoints (Phase 3 MVP) ==========

@app.post(
    "/organizations/{organization_id}/documents/upload",
    response_model=schemas.DocumentProcessingResponse,
    status_code=201,
    tags=["Document Processing"]
)
def upload_document_for_processing(
    organization_id: int,
    doc: schemas.DocumentProcessingCreate,
    db: Session = Depends(get_db)
):
    """
    Upload document (receipt, invoice, bank statement) for AI processing.
    
    In MVP, documents are registered but processing via OpenAI is deferred.
    Next phase: Implement actual OCR and AI extraction.
    
    File types: PDF, image, Excel, CSV
    """
    org = crud.get_organization(db, organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    return crud.create_document_processing(db, doc, organization_id)


@app.get(
    "/organizations/{organization_id}/documents",
    response_model=List[schemas.DocumentProcessingResponse],
    tags=["Document Processing"]
)
def get_organization_documents(
    organization_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get all documents uploaded to organization"""
    org = crud.get_organization(db, organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    return crud.get_organization_documents(db, organization_id, skip, limit)


@app.get(
    "/organizations/{organization_id}/documents/{document_id}",
    response_model=schemas.DocumentProcessingResponse,
    tags=["Document Processing"]
)
def get_document(
    organization_id: int,
    document_id: UUID,
    db: Session = Depends(get_db)
):
    """Get specific document and its extraction status"""
    org = crud.get_organization(db, organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    doc = crud.get_document_processing(db, document_id, organization_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return doc


@app.post(
    "/organizations/{organization_id}/documents/upload-file",
    response_model=schemas.DocumentProcessingResponse,
    status_code=201,
    tags=["Document Processing"]
)
async def upload_pdf_with_ai_extraction(
    organization_id: int,
    file: UploadFile = File(...),
    analysis_type: str = Query("cost", regex="^(cost|profit)$"),
    db: Session = Depends(get_db)
):
    """
    Upload a PDF file for AI-powered extraction and analysis.
    
    **Workflow:**
    1. Upload PDF file (receipt, invoice, bank statement, donation receipt)
    2. Extract text from PDF using PyPDF2
    3. Analyze with OpenAI GPT-4 (extract cost or profit data)
    4. Store raw text and structured data in database
    5. Return processing results
    
    **Parameters:**
    - file: PDF file to upload (required)
    - analysis_type: "cost" for expenses or "profit" for revenue (default: cost)
    
    **Returns:**
    - Document record with extracted_data (JSON) and processing_status
    
    **Example Response:**
    ```json
    {
      "id": "uuid",
      "file_name": "invoice.pdf",
      "raw_text": "INVOICE\\nDigital Solutions GmbH...",
      "extracted_data": {
        "date": "2025-12-15",
        "vendor": "Digital Solutions GmbH",
        "amount": 16570.75,
        "currency": "EUR",
        "category": "consulting",
        "confidence": 0.95
      },
      "processing_status": "completed"
    }
    ```
    """
    try:
        # Verify organization exists
        org = crud.get_organization(db, organization_id)
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        
        # Validate file type
        if not file.content_type == "application/pdf":
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid file type: {file.content_type}. Only PDF files are supported."
            )
        
        logger.info(f"Processing PDF upload: {file.filename} ({file.content_type})")
        
        # Read file bytes
        file_bytes = await file.read()
        file_size = len(file_bytes)
        
        if file_size == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")
        
        logger.info(f"File size: {file_size} bytes")
        
        # Extract text from PDF
        try:
            raw_text = extract_text_from_pdf(file_bytes)
            logger.info(f"Extracted {len(raw_text)} characters from PDF")
        except Exception as e:
            logger.error(f"PDF extraction failed: {str(e)}")
            raise HTTPException(
                status_code=422, 
                detail=f"Failed to extract text from PDF: {str(e)}"
            )
        
        if not raw_text or len(raw_text.strip()) < 10:
            raise HTTPException(
                status_code=422,
                detail="PDF appears to be empty or contains no extractable text"
            )
        
        # AI extraction based on analysis type
        try:
            if analysis_type == "cost":
                logger.info("Extracting cost/expense data with AI")
                extracted_data = ai_service.extract_cost_from_text(raw_text)
            else:  # profit
                logger.info("Extracting profit/revenue data with AI")
                extracted_data = ai_service.extract_profit_from_text(raw_text)
            
            logger.info(f"AI extraction successful: {extracted_data}")
        except Exception as e:
            logger.error(f"AI extraction failed: {str(e)}")
            # Still save document but mark as failed
            doc = models.DocumentProcessing(
                organization_id=organization_id,
                file_name=file.filename,
                file_type=file.content_type,
                file_size=file_size,
                raw_text=raw_text,
                extracted_data=None,
                processing_status="failed",
                error_message=f"AI extraction error: {str(e)}"
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)
            return doc
        
        # If extraction is empty, mark as failed with clear error
        if not extracted_data or (isinstance(extracted_data, dict) and len(extracted_data) == 0):
            doc = models.DocumentProcessing(
                organization_id=organization_id,
                file_name=file.filename,
                file_type=file.content_type,
                file_size=file_size,
                raw_text=raw_text,
                extracted_data=None,
                processing_status="failed",
                error_message="AI extraction returned empty result"
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)
            logger.warning("AI extraction returned empty result; document marked as failed")
            return doc

        # Save to database with extracted data
        doc = models.DocumentProcessing(
            organization_id=organization_id,
            file_name=file.filename,
            file_type=file.content_type,
            file_size=file_size,
            raw_text=raw_text,
            extracted_data=extracted_data,
            processing_status="completed",
            error_message=None
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        
        logger.info(f"Document saved successfully: {doc.id}")
        return doc
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")