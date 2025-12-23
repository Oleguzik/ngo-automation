"""
Configuration settings for the NGO Automation Backend.
Loads environment variables for database connection and app settings.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Attributes:
        DATABASE_URL: PostgreSQL connection string
        DEBUG: Enable debug mode (more verbose logging)
    """
    
    DATABASE_URL: str = "postgresql://ngo_user:secure_password@postgres:5432/ngo_db"
    DEBUG: bool = False
    
    class Config:
        """Pydantic configuration to load from .env file"""
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra environment variables


@lru_cache()
def get_settings() -> Settings:
    """
    Create cached settings instance.
    
    Returns:
        Settings: Application settings object
        
    Note:
        Uses lru_cache to create singleton - settings loaded once
    """
    return Settings()


# Global settings instance
settings = get_settings()
