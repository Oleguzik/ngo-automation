"""
CRUD (Create, Read, Update, Delete) operations for database models.
Contains all database query logic separated from API endpoints.
"""

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from typing import List, Optional
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
