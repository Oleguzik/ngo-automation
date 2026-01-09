"""
CRUD (Create, Read, Update, Delete) operations for database models.
Contains all database query logic separated from API endpoints.
"""

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from typing import List, Optional, Tuple
from datetime import datetime
from uuid import UUID
from app import models, schemas


# ========== Organization CRUD ==========

def create_organization(db: Session, organization: schemas.OrganizationCreate) -> models.Organization:
    """
    Create new organization in database.
    
    Args:
        db: Database session
        organization: Organization data from request
        
    Returns:
        Created organization object with generated id
        
    Raises:
        HTTPException 409: If email or name already exists (unique constraint)
    """
    db_org = models.Organization(**organization.model_dump())
    
    try:
        db.add(db_org)
        db.commit()
        db.refresh(db_org)  # Refresh to get generated id and timestamps
        return db_org
    except IntegrityError as e:
        db.rollback()
        # Check which unique constraint failed
        if "email" in str(e.orig):
            raise HTTPException(status_code=409, detail=f"Email {organization.email} already exists")
        elif "name" in str(e.orig):
            raise HTTPException(status_code=409, detail=f"Organization name {organization.name} already exists")
        else:
            raise HTTPException(status_code=400, detail="Database integrity error")


def get_organization(db: Session, organization_id: int) -> Optional[models.Organization]:
    """
    Get organization by ID.
    
    Args:
        db: Database session
        organization_id: Organization ID
        
    Returns:
        Organization object or None if not found
    """
    return db.query(models.Organization).filter(models.Organization.id == organization_id).first()


def get_all_organizations(db: Session, skip: int = 0, limit: int = 10) -> List[models.Organization]:
    """
    Get list of organizations with pagination.
    
    Args:
        db: Database session
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return
        
    Returns:
        List of organization objects
    """
    return db.query(models.Organization).offset(skip).limit(limit).all()


def update_organization(
    db: Session, 
    organization_id: int, 
    organization_update: schemas.OrganizationUpdate
) -> Optional[models.Organization]:
    """
    Update organization by ID.
    
    Args:
        db: Database session
        organization_id: Organization ID
        organization_update: Fields to update (only provided fields updated)
        
    Returns:
        Updated organization object or None if not found
        
    Raises:
        HTTPException 409: If updated email/name conflicts with existing record
    """
    db_org = get_organization(db, organization_id)
    if not db_org:
        return None
    
    # Update only provided fields (exclude_unset=True)
    update_data = organization_update.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(db_org, field, value)
    
    try:
        db.commit()
        db.refresh(db_org)
        return db_org
    except IntegrityError as e:
        db.rollback()
        if "email" in str(e.orig):
            raise HTTPException(status_code=409, detail=f"Email already exists")
        elif "name" in str(e.orig):
            raise HTTPException(status_code=409, detail=f"Organization name already exists")
        else:
            raise HTTPException(status_code=400, detail="Database integrity error")


def delete_organization(db: Session, organization_id: int) -> bool:
    """
    Delete organization by ID (cascade deletes all projects).
    
    Args:
        db: Database session
        organization_id: Organization ID
        
    Returns:
        True if deleted, False if not found
        
    Note:
        All projects belonging to this organization are automatically deleted
    """
    db_org = get_organization(db, organization_id)
    if not db_org:
        return False
    
    db.delete(db_org)
    db.commit()
    return True


# ========== Project CRUD ==========

def create_project(db: Session, project: schemas.ProjectCreate) -> models.Project:
    """
    Create new project in database.
    
    Args:
        db: Database session
        project: Project data from request
        
    Returns:
        Created project object with generated id
        
    Raises:
        HTTPException 404: If organization_id doesn't exist
    """
    # Verify organization exists
    org = get_organization(db, project.organization_id)
    if not org:
        raise HTTPException(
            status_code=404, 
            detail=f"Organization with id {project.organization_id} not found"
        )
    
    db_project = models.Project(**project.model_dump())
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project


def get_project(db: Session, project_id: int) -> Optional[models.Project]:
    """
    Get project by ID.
    
    Args:
        db: Database session
        project_id: Project ID
        
    Returns:
        Project object or None if not found
    """
    return db.query(models.Project).filter(models.Project.id == project_id).first()


def get_all_projects(db: Session, skip: int = 0, limit: int = 10) -> List[models.Project]:
    """
    Get list of projects with pagination.
    
    Args:
        db: Database session
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return
        
    Returns:
        List of project objects
    """
    return db.query(models.Project).offset(skip).limit(limit).all()


def get_projects_by_organization(
    db: Session, 
    organization_id: int,
    skip: int = 0,
    limit: int = 10
) -> List[models.Project]:
    """
    Get all projects for specific organization.
    
    Args:
        db: Database session
        organization_id: Organization ID to filter by
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return
        
    Returns:
        List of project objects for this organization
    """
    return db.query(models.Project)\
        .filter(models.Project.organization_id == organization_id)\
        .offset(skip)\
        .limit(limit)\
        .all()


def update_project(
    db: Session,
    project_id: int,
    project_update: schemas.ProjectUpdate
) -> Optional[models.Project]:
    """
    Update project by ID.
    
    Args:
        db: Database session
        project_id: Project ID
        project_update: Fields to update (only provided fields updated)
        
    Returns:
        Updated project object or None if not found
        
    Raises:
        HTTPException 404: If organization_id in update doesn't exist
    """
    db_project = get_project(db, project_id)
    if not db_project:
        return None
    
    # Update only provided fields
    update_data = project_update.model_dump(exclude_unset=True)
    
    # If updating organization_id, verify it exists
    if "organization_id" in update_data:
        org = get_organization(db, update_data["organization_id"])
        if not org:
            raise HTTPException(
                status_code=404,
                detail=f"Organization with id {update_data['organization_id']} not found"
            )
    
    for field, value in update_data.items():
        setattr(db_project, field, value)
    
    db.commit()
    db.refresh(db_project)
    return db_project


def delete_project(db: Session, project_id: int) -> bool:
    """
    Delete project by ID.
    
    Args:
        db: Database session
        project_id: Project ID
        
    Returns:
        True if deleted, False if not found
    """
    db_project = get_project(db, project_id)
    if not db_project:
        return False
    
    db.delete(db_project)
    db.commit()
    return True


# ========== PHASE 2 LITE: Expense CRUD ==========

def create_expense(db: Session, expense: schemas.ExpenseCreate) -> models.Expense:
    """
    Create new expense record.
    
    PHASE 2 Lite: MVP for expense tracking
    - Validates organization exists
    - Stores purchase/receipt information
    - Returns created expense with UUID
    
    Args:
        db: Database session
        expense: Expense data from request
        
    Returns:
        Created expense object with generated UUID and timestamps
        
    Raises:
        HTTPException 404: If organization not found
        HTTPException 400: If database constraint violated
    """
    # Verify organization exists
    org = get_organization(db, expense.organization_id)
    if not org:
        raise HTTPException(
            status_code=404,
            detail=f"Organization with id {expense.organization_id} not found"
        )
    
    # Create expense record
    db_expense = models.Expense(**expense.model_dump())
    
    try:
        db.add(db_expense)
        db.commit()
        db.refresh(db_expense)
        return db_expense
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Database constraint error: {str(e.orig)}"
        )


def get_expense(db: Session, expense_id: UUID) -> Optional[models.Expense]:
    """
    Get expense by UUID.
    
    Args:
        db: Database session
        expense_id: Expense UUID
        
    Returns:
        Expense object or None if not found
    """
    return db.query(models.Expense).filter(models.Expense.id == expense_id).first()


def get_all_expenses(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    organization_id: Optional[int] = None,
    status: Optional[str] = None
) -> Tuple[List[models.Expense], int]:
    """
    Get all expenses with optional filtering.
    
    Args:
        db: Database session
        skip: Number of records to skip (pagination)
        limit: Maximum records to return
        organization_id: Filter by organization (optional)
        status: Filter by status (optional)
        
    Returns:
        Tuple of (expenses list, total count)
    """
    query = db.query(models.Expense)
    
    # Apply filters
    if organization_id:
        query = query.filter(models.Expense.organization_id == organization_id)
    if status:
        query = query.filter(models.Expense.status == status)
    
    # Get total count before pagination
    total = query.count()
    
    # Apply pagination
    expenses = query.offset(skip).limit(limit).all()
    
    return expenses, total


def get_organization_expenses(
    db: Session,
    organization_id: int,
    skip: int = 0,
    limit: int = 10
) -> Tuple[List[models.Expense], int]:
    """
    Get all expenses for specific organization.
    
    Args:
        db: Database session
        organization_id: Organization ID
        skip: Pagination skip
        limit: Pagination limit
        
    Returns:
        Tuple of (expenses list, total count)
        
    Raises:
        HTTPException 404: If organization not found
    """
    # Verify organization exists
    org = get_organization(db, organization_id)
    if not org:
        raise HTTPException(
            status_code=404,
            detail=f"Organization with id {organization_id} not found"
        )
    
    return get_all_expenses(db, skip, limit, organization_id=organization_id)


def update_expense(
    db: Session,
    expense_id: UUID,
    expense_update: schemas.ExpenseUpdate
) -> Optional[models.Expense]:
    """
    Update expense by UUID.
    
    Args:
        db: Database session
        expense_id: Expense UUID
        expense_update: Partial update data
        
    Returns:
        Updated expense object or None if not found
    """
    db_expense = get_expense(db, expense_id)
    if not db_expense:
        return None
    
    # Update only provided fields
    update_data = expense_update.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(db_expense, field, value)
    
    db.commit()
    db.refresh(db_expense)
    return db_expense


def delete_expense(db: Session, expense_id: UUID) -> bool:
    """
    Delete expense by UUID.
    
    Args:
        db: Database session
        expense_id: Expense UUID
        
    Returns:
        True if deleted, False if not found
    """
    db_expense = get_expense(db, expense_id)
    if not db_expense:
        return False
    
    db.delete(db_expense)
    db.commit()
    return True


# ============================================================================
# PHASE 3: Cost & Profit MVP CRUD Operations
# ============================================================================

# ========== Cost Category CRUD ==========

def create_cost_category(
    db: Session,
    category: schemas.CostCategoryCreate,
    organization_id: int
) -> models.CostCategory:
    """
    Create new cost category for organization.
    
    Args:
        db: Database session
        category: Category data
        organization_id: Parent organization ID
        
    Returns:
        Created cost category
    """
    db_category = models.CostCategory(
        organization_id=organization_id,
        **category.model_dump()
    )
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category


def get_cost_categories(
    db: Session,
    organization_id: int,
    skip: int = 0,
    limit: int = 10
) -> List[models.CostCategory]:
    """Get all cost categories for organization"""
    return db.query(models.CostCategory)\
        .filter(models.CostCategory.organization_id == organization_id)\
        .filter(models.CostCategory.is_active == True)\
        .offset(skip)\
        .limit(limit)\
        .all()


def delete_cost_category(db: Session, category_id: int) -> bool:
    """Soft delete cost category"""
    db_category = db.query(models.CostCategory).filter(models.CostCategory.id == category_id).first()
    if not db_category:
        return False
    db_category.is_active = False
    db.commit()
    return True


# ========== Profit Record CRUD ==========

def create_profit_record(
    db: Session,
    profit: schemas.ProfitRecordCreate,
    organization_id: int
) -> models.ProfitRecord:
    """
    Create new profit/revenue record.
    
    Args:
        db: Database session
        profit: Profit record data
        organization_id: Parent organization ID
        
    Returns:
        Created profit record
        
    Raises:
        HTTPException 404: If project_id provided but project doesn't exist
    """
    # Validate project_id if provided
    if profit.project_id:
        project = db.query(models.Project).filter(
            models.Project.id == profit.project_id,
            models.Project.organization_id == organization_id
        ).first()
        if not project:
            raise HTTPException(status_code=404, detail=f"Project {profit.project_id} not found in this organization")
    
    db_profit = models.ProfitRecord(
        organization_id=organization_id,
        **profit.model_dump()
    )
    db.add(db_profit)
    db.commit()
    db.refresh(db_profit)
    return db_profit


def get_profit_record(db: Session, profit_id: UUID, organization_id: int) -> Optional[models.ProfitRecord]:
    """Get profit record by ID (with org validation)"""
    return db.query(models.ProfitRecord).filter(
        models.ProfitRecord.id == profit_id,
        models.ProfitRecord.organization_id == organization_id
    ).first()


def get_profit_records(
    db: Session,
    organization_id: int,
    skip: int = 0,
    limit: int = 10,
    status: Optional[str] = None
) -> List[models.ProfitRecord]:
    """Get all profit records for organization with optional filtering"""
    query = db.query(models.ProfitRecord).filter(models.ProfitRecord.organization_id == organization_id)
    if status:
        query = query.filter(models.ProfitRecord.status == status)
    return query.offset(skip).limit(limit).all()


def update_profit_record(
    db: Session,
    profit_id: UUID,
    profit_update: schemas.ProfitRecordUpdate,
    organization_id: int
) -> Optional[models.ProfitRecord]:
    """Update profit record"""
    db_profit = get_profit_record(db, profit_id, organization_id)
    if not db_profit:
        return None
    
    update_data = profit_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_profit, field, value)
    
    db.commit()
    db.refresh(db_profit)
    return db_profit


def delete_profit_record(db: Session, profit_id: UUID, organization_id: int) -> bool:
    """Delete profit record"""
    db_profit = get_profit_record(db, profit_id, organization_id)
    if not db_profit:
        return False
    
    db.delete(db_profit)
    db.commit()
    return True


# ========== Document Processing CRUD ==========

def create_document_processing(
    db: Session,
    doc: schemas.DocumentProcessingCreate,
    organization_id: int
) -> models.DocumentProcessing:
    """
    Create document processing record.
    Used to track uploaded files and AI extraction progress.
    """
    db_doc = models.DocumentProcessing(
        organization_id=organization_id,
        **doc.model_dump()
    )
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)
    return db_doc


def get_document_processing(db: Session, doc_id: UUID, organization_id: int) -> Optional[models.DocumentProcessing]:
    """Get document processing record"""
    return db.query(models.DocumentProcessing).filter(
        models.DocumentProcessing.id == doc_id,
        models.DocumentProcessing.organization_id == organization_id
    ).first()


def get_organization_documents(
    db: Session,
    organization_id: int,
    skip: int = 0,
    limit: int = 10
) -> List[models.DocumentProcessing]:
    """Get all documents for organization"""
    return db.query(models.DocumentProcessing).filter(
        models.DocumentProcessing.organization_id == organization_id
    ).offset(skip).limit(limit).all()


def update_document_processing(
    db: Session,
    doc_id: UUID,
    organization_id: int,
    raw_text: Optional[str] = None,
    extracted_data: Optional[dict] = None,
    processing_status: Optional[str] = None,
    error_message: Optional[str] = None
) -> Optional[models.DocumentProcessing]:
    """Update document processing record with extraction results"""
    db_doc = get_document_processing(db, doc_id, organization_id)
    if not db_doc:
        return None
    
    if raw_text is not None:
        db_doc.raw_text = raw_text
    if extracted_data is not None:
        db_doc.extracted_data = extracted_data
    if processing_status is not None:
        db_doc.processing_status = processing_status
    if error_message is not None:
        db_doc.error_message = error_message
    
    db.commit()
    db.refresh(db_doc)
    return db_doc


# ========== Cost/Profit Analysis CRUD ==========

def get_cost_profit_summary(
    db: Session,
    organization_id: int,
    period_days: int = 30
) -> schemas.CostProfitSummary:
    """
    Get cost and profit summary for organization (last N days).
    
    Returns aggregated data for cost/profit analysis.
    """
    from datetime import datetime, timedelta
    from decimal import Decimal
    
    start_date = datetime.utcnow().date() - timedelta(days=period_days)
    
    # Aggregate expenses
    expenses = db.query(models.Expense).filter(
        models.Expense.organization_id == organization_id,
        models.Expense.created_at >= start_date
    ).all()
    
    total_costs = sum(e.amount for e in expenses) if expenses else Decimal('0')
    
    # Aggregate profits
    profits = db.query(models.ProfitRecord).filter(
        models.ProfitRecord.organization_id == organization_id,
        models.ProfitRecord.received_date >= start_date,
        models.ProfitRecord.status == "received"
    ).all()
    
    total_profits = sum(p.amount for p in profits) if profits else Decimal('0')
    
    # Calculate net balance
    net_balance = total_profits - total_costs
    
    return schemas.CostProfitSummary(
        organization_id=organization_id,
        total_costs=total_costs,
        total_profits=total_profits,
        net_balance=net_balance,
        cost_count=len(expenses),
        profit_count=len(profits),
        period_start=start_date,
        period_end=datetime.utcnow().date()
    )


