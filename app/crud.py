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
    
    # Create chunk object
    db_chunk = models.DocumentChunk(
        document_processing_id=document_processing_id,
        chunk_text=chunk_create.chunk_text,
        embedding=chunk_create.embedding,
        chunk_index=chunk_create.chunk_index,
        chunk_metadata=chunk_create.chunk_metadata or {}
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
                
                # Generate embedding via OpenAI
                embedding = embedding_service.generate_embedding(chunk["chunk_text"])
                
                # Create chunk object with embedding
                db_chunk = models.DocumentChunk(
                    document_processing_id=document_processing_id,
                    chunk_text=chunk["chunk_text"],
                    embedding=embedding,  # 1536-dimensional vector
                    chunk_index=chunk.get("chunk_index", 0),
                    chunk_metadata={
                        "token_count": chunk.get("token_count", 0),
                        "source_metadata": chunk.get("metadata", {}),
                        "embedded_at": datetime.utcnow().isoformat()
                    }
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



