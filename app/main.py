"""
FastAPI application with REST API endpoints for NGO management.
Provides CRUD operations for Organizations and Projects.
"""

from fastapi import FastAPI, Depends, HTTPException, Query, Header, Path, Body, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
from uuid import UUID
import logging

from app import models, schemas, crud
from app.database import engine, get_db, Base
from app.pdf_utils import extract_text_from_pdf
from app.document_utils import extract_text_from_file, get_supported_file_types
from app.ai_service import AIService
from app.embedding_service import get_embedding_service  # Phase 5D: Ollama integration

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize AI Service
ai_service = AIService()

# Create database tables from SQLAlchemy models
# (Will be managed by Alembic migrations after initial setup)
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


# ========== Exception Handlers ==========

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """
    Custom exception handler to return errors in standardized format.
    Always uses 'error' key for consistency across all error responses.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail
        }
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


# ============= EXPENSES ENDPOINTS (DEPRECATED - Use /transactions instead) =============
# NOTE: Expense model and endpoints have been consolidated into Transaction model (Phase 4)
# All expense functionality is now available through /organizations/{org_id}/transactions
# with transaction_type='expense'

@app.api_route("/expenses", methods=["POST", "GET"], status_code=410, tags=["Deprecated"])
@app.api_route("/expenses/{expense_id}", methods=["GET", "PUT", "DELETE"], status_code=410, tags=["Deprecated"])
@app.api_route("/organizations/{organization_id}/expenses", methods=["GET"], status_code=410, tags=["Deprecated"])
async def expenses_deprecated():
    """
    DEPRECATED: Expense endpoints have been consolidated into Transactions (Phase 4).
    
    Migration Guide:
        OLD: POST /expenses
        NEW: POST /organizations/{org_id}/transactions
             - Use transaction_type='expense'
             - Rename 'products' → 'line_items'
             - Rename 'shop_name' → 'vendor_name'
             - Rename 'purchase_date' → 'transaction_date'
        
        OLD: GET /expenses
        NEW: GET /organizations/{org_id}/transactions?transaction_type=expense
        
        OLD: GET /expenses/{id}
        NEW: GET /organizations/{org_id}/transactions/{id}
    
    For more details, see: docs/ARCHITECTURE_CONSISTENCY_ANALYSIS.md
    """
    raise HTTPException(
        status_code=410,
        detail={
            "error": "Endpoint deprecated",
            "message": "Expense endpoints have been consolidated into Transaction endpoints (Phase 4)",
            "migration": {
                "create": "POST /organizations/{org_id}/transactions with transaction_type='expense'",
                "list": "GET /organizations/{org_id}/transactions?transaction_type=expense",
                "get": "GET /organizations/{org_id}/transactions/{tx_id}",
                "update": "PATCH /transactions/{tx_id}",
                "delete": "Not supported (use is_active=false for GoBD compliance)"
            },
            "documentation": "docs/ARCHITECTURE_CONSISTENCY_ANALYSIS.md"
        }
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
    enable_rag: bool = Query(False, description="Enable RAG chunking and embedding (Phase 5)"),
    db: Session = Depends(get_db)
):
    """
    Upload a document (PDF, XLSX, CSV, or image) for AI-powered extraction and analysis.
    
    **Supported File Types (Phase 3 MVP Extension):**
    - PDF: Invoices, receipts, bank statements (native text extraction via PyPDF2)
    - XLSX: Excel spreadsheets with financial data (cell-by-cell extraction)
    - CSV: Comma-separated value files (bank exports, donation logs)
    - Images: PNG, JPG, JPEG, GIF, BMP, TIFF (OCR text extraction via Tesseract)
    
    **Workflow:**
    1. Upload document file (any supported format)
    2. Extract text (format-specific: PDF→PyPDF2, XLSX→openpyxl, CSV→pandas, IMG→OCR)
    3. Analyze with OpenAI GPT-4.1-mini (extract cost or profit data)
    4. Store raw text and structured data in database
    5. [Optional Phase 5] Chunk, embed, and store for RAG if enable_rag=True
    
    **Reference:**
    - Spec: docs/00-spec-phase4.md - Document Processing
    - Architecture: docs/02-architecture-phase4.md - Text Extraction Pipeline
    
    **Parameters:**
    - file: Document file to upload (required, any supported format)
    - analysis_type: "cost" for expenses or "profit" for revenue (default: cost)
    - enable_rag: Enable RAG chunking and embedding (default: false)
    
    **Returns:**
    - Document record with extracted_data (JSON) and processing_status
    - file_type shows detected format (pdf, xlsx, csv, image)
    - If enable_rag=True: includes chunks_created count in metadata
    
    **Example Response (XLSX cost extraction):**
    ```json
    {
      "id": "uuid",
      "file_name": "bank_statement_jan2026.xlsx",
      "file_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      "raw_text": "--- Sheet: Transactions ---\\nDate | Amount | Vendor\\n2026-01-05 | 2500 | AWS...",
      "extracted_data": {
        "date": "2026-01-05",
        "vendor": "AWS",
        "amount": 2500.0,
        "currency": "EUR",
        "category": "cloud_services",
        "confidence": 0.93
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
        
        # Validate file type against supported formats
        supported_types = get_supported_file_types()
        all_mime_types = []
        all_extensions = []
        for category in supported_types.values():
            all_mime_types.extend(category['mime_types'])
            all_extensions.extend(category['extensions'])
        
        file_ext = "." + file.filename.lower().split(".")[-1] if "." in file.filename else ""
        
        if file.content_type not in all_mime_types and file_ext not in all_extensions:
            supported_formats = " | ".join([f"{cat} ({', '.join(info['extensions'])})" for cat, info in supported_types.items()])
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type: {file.content_type}. Supported formats: {supported_formats}"
            )
        
        logger.info(f"Processing document upload: {file.filename} ({file.content_type})")
        
        # Read file bytes
        file_bytes = await file.read()
        file_size = len(file_bytes)
        
        if file_size == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")
        
        logger.info(f"File size: {file_size} bytes")
        
        # Extract text using universal extractor (routes to PDF, XLSX, CSV, or OCR)
        try:
            raw_text, file_format = extract_text_from_file(file_bytes, file.content_type, file.filename)
            
            if file_format == "unsupported":
                raise HTTPException(
                    status_code=422,
                    detail=f"Could not determine file format for: {file.filename}"
                )
            
            logger.info(f"Extracted {len(raw_text) if raw_text else 0} characters from {file_format.upper()}")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Text extraction failed: {str(e)}")
            raise HTTPException(
                status_code=422, 
                detail=f"Failed to extract text from document: {str(e)}"
            )
        
        if not raw_text or len(raw_text.strip()) < 10:
            raise HTTPException(
                status_code=422,
                detail=f"Document appears to be empty or contains no extractable text (format: {file_format.upper()})"
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
        
        # Phase 5: RAG processing (chunking + embedding)
        if enable_rag:
            try:
                from app.chunking_service import ChunkingService
                from app.embedding_service import get_embedding_service
                
                logger.info(f"Starting RAG processing for document {doc.id}")
                
                # Chunk the document
                chunking_service = ChunkingService()
                chunks = chunking_service.chunk_text(
                    raw_text,
                    chunk_size=500,
                    overlap=50,
                    strategy="fixed",
                    metadata={"source": file.filename, "org_id": organization_id}
                )
                logger.info(f"Created {len(chunks)} chunks for document {doc.id}")
                
                # Generate embeddings and save chunks
                embedding_service = get_embedding_service()
                saved_chunks = crud.create_document_chunks(
                    db=db,
                    document_processing_id=doc.id,
                    chunks=chunks,
                    embedding_service=embedding_service
                )
                
                logger.info(f"Saved {len(saved_chunks)} chunks with embeddings for document {doc.id}")
                
                # Update document metadata
                if doc.metadata is None:
                    doc.metadata = {}
                doc.metadata["chunks_created"] = len(saved_chunks)
                doc.metadata["embeddings_generated"] = len(saved_chunks)
                doc.metadata["rag_enabled"] = True
                doc.metadata["rag_status"] = "completed"
                
                db.add(doc)
                db.commit()
                db.refresh(doc)
                
                logger.info(f"RAG processing completed for document {doc.id}")
                
            except Exception as e:
                logger.error(f"RAG processing failed for document {doc.id}: {str(e)}")
                # Log error but don't fail the upload - document is already saved
                if doc.metadata is None:
                    doc.metadata = {}
                doc.metadata["rag_error"] = str(e)
                doc.metadata["rag_status"] = "failed"
                db.add(doc)
                db.commit()
                db.refresh(doc)
        
        return doc
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.post(
    "/documents/upload",
    response_model=schemas.DocumentProcessingResponse,
    status_code=201,
    tags=["Document Processing"]
)
async def upload_document_convenience(
    file: UploadFile = File(...),
    organization_id: int = Query(1, gt=0, description="Organization ID (defaults to 1 for testing)"),
    analysis_type: str = Query("cost", regex="^(cost|profit)$"),
    db: Session = Depends(get_db)
):
    """
    Convenience endpoint for uploading documents (primarily for testing).
    
    This endpoint wraps the full document upload workflow with sensible defaults.
    
    **Parameters:**
    - file: PDF file to upload (required)
    - organization_id: Organization ID (defaults to 1 for testing)
    - analysis_type: "cost" or "profit" (default: cost)
    
    **Returns:**
    - DocumentProcessingResponse with extracted data or error status
    """
    # Verify organization exists
    org = crud.get_organization(db, organization_id)
    if not org:
        raise HTTPException(status_code=404, detail=f"Organization {organization_id} not found")
    
    try:
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


# ========== Phase 4: Financial System Endpoints ==========
# Transaction Management

@app.post(
    "/organizations/{org_id}/transactions",
    response_model=schemas.TransactionResponse,
    status_code=201,
    tags=["Transactions"]
)
def create_transaction(
    org_id: int = Path(..., gt=0, description="Organization ID"),
    transaction: schemas.TransactionCreate = Body(...),
    db: Session = Depends(get_db)
):
    """
    Create new financial transaction (expense or revenue).
    
    Path Parameters:
        org_id: Organization ID
    
    Request Body:
        - transaction_type: "expense" or "revenue"
        - transaction_date: Date of transaction
        - amount: Transaction amount (Decimal, 2 decimals)
        - currency: Currency code (EUR, USD, etc.)
        - vendor_name: Vendor/customer name
        - category: Transaction category (Lebensmittel, Büromaterial, etc.)
        - transaction_hash: Auto-generated if not provided (SHA-256 for dedup)
        - notes: Optional notes
    
    Returns:
        Created Transaction with id, timestamps, and hash
        
    Raises:
        400: Bad Request (invalid data)
        404: Organization not found
        409: Conflict (duplicate transaction)
    """
    return crud.create_transaction(db=db, transaction=transaction, organization_id=org_id)


# ========== Convenience Endpoints (for testing without organization nesting) ==========

@app.post(
    "/transactions",
    response_model=schemas.TransactionResponse,
    status_code=201,
    tags=["Transactions"]
)
def create_transaction_convenience(
    transaction: schemas.TransactionCreate = Body(...),
    organization_id: int = Query(None, gt=0, description="Organization ID (optional if provided in body, defaults to 1 if neither provided)"),
    db: Session = Depends(get_db)
):
    """
    Convenience endpoint for creating transactions without organization nesting.
    
    This is primarily for testing and simple use cases.
    
    **Query Parameters:**
    - organization_id: Organization ID (optional if provided in body, defaults to 1)
    
    **Request Body:**
    - transaction_type: "expense" or "revenue" (optional, defaults to "expense")
    - transaction_date: Date of transaction (ISO format, optional, defaults to today)
    - amount: Transaction amount
    - currency: Currency code (optional, defaults to EUR)
    - vendor_name: Vendor/customer name (optional)
    - category: Transaction category (optional)
    - notes: Optional notes
    - organization_id: Organization ID (optional if provided as query param)
    - project_id: Project ID (optional)
    
    Returns:
        Created Transaction with id, timestamps, and hash
    """
    # Determine organization_id from body or query parameter
    final_org_id = transaction.organization_id or organization_id or 1
    
    # Verify organization exists
    org = crud.get_organization(db, final_org_id)
    if not org:
        raise HTTPException(status_code=404, detail=f"Organization {final_org_id} not found")
    
    # Update transaction with resolved organization_id
    transaction.organization_id = final_org_id
    
    return crud.create_transaction(db=db, transaction=transaction, organization_id=final_org_id)


@app.get(
    "/organizations/{org_id}/transactions",
    response_model=List[schemas.TransactionResponse],
    tags=["Transactions"]
)
def list_transactions(
    org_id: int = Path(..., gt=0, description="Organization ID"),
    skip: int = Query(0, ge=0, description="Skip N records"),
    limit: int = Query(10, ge=1, le=100, description="Max records"),
    transaction_type: Optional[str] = Query(None, description="Filter: expense or revenue"),
    category: Optional[str] = Query(None, description="Filter by category"),
    db: Session = Depends(get_db)
):
    """
    List financial transactions for organization.
    
    Query Parameters:
        skip: Pagination offset
        limit: Max records (1-100)
        transaction_type: Optional filter (expense/revenue)
        category: Optional category filter
    
    Returns:
        List of transactions sorted by date (newest first)
    """
    return crud.get_transactions_by_organization(
        db=db,
        organization_id=org_id,
        skip=skip,
        limit=limit,
        transaction_type=transaction_type,
        category=category
    )


@app.get(
    "/organizations/{org_id}/transactions/{tx_id}",
    response_model=schemas.TransactionResponse,
    tags=["Transactions"]
)
def get_transaction(
    org_id: int = Path(..., gt=0, description="Organization ID"),
    tx_id: int = Path(..., gt=0, description="Transaction ID"),
    db: Session = Depends(get_db)
):
    """
    Get specific transaction details.
    
    Returns:
        Transaction object with all details
        
    Raises:
        404: Transaction not found
    """
    tx = crud.get_transaction(db=db, transaction_id=tx_id)
    if not tx or tx.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return tx


@app.patch(
    "/transactions/{tx_id}",
    response_model=schemas.TransactionResponse,
    tags=["Transactions"]
)
def update_transaction(
    tx_id: int = Path(..., gt=0, description="Transaction ID"),
    transaction_update: schemas.TransactionUpdate = Body(...),
    db: Session = Depends(get_db)
):
    """
    Update transaction details (partial update).
    
    Request Body:
        Only include fields to update:
        - amount, category, notes, etc.
    
    Returns:
        Updated Transaction
        
    Raises:
        404: Transaction not found
    """
    tx = crud.update_transaction(db=db, transaction_id=tx_id, transaction_update=transaction_update)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return tx


@app.delete(
    "/transactions/{tx_id}",
    response_model=schemas.TransactionResponse,
    tags=["Transactions"]
)
def delete_transaction(
    tx_id: int = Path(..., gt=0, description="Transaction ID"),
    db: Session = Depends(get_db)
):
    """
    Soft delete transaction (marks as inactive).
    
    GoBD Compliant: Transaction is never removed from database, only marked inactive.
    
    Returns:
        Deleted Transaction (with is_active=False)
        
    Raises:
        404: Transaction not found
    """
    tx = crud.delete_transaction(db=db, transaction_id=tx_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return tx


@app.get(
    "/organizations/{org_id}/transactions/project/{project_id}",
    response_model=List[schemas.TransactionResponse],
    tags=["Transactions"]
)
def get_project_transactions(
    org_id: int = Path(..., gt=0, description="Organization ID"),
    project_id: int = Path(..., gt=0, description="Project ID"),
    skip: int = Query(0, ge=0, description="Skip N records"),
    limit: int = Query(10, ge=1, le=100, description="Max records"),
    db: Session = Depends(get_db)
):
    """
    List transactions for specific project.
    
    Returns:
        Transactions associated with project
    """
    return crud.get_transactions_by_project(
        db=db,
        project_id=project_id,
        skip=skip,
        limit=limit
    )


# ========== Convenience Endpoints for Testing ==========

@app.post(
    "/transactions",
    response_model=schemas.TransactionResponse,
    status_code=201,
    tags=["Transactions"]
)
def create_transaction_convenience(
    transaction: schemas.TransactionCreate = Body(...),
    organization_id: int = Query(1, gt=0, description="Organization ID (defaults to 1 for testing)"),
    db: Session = Depends(get_db)
):
    """
    Convenience endpoint for creating transactions (primarily for testing).
    
    This endpoint wraps the full transaction creation workflow with a default organization ID.
    
    **Parameters:**
    - organization_id: Organization ID (defaults to 1 for testing)
    - transaction: Transaction data in request body
    
    **Returns:**
    - TransactionResponse with created transaction data
    """
    org = crud.get_organization(db, organization_id)
    if not org:
        raise HTTPException(status_code=404, detail=f"Organization {organization_id} not found")
    
    return crud.create_transaction(db=db, transaction=transaction, organization_id=organization_id)


@app.get(
    "/transactions",
    response_model=List[schemas.TransactionResponse],
    tags=["Transactions"]
)
def list_transactions_convenience(
    skip: int = Query(0, ge=0, description="Skip N records"),
    limit: int = Query(10, ge=1, le=100, description="Max records"),
    organization_id: int = Query(1, gt=0, description="Organization ID (defaults to 1 for testing)"),
    transaction_type: Optional[str] = Query(None, description="Filter: expense or revenue"),
    category: Optional[str] = Query(None, description="Filter by category"),
    db: Session = Depends(get_db)
):
    """
    Convenience endpoint for listing transactions (primarily for testing).
    
    This endpoint wraps the full transaction listing workflow with a default organization ID.
    
    **Parameters:**
    - organization_id: Organization ID (defaults to 1 for testing)
    - skip: Pagination offset
    - limit: Max records (1-100)
    - transaction_type: Optional filter (expense/revenue)
    - category: Optional category filter
    
    **Returns:**
    - List of transactions sorted by date (newest first)
    """
    org = crud.get_organization(db, organization_id)
    if not org:
        raise HTTPException(status_code=404, detail=f"Organization {organization_id} not found")
    
    return crud.get_transactions_by_organization(
        db=db,
        organization_id=organization_id,
        skip=skip,
        limit=limit,
        transaction_type=transaction_type,
        category=category
    )


@app.get(
    "/transactions/{tx_id}",
    response_model=schemas.TransactionResponse,
    tags=["Transactions"]
)
def get_transaction_convenience(
    tx_id: int = Path(..., gt=0, description="Transaction ID"),
    db: Session = Depends(get_db)
):
    """
    Convenience endpoint for getting a single transaction (primarily for testing).
    
    This endpoint allows direct access to a transaction by ID without specifying organization.
    
    **Parameters:**
    - tx_id: Transaction ID
    
    **Returns:**
    - Transaction object with all details
    
    **Raises:**
    - 404: Transaction not found
    """
    tx = crud.get_transaction(db=db, transaction_id=tx_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return tx


# ========== Financial Reporting (Phase 4 - Excel Export) ==========

@app.get(
    "/organizations/{organization_id}/reports/financial-excel",
    response_class=StreamingResponse,
    tags=["Phase 4 - Financial Reporting"]
)
def export_financial_report_excel(
    organization_id: int = Path(..., gt=0, description="Organization ID"),
    start_date: date = Query(..., description="Report start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="Report end date (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """
    Generate and download GoBD-compliant Excel financial report.
    
    **Phase 4 Feature:** Excel export with multi-sheet workbook (Summary, Transactions)
    
    **GoBD Compliance:**
    - Immutable transaction records (soft delete only, is_active=True)
    - German date/number formatting (DD.MM.YYYY, comma as decimal separator)
    - Euro currency format (#,##0.00 €)
    - VAT breakdown by rate (19%, 7%, 0%)
    - Audit trail (transaction_hash, created_at, updated_at)
    - Deterministic filename for traceability
    
    **Workflow:**
    1. Validate organization exists and is active
    2. Query transactions for date range (only is_active=True)
    3. Calculate summary metrics (total revenue, total expenses, net position, VAT totals)
    4. Generate Excel workbook with openpyxl
    5. Return as downloadable .xlsx file
    
    **Parameters:**
    - organization_id: Organization ID (must exist and be active)
    - start_date: Report period start date (inclusive, ISO format YYYY-MM-DD)
    - end_date: Report period end date (inclusive, ISO format YYYY-MM-DD)
    
    **Returns:**
    - Excel file (.xlsx) with GoBD-compliant financial report
    - Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
    - Filename: `{org_name}_{start_date}_to_{end_date}_financial_report.xlsx`
    
    **Excel Structure:**
    - **Summary Sheet:** Organization metadata, period totals, VAT breakdown
    - **Transactions Sheet:** All transactions with full details (date, vendor, amounts, VAT, category, etc.)
    
    **Example Request:**
    ```
    GET /organizations/5/reports/financial-excel?start_date=2025-01-01&end_date=2025-12-31
    ```
    
    **Example Response Headers:**
    ```
    Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
    Content-Disposition: attachment; filename=Kinderhilfe_Deutschland_eV_2025-01-01_to_2025-12-31_financial_report.xlsx
    ```
    
    **Reference:**
    - Spec: docs/00-spec-phase4.md - Financial Reporting
    - Architecture: docs/02-architecture-phase4.md - Excel Generator
    - Implementation: docs/EXCEL_GENERATOR_READINESS_REPORT.md
    """
    try:
        # Validate date range
        if start_date > end_date:
            raise HTTPException(
                status_code=400,
                detail=f"start_date ({start_date}) must be before or equal to end_date ({end_date})"
            )
        
        logger.info(
            f"Generating Excel report for organization {organization_id}, "
            f"period {start_date} to {end_date}"
        )
        
        # Generate Excel report
        excel_buffer, filename = crud.generate_financial_report_excel(
            db=db,
            organization_id=organization_id,
            start_date=start_date,
            end_date=end_date,
            generated_by="API User"
        )
        
        logger.info(
            f"Excel report generated successfully: {filename}, "
            f"size: {excel_buffer.getbuffer().nbytes} bytes"
        )
        
        # Return as downloadable file
        return StreamingResponse(
            excel_buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except ValueError as e:
        # Organization not found or no transactions
        logger.warning(f"Excel generation failed (ValueError): {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Excel generation failed (unexpected error): {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate Excel report: {str(e)}"
        )


# Transaction Duplicate Detection & Resolution

@app.post(
    "/organizations/{org_id}/duplicates",
    response_model=schemas.TransactionDuplicateResponse,
    status_code=201,
    tags=["Duplicates"]
)
def create_duplicate_record(
    org_id: int = Path(..., gt=0, description="Organization ID"),
    duplicate: schemas.TransactionDuplicateCreate = Body(...),
    db: Session = Depends(get_db)
):
    """
    Create duplicate transaction record.
    
    Request Body:
        - original_transaction_id: Transaction ID
        - duplicate_transaction_id: Potential duplicate ID
        - similarity_score: Similarity 0.0-1.0
    
    Returns:
        Duplicate record for manual review
    """
    return crud.create_transaction_duplicate(db=db, duplicate=duplicate)


@app.get(
    "/organizations/{org_id}/duplicates",
    response_model=List[schemas.TransactionDuplicateResponse],
    tags=["Duplicates"]
)
def get_unresolved_duplicates(
    org_id: int = Path(..., gt=0, description="Organization ID"),
    skip: int = Query(0, ge=0, description="Skip N records"),
    limit: int = Query(10, ge=1, le=100, description="Max records"),
    db: Session = Depends(get_db)
):
    """
    Get unresolved duplicate transactions (dashboard queue).
    
    Returns:
        List of unresolved duplicates for manual review
    """
    return crud.get_unresolved_duplicates(
        db=db,
        organization_id=org_id,
        skip=skip,
        limit=limit
    )


@app.get(
    "/organizations/{org_id}/duplicates/{dup_id}",
    response_model=schemas.TransactionDuplicateResponse,
    tags=["Duplicates"]
)
def get_duplicate(
    org_id: int = Path(..., gt=0, description="Organization ID"),
    dup_id: int = Path(..., gt=0, description="Duplicate ID"),
    db: Session = Depends(get_db)
):
    """
    Get specific duplicate record details.
    
    Returns:
        Duplicate with original and duplicate transactions
        
    Raises:
        404: Duplicate not found
    """
    dup = crud.get_transaction_duplicate(db=db, duplicate_id=dup_id)
    if not dup:
        raise HTTPException(status_code=404, detail="Duplicate record not found")
    return dup


@app.patch(
    "/duplicates/{dup_id}",
    response_model=schemas.TransactionDuplicateResponse,
    tags=["Duplicates"]
)
def resolve_duplicate(
    dup_id: int = Path(..., gt=0, description="Duplicate ID"),
    duplicate_update: schemas.TransactionDuplicateUpdate = Body(...),
    db: Session = Depends(get_db)
):
    """
    Resolve duplicate (mark as reviewed and set strategy).
    
    Request Body:
        - resolution_strategy: "merged", "auto_ignored", "false_positive", "manual_review"
    
    Returns:
        Resolved Duplicate (with resolved_at timestamp)
        
    Raises:
        404: Duplicate not found
    """
    dup = crud.update_transaction_duplicate(
        db=db,
        duplicate_id=dup_id,
        duplicate_update=duplicate_update
    )
    if not dup:
        raise HTTPException(status_code=404, detail="Duplicate not found")
    return dup


# Fee Records & Contractor Payments

@app.post(
    "/organizations/{org_id}/fees",
    response_model=schemas.FeeRecordResponse,
    status_code=201,
    tags=["Fees"]
)
def create_fee_record(
    org_id: int = Path(..., gt=0, description="Organization ID"),
    fee: schemas.FeeRecordCreate = Body(...),
    db: Session = Depends(get_db)
):
    """
    Create contractor payment record.
    
    Request Body:
        - contractor_name: Contractor name
        - contractor_id_hash: SHA-256 hash (GDPR anonymization)
        - service_description: What service was provided
        - gross_amount: Total amount (Decimal, 2 decimals)
        - tax_withheld: Tax deducted (German compliance)
        - net_amount: Amount after tax
        - payment_date: Payment date
        - payment_method: bank_transfer, cash, check, etc.
        - payment_reference: Invoice number for tracking
    
    Returns:
        Created Fee Record with validation
        
    Raises:
        400: Invalid data (tax calculation mismatch)
        404: Organization not found
    """
    return crud.create_fee_record(db=db, fee=fee, organization_id=org_id)


@app.get(
    "/organizations/{org_id}/fees",
    response_model=List[schemas.FeeRecordResponse],
    tags=["Fees"]
)
def list_fee_records(
    org_id: int = Path(..., gt=0, description="Organization ID"),
    skip: int = Query(0, ge=0, description="Skip N records"),
    limit: int = Query(10, ge=1, le=100, description="Max records"),
    db: Session = Depends(get_db)
):
    """
    List contractor payments for organization.
    
    Returns:
        Fee records sorted by payment_date (newest first)
    """
    return crud.get_fee_records_by_organization(
        db=db,
        organization_id=org_id,
        skip=skip,
        limit=limit
    )


@app.get(
    "/organizations/{org_id}/fees/{fee_id}",
    response_model=schemas.FeeRecordResponse,
    tags=["Fees"]
)
def get_fee_record(
    org_id: int = Path(..., gt=0, description="Organization ID"),
    fee_id: int = Path(..., gt=0, description="Fee Record ID"),
    db: Session = Depends(get_db)
):
    """
    Get specific fee record details.
    
    Returns:
        Fee Record with contractor info
        
    Raises:
        404: Fee not found
    """
    fee = crud.get_fee_record(db=db, fee_id=fee_id)
    if not fee or fee.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Fee record not found")
    return fee


@app.patch(
    "/fees/{fee_id}",
    response_model=schemas.FeeRecordResponse,
    tags=["Fees"]
)
def update_fee_record(
    fee_id: int = Path(..., gt=0, description="Fee Record ID"),
    fee_update: schemas.FeeRecordUpdate = Body(...),
    db: Session = Depends(get_db)
):
    """
    Update fee record details.
    
    Returns:
        Updated Fee Record
        
    Raises:
        404: Fee not found
    """
    fee = crud.update_fee_record(db=db, fee_id=fee_id, fee_update=fee_update)
    if not fee:
        raise HTTPException(status_code=404, detail="Fee record not found")
    return fee


@app.delete(
    "/fees/{fee_id}",
    response_model=schemas.FeeRecordResponse,
    tags=["Fees"]
)
def delete_fee_record(
    fee_id: int = Path(..., gt=0, description="Fee Record ID"),
    db: Session = Depends(get_db)
):
    """
    Soft delete fee record.
    
    Returns:
        Deleted Fee Record (with is_active=False)
        
    Raises:
        404: Fee not found
    """
    fee = crud.delete_fee_record(db=db, fee_id=fee_id)
    if not fee:
        raise HTTPException(status_code=404, detail="Fee record not found")
    return fee


@app.get(
    "/organizations/{org_id}/fees/summary",
    response_model=dict,
    tags=["Fees"]
)
def get_fee_summary(
    org_id: int = Path(..., gt=0, description="Organization ID"),
    db: Session = Depends(get_db)
):
    """
    Get financial summary of contractor payments.
    
    Returns:
        {
            "total_gross": Decimal,
            "total_tax_withheld": Decimal,
            "total_net": Decimal,
            "fee_count": int
        }
    
    Use Case:
        - Tax reporting
        - Financial dashboards
        - Budget reconciliation
    """
    return crud.get_fee_summary_by_organization(db=db, organization_id=org_id)


# Event Costs & Impact Metrics

@app.post(
    "/organizations/{org_id}/events",
    response_model=schemas.EventCostResponse,
    status_code=201,
    tags=["Events"]
)
def create_event_cost(
    org_id: int = Path(..., gt=0, description="Organization ID"),
    event: schemas.EventCostCreate = Body(...),
    db: Session = Depends(get_db)
):
    """
    Create event cost record (for impact measurement).
    
    Request Body:
        - event_name: Event title
        - event_date: Date of event
        - total_cost: Total event budget (Decimal)
        - attendee_count: Number of people reached
        - location: Where event happened
        - cost_breakdown: JSONB with breakdown (venue, catering, materials, etc.)
        - notes: Optional notes
    
    Returns:
        Event Cost with auto-calculated cost_per_person
        
    Raises:
        400: Invalid data
        404: Organization not found
    """
    return crud.create_event_cost(db=db, event=event, organization_id=org_id)


@app.get(
    "/organizations/{org_id}/events",
    response_model=List[schemas.EventCostResponse],
    tags=["Events"]
)
def list_event_costs(
    org_id: int = Path(..., gt=0, description="Organization ID"),
    skip: int = Query(0, ge=0, description="Skip N records"),
    limit: int = Query(10, ge=1, le=100, description="Max records"),
    db: Session = Depends(get_db)
):
    """
    List events for organization.
    
    Returns:
        Event costs sorted by date (newest first)
    """
    return crud.get_event_costs_by_organization(
        db=db,
        organization_id=org_id,
        skip=skip,
        limit=limit
    )


@app.get(
    "/organizations/{org_id}/events/{event_id}",
    response_model=schemas.EventCostResponse,
    tags=["Events"]
)
def get_event_cost(
    org_id: int = Path(..., gt=0, description="Organization ID"),
    event_id: int = Path(..., gt=0, description="Event ID"),
    db: Session = Depends(get_db)
):
    """
    Get specific event cost details.
    
    Returns:
        Event with cost breakdown and impact metrics
        
    Raises:
        404: Event not found
    """
    event = crud.get_event_cost(db=db, event_id=event_id)
    if not event or event.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@app.patch(
    "/events/{event_id}",
    response_model=schemas.EventCostResponse,
    tags=["Events"]
)
def update_event_cost(
    event_id: int = Path(..., gt=0, description="Event ID"),
    event_update: schemas.EventCostUpdate = Body(...),
    db: Session = Depends(get_db)
):
    """
    Update event cost details.
    
    Note: If total_cost or attendee_count changes, cost_per_person is auto-recalculated.
    
    Returns:
        Updated Event
        
    Raises:
        404: Event not found
    """
    event = crud.update_event_cost(db=db, event_id=event_id, event_update=event_update)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@app.delete(
    "/events/{event_id}",
    response_model=schemas.EventCostResponse,
    tags=["Events"]
)
def delete_event_cost(
    event_id: int = Path(..., gt=0, description="Event ID"),
    db: Session = Depends(get_db)
):
    """
    Soft delete event cost record.
    
    Returns:
        Deleted Event (with is_active=False)
        
    Raises:
        404: Event not found
    """
    event = crud.delete_event_cost(db=db, event_id=event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@app.get(
    "/organizations/{org_id}/events/project/{project_id}",
    response_model=List[schemas.EventCostResponse],
    tags=["Events"]
)
def get_project_events(
    org_id: int = Path(..., gt=0, description="Organization ID"),
    project_id: int = Path(..., gt=0, description="Project ID"),
    skip: int = Query(0, ge=0, description="Skip N records"),
    limit: int = Query(10, ge=1, le=100, description="Max records"),
    db: Session = Depends(get_db)
):
    """
    List events for specific project.
    
    Returns:
        Events associated with project
    """
    return crud.get_event_costs_by_project(
        db=db,
        project_id=project_id,
        skip=skip,
        limit=limit
    )


@app.get(
    "/organizations/{org_id}/events/summary",
    response_model=dict,
    tags=["Events"]
)
def get_event_summary(
    org_id: int = Path(..., gt=0, description="Organization ID"),
    db: Session = Depends(get_db)
):
    """
    Get financial and impact summary of events.
    
    Returns:
        {
            "total_event_cost": Decimal,
            "total_attendees": int,
            "event_count": int,
            "average_cost_per_event": Decimal,
            "average_cost_per_person": Decimal
        }
    
    Use Case:
        - Impact reporting to donors
        - ROI analysis (cost per person reached)
        - Event planning budget
    """
    return crud.get_event_cost_summary_by_organization(db=db, organization_id=org_id)


# ========== Convenience Endpoints for FeeRecords (testing without organization nesting) ==========

@app.post(
    "/fee-records",
    response_model=schemas.FeeRecordResponse,
    status_code=201,
    tags=["Fee Records"]
)
def create_fee_record_convenience(
    fee: schemas.FeeRecordCreate = Body(...),
    organization_id: int = Query(None, gt=0, description="Organization ID (optional if provided in body, defaults to 1)"),
    db: Session = Depends(get_db)
):
    """
    Convenience endpoint for creating fee records without organization nesting.
    
    **Query Parameters:**
    - organization_id: Organization ID (optional if provided in body, defaults to 1)
    
    **Request Body:**
    - amount: Fee amount
    - currency: Currency code (default: EUR)
    - fee_type: Type of fee (e.g., "admin", "processing", "membership")
    - description: Fee description
    - organization_id: Organization ID (optional if provided as query param)
    """
    final_org_id = fee.organization_id or organization_id or 1
    
    org = crud.get_organization(db, final_org_id)
    if not org:
        raise HTTPException(status_code=404, detail=f"Organization {final_org_id} not found")
    
    fee.organization_id = final_org_id
    return crud.create_fee_record(db=db, fee=fee, organization_id=final_org_id)


@app.get(
    "/fee-records",
    response_model=List[schemas.FeeRecordResponse],
    tags=["Fee Records"]
)
def list_fee_records_convenience(
    organization_id: int = Query(1, gt=0, description="Organization ID (defaults to 1 for testing)"),
    skip: int = Query(0, ge=0, description="Skip N records"),
    limit: int = Query(10, ge=1, le=100, description="Max records"),
    db: Session = Depends(get_db)
):
    """
    Convenience endpoint for listing fee records without organization nesting.
    
    **Parameters:**
    - organization_id: Organization ID (defaults to 1 for testing)
    - skip: Pagination offset
    - limit: Max records (1-100)
    """
    org = crud.get_organization(db, organization_id)
    if not org:
        raise HTTPException(status_code=404, detail=f"Organization {organization_id} not found")
    
    return crud.get_fee_records_by_organization(
        db=db,
        organization_id=organization_id,
        skip=skip,
        limit=limit
    )


@app.get(
    "/fee-records/{fee_id}",
    response_model=schemas.FeeRecordResponse,
    tags=["Fee Records"]
)
def get_fee_record_convenience(
    fee_id: int = Path(..., gt=0, description="Fee Record ID"),
    db: Session = Depends(get_db)
):
    """
    Convenience endpoint for getting a single fee record (primarily for testing).
    """
    fee = crud.get_fee_record(db, fee_id)
    if not fee:
        raise HTTPException(status_code=404, detail="Fee record not found")
    return fee


@app.put(
    "/fee-records/{fee_id}",
    response_model=schemas.FeeRecordResponse,
    tags=["Fee Records"]
)
def update_fee_record_convenience(
    fee_id: int = Path(..., gt=0, description="Fee Record ID"),
    fee_update: schemas.FeeRecordUpdate = Body(...),
    db: Session = Depends(get_db)
):
    """
    Convenience endpoint for updating a fee record (primarily for testing).
    """
    updated_fee = crud.update_fee_record(db=db, fee_id=fee_id, fee_update=fee_update)
    if not updated_fee:
        raise HTTPException(status_code=404, detail="Fee record not found")
    return updated_fee


@app.delete(
    "/fee-records/{fee_id}",
    status_code=204,
    tags=["Fee Records"]
)
def delete_fee_record_convenience(
    fee_id: int = Path(..., gt=0, description="Fee Record ID"),
    db: Session = Depends(get_db)
):
    """
    Convenience endpoint for deleting a fee record (primarily for testing).
    """
    deleted = crud.delete_fee_record(db=db, fee_id=fee_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Fee record not found")
    return None


# ========== Convenience Endpoints for EventCosts (testing without organization nesting) ==========

@app.post(
    "/event-costs",
    response_model=schemas.EventCostResponse,
    status_code=201,
    tags=["Events"]
)
def create_event_cost_convenience(
    event: schemas.EventCostCreate = Body(...),
    organization_id: int = Query(None, gt=0, description="Organization ID (optional if provided in body, defaults to 1)"),
    db: Session = Depends(get_db)
):
    """
    Convenience endpoint for creating event costs without organization nesting.
    
    **Query Parameters:**
    - organization_id: Organization ID (optional if provided in body, defaults to 1)
    """
    final_org_id = event.organization_id or organization_id or 1
    
    org = crud.get_organization(db, final_org_id)
    if not org:
        raise HTTPException(status_code=404, detail=f"Organization {final_org_id} not found")
    
    event.organization_id = final_org_id
    return crud.create_event_cost(db=db, event=event, organization_id=final_org_id)


@app.get(
    "/event-costs",
    response_model=List[schemas.EventCostResponse],
    tags=["Events"]
)
def list_event_costs_convenience(
    organization_id: int = Query(1, gt=0, description="Organization ID (defaults to 1 for testing)"),
    skip: int = Query(0, ge=0, description="Skip N records"),
    limit: int = Query(10, ge=1, le=100, description="Max records"),
    db: Session = Depends(get_db)
):
    """
    Convenience endpoint for listing event costs without organization nesting.
    """
    org = crud.get_organization(db, organization_id)
    if not org:
        raise HTTPException(status_code=404, detail=f"Organization {organization_id} not found")
    
    return crud.get_event_costs_by_organization(
        db=db,
        organization_id=organization_id,
        skip=skip,
        limit=limit
    )


@app.get(
    "/event-costs/{event_id}",
    response_model=schemas.EventCostResponse,
    tags=["Events"]
)
def get_event_cost_convenience(
    event_id: int = Path(..., gt=0, description="Event Cost ID"),
    db: Session = Depends(get_db)
):
    """
    Convenience endpoint for getting a single event cost (primarily for testing).
    """
    event = crud.get_event_cost(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event cost not found")
    return event


@app.put(
    "/event-costs/{event_id}",
    response_model=schemas.EventCostResponse,
    tags=["Events"]
)
def update_event_cost_convenience(
    event_id: int = Path(..., gt=0, description="Event Cost ID"),
    event_update: schemas.EventCostUpdate = Body(...),
    db: Session = Depends(get_db)
):
    """
    Convenience endpoint for updating an event cost (primarily for testing).
    """
    updated_event = crud.update_event_cost(db=db, event_id=event_id, event_update=event_update)
    if not updated_event:
        raise HTTPException(status_code=404, detail="Event cost not found")
    return updated_event


@app.delete(
    "/event-costs/{event_id}",
    status_code=204,
    tags=["Events"]
)
def delete_event_cost_convenience(
    event_id: int = Path(..., gt=0, description="Event Cost ID"),
    db: Session = Depends(get_db)
):
    """
    Convenience endpoint for deleting an event cost (primarily for testing).
    """
    deleted = crud.delete_event_cost(db=db, event_id=event_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Event cost not found")
    return None


@app.get(
    "/event-costs/summary",
    response_model=dict,
    tags=["Events"]
)
def get_event_costs_summary_convenience(
    organization_id: int = Query(1, gt=0, description="Organization ID (defaults to 1 for testing)"),
    db: Session = Depends(get_db)
):
    """
    Convenience endpoint for getting event costs summary without organization nesting.
    """
    org = crud.get_organization(db, organization_id)
    if not org:
        raise HTTPException(status_code=404, detail=f"Organization {organization_id} not found")
    
    return crud.get_event_cost_summary_by_organization(db=db, organization_id=organization_id)


# ========== Phase 5B: RAG Query Endpoints ==========

@app.post(
    "/organizations/{organization_id}/search",
    response_model=schemas.SearchResponse,
    status_code=200,
    tags=["RAG - Semantic Search"]
)
def semantic_document_search(
    organization_id: int,
    request: schemas.SearchRequest,
    db: Session = Depends(get_db)
) -> schemas.SearchResponse:
    """
    Search for documents using semantic similarity (Phase 5B RAG).
    
    Finds document chunks most relevant to the query using vector embeddings.
    Returns chunks ranked by cosine similarity to the query.
    
    **How it works:**
    1. Embed user query using OpenAI text-embedding-3-small (1536 dims)
    2. Search document chunks in database using pgvector cosine similarity
    3. Return top-K chunks with similarity scores
    4. Can cite specific documents/pages for transparency
    
    **Parameters:**
    - query: Natural language search query (e.g., "tech expenses Q4")
    - top_k: Maximum results to return (1-20, default 5)
    - min_similarity: Minimum relevance threshold (0.0-1.0, default 0.7)
    
    **Returns:**
    - Chunks with text, source document, and similarity score
    - Metadata (page number, section, etc.) if available
    
    **Example Request:**
    ```json
    {
        "query": "How much did we spend on consulting?",
        "top_k": 5,
        "min_similarity": 0.7
    }
    ```
    
    **Example Response:**
    ```json
    {
        "query": "How much did we spend on consulting?",
        "chunks": [
            {
                "chunk_id": "uuid-1",
                "chunk_text": "Invoice from Acme Consulting - €8,000 for Q4 strategic planning",
                "similarity_score": 0.94,
                "document_name": "invoice_2025-12-01.pdf",
                "metadata": {"page": 1}
            }
        ],
        "total_results": 1,
        "query_time_ms": 1234
    }
    ```
    
    **Error Codes:**
    - 404: Organization not found
    - 400: Invalid parameters
    - 500: Search failed
    """
    import time
    
    try:
        # Verify organization exists
        org = crud.get_organization(db, organization_id)
        if not org:
            raise HTTPException(status_code=404, detail=f"Organization {organization_id} not found")
        
        logger.info(f"Semantic search: '{request.query[:50]}...' for org {organization_id}")
        
        # Generate embedding for query
        embedding_service = get_embedding_service()
        query_embedding = embedding_service.generate_embedding(request.query)
        logger.debug(f"Query embedding generated: {len(query_embedding)} dimensions")
        
        # Search similar chunks
        start_time = time.time()
        search_results = crud.search_similar_chunks(
            db=db,
            query_embedding=query_embedding,
            organization_id=organization_id,
            top_k=request.top_k,
            min_similarity=request.min_similarity
        )
        query_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        # Convert to response schema
        chunks = [
            schemas.SearchChunkResult(
                chunk_id=r["chunk_id"],
                chunk_text=r["chunk_text"],
                similarity_score=r["similarity_score"],
                document_name=r["document_name"],
                metadata=r["metadata"]
            )
            for r in search_results
        ]
        
        logger.info(f"Search completed: {len(chunks)} chunks found in {query_time:.0f}ms")
        
        return schemas.SearchResponse(
            query=request.query,
            chunks=chunks,
            total_results=len(chunks),
            query_time_ms=query_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.post(
    "/organizations/{organization_id}/rag/query",
    response_model=schemas.RAGResponse,
    status_code=200,
    tags=["RAG - Q&A"]
)
def rag_query_endpoint(
    organization_id: int,
    request: schemas.RAGRequest,
    db: Session = Depends(get_db)
) -> schemas.RAGResponse:
    """
    Ask a natural language question about uploaded financial documents (Phase 5B RAG).
    
    Uses semantic search to retrieve relevant document chunks, constructs a prompt
    with the retrieved context, and generates a factual answer using GPT-4.1-mini.
    Responses include citations to source documents for transparency.
    
    **RAG Pipeline:**
    1. Embed user question (OpenAI text-embedding-3-small)
    2. Find similar chunks (pgvector cosine similarity search)
    3. Construct prompt (system instructions + context + question)
    4. Generate answer (GPT-4.1-mini, temperature=0.1 for factuality)
    5. Parse citations (extract [Source: document, page X] references)
    6. Calculate confidence (average similarity of top chunks)
    
    **Parameters:**
    - question: Natural language question about finances
    - top_k: Max chunks to retrieve for context (1-50, default 10)
    - min_similarity: Relevance threshold (0.0-1.0, default 0.7)
    - temperature: LLM temperature (0.0=factual, 1.0=creative, default 0.1)
    
    **Returns:**
    - answer: Generated answer with source citations
    - sources: List of documents/chunks used
    - confidence: Score 0-1 based on chunk similarity
    - chunks_used: Number of chunks included in context
    - query_time_ms: Total request duration
    
    **Example Request:**
    ```json
    {
        "question": "How much did we spend on consulting services in Q4 2025?",
        "top_k": 10,
        "min_similarity": 0.7,
        "temperature": 0.1
    }
    ```
    
    **Example Response:**
    ```json
    {
        "question": "How much did we spend on consulting services in Q4 2025?",
        "answer": "Based on the uploaded documents, your organization spent €15,000 on consulting services in Q4 2025, primarily from Acme Consulting Group for strategic planning. [Source: invoice_2025-12-01.pdf, page 1]",
        "sources": [
            {
                "document_name": "invoice_2025-12-01.pdf",
                "chunk_id": "uuid-1",
                "similarity_score": 0.94,
                "page_number": 1
            }
        ],
        "confidence": 0.94,
        "chunks_used": 1,
        "query_time_ms": 2345
    }
    ```
    
    **How to Interpret Results:**
    - **confidence:** 0.9+ = very confident, 0.7-0.9 = confident, <0.7 = uncertain
    - **chunks_used:** Higher = more context considered, max 50
    - **sources:** Click to verify information in original documents
    - If answer says "I don't have that information" = no relevant chunks found
    
    **Error Codes:**
    - 404: Organization not found
    - 400: Invalid question or parameters
    - 500: RAG processing failed (embedding, search, or AI generation)
    
    **Best Practices:**
    - Ask specific questions (not "tell me everything")
    - Use dates, amounts, categories when possible
    - Try rephrasing if first answer is too generic
    - Upload additional documents if information is missing
    
    **Performance:**
    - Embedding: ~150ms (OpenAI)
    - Vector search: ~50-100ms (pgvector)
    - LLM generation: ~1000-2000ms (GPT-4.1-mini)
    - Total: typically 1.5-2.5 seconds
    
    **Cost Note:**
    - Each question incurs: embedding cost (~$0.000002) + GPT-4.1-mini cost (~$0.0001)
    - Budget ~$0.0002 per question, 5000 questions = $1/month
    """
    import time
    
    try:
        # Verify organization exists
        org = crud.get_organization(db, organization_id)
        if not org:
            raise HTTPException(status_code=404, detail=f"Organization {organization_id} not found")
        
        logger.info(
            f"RAG query received",
            extra={
                "organization_id": organization_id,
                "question": request.question[:50],
                "top_k": request.top_k
            }
        )
        
        # Use RAGService to process query
        from app.rag_service import RAGService
        
        rag_service = RAGService()
        response = rag_service.query(
            question=request.question,
            organization_id=organization_id,
            db=db,
            top_k=request.top_k,
            temperature=request.temperature,
            min_similarity=request.min_similarity
        )
        
        logger.info(
            f"RAG query completed",
            extra={
                "organization_id": organization_id,
                "chunks_used": response.chunks_used,
                "confidence": response.confidence,
                "query_time_ms": response.query_time_ms
            }
        )
        
        return response
        
    except ValueError as e:
        logger.warning(f"Invalid RAG request: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"RAG query failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"RAG processing failed: {str(e)}")


# ========== Phase 5B: Conversation Management Endpoints ==========

@app.post(
    "/organizations/{organization_id}/conversations",
    response_model=schemas.ConversationResponse,
    status_code=201,
    tags=["RAG - Conversations"]
)
def create_conversation_endpoint(
    organization_id: int,
    request: schemas.ConversationCreate,
    db: Session = Depends(get_db)
) -> schemas.ConversationResponse:
    """
    Create a new conversation for multi-turn RAG queries.
    
    A conversation is a thread of messages (user questions + AI answers) that maintains
    context across multiple turns. Each conversation belongs to an organization.
    
    Args:
        organization_id: Organization ID
        request: ConversationCreate with title
        db: Database session
        
    Returns:
        ConversationResponse with conversation ID and empty messages list
        
    Raises:
        HTTPException: 404 if organization not found, 500 if creation fails
    """
    try:
        org = crud.get_organization(db, organization_id)
        if not org:
            raise HTTPException(status_code=404, detail=f"Organization {organization_id} not found")
        logger.info(f"Creating conversation for org {organization_id}")
        conversation = crud.create_conversation(db=db, organization_id=organization_id, title=request.title)
        return schemas.ConversationResponse(
            id=conversation.id,
            organization_id=conversation.organization_id,
            title=conversation.title,
            messages=[],
            created_at=conversation.created_at,
            updated_at=conversation.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create conversation: {str(e)}")


@app.get(
    "/organizations/{organization_id}/conversations",
    response_model=List[schemas.ConversationListItem],
    status_code=200,
    tags=["RAG - Conversations"]
)
def list_conversations_endpoint(
    organization_id: int,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
) -> List[schemas.ConversationListItem]:
    """
    List all conversations for an organization.
    
    Returns paginated list of conversation summaries (no full message history to save bandwidth).
    Ordered by creation date (newest first).
    
    Args:
        organization_id: Organization ID
        skip: Number of conversations to skip (pagination)
        limit: Maximum conversations to return (max 100)
        db: Database session
        
    Returns:
        List of ConversationListItem with ID, title, message count, timestamps
        
    Raises:
        HTTPException: 404 if organization not found, 500 if listing fails
    """
    try:
        org = crud.get_organization(db, organization_id)
        if not org:
            raise HTTPException(status_code=404, detail=f"Organization {organization_id} not found")
        conversations = crud.list_conversations(db=db, organization_id=organization_id, skip=skip, limit=min(limit, 100))
        return [
            schemas.ConversationListItem(
                id=conv.id,
                title=conv.title,
                message_count=len(conv.messages) if conv.messages else 0,
                created_at=conv.created_at,
                updated_at=conv.updated_at
            )
            for conv in conversations
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list conversations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list conversations: {str(e)}")


@app.get(
    "/organizations/{organization_id}/conversations/{conversation_id}",
    response_model=schemas.ConversationResponse,
    status_code=200,
    tags=["RAG - Conversations"]
)
def get_conversation_endpoint(
    organization_id: int,
    conversation_id: UUID,
    db: Session = Depends(get_db)
) -> schemas.ConversationResponse:
    """
    Get a conversation with full message history.
    
    Retrieves conversation including all messages (user questions + AI answers with sources).
    Verifies organization isolation - conversation must belong to the specified organization.
    
    Args:
        organization_id: Organization ID
        conversation_id: Conversation ID (UUID)
        db: Database session
        
    Returns:
        ConversationResponse with all messages and metadata
        
    Raises:
        HTTPException: 404 if organization/conversation not found, 500 if retrieval fails
    """
    try:
        org = crud.get_organization(db, organization_id)
        if not org:
            raise HTTPException(status_code=404, detail=f"Organization {organization_id} not found")
        conversation = crud.get_conversation(db, conversation_id)
        if not conversation or conversation.organization_id != organization_id:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Format messages from JSONB storage to ConversationMessage schema
        messages = []
        for msg in (conversation.messages or []):
            sources = None
            if msg.get("sources"):
                sources = [
                    schemas.SourceCitation(
                        document_name=s.get("document_name"),
                        chunk_id=UUID(s.get("chunk_id")) if isinstance(s.get("chunk_id"), str) else s.get("chunk_id"),
                        similarity_score=s.get("similarity_score"),
                        page_number=s.get("page_number")
                    )
                    for s in msg.get("sources")
                ]
            messages.append(
                schemas.ConversationMessage(
                    role=msg.get("role"),
                    content=msg.get("content"),
                    timestamp=msg.get("timestamp"),
                    sources=sources,
                    confidence=msg.get("confidence")
                )
            )
        
        return schemas.ConversationResponse(
            id=conversation.id,
            organization_id=conversation.organization_id,
            title=conversation.title,
            messages=messages,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get conversation: {str(e)}")


@app.post(
    "/organizations/{organization_id}/conversations/{conversation_id}/messages",
    response_model=schemas.ConversationResponse,
    status_code=200,
    tags=["RAG - Conversations"]
)
def add_message_to_conversation_endpoint(
    organization_id: int,
    conversation_id: UUID,
    request: schemas.MessageAddRequest,
    db: Session = Depends(get_db)
) -> schemas.ConversationResponse:
    """
    Add user question to conversation and get AI answer.
    
    Multi-turn workflow:
    1. Verify organization and conversation exist
    2. Add user message to conversation
    3. Call RAGService with question and last 5 messages as context
    4. Add AI answer message with sources and confidence
    5. Return full updated conversation
    
    This enables context-aware follow-up questions. RAGService automatically injects
    previous conversation messages as context for the LLM.
    
    Args:
        organization_id: Organization ID
        conversation_id: Conversation ID (UUID)
        request: MessageAddRequest with question, top_k, min_similarity
        db: Database session
        
    Returns:
        ConversationResponse with all messages (including new user + assistant messages)
        
    Raises:
        HTTPException: 400 if invalid question, 404 if org/conversation not found,
                      500 if RAG processing fails
        
    Performance:
        ~2-3 seconds typical (dominated by RAG query and vector search)
    """
    try:
        # Verify organization exists
        org = crud.get_organization(db, organization_id)
        if not org:
            raise HTTPException(status_code=404, detail=f"Organization {organization_id} not found")
        
        # Verify conversation exists and belongs to organization
        conversation = crud.get_conversation(db, conversation_id)
        if not conversation or conversation.organization_id != organization_id:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Add user message to conversation
        conversation = crud.add_message_to_conversation(
            db=db,
            conversation_id=conversation_id,
            role="user",
            content=request.question
        )
        
        # Call RAGService to get AI answer with context from conversation
        from app.rag_service import RAGService
        rag_service = RAGService()
        rag_response = rag_service.query(
            question=request.question,
            organization_id=organization_id,
            db=db,
            top_k=request.top_k,
            min_similarity=request.min_similarity
        )
        
        # Format sources for JSONB storage
        sources = [
            {
                "document_name": source.document_name,
                "chunk_id": str(source.chunk_id),
                "similarity_score": source.similarity_score,
                "page_number": source.page_number
            }
            for source in rag_response.sources
        ]
        
        # Add AI answer message to conversation
        conversation = crud.add_message_to_conversation(
            db=db,
            conversation_id=conversation_id,
            role="assistant",
            content=rag_response.answer,
            sources=sources,
            confidence=rag_response.confidence
        )
        
        # Format messages for response
        messages = []
        for msg in (conversation.messages or []):
            sources = None
            if msg.get("sources"):
                sources = [
                    schemas.SourceCitation(
                        document_name=s.get("document_name"),
                        chunk_id=UUID(s.get("chunk_id")) if isinstance(s.get("chunk_id"), str) else s.get("chunk_id"),
                        similarity_score=s.get("similarity_score"),
                        page_number=s.get("page_number")
                    )
                    for s in msg.get("sources")
                ]
            messages.append(
                schemas.ConversationMessage(
                    role=msg.get("role"),
                    content=msg.get("content"),
                    timestamp=msg.get("timestamp"),
                    sources=sources,
                    confidence=msg.get("confidence")
                )
            )
        
        return schemas.ConversationResponse(
            id=conversation.id,
            organization_id=conversation.organization_id,
            title=conversation.title,
            messages=messages,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at
        )
    
    except ValueError as e:
        logger.warning(f"Invalid request: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add message: {str(e)}", exc_info=True)


# ============================================================================
# PHASE 5C: Agent Orchestration Endpoints
# ============================================================================

@app.post(
    "/organizations/{org_id}/agent/analyze",
    response_model=schemas.AgentTaskResponse,
    tags=["Agent Orchestration"],
    status_code=200,
    summary="Execute multi-step financial analysis",
    description="""
    Execute complex financial analysis using multi-step agent orchestration.
    
    The agent will:
    1. Generate a step-by-step execution plan
    2. Execute each step using appropriate tools (RAG, data queries, calculations)
    3. Synthesize findings into a comprehensive report
    
    **Example Objectives:**
    - "Analyze Q4 2025 spending trends and recommend budget cuts"
    - "Compare income vs expenses for the last 6 months"
    - "Identify unusual transactions and potential errors"
    - "Generate year-end financial summary with key insights"
    
    **Cost:** Typically $0.10 - $0.50 per complex analysis
    **Duration:** Usually 10-30 seconds
    """
)
def analyze_with_agent(
    org_id: int = Path(..., gt=0, description="Organization ID"),
    request: schemas.AgentAnalysisRequest = Body(...),
    db: Session = Depends(get_db)
):
    """Execute multi-step agent analysis task."""
    try:
        # Verify organization exists
        organization = crud.get_organization(db, org_id)
        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")
        
        logger.info(f"Starting agent analysis for org {org_id}: {request.objective}")
        
        # Execute agent task
        from app.orchestration_service import OrchestrationService
        orchestrator = OrchestrationService()
        
        result = orchestrator.execute_task(
            objective=request.objective,
            organization_id=org_id,
            db=db,
            context=request.context,
            max_steps=request.max_steps
        )
        
        return schemas.AgentTaskResponse(**result)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Agent analysis failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent analysis failed: {str(e)}")


@app.get(
    "/organizations/{org_id}/agent/tasks",
    response_model=schemas.AgentTaskList,
    tags=["Agent Orchestration"],
    summary="List agent tasks",
    description="List all agent analysis tasks for an organization with optional status filter."
)
def list_agent_tasks(
    org_id: int = Path(..., gt=0, description="Organization ID"),
    status: Optional[str] = Query(
        None,
        description="Filter by status (pending, planning, executing, completed, failed)"
    ),
    limit: int = Query(20, ge=1, le=100, description="Results per page"),
    offset: int = Query(0, ge=0, description="Results to skip"),
    db: Session = Depends(get_db)
):
    """List agent tasks for organization."""
    try:
        # Verify organization exists
        organization = crud.get_organization(db, org_id)
        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")
        
        # Get tasks
        tasks = crud.list_agent_tasks(db, org_id, status, limit, offset)
        total = crud.count_agent_tasks(db, org_id, status)
        
        # Convert to response format
        task_summaries = [
            schemas.AgentTaskSummary(
                task_id=str(task.id),
                objective=task.objective,
                status=task.status,
                steps_completed=task.current_step,
                total_cost=float(task.total_cost_usd),
                created_at=task.created_at,
                completed_at=task.completed_at
            )
            for task in tasks
        ]
        
        return schemas.AgentTaskList(
            tasks=task_summaries,
            total=total,
            limit=limit,
            offset=offset
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list agent tasks: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/organizations/{org_id}/agent/tasks/{task_id}",
    response_model=schemas.AgentTaskDetail,
    tags=["Agent Orchestration"],
    summary="Get agent task details",
    description="Get detailed information about a specific agent task including all execution steps."
)
def get_agent_task_details(
    org_id: int = Path(..., gt=0, description="Organization ID"),
    task_id: str = Path(..., description="Task UUID"),
    db: Session = Depends(get_db)
):
    """Get detailed agent task with all steps."""
    try:
        from uuid import UUID
        
        # Get task with steps
        task = crud.get_agent_task_with_steps(db, UUID(task_id))
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Verify organization ownership
        if task.organization_id != org_id:
            raise HTTPException(status_code=403, detail="Task belongs to different organization")
        
        # Convert steps to response format
        steps = [
            schemas.AgentStepDetail(
                step_number=step.step_number,
                step_name=step.step_name,
                action=step.action,
                status=step.status,
                input_data=step.input_data,
                output_data=step.output_data,
                error_message=step.error_message,
                tokens_used=step.tokens_used,
                cost_usd=float(step.cost_usd) if step.cost_usd else 0.0,
                duration_seconds=float(step.duration_seconds) if step.duration_seconds else None
            )
            for step in sorted(task.steps, key=lambda s: s.step_number)
        ]
        
        # Build Langfuse trace URL
        langfuse_url = None
        if task.langfuse_trace_id:
            langfuse_url = f"https://cloud.langfuse.com/trace/{task.langfuse_trace_id}"
        
        return schemas.AgentTaskDetail(
            task_id=str(task.id),
            organization_id=task.organization_id,
            objective=task.objective,
            context=task.context,
            status=task.status,
            plan=task.plan,
            result=task.result,
            error_message=task.error_message,
            steps=steps,
            total_cost=float(task.total_cost_usd),
            total_tokens=task.total_tokens_used,
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
            langfuse_trace_url=langfuse_url
        )
    
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task ID format")
    except Exception as e:
        logger.error(f"Failed to get task details: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete(
    "/organizations/{org_id}/agent/tasks/{task_id}",
    tags=["Agent Orchestration"],
    summary="Delete agent task",
    description="Delete an agent task and all its steps."
)
def delete_agent_task(
    org_id: int = Path(..., gt=0, description="Organization ID"),
    task_id: str = Path(..., description="Task UUID"),
    db: Session = Depends(get_db)
):
    """Delete agent task."""
    try:
        from uuid import UUID
        
        # Get task first to verify ownership
        task = crud.get_agent_task(db, UUID(task_id))
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        if task.organization_id != org_id:
            raise HTTPException(status_code=403, detail="Task belongs to different organization")
        
        # Delete task
        crud.delete_agent_task(db, UUID(task_id))
        
        return {"message": "Task deleted successfully", "task_id": task_id}
    
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task ID format")
    except Exception as e:
        logger.error(f"Failed to delete task: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/organizations/{org_id}/agent/cost-summary",
    response_model=schemas.AgentCostSummary,
    tags=["Agent Orchestration"],
    summary="Get cost summary",
    description="Get aggregate cost statistics for all agent tasks by organization."
)
def get_agent_cost_summary(
    org_id: int = Path(..., gt=0, description="Organization ID"),
    db: Session = Depends(get_db)
):
    """Get agent task cost summary."""
    try:
        # Verify organization exists
        organization = crud.get_organization(db, org_id)
        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")
        
        summary = crud.get_agent_task_cost_summary(db, org_id)
        
        return schemas.AgentCostSummary(**summary)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get cost summary: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# PHASE 5C: Langfuse Advanced Features - User Feedback
# ============================================================================

@app.post(
    "/feedback/submit",
    response_model=schemas.UserFeedbackResponse,
    tags=["Langfuse Feedback"],
    summary="Submit user feedback",
    description="""
    Submit user feedback (thumbs up/down) for a RAG response or agent task.
    
    This feedback is stored in Langfuse and can be used for:
    - Building evaluation datasets
    - Identifying problem cases
    - A/B testing analysis
    - Continuous improvement
    """
)
def submit_user_feedback(
    request: schemas.UserFeedbackRequest = Body(...),
    db: Session = Depends(get_db)
):
    """Submit user feedback to Langfuse."""
    try:
        from langfuse import Langfuse
        
        # Initialize Langfuse client
        langfuse = Langfuse()
        
        # Submit feedback as score
        langfuse.score(
            trace_id=request.trace_id,
            name="user_feedback",
            value=request.score,
            comment=request.comment
        )
        
        logger.info(f"User feedback submitted for trace {request.trace_id}: score={request.score}")
        
        return schemas.UserFeedbackResponse(
            success=True,
            trace_id=request.trace_id,
            score=request.score,
            message="Feedback recorded successfully"
        )
    
    except Exception as e:
        logger.error(f"Failed to submit feedback: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to submit feedback: {str(e)}")


# ========================================
# LANGFUSE ADVANCED FEATURES ENDPOINTS
# ========================================

@app.post("/langfuse/ab-test/create", response_model=schemas.ABTestResponse, status_code=201)
def create_ab_test(
    request: schemas.ABTestConfig,
    db: Session = Depends(get_db)
) -> schemas.ABTestResponse:
    """
    Create a new A/B test configuration for prompt variants.
    
    Args:
        request: A/B test configuration with prompt variants and traffic split
        db: Database session
        
    Returns:
        ABTestResponse with test details
        
    Raises:
        HTTPException: 400 if configuration invalid
    """
    try:
        from app.langfuse_advanced_service import LangfuseAdvancedService
        
        service = LangfuseAdvancedService()
        
        # Validate configuration
        if len(request.variants) < 2:
            raise HTTPException(
                status_code=400,
                detail="A/B test requires at least 2 variants"
            )
        
        total_traffic = sum(v.traffic_percentage for v in request.variants)
        if abs(total_traffic - 1.0) > 0.001:  # Allow small floating point error
            raise HTTPException(
                status_code=400,
                detail=f"Traffic percentages must sum to 1.0, got {total_traffic}"
            )
        
        logger.info(f"Created A/B test '{request.test_name}' with {len(request.variants)} variants")
        
        return schemas.ABTestResponse(
            test_name=request.test_name,
            variants=[
                schemas.PromptVariant(
                    variant_id=v.variant_id,
                    prompt_name=v.prompt_name,
                    prompt_version=v.prompt_version,
                    traffic_percentage=v.traffic_percentage
                ) for v in request.variants
            ],
            status="active",
            created_at=datetime.utcnow()
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create A/B test: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create A/B test: {str(e)}")


@app.get("/langfuse/ab-test/{test_name}/results", response_model=schemas.ABTestResults)
def get_ab_test_results(
    test_name: str,
    min_observations: int = 100,
    db: Session = Depends(get_db)
) -> schemas.ABTestResults:
    """
    Get A/B test results with statistical significance analysis.
    
    Args:
        test_name: Name of the A/B test
        min_observations: Minimum observations required for statistical significance
        db: Database session
        
    Returns:
        ABTestResults with performance comparison and significance
        
    Raises:
        HTTPException: 404 if test not found
    """
    try:
        from app.langfuse_advanced_service import LangfuseAdvancedService
        
        service = LangfuseAdvancedService()
        results = service.get_ab_test_results(test_name, min_observations=min_observations)
        
        logger.info(f"Retrieved A/B test results for '{test_name}': {len(results['variants'])} variants")
        
        return schemas.ABTestResults(
            test_name=test_name,
            total_observations=results['total_observations'],
            variants=results['variants'],
            is_significant=results['is_significant'],
            winning_variant=results.get('winning_variant'),
            confidence_level=results.get('confidence_level', 0.95)
        )
    
    except Exception as e:
        logger.error(f"Failed to get A/B test results: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get A/B test results: {str(e)}")


@app.post("/langfuse/dataset/create", response_model=schemas.DatasetResponse, status_code=201)
def create_evaluation_dataset(
    request: schemas.DatasetCreateRequest,
    db: Session = Depends(get_db)
) -> schemas.DatasetResponse:
    """
    Create a new evaluation dataset with test cases.
    
    Args:
        request: Dataset creation request with name and test cases
        db: Database session
        
    Returns:
        DatasetResponse with dataset details
        
    Raises:
        HTTPException: 400 if dataset already exists
    """
    try:
        from app.langfuse_advanced_service import LangfuseAdvancedService
        
        service = LangfuseAdvancedService()
        dataset_name = service.create_evaluation_dataset(
            name=request.dataset_name,
            description=request.description,
            test_cases=request.test_cases
        )
        
        logger.info(f"Created evaluation dataset '{dataset_name}' with {len(request.test_cases)} test cases")
        
        return schemas.DatasetResponse(
            dataset_name=dataset_name,
            description=request.description,
            test_cases_count=len(request.test_cases),
            created_at=datetime.utcnow()
        )
    
    except Exception as e:
        logger.error(f"Failed to create evaluation dataset: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create dataset: {str(e)}")


@app.post("/langfuse/dataset/{dataset_name}/evaluate", response_model=schemas.EvaluationResults)
def run_dataset_evaluation(
    dataset_name: str,
    variant_id: str,
    db: Session = Depends(get_db)
) -> schemas.EvaluationResults:
    """
    Run evaluation against a dataset with a specific prompt variant.
    
    Args:
        dataset_name: Name of the evaluation dataset
        variant_id: ID of the prompt variant to evaluate
        db: Database session
        
    Returns:
        EvaluationResults with pass/fail metrics
        
    Raises:
        HTTPException: 404 if dataset not found
    """
    try:
        from app.langfuse_advanced_service import LangfuseAdvancedService
        
        service = LangfuseAdvancedService()
        results = service.run_evaluation_dataset(dataset_name, variant_id)
        
        logger.info(
            f"Evaluation complete for dataset '{dataset_name}' with variant '{variant_id}': "
            f"{results['pass_count']}/{results['total_cases']} passed"
        )
        
        return schemas.EvaluationResults(
            dataset_name=dataset_name,
            variant_id=variant_id,
            total_cases=results['total_cases'],
            pass_count=results['pass_count'],
            fail_count=results['fail_count'],
            pass_rate=results['pass_rate'],
            avg_latency_ms=results['avg_latency_ms'],
            avg_tokens=results['avg_tokens']
        )
    
    except Exception as e:
        logger.error(f"Failed to run dataset evaluation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to run evaluation: {str(e)}")


@app.get("/langfuse/feedback/summary", response_model=schemas.FeedbackSummary)
def get_feedback_summary(
    days: int = 7,
    variant_id: Optional[str] = None,
    db: Session = Depends(get_db)
) -> schemas.FeedbackSummary:
    """
    Get aggregated user feedback summary with sentiment analysis.
    
    Args:
        days: Number of days to analyze (default 7)
        variant_id: Optional filter by prompt variant
        db: Database session
        
    Returns:
        FeedbackSummary with aggregated metrics
    """
    try:
        from app.langfuse_advanced_service import LangfuseAdvancedService
        
        service = LangfuseAdvancedService()
        summary = service.get_feedback_summary(days=days, variant_id=variant_id)
        
        logger.info(
            f"Feedback summary: {summary['total_feedback']} responses, "
            f"avg score: {summary['avg_score']:.2f}, "
            f"satisfaction: {summary['satisfaction_rate']:.1%}"
        )
        
        return schemas.FeedbackSummary(
            total_feedback=summary['total_feedback'],
            avg_score=summary['avg_score'],
            satisfaction_rate=summary['satisfaction_rate'],
            sentiment_distribution=summary['sentiment_distribution'],
            period_days=days,
            variant_id=variant_id
        )
    
    except Exception as e:
        logger.error(f"Failed to get feedback summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get feedback summary: {str(e)}")


@app.get("/langfuse/prompts/{prompt_name}/variants", response_model=List[schemas.PromptVariantDetail])
def get_prompt_variants(
    prompt_name: str,
    db: Session = Depends(get_db)
) -> List[schemas.PromptVariantDetail]:
    """
    Get all versions of a prompt with usage statistics.
    
    Args:
        prompt_name: Name of the prompt
        db: Database session
        
    Returns:
        List of PromptVariantDetail with version info and stats
    """
    try:
        from app.langfuse_advanced_service import LangfuseAdvancedService
        
        service = LangfuseAdvancedService()
        variants = service.get_prompt_variants(prompt_name)
        
        logger.info(f"Retrieved {len(variants)} variants for prompt '{prompt_name}'")
        
        return [
            schemas.PromptVariantDetail(
                variant_id=v['variant_id'],
                prompt_name=v['prompt_name'],
                prompt_version=v['version'],
                is_production=v['is_production'],
                usage_count=v['usage_count'],
                avg_latency_ms=v['avg_latency_ms'],
                avg_tokens=v['avg_tokens'],
                created_at=v['created_at']
            ) for v in variants
        ]
    
    except Exception as e:
        logger.error(f"Failed to get prompt variants: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get prompt variants: {str(e)}")


        raise HTTPException(status_code=500, detail=f"Failed to add message: {str(e)}")