"""
Database connection and session management using SQLAlchemy.
Provides database engine, session factory, and dependency for FastAPI.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

# Create database engine
# pool_pre_ping=True checks connection health before using from pool
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=settings.DEBUG  # Log SQL queries in debug mode
)

# Create session factory
# autocommit=False: We control when to commit transactions
# autoflush=False: We control when to flush changes to DB
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base class for all ORM models
Base = declarative_base()


def get_db():
    """
    FastAPI dependency that provides database session.
    
    Yields:
        Session: SQLAlchemy database session
        
    Usage:
        @app.get("/endpoint")
        def endpoint(db: Session = Depends(get_db)):
            # Use db here
            pass
            
    Note:
        Session is automatically closed after request completes
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
