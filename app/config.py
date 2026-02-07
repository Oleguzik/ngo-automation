"""
Configuration settings for the NGO Automation Backend.
Loads environment variables for database connection and app settings.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from enum import Enum


class EmbeddingBackend(Enum):
    """Supported embedding backends for RAG system."""
    OPENAI = "openai"
    OLLAMA = "ollama"


class LLMBackend(Enum):
    """Supported LLM backends for RAG generation."""
    OPENAI = "openai"
    OLLAMA = "ollama"


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Attributes:
        DATABASE_URL: PostgreSQL connection string
        DEBUG: Enable debug mode (more verbose logging)
        OPENAI_API_KEY: OpenAI API key for AI features (Phase 3)
        OPENAI_MODEL: Model to use for chat completion
        
        # Phase 5D: Embedding Backend Configuration
        EMBEDDING_BACKEND: Which backend to use for embeddings (openai | ollama)
        OPENAI_EMBEDDING_MODEL: OpenAI embedding model (if backend=openai)
        OLLAMA_BASE_URL: Ollama API endpoint (if backend=ollama)
        OLLAMA_EMBEDDING_MODEL: Ollama embedding model (if backend=ollama)
        OLLAMA_CHAT_MODEL: Ollama chat model for generation
        
        # Phase 5E: LLM Backend Configuration (Hybrid RAG)
        LLM_BACKEND: Which backend to use for generation (openai | ollama)
    """
    
    DATABASE_URL: str = "postgresql://ngo_user:secure_password@postgres:5432/ngo_db"
    DEBUG: bool = False
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4.1-mini"  # Default - matches user's API key available models
    
    # Phase 5D: Embedding Backend Selection
    EMBEDDING_BACKEND: str = "ollama"  # Default to Ollama (local, free)
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"  # 1536 dims (if using OpenAI)
    OLLAMA_BASE_URL: str = "http://ollama:11434"  # Docker service name
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"  # 768 dims (default local model)
    OLLAMA_CHAT_MODEL: str = "llama3.2"  # For generation
    
    # Phase 5E: LLM Backend Selection (Hybrid RAG)
    LLM_BACKEND: str = "openai"  # Default to OpenAI (production quality)
    
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
