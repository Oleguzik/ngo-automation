"""
SQLAlchemy ORM models for database tables.
Defines Organizations and Projects tables with relationships.
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Organization(Base):
    """
    Organization entity representing an NGO.
    
    Attributes:
        id: Unique identifier (auto-generated)
        name: Organization name (must be unique)
        email: Contact email (must be unique)
        country: Country of operation (optional)
        description: Detailed description (optional)
        is_active: Soft delete flag (True = active, False = deleted)
        created_at: Creation timestamp (UTC)
        updated_at: Last modification timestamp (UTC, auto-updates)
        projects: Relationship to associated Project objects
    
    Note:
        When organization is deleted, all related projects are deleted too (cascade)
    """
    
    __tablename__ = "organizations"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Required fields with unique constraints
    name = Column(String(255), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    
    # Optional fields
    country = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    
    # Soft delete flag (don't actually delete, just mark inactive)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Timestamps (auto-managed)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationship: 1 Organization → Many Projects
    # cascade="all,delete": When org deleted, delete all projects automatically
    # back_populates: Bidirectional relationship (org.projects ↔ project.organization)
    projects = relationship("Project", back_populates="organization", cascade="all,delete")
    
    def __repr__(self):
        """String representation for debugging"""
        return f"<Organization(id={self.id}, name='{self.name}', email='{self.email}')>"


class Project(Base):
    """
    Project entity representing a project owned by an organization.
    
    Attributes:
        id: Unique identifier (auto-generated)
        name: Project name
        description: Project description (optional)
        organization_id: Foreign key to Organizations table (required)
        status: Current project status (default: 'active')
        is_active: Soft delete flag (True = active, False = deleted)
        created_at: Creation timestamp (UTC)
        updated_at: Last modification timestamp (UTC, auto-updates)
        organization: Relationship to parent Organization object
    
    Note:
        Cannot create project without valid organization_id
    """
    
    __tablename__ = "projects"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Required fields
    name = Column(String(255), index=True, nullable=False)
    
    # Optional description
    description = Column(Text, nullable=True)
    
    # Foreign key to organizations table (required, not null)
    # If organization deleted, project is deleted too (cascade handled in Organization model)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    
    # Project status (active, paused, completed, etc.)
    status = Column(String(50), default="active", nullable=False)
    
    # Soft delete flag
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Timestamps (auto-managed)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationship: Many Projects → 1 Organization
    # back_populates: Bidirectional relationship (project.organization ↔ org.projects)
    organization = relationship("Organization", back_populates="projects")
    
    def __repr__(self):
        """String representation for debugging"""
        return f"<Project(id={self.id}, name='{self.name}', org_id={self.organization_id})>"
