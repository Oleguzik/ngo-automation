"""
FastAPI application with REST API endpoints for NGO management.
Provides CRUD operations for Organizations and Projects.
"""

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List

from app import models, schemas, crud
from app.database import engine, get_db, Base

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
