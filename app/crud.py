"""
CRUD (Create, Read, Update, Delete) operations for database models.
Contains all database query logic separated from API endpoints.
"""

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from typing import List, Optional, Tuple
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID
from io import BytesIO
from app import models, schemas
from app.excel_generator import GoBDExcelGenerator


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


# ========== PHASE 2 LITE: Expense CRUD (DEPRECATED - Use Transaction CRUD) ==========
# NOTE: Expense CRUD functions have been removed and consolidated into Transaction CRUD
# See create_transaction(), get_transaction(), etc. with transaction_type='expense'


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


# ============================================================================
# PHASE 4: Transaction CRUD
# ============================================================================

def create_transaction(db: Session, transaction: schemas.TransactionCreate, organization_id: int) -> models.Transaction:
    """
    Create new transaction in database.
    
    Args:
        db: Database session
        transaction: Transaction data from request
        organization_id: Organization ID (set in endpoint or from request body)
        
    Returns:
        Created transaction object with generated id
        
    Raises:
        HTTPException 400: If transaction_hash already exists (duplicate)
        HTTPException 400: If referenced project doesn't exist (FK violation)
    """
    try:
        db_tx = models.Transaction(
            **transaction.model_dump(exclude={'transaction_hash', 'project_id', 'organization_id'}),
            organization_id=organization_id,
            project_id=transaction.project_id
        )
        
        # Generate transaction_hash for duplicate detection
        # Hash formula: SHA256(date|amount|normalized_vendor|currency)[:16]
        import hashlib
        import re
        
        # Normalize vendor name for consistent hashing
        vendor = (transaction.vendor_name or '').lower()
        vendor = re.sub(r'\s+(gmbh|ag|e\.v\.|ltd|inc|corp)\.?\s*$', '', vendor)  # Remove company suffixes
        vendor = re.sub(r'[^a-z0-9]', '', vendor)  # Remove special characters
        
        # Generate hash from key transaction attributes
        hash_input = f"{transaction.transaction_date}|{float(transaction.amount)}|{vendor}|{transaction.currency}"
        generated_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
        
        # Use provided hash if available, otherwise use generated hash
        db_tx.transaction_hash = transaction.transaction_hash or generated_hash
        
        db.add(db_tx)
        db.commit()
        db.refresh(db_tx)
        return db_tx
    except IntegrityError as e:
        db.rollback()
        if "transaction_hash" in str(e.orig):
            raise HTTPException(status_code=400, detail="Transaction with this hash already exists (possible duplicate)")
        elif "organization_id" in str(e.orig):
            raise HTTPException(status_code=400, detail="Organization not found")
        elif "project_id" in str(e.orig):
            raise HTTPException(status_code=400, detail="Project not found")
        else:
            raise HTTPException(status_code=400, detail="Database integrity error")


def get_transaction(db: Session, transaction_id: int) -> Optional[models.Transaction]:
    """
    Get transaction by ID.
    
    Args:
        db: Database session
        transaction_id: Transaction ID
        
    Returns:
        Transaction object or None if not found
    """
    return db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first()


def get_transactions_by_organization(
    db: Session, 
    organization_id: int, 
    skip: int = 0, 
    limit: int = 10,
    transaction_type: Optional[str] = None,
    category: Optional[str] = None
) -> List[models.Transaction]:
    """
    Get transactions for organization with optional filtering.
    
    Args:
        db: Database session
        organization_id: Organization ID
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return
        transaction_type: Optional filter by 'expense' or 'revenue'
        category: Optional filter by category
        
    Returns:
        List of transaction objects
    """
    query = db.query(models.Transaction).filter(models.Transaction.organization_id == organization_id)
    
    if transaction_type:
        query = query.filter(models.Transaction.transaction_type == transaction_type)
    if category:
        query = query.filter(models.Transaction.category == category)
    
    return query.order_by(models.Transaction.transaction_date.desc()).offset(skip).limit(limit).all()


def get_transactions_by_project(
    db: Session,
    project_id: int,
    skip: int = 0,
    limit: int = 10
) -> List[models.Transaction]:
    """
    Get transactions for specific project.
    
    Args:
        db: Database session
        project_id: Project ID
        skip: Number of records to skip
        limit: Maximum number of records to return
        
    Returns:
        List of transaction objects
    """
    return db.query(models.Transaction).filter(
        models.Transaction.project_id == project_id
    ).order_by(models.Transaction.transaction_date.desc()).offset(skip).limit(limit).all()


def update_transaction(
    db: Session,
    transaction_id: int,
    transaction_update: schemas.TransactionUpdate
) -> Optional[models.Transaction]:
    """
    Update transaction by ID (partial update).
    
    Args:
        db: Database session
        transaction_id: Transaction ID
        transaction_update: Fields to update
        
    Returns:
        Updated transaction object or None if not found
    """
    db_tx = get_transaction(db, transaction_id)
    if not db_tx:
        return None
    
    update_data = transaction_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_tx, field, value)
    
    db.add(db_tx)
    db.commit()
    db.refresh(db_tx)
    return db_tx


def delete_transaction(db: Session, transaction_id: int) -> Optional[models.Transaction]:
    """
    Soft delete transaction by setting is_active=False (GoBD compliance).
    
    Args:
        db: Database session
        transaction_id: Transaction ID
        
    Returns:
        Deleted transaction object or None if not found
    """
    db_tx = get_transaction(db, transaction_id)
    if not db_tx:
        return None
    
    db_tx.is_active = False
    db.add(db_tx)
    db.commit()
    db.refresh(db_tx)
    return db_tx


# ============================================================================
# PHASE 4: Transaction Duplicate CRUD
# ============================================================================

def create_transaction_duplicate(
    db: Session,
    duplicate: schemas.TransactionDuplicateCreate
) -> models.TransactionDuplicate:
    """
    Create transaction duplicate detection record.
    
    Args:
        db: Database session
        duplicate: Duplicate data from request
        
    Returns:
        Created duplicate record
        
    Raises:
        HTTPException 400: If transaction IDs don't exist
    """
    try:
        db_dup = models.TransactionDuplicate(**duplicate.model_dump())
        db.add(db_dup)
        db.commit()
        db.refresh(db_dup)
        return db_dup
    except IntegrityError as e:
        db.rollback()
        if "transaction" in str(e.orig):
            raise HTTPException(status_code=400, detail="One or both transaction IDs not found")
        else:
            raise HTTPException(status_code=400, detail="Database integrity error")


def get_transaction_duplicate(db: Session, duplicate_id: int) -> Optional[models.TransactionDuplicate]:
    """
    Get transaction duplicate record by ID.
    
    Args:
        db: Database session
        duplicate_id: Duplicate record ID
        
    Returns:
        Duplicate record or None if not found
    """
    return db.query(models.TransactionDuplicate).filter(models.TransactionDuplicate.id == duplicate_id).first()


def get_duplicates_for_transaction(
    db: Session,
    transaction_id: int,
    skip: int = 0,
    limit: int = 10
) -> List[models.TransactionDuplicate]:
    """
    Get all duplicate records for a transaction.
    
    Args:
        db: Database session
        transaction_id: Transaction ID
        skip: Number of records to skip
        limit: Maximum number of records to return
        
    Returns:
        List of duplicate records
    """
    return db.query(models.TransactionDuplicate).filter(
        (models.TransactionDuplicate.original_transaction_id == transaction_id) |
        (models.TransactionDuplicate.duplicate_transaction_id == transaction_id)
    ).offset(skip).limit(limit).all()


def update_transaction_duplicate(
    db: Session,
    duplicate_id: int,
    duplicate_update: schemas.TransactionDuplicateUpdate
) -> Optional[models.TransactionDuplicate]:
    """
    Update duplicate record (resolve duplicate).
    
    Args:
        db: Database session
        duplicate_id: Duplicate record ID
        duplicate_update: Resolution data
        
    Returns:
        Updated duplicate record or None if not found
    """
    db_dup = get_transaction_duplicate(db, duplicate_id)
    if not db_dup:
        return None
    
    update_data = duplicate_update.model_dump(exclude_unset=True)
    
    # If resolution_strategy is provided, set resolved_at
    if 'resolution_strategy' in update_data and update_data['resolution_strategy']:
        update_data['resolved_at'] = datetime.utcnow()
    
    for field, value in update_data.items():
        setattr(db_dup, field, value)
    
    db.add(db_dup)
    db.commit()
    db.refresh(db_dup)
    return db_dup


def get_unresolved_duplicates(
    db: Session,
    organization_id: int,
    skip: int = 0,
    limit: int = 10
) -> List[models.TransactionDuplicate]:
    """
    Get unresolved duplicate records for organization.
    
    Args:
        db: Database session
        organization_id: Organization ID
        skip: Number of records to skip
        limit: Maximum number of records to return
        
    Returns:
        List of unresolved duplicates
    """
    return db.query(models.TransactionDuplicate).join(
        models.Transaction,
        models.TransactionDuplicate.original_transaction_id == models.Transaction.id
    ).filter(
        models.Transaction.organization_id == organization_id,
        models.TransactionDuplicate.resolved_at == None
    ).offset(skip).limit(limit).all()


# ============================================================================
# PHASE 4: Fee Record CRUD
# ============================================================================

def create_fee_record(db: Session, fee: schemas.FeeRecordCreate, organization_id: int) -> models.FeeRecord:
    """
    Create fee record for contractor payment.
    
    Args:
        db: Database session
        fee: Fee record data from request
        organization_id: Organization ID
        
    Returns:
        Created fee record
        
    Raises:
        HTTPException 400: If transaction_id invalid (FK constraint)
    """
    try:
        db_fee = models.FeeRecord(
            **fee.model_dump(exclude={'transaction_id', 'organization_id'}),
            organization_id=organization_id,
            transaction_id=fee.transaction_id
        )
        db.add(db_fee)
        db.commit()
        db.refresh(db_fee)
        return db_fee
    except IntegrityError as e:
        db.rollback()
        if "transaction_id" in str(e.orig):
            raise HTTPException(status_code=400, detail="Transaction not found")
        elif "organization_id" in str(e.orig):
            raise HTTPException(status_code=400, detail="Organization not found")
        else:
            raise HTTPException(status_code=400, detail="Database integrity error")


def get_fee_record(db: Session, fee_id: int) -> Optional[models.FeeRecord]:
    """
    Get fee record by ID.
    
    Args:
        db: Database session
        fee_id: Fee record ID
        
    Returns:
        Fee record or None if not found
    """
    return db.query(models.FeeRecord).filter(models.FeeRecord.id == fee_id).first()


def get_fee_records_by_organization(
    db: Session,
    organization_id: int,
    skip: int = 0,
    limit: int = 10
) -> List[models.FeeRecord]:
    """
    Get fee records for organization.
    
    Args:
        db: Database session
        organization_id: Organization ID
        skip: Number of records to skip
        limit: Maximum number of records to return
        
    Returns:
        List of fee records
    """
    return db.query(models.FeeRecord).filter(
        models.FeeRecord.organization_id == organization_id
    ).order_by(models.FeeRecord.payment_date.desc()).offset(skip).limit(limit).all()


def update_fee_record(
    db: Session,
    fee_id: int,
    fee_update: schemas.FeeRecordUpdate
) -> Optional[models.FeeRecord]:
    """
    Update fee record (partial update).
    
    Args:
        db: Database session
        fee_id: Fee record ID
        fee_update: Fields to update
        
    Returns:
        Updated fee record or None if not found
    """
    db_fee = get_fee_record(db, fee_id)
    if not db_fee:
        return None
    
    update_data = fee_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_fee, field, value)
    
    db.add(db_fee)
    db.commit()
    db.refresh(db_fee)
    return db_fee


def delete_fee_record(db: Session, fee_id: int) -> Optional[models.FeeRecord]:
    """
    Soft delete fee record.
    
    Args:
        db: Database session
        fee_id: Fee record ID
        
    Returns:
        Deleted fee record or None if not found
    """
    db_fee = get_fee_record(db, fee_id)
    if not db_fee:
        return None
    
    db_fee.is_active = False
    db.add(db_fee)
    db.commit()
    db.refresh(db_fee)
    return db_fee


def get_fee_summary_by_organization(db: Session, organization_id: int) -> dict:
    """
    Get fee summary for organization (total paid, tax withheld, count).
    
    Args:
        db: Database session
        organization_id: Organization ID
        
    Returns:
        Dictionary with summary stats
    """
    from decimal import Decimal
    
    fees = db.query(models.FeeRecord).filter(
        models.FeeRecord.organization_id == organization_id,
        models.FeeRecord.is_active == True
    ).all()
    
    if not fees:
        return {
            "total_gross": Decimal("0"),
            "total_tax_withheld": Decimal("0"),
            "total_net": Decimal("0"),
            "fee_count": 0
        }
    
    return {
        "total_gross": sum(f.gross_amount for f in fees),
        "total_tax_withheld": sum(f.tax_withheld for f in fees),
        "total_net": sum(f.net_amount for f in fees),
        "fee_count": len(fees)
    }


# ============================================================================
# PHASE 4: Event Cost CRUD
# ============================================================================

def create_event_cost(db: Session, event: schemas.EventCostCreate, organization_id: int) -> models.EventCost:
    """
    Create event cost record.
    
    Args:
        db: Database session
        event: Event cost data from request
        organization_id: Organization ID
        
    Returns:
        Created event cost record
        
    Raises:
        HTTPException 400: If project_id invalid (FK constraint)
    """
    try:
        # Auto-calculate cost_per_person if not provided
        cost_per_person = event.cost_per_person
        if not cost_per_person and event.attendee_count:
            from decimal import Decimal
            cost_per_person = event.total_cost / Decimal(str(event.attendee_count))
        
        # Convert cost_breakdown Decimals to floats for JSON serialization
        cost_breakdown_dict = None
        if event.cost_breakdown:
            cost_breakdown_dict = {}
            for key, value in event.cost_breakdown.model_dump().items():
                if value is not None:
                    cost_breakdown_dict[key] = float(value)
        
        db_event = models.EventCost(
            **event.model_dump(exclude={'project_id', 'cost_per_person', 'organization_id', 'cost_breakdown'}),
            organization_id=organization_id,
            project_id=event.project_id,
            cost_per_person=cost_per_person,
            cost_breakdown=cost_breakdown_dict
        )
        db.add(db_event)
        db.commit()
        db.refresh(db_event)
        return db_event
    except IntegrityError as e:
        db.rollback()
        if "project_id" in str(e.orig):
            raise HTTPException(status_code=400, detail="Project not found")
        elif "organization_id" in str(e.orig):
            raise HTTPException(status_code=400, detail="Organization not found")
        else:
            raise HTTPException(status_code=400, detail="Database integrity error")


def get_event_cost(db: Session, event_id: int) -> Optional[models.EventCost]:
    """
    Get event cost record by ID.
    
    Args:
        db: Database session
        event_id: Event cost ID
        
    Returns:
        Event cost record or None if not found
    """
    return db.query(models.EventCost).filter(models.EventCost.id == event_id).first()


def get_event_costs_by_organization(
    db: Session,
    organization_id: int,
    skip: int = 0,
    limit: int = 10
) -> List[models.EventCost]:
    """
    Get event costs for organization.
    
    Args:
        db: Database session
        organization_id: Organization ID
        skip: Number of records to skip
        limit: Maximum number of records to return
        
    Returns:
        List of event cost records
    """
    return db.query(models.EventCost).filter(
        models.EventCost.organization_id == organization_id
    ).order_by(models.EventCost.event_date.desc()).offset(skip).limit(limit).all()


def get_event_costs_by_project(
    db: Session,
    project_id: int,
    skip: int = 0,
    limit: int = 10
) -> List[models.EventCost]:
    """
    Get event costs for specific project.
    
    Args:
        db: Database session
        project_id: Project ID
        skip: Number of records to skip
        limit: Maximum number of records to return
        
    Returns:
        List of event cost records
    """
    return db.query(models.EventCost).filter(
        models.EventCost.project_id == project_id
    ).order_by(models.EventCost.event_date.desc()).offset(skip).limit(limit).all()


def update_event_cost(
    db: Session,
    event_id: int,
    event_update: schemas.EventCostUpdate
) -> Optional[models.EventCost]:
    """
    Update event cost record (partial update).
    
    Args:
        db: Database session
        event_id: Event cost ID
        event_update: Fields to update
        
    Returns:
        Updated event cost record or None if not found
    """
    db_event = get_event_cost(db, event_id)
    if not db_event:
        return None
    
    update_data = event_update.model_dump(exclude_unset=True)
    
    # Recalculate cost_per_person if total_cost or attendee_count changed
    if 'total_cost' in update_data or 'attendee_count' in update_data:
        total = update_data.get('total_cost', db_event.total_cost)
        count = update_data.get('attendee_count', db_event.attendee_count)
        if count:
            from decimal import Decimal
            update_data['cost_per_person'] = total / Decimal(str(count))
    
    for field, value in update_data.items():
        setattr(db_event, field, value)
    
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event


def delete_event_cost(db: Session, event_id: int) -> Optional[models.EventCost]:
    """
    Soft delete event cost record.
    
    Args:
        db: Database session
        event_id: Event cost ID
        
    Returns:
        Deleted event cost record or None if not found
    """
    db_event = get_event_cost(db, event_id)
    if not db_event:
        return None
    
    db_event.is_active = False
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event


def get_event_cost_summary_by_organization(db: Session, organization_id: int) -> dict:
    """
    Get event cost summary for organization.
    
    Args:
        db: Database session
        organization_id: Organization ID
        
    Returns:
        Dictionary with summary stats
    """
    from decimal import Decimal
    
    events = db.query(models.EventCost).filter(
        models.EventCost.organization_id == organization_id,
        models.EventCost.is_active == True
    ).all()
    
    if not events:
        return {
            "total_event_cost": Decimal("0"),
            "total_attendees": 0,
            "event_count": 0,
            "average_cost_per_event": Decimal("0"),
            "average_cost_per_person": Decimal("0")
        }
    
    total_cost = sum(e.total_cost for e in events)
    total_attendees = sum(e.attendee_count or 0 for e in events)
    
    return {
        "total_event_cost": total_cost,
        "total_attendees": total_attendees,
        "event_count": len(events),
        "average_cost_per_event": total_cost / len(events),
        "average_cost_per_person": total_cost / total_attendees if total_attendees > 0 else Decimal("0")
    }


# ========== PHASE 5: DocumentChunk CRUD (RAG Foundation) ==========

def create_document_chunk(
    db: Session,
    document_processing_id: UUID,
    chunk_create: schemas.DocumentChunkCreate
) -> models.DocumentChunk:
    """
    Create a single document chunk with embedding.
    
    PHASE 5 RAG Foundation: Store text chunk with vector embedding for semantic search.
    
    Args:
        db: Database session
        document_processing_id: ID of parent DocumentProcessing
        chunk_create: Chunk data from request (includes optional pre-generated embedding)
        
    Returns:
        Created DocumentChunk object with generated id
        
    Raises:
        HTTPException 404: If document_processing_id does not exist
        HTTPException 400: If database constraint violated
        
    Example:
        >>> chunk = create_document_chunk(db, doc_id, DocumentChunkCreate(...))
        >>> assert chunk.id is not None
        >>> assert chunk.embedding is not None
    """
    # Verify document exists
    doc = db.query(models.DocumentProcessing).filter_by(id=document_processing_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail=f"DocumentProcessing {document_processing_id} not found")
    
    if not chunk_create.embedding:
        raise HTTPException(status_code=400, detail="Embedding is required")

    from app.embedding_service import get_embedding_column_name_for_dimensions

    embedding_column = get_embedding_column_name_for_dimensions(len(chunk_create.embedding))
    embedding_payload = {embedding_column: chunk_create.embedding}

    # Create chunk object
    db_chunk = models.DocumentChunk(
        document_processing_id=document_processing_id,
        chunk_text=chunk_create.chunk_text,
        chunk_index=chunk_create.chunk_index,
        chunk_metadata=chunk_create.chunk_metadata or {},
        **embedding_payload
    )
    
    try:
        db.add(db_chunk)
        db.commit()
        db.refresh(db_chunk)
        return db_chunk
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to create chunk: {str(e.orig)}")


def get_document_chunk(db: Session, chunk_id: int) -> Optional[models.DocumentChunk]:
    """
    Retrieve document chunk by ID.
    
    Args:
        db: Database session
        chunk_id: Chunk ID
        
    Returns:
        DocumentChunk object or None if not found
    """
    return db.query(models.DocumentChunk).filter_by(id=chunk_id).first()


def get_document_chunks(
    db: Session,
    document_processing_id: UUID,
    skip: int = 0,
    limit: int = 100
) -> Tuple[List[models.DocumentChunk], int]:
    """
    Retrieve all chunks for a document with pagination.
    
    PHASE 5: Efficiently retrieve chunks for a document for listing/export.
    
    Args:
        db: Database session
        document_processing_id: ID of parent DocumentProcessing
        skip: Number of records to skip (for pagination)
        limit: Maximum records to return (default 100, max 1000)
        
    Returns:
        Tuple of (chunks list, total count)
        
    Note:
        Indexed query on document_processing_id for fast retrieval.
        Default limit=100 balances pagination overhead vs API response size.
    """
    # Enforce maximum limit
    limit = min(limit, 1000)
    
    # Get total count
    total = db.query(models.DocumentChunk).filter_by(
        document_processing_id=document_processing_id
    ).count()
    
    # Get paginated results ordered by chunk_index (natural document order)
    chunks = db.query(models.DocumentChunk).filter_by(
        document_processing_id=document_processing_id
    ).order_by(models.DocumentChunk.chunk_index).offset(skip).limit(limit).all()
    
    return chunks, total


def create_document_chunks_batch(
    db: Session,
    document_processing_id: UUID,
    chunks_data: List[schemas.DocumentChunkCreate]
) -> Tuple[List[models.DocumentChunk], int]:
    """
    Create multiple document chunks in a single transaction.
    
    PHASE 5: Efficient batch creation for documents with many chunks.
    
    Args:
        db: Database session
        document_processing_id: ID of parent DocumentProcessing
        chunks_data: List of chunk data to create
        
    Returns:
        Tuple of (created chunks list, number created)
        
    Raises:
        HTTPException 404: If document_processing_id does not exist
        HTTPException 400: If batch creation fails
        
    Performance:
        - Single transaction for all chunks
        - Commits once after all added (much faster than individual commits)
        - Typical: 1000 chunks created in <500ms
        
    Example:
        >>> chunks_to_create = [DocumentChunkCreate(...), DocumentChunkCreate(...)]
        >>> created, count = create_document_chunks_batch(db, doc_id, chunks_to_create)
        >>> assert count == len(chunks_to_create)
    """
    # Verify document exists
    doc = db.query(models.DocumentProcessing).filter_by(id=document_processing_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail=f"DocumentProcessing {document_processing_id} not found")
    
    if not chunks_data:
        return [], 0
    
    try:
        # Create all chunk objects
        db_chunks = [
            models.DocumentChunk(
                document_processing_id=document_processing_id,
                chunk_text=chunk.chunk_text,
                embedding=chunk.embedding,
                chunk_index=chunk.chunk_index,
                chunk_metadata=chunk.chunk_metadata or {}
            )
            for chunk in chunks_data
        ]
        
        # Add all at once
        db.add_all(db_chunks)
        
        # Single commit for performance
        db.commit()
        
        # Refresh all to get generated IDs
        for chunk in db_chunks:
            db.refresh(chunk)
        
        return db_chunks, len(db_chunks)
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Batch creation failed: {str(e.orig)}")


def update_chunk_metadata(
    db: Session,
    chunk_id: int,
    metadata: dict
) -> Optional[models.DocumentChunk]:
    """
    Update metadata for a chunk (e.g., page_number, section corrections).
    
    PHASE 5: Update chunk metadata after creation (e.g., OCR corrections).
    
    Args:
        db: Database session
        chunk_id: Chunk ID to update
        metadata: New metadata dict (will be merged with existing)
        
    Returns:
        Updated DocumentChunk or None if not found
        
    Note:
        Metadata is merged with existing (not replaced).
        updated_at is automatically set by database.
    """
    chunk = db.query(models.DocumentChunk).filter_by(id=chunk_id).first()
    if not chunk:
        return None
    
    # Merge metadata
    current_meta = chunk.chunk_metadata or {}
    current_meta.update(metadata)
    chunk.chunk_metadata = current_meta
    
    db.commit()
    db.refresh(chunk)
    return chunk


def delete_document_chunk(db: Session, chunk_id: int) -> bool:
    """
    Delete a specific chunk.
    
    Note: Chunks are typically deleted via CASCADE when document is deleted.
    Use this only for individual chunk deletion (rare).
    
    Args:
        db: Database session
        chunk_id: Chunk ID to delete
        
    Returns:
        True if deleted, False if not found
    """
    chunk = db.query(models.DocumentChunk).filter_by(id=chunk_id).first()
    if not chunk:
        return False
    
    db.delete(chunk)
    db.commit()
    return True


def delete_document_chunks_by_document(
    db: Session,
    document_processing_id: UUID
) -> int:
    """
    Delete all chunks for a document.
    
    Note: This is typically called via CASCADE when document is deleted.
    Use this for explicit cleanup only.
    
    Args:
        db: Database session
        document_processing_id: ID of parent DocumentProcessing
        
    Returns:
        Number of chunks deleted
    """
    count = db.query(models.DocumentChunk).filter_by(
        document_processing_id=document_processing_id
    ).delete()
    db.commit()
    return count


def create_document_chunks(
    db: Session,
    document_processing_id: UUID,
    chunks: List[dict],
    embedding_service
) -> List[models.DocumentChunk]:
    """
    Create document chunks with embeddings from ChunkingService output.
    
    PHASE 5: Integration point for document chunking + embedding pipeline.
    
    This function:
    1. Takes raw chunks from ChunkingService (text-based)
    2. Generates embeddings via EmbeddingService
    3. Saves chunks with embeddings to database
    4. Handles errors gracefully (individual chunk failures don't block others)
    
    Args:
        db: Database session
        document_processing_id: ID of parent DocumentProcessing
        chunks: List of chunk dicts from ChunkingService with:
                - chunk_index: int
                - chunk_text: str
                - token_count: int
                - metadata: dict (optional)
        embedding_service: EmbeddingService instance for generating embeddings
        
    Returns:
        List of created DocumentChunk objects with embeddings
        
    Raises:
        HTTPException 404: If document_processing_id does not exist
        HTTPException 400: If all chunks fail to create
        
    Performance:
        - Batch creates all chunks in single transaction
        - Embedding generation can be parallelized (Phase 5B)
        - Typical: 10 chunks with embeddings created in <3s (API calls are slow)
        
    Example:
        >>> embedding_service = EmbeddingService()
        >>> chunks_from_service = chunking_service.chunk_text("text...")
        >>> created = create_document_chunks(db, doc_id, chunks_from_service, embedding_service)
        >>> assert len(created) == len(chunks_from_service)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Verify document exists
    doc = db.query(models.DocumentProcessing).filter_by(id=document_processing_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail=f"DocumentProcessing {document_processing_id} not found")
    
    if not chunks:
        logger.warning(f"No chunks provided for document {document_processing_id}")
        return []
    
    created_chunks = []
    failed_chunks = []
    
    try:
        # Generate embeddings for each chunk
        for chunk in chunks:
            try:
                logger.info(f"Generating embedding for chunk {chunk.get('chunk_index', '?')} of {document_processing_id}")
                
                # Generate embedding via active backend
                embedding = embedding_service.generate_embedding(chunk["chunk_text"])
                
                from app.embedding_service import (
                    get_embedding_column_name_for_dimensions,
                    get_embedding_model_name,
                )
                from app.config import settings

                # PHASE 5D: Optimized embedding storage with schema fallback
                # Handle both new schema (embedding_768/embedding_1536) and legacy (embedding)
                embedding_payload = {}
                
                try:
                    # Try new schema first (preferred)
                    embedding_column = get_embedding_column_name_for_dimensions(len(embedding))
                    embedding_payload[embedding_column] = embedding
                except ValueError:
                    # Fallback to legacy schema for unsupported dimensions
                    logger.warning(f"Unsupported dimensions {len(embedding)}, using legacy embedding column")
                    embedding_payload["embedding"] = embedding
                
                # Enhanced metadata with performance tracking
                enhanced_metadata = {
                    "token_count": chunk.get("token_count", 0),
                    "source_metadata": chunk.get("metadata", {}),
                    "embedded_at": datetime.utcnow().isoformat(),
                    "embedding_backend": settings.EMBEDDING_BACKEND,
                    "embedding_model": get_embedding_model_name(),
                    "embedding_dimensions": len(embedding),
                    "schema_version": "v2.0" if embedding_column.startswith("embedding_") else "v1.0",
                    "optimization_flags": {
                        "batch_processed": len(chunks) > 1,
                        "langfuse_enabled": True,
                        "vector_indexed": True
                    }
                }
                
                # Create chunk object with optimized embedding storage
                db_chunk = models.DocumentChunk(
                    document_processing_id=document_processing_id,
                    chunk_text=chunk["chunk_text"],
                    chunk_index=chunk.get("chunk_index", 0),
                    chunk_metadata=enhanced_metadata,
                    **embedding_payload
                )
                
                db.add(db_chunk)
                created_chunks.append(db_chunk)
                logger.debug(f"Chunk {chunk.get('chunk_index', '?')} queued for insertion")
                
            except Exception as e:
                failed_chunks.append({
                    "chunk_index": chunk.get("chunk_index", "?"),
                    "error": str(e)
                })
                logger.error(f"Failed to process chunk {chunk.get('chunk_index', '?')}: {str(e)}")
                # Continue with next chunk instead of failing the whole batch
        
        # If some chunks succeeded, save them
        if created_chunks:
            db.commit()
            
            # Refresh all to get generated IDs
            for chunk in created_chunks:
                db.refresh(chunk)
            
            logger.info(f"Successfully created {len(created_chunks)} chunks for document {document_processing_id}")
            
            if failed_chunks:
                logger.warning(f"Failed to create {len(failed_chunks)} chunks: {failed_chunks}")
        else:
            # All chunks failed
            raise HTTPException(
                status_code=400,
                detail=f"Failed to create any chunks. Errors: {failed_chunks}"
            )
        
        return created_chunks
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error in create_document_chunks: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create chunks: {str(e)}")


# ========== Phase 5B: RAG Query CRUD ==========

def search_similar_chunks(
    db: Session,
    query_embedding: List[float],
    organization_id: int,
    top_k: int = 10,
    min_similarity: float = 0.5
) -> List[dict]:
    """
    Search for document chunks similar to query using vector similarity.
    
    PHASE 5B: Semantic search using pgvector cosine similarity.
    
    Uses pgvector <=> operator for cosine distance (1 - cosine_sim).
    Filters by organization for multi-tenancy isolation.
    
    Args:
        db: Database session
        query_embedding: Query vector (dimensions must match embedding backend)
        organization_id: Organization ID for filtering
        top_k: Maximum number of chunks to return (default 10, max 50)
        min_similarity: Minimum cosine similarity threshold (0.0-1.0, default 0.5)
        
    Returns:
        List of dicts with:
        - chunk_id: UUID
        - chunk_text: str
        - similarity_score: float (0-1)
        - document_name: str
        - metadata: dict (page, section, etc.)
        
    Raises:
        HTTPException 400: If query_embedding has wrong dimensions
        
    Performance:
        - With IVFFlat index: ~50ms for 10K chunks
        - Without index: ~500ms (fallback to full scan)
        
    Example:
        >>> from app.embedding_service import EmbeddingService
        >>> embedding_service = EmbeddingService()
        >>> query_vec = embedding_service.generate_embedding("tech expenses")
        >>> results = search_similar_chunks(db, query_vec, org_id=1, top_k=5)
        >>> assert len(results) <= 5
        >>> assert all(0 <= r['similarity_score'] <= 1 for r in results)
    """
    import logging
    from app.embedding_service import get_embedding_dimensions
    logger = logging.getLogger(__name__)
    
    # PHASE 5D: Optimized schema-agnostic vector search
    # Handle both new schema (embedding_768/embedding_1536) and legacy (embedding)
    DB_VECTOR_DIMS = get_embedding_dimensions()
    
    # Determine available embedding column based on dimensions and schema
    embedding_column = None
    if len(query_embedding) == 768:
        # Try new schema first, fallback to legacy
        embedding_column = "embedding_768"  # Will fallback if column doesn't exist
    elif len(query_embedding) == 1536:
        embedding_column = "embedding_1536"
    else:
        # For other dimensions, use legacy column
        embedding_column = "embedding"
    
    # Validate final dimensions
    if len(query_embedding) != DB_VECTOR_DIMS:
        raise HTTPException(
            status_code=400,
            detail=f"Query embedding must be {DB_VECTOR_DIMS} dimensions, got {len(query_embedding)}"
        )
    
    # Validate parameters
    if not 0.0 <= min_similarity <= 1.0:
        raise HTTPException(status_code=400, detail="min_similarity must be between 0.0 and 1.0")
    
    if top_k < 1 or top_k > 50:
        raise HTTPException(status_code=400, detail="top_k must be between 1 and 50")
    
    try:
        # Cast query embedding to pgvector format string
        # pgvector expects format: [val1, val2, ..., valN]
        query_vec_str = f"[{','.join(str(x) for x in query_embedding)}]"
        
        # PHASE 5D: Schema-agnostic vector search with graceful fallback
        # Try new schema first, fallback to legacy if needed
        search_queries = []
        
        if len(query_embedding) == 768:
            # Priority order: embedding_768 -> embedding
            search_queries = ["embedding_768", "embedding"]
        elif len(query_embedding) == 1536:
            # Priority order: embedding_1536 -> embedding (if compatible)
            search_queries = ["embedding_1536"]
        else:
            # Fallback to legacy column
            search_queries = ["embedding"]
        
        # Try each column until one works
        results = []
        for col_name in search_queries:
            try:
                # Dynamic SQL building using format() for column names and %(...)s for query parameters
                # Column names must be injected via .format() since they can't be query parameters
                sql_template = """
                    SELECT 
                        dc.id,
                        dc.chunk_text,
                        dc.chunk_metadata,
                        dp.file_name,
                        1 - (dc.{col_name} <=> %(query_vector)s::vector) as similarity,
                        '{col_name}' as embedding_column_used
                    FROM document_chunks dc
                    JOIN document_processing dp ON dc.document_processing_id = dp.id
                    WHERE dp.organization_id = %(org_id)s
                        AND dc.{col_name} IS NOT NULL
                        AND 1 - (dc.{col_name} <=> %(query_vector)s::vector) > %(min_similarity)s
                    ORDER BY dc.{col_name} <=> %(query_vector)s::vector
                    LIMIT %(top_k)s
                """
               
                # Format SQL with column name (inject into SQL string)
                sql = sql_template.format(col_name=col_name)
                
                logger.info(f"Trying vector search with column: {col_name}")
                
                # Use SQLAlchemy connection to execute raw SQL with psycopg2 parameter binding
                # This avoids SQLAlchemy text() parsing issues with %(...)s style
                conn_obj = db.connection()
                
                try:
                    result_proxy = conn_obj.exec_driver_sql(sql, {
                        "query_vector": query_vec_str,
                        "org_id": organization_id,
                        "min_similarity": min_similarity,
                        "top_k": top_k
                    })
                    
                    rows = result_proxy.fetchall()
                    logger.info(f"Vector search completed for {col_name}: found {len(rows) if rows else 0} rows")
                    
                    if rows:
                        logger.info(f"✓ Vector search successful using {col_name}: {len(rows)} chunks found")
                        results = rows
                        break
                    else:
                        logger.info(f"No results found using column {col_name}, trying next column...")
                        
                finally:
                    # Connection will be returned to pool automatically
                    pass
                    
            except Exception as e:
                logger.error(f"Column {col_name} failed: {type(e).__name__}: {str(e)}")
                logger.debug(f"SQL that failed:\n{sql}")
                continue
        
        if not results:
            logger.warning(f"No vector search results found for org {organization_id} with any embedding column")
            return []
        
        # Format results with enhanced metadata
        chunks = []
        for row in results:
            chunk_id, chunk_text, chunk_metadata, document_name, similarity, col_used = row
            
            # Enhanced chunk result with optimization metadata
            chunk_result = {
                "chunk_id": chunk_id,
                "chunk_text": chunk_text,
                "similarity_score": float(similarity) if similarity else 0.0,
                "document_name": document_name,
                "metadata": chunk_metadata or {},
                "search_metadata": {
                    "embedding_column_used": col_used,
                    "query_dimensions": len(query_embedding),
                    "search_optimized": True
                }
            }
            chunks.append(chunk_result)
        
        return chunks
        
    except Exception as e:
        logger.error(f"Vector search failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


# ============================================================================
# PHASE 5B: Conversation Management CRUD Operations
# ============================================================================

def create_conversation(
    db: Session,
    organization_id: int,
    title: str
) -> "models.Conversation":
    """
    Create a new conversation for multi-turn RAG queries.
    
    Args:
        db: Database session
        organization_id: Organization that owns the conversation
        title: Conversation title/topic
    
    Returns:
        Created Conversation object with empty messages list
    
    Raises:
        ValueError: If organization not found
    
    Example:
        >>> conv = create_conversation(db, org_id=1, title="Q4 Analysis")
        >>> conv.id
        UUID('...')
    """
    from uuid import uuid4
    from datetime import datetime
    
    # Verify organization exists
    org = db.query(models.Organization).filter(
        models.Organization.id == organization_id
    ).first()
    if not org:
        raise ValueError(f"Organization {organization_id} not found")
    
    # Create conversation
    conversation = models.Conversation(
        id=uuid4(),
        organization_id=organization_id,
        title=title,
        messages=[]
    )
    
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    
    logger.info(f"Created conversation: {conversation.id} for org {organization_id}, title='{title}'")
    
    return conversation


def get_conversation(db: Session, conversation_id) -> Optional["models.Conversation"]:
    """
    Retrieve a conversation by ID with full message history.
    
    Args:
        db: Database session
        conversation_id: Conversation UUID
    
    Returns:
        Conversation object or None if not found
    
    Example:
        >>> conv = get_conversation(db, conv_id)
        >>> len(conv.messages)
        5
    """
    return db.query(models.Conversation).filter(
        models.Conversation.id == conversation_id
    ).first()


def list_conversations(
    db: Session,
    organization_id: int,
    skip: int = 0,
    limit: int = 50
) -> List["models.Conversation"]:
    """
    List all conversations for an organization.
    
    Args:
        db: Database session
        organization_id: Organization ID
        skip: Number to skip (pagination)
        limit: Max results to return
    
    Returns:
        List of Conversation objects (ordered by created_at DESC)
    
    Example:
        >>> convs = list_conversations(db, org_id=1, limit=10)
        >>> len(convs)
        10
    """
    return db.query(models.Conversation).filter(
        models.Conversation.organization_id == organization_id
    ).order_by(models.Conversation.created_at.desc()).offset(skip).limit(limit).all()


def add_message_to_conversation(
    db: Session,
    conversation_id,
    role: str,
    content: str,
    sources: Optional[List[dict]] = None,
    confidence: Optional[float] = None
) -> "models.Conversation":
    """
    Add a message to a conversation and update timestamp.
    
    Args:
        db: Database session
        conversation_id: Conversation UUID
        role: "user" or "assistant"
        content: Message text
        sources: List of source citations (for assistant messages)
        confidence: Confidence score (for assistant messages)
    
    Returns:
        Updated Conversation object
    
    Raises:
        ValueError: If conversation not found
    
    Example:
        >>> conv = add_message_to_conversation(
        ...     db=db,
        ...     conversation_id=conv_id,
        ...     role="assistant",
        ...     content="Answer text",
        ...     sources=[...],
        ...     confidence=0.92
        ... )
    """
    from datetime import datetime
    
    # Get conversation
    conversation = db.query(models.Conversation).filter(
        models.Conversation.id == conversation_id
    ).first()
    
    if not conversation:
        raise ValueError(f"Conversation {conversation_id} not found")
    
    # Create message
    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    
    # Add optional fields for assistant messages
    if role == "assistant":
        if sources:
            message["sources"] = [
                {
                    "document_name": s.get("document_name"),
                    "chunk_id": str(s.get("chunk_id")),
                    "similarity_score": s.get("similarity_score"),
                    "page_number": s.get("page_number")
                }
                for s in sources
            ]
        if confidence is not None:
            message["confidence"] = confidence
    
    # Add to messages list
    if conversation.messages is None:
        conversation.messages = []
    conversation.messages.append(message)
    conversation.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(conversation)
    
    logger.info(
        f"Added message to conversation {conversation_id}",
        extra={"role": role, "message_count": len(conversation.messages)}
    )
    
    return conversation


def delete_conversation(db: Session, conversation_id) -> bool:
    """
    Delete a conversation by ID.
    
    Args:
        db: Database session
        conversation_id: Conversation UUID
    
    Returns:
        True if deleted, False if not found
    
    Example:
        >>> deleted = delete_conversation(db, conv_id)
        >>> deleted
        True
    """
    conversation = db.query(models.Conversation).filter(
        models.Conversation.id == conversation_id
    ).first()
    
    if not conversation:
        return False
    
    db.delete(conversation)
    db.commit()
    
    logger.info(f"Deleted conversation {conversation_id}")
    
    return True


# ============================================================================
# PHASE 5C: Agent Orchestration CRUD Operations
# ============================================================================

def get_agent_task(db: Session, task_id: UUID) -> Optional[models.AgentTask]:
    """
    Get agent task by ID.
    
    Args:
        db: Database session
        task_id: Task UUID
        
    Returns:
        AgentTask instance or None if not found
        
    Example:
        >>> task = get_agent_task(db, task_id)
        >>> task.status
        'completed'
    """
    return db.query(models.AgentTask).filter(
        models.AgentTask.id == task_id
    ).first()


def get_agent_task_with_steps(db: Session, task_id: UUID) -> Optional[models.AgentTask]:
    """
    Get agent task with all steps eagerly loaded.
    
    Args:
        db: Database session
        task_id: Task UUID
        
    Returns:
        AgentTask with steps relationship loaded
        
    Example:
        >>> task = get_agent_task_with_steps(db, task_id)
        >>> len(task.steps)
        5
    """
    from sqlalchemy.orm import joinedload
    
    return db.query(models.AgentTask).options(
        joinedload(models.AgentTask.steps)
    ).filter(
        models.AgentTask.id == task_id
    ).first()


def list_agent_tasks(
    db: Session,
    organization_id: int,
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0
) -> List[models.AgentTask]:
    """
    List agent tasks for organization with optional status filter.
    
    Args:
        db: Database session
        organization_id: Organization ID
        status: Optional status filter (pending, executing, completed, failed)
        limit: Maximum results to return
        offset: Number of results to skip
        
    Returns:
        List of AgentTask instances
        
    Example:
        >>> tasks = list_agent_tasks(db, org_id=1, status='completed', limit=10)
        >>> len(tasks)
        10
    """
    query = db.query(models.AgentTask).filter(
        models.AgentTask.organization_id == organization_id
    )
    
    if status:
        query = query.filter(models.AgentTask.status == status)
    
    return query.order_by(
        models.AgentTask.created_at.desc()
    ).limit(limit).offset(offset).all()


def count_agent_tasks(
    db: Session,
    organization_id: int,
    status: Optional[str] = None
) -> int:
    """
    Count agent tasks for organization with optional status filter.
    
    Args:
        db: Database session
        organization_id: Organization ID
        status: Optional status filter
        
    Returns:
        Count of matching tasks
    """
    query = db.query(models.AgentTask).filter(
        models.AgentTask.organization_id == organization_id
    )
    
    if status:
        query = query.filter(models.AgentTask.status == status)
    
    return query.count()


def create_agent_step(
    db: Session,
    task_id: UUID,
    step_number: int,
    step_name: str,
    action: str,
    input_data: dict
) -> models.AgentStep:
    """
    Create new agent step.
    
    Args:
        db: Database session
        task_id: Parent task UUID
        step_number: Step number (1-indexed)
        step_name: Human-readable step name
        action: Tool action name
        input_data: Tool input parameters
        
    Returns:
        Created AgentStep instance
        
    Example:
        >>> step = create_agent_step(
        ...     db, task_id, 1, "Fetch transactions", "fetch_transactions",
        ...     {"date_from": "2025-10-01", "date_to": "2025-12-31"}
        ... )
    """
    step = models.AgentStep(
        task_id=task_id,
        step_number=step_number,
        step_name=step_name,
        action=action,
        input_data=input_data,
        status="pending"
    )
    
    db.add(step)
    db.commit()
    db.refresh(step)
    
    return step


def update_agent_step_status(
    db: Session,
    step_id: UUID,
    status: str,
    output_data: Optional[dict] = None,
    error_message: Optional[str] = None
) -> models.AgentStep:
    """
    Update agent step status and results.
    
    Args:
        db: Database session
        step_id: Step UUID
        status: New status (running, completed, error)
        output_data: Tool output (if completed)
        error_message: Error message (if failed)
        
    Returns:
        Updated AgentStep instance
        
    Raises:
        HTTPException 404: If step not found
    """
    step = db.query(models.AgentStep).filter(
        models.AgentStep.id == step_id
    ).first()
    
    if not step:
        raise HTTPException(status_code=404, detail="Agent step not found")
    
    step.status = status
    
    if output_data:
        step.output_data = output_data
    
    if error_message:
        step.error_message = error_message
    
    if status == "completed" or status == "error":
        step.completed_at = datetime.utcnow()
        if step.started_at:
            duration = (step.completed_at - step.started_at).total_seconds()
            step.duration_seconds = duration
    
    db.commit()
    db.refresh(step)
    
    return step


def delete_agent_task(db: Session, task_id: UUID) -> bool:
    """
    Delete agent task (cascades to steps).
    
    Args:
        db: Database session
        task_id: Task UUID
        
    Returns:
        True if deleted, False if not found
        
    Example:
        >>> deleted = delete_agent_task(db, task_id)
        >>> deleted
        True
    """
    task = db.query(models.AgentTask).filter(
        models.AgentTask.id == task_id
    ).first()
    
    if not task:
        return False
    
    db.delete(task)
    db.commit()
    
    logger.info(f"Deleted agent task {task_id} with all steps")
    
    return True


def get_agent_task_cost_summary(db: Session, organization_id: int) -> dict:
    """
    Get cost summary for all agent tasks by organization.
    
    Args:
        db: Database session
        organization_id: Organization ID
        
    Returns:
        {
            "total_tasks": 10,
            "total_cost_usd": 2.45,
            "total_tokens": 150000,
            "avg_cost_per_task": 0.245,
            "completed_tasks": 8,
            "failed_tasks": 2
        }
    """
    from sqlalchemy import func
    
    stats = db.query(
        func.count(models.AgentTask.id).label("total_tasks"),
        func.sum(models.AgentTask.total_cost_usd).label("total_cost"),
        func.sum(models.AgentTask.total_tokens_used).label("total_tokens"),
        func.count(
            models.AgentTask.id
        ).filter(models.AgentTask.status == "completed").label("completed"),
        func.count(
            models.AgentTask.id
        ).filter(models.AgentTask.status == "failed").label("failed")
    ).filter(
        models.AgentTask.organization_id == organization_id
    ).first()
    
    total_tasks = stats.total_tasks or 0
    total_cost = float(stats.total_cost or 0.0)
    total_tokens = stats.total_tokens or 0
    completed = stats.completed or 0
    failed = stats.failed or 0
    
    return {
        "total_tasks": total_tasks,
        "total_cost_usd": round(total_cost, 4),
        "total_tokens": total_tokens,
        "avg_cost_per_task": round(total_cost / total_tasks, 4) if total_tasks > 0 else 0.0,
        "completed_tasks": completed,
        "failed_tasks": failed
    }


# ========== Financial Reporting (Phase 4 - Excel Export) ==========

def generate_financial_report_excel(
    db: Session,
    organization_id: int,
    start_date: date,
    end_date: date,
    generated_by: Optional[str] = "System"
) -> Tuple[BytesIO, str]:
    """
    Generate GoBD-compliant Excel financial report for organization.
    
    This function queries transactions for a specified period, calculates summary
    metrics (revenue, expenses, VAT totals), and generates a multi-sheet Excel
    workbook with GoBD-compliant German formatting.
    
    Args:
        db: Database session
        organization_id: Organization ID
        start_date: Report start date (inclusive)
        end_date: Report end date (inclusive)
        generated_by: Name of user generating report (default: "System")
        
    Returns:
        Tuple of (BytesIO buffer with Excel file, filename)
        
    Raises:
        ValueError: If organization not found or no transactions in period
        
    Example:
        >>> buffer, filename = generate_financial_report_excel(
        ...     db, org_id=5, 
        ...     start_date=date(2025,1,1), 
        ...     end_date=date(2025,12,31)
        ... )
        >>> # filename: "Kinderhilfe_Deutschland_eV_2025-01-01_to_2025-12-31_financial_report.xlsx"
    """
    from sqlalchemy import and_
    
    # 1. Verify organization exists
    org = db.query(models.Organization).filter(
        models.Organization.id == organization_id,
        models.Organization.is_active == True
    ).first()
    
    if not org:
        raise ValueError(f"Organization {organization_id} not found")
    
    # 2. Query transactions for period (GoBD: only active records)
    transactions = db.query(models.Transaction).filter(
        and_(
            models.Transaction.organization_id == organization_id,
            models.Transaction.transaction_date >= start_date,
            models.Transaction.transaction_date <= end_date,
            models.Transaction.is_active == True
        )
    ).order_by(models.Transaction.transaction_date.desc()).all()
    
    if not transactions:
        raise ValueError(f"No transactions found for period {start_date} to {end_date}")
    
    # 3. Calculate summary metrics
    total_revenue = sum(
        tx.amount for tx in transactions if tx.transaction_type == "revenue"
    ) or Decimal("0.00")
    
    total_expenses = sum(
        tx.amount for tx in transactions if tx.transaction_type == "expense"
    ) or Decimal("0.00")
    
    net_position = total_revenue - total_expenses
    
    # Calculate VAT totals by rate
    vat_19 = sum(
        tx.vat_amount for tx in transactions 
        if tx.vat_rate == Decimal("0.19") and tx.vat_amount
    ) or Decimal("0.00")
    
    vat_7 = sum(
        tx.vat_amount for tx in transactions 
        if tx.vat_rate == Decimal("0.07") and tx.vat_amount
    ) or Decimal("0.00")
    
    vat_0 = sum(
        tx.vat_amount for tx in transactions 
        if tx.vat_rate == Decimal("0.00") and tx.vat_amount
    ) or Decimal("0.00")
    
    duplicate_count = sum(1 for tx in transactions if tx.is_duplicate)
    
    # 4. Initialize Excel generator
    generator = GoBDExcelGenerator(
        organization_name=org.name,
        report_title=f"Financial Report {start_date.isoformat()} to {end_date.isoformat()}",
        generated_by=generated_by
    )
    
    wb = generator.get_workbook()
    
    # 5. Build Summary sheet
    summary_sheet = wb.create_sheet("Summary", 0)
    summary_headers = [
        "Organization", "Report Period", "Total Revenue (EUR)", 
        "Total Expenses (EUR)", "Net Position (EUR)", "VAT 19% (EUR)", 
        "VAT 7% (EUR)", "VAT 0% (EUR)", "Duplicate Count", "Generated At"
    ]
    
    summary_sheet.append(summary_headers)
    summary_sheet.append([
        org.name,
        f"{start_date.isoformat()} to {end_date.isoformat()}",
        float(total_revenue),
        float(total_expenses),
        float(net_position),
        float(vat_19),
        float(vat_7),
        float(vat_0),
        duplicate_count,
        datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    ])
    
    # Apply header style to Summary sheet
    for cell in summary_sheet[1]:
        cell.style = "header"
    
    # Apply currency formatting to monetary columns (columns C-H)
    for col_idx in [3, 4, 5, 6, 7, 8]:  # Revenue, Expenses, Net, VAT columns
        summary_sheet.cell(row=2, column=col_idx).style = "currency_eur"
    
    # Auto-adjust column widths for Summary
    for col in summary_sheet.columns:
        max_length = 0
        col_letter = col[0].column_letter
        for cell in col:
            try:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        summary_sheet.column_dimensions[col_letter].width = adjusted_width
    
    # 6. Build Transactions sheet
    tx_sheet = wb.create_sheet("Transactions", 1)
    tx_headers = [
        "Date", "Vendor", "Amount (EUR)", "VAT Rate", "VAT Amount (EUR)", 
        "Net Amount (EUR)", "Category", "Type", "Payment Method", "Source", 
        "Project", "Notes", "Transaction Hash"
    ]
    
    tx_sheet.append(tx_headers)
    
    # Populate transaction rows
    for tx in transactions:
        # Get project name if exists
        project_name = ""
        if tx.project_id:
            project = db.query(models.Project).filter(
                models.Project.id == tx.project_id
            ).first()
            if project:
                project_name = project.name
        
        tx_sheet.append([
            tx.transaction_date,
            tx.vendor_name or "",
            float(tx.amount) if tx.amount else 0.00,
            float(tx.vat_rate) if tx.vat_rate else 0.00,
            float(tx.vat_amount) if tx.vat_amount else 0.00,
            float(tx.net_amount) if tx.net_amount else 0.00,
            tx.category or "",
            tx.transaction_type,
            tx.payment_method or "",
            tx.source_type,
            project_name,
            tx.notes or "",
            tx.transaction_hash
        ])
    
    # Apply styles to Transactions sheet
    for cell in tx_sheet[1]:
        cell.style = "header"
    
    # Format date and currency columns for all data rows
    for row in tx_sheet.iter_rows(min_row=2, max_row=tx_sheet.max_row):
        row[0].style = "date_de"  # Date column (A)
        row[2].style = "currency_eur"  # Amount column (C)
        row[4].style = "currency_eur"  # VAT Amount column (E)
        row[5].style = "currency_eur"  # Net Amount column (F)
    
    # Auto-adjust column widths for Transactions
    for col in tx_sheet.columns:
        max_length = 0
        col_letter = col[0].column_letter
        for cell in col:
            try:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        tx_sheet.column_dimensions[col_letter].width = adjusted_width
    
    # 7. Remove default "Init" sheet
    if "Init" in wb.sheetnames:
        wb.remove(wb["Init"])
    
    # 8. Save to BytesIO buffer
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    
    # 9. Generate filename
    filename = generator.build_filename(
        organization_name=org.name,
        start=start_date,
        end=end_date,
        suffix="financial_report"
    )
    
    return output, filename


