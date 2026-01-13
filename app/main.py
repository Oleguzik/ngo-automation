"""
FastAPI application with REST API endpoints for NGO management.
Provides CRUD operations for Organizations and Projects.
"""

from fastapi import FastAPI, Depends, HTTPException, Query, Header, Path, Body, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
        
        # Validate file type (accept both standard PDF content types)
        allowed_types = ["application/pdf", "application/x-pdf", "application/acrobat", "application/vnd.pdf"]
        if file.content_type not in allowed_types and not file.filename.lower().endswith('.pdf'):
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