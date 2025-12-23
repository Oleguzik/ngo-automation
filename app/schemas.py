"""
Pydantic schemas for request/response validation.
Defines data structures for API endpoints with automatic validation.
"""

from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, List


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


# Update forward references for nested models
OrganizationWithProjects.model_rebuild()
