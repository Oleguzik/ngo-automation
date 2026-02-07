"""
Phase 5D: Embedding Service Factory

Factory pattern to create the appropriate embedding service based on configuration.
Supports multiple backends:
- OpenAI: Cloud-based, requires API key, costs money (1536 dims)
- Ollama: Local, free, no API key needed (768 dims default)

Usage:
    from app.embedding_service import get_embedding_service
    
    service = get_embedding_service()  # Auto-detects from EMBEDDING_BACKEND
    embedding = service.generate_embedding("some text")

Reference: docs/00-spec-ollama-integration.md
"""

import logging
from typing import Protocol, List, Dict, Any
from app.config import settings, EmbeddingBackend

logger = logging.getLogger(__name__)


class BaseEmbeddingService(Protocol):
    """
    Protocol defining the interface for embedding services.
    
    All embedding service implementations must provide these methods.
    """
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for single text.
        
        Args:
            text: Input text to embed
            
        Returns:
            List of floats representing embedding vector
        """
        ...
    
    def generate_embeddings_batch(
        self,
        texts: List[str],
        batch_size: int = 100
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            batch_size: Number of texts per batch
            
        Returns:
            List of embedding vectors
        """
        ...
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get service metrics for monitoring."""
        ...
    
    def check_health(self) -> Dict[str, Any]:
        """Check if service is healthy and operational."""
        ...
    
    @property
    def model(self) -> str:
        """Get the model name being used."""
        ...
    
    @property
    def dimensions(self) -> int:
        """Get the number of dimensions in embeddings."""
        ...


def get_embedding_service() -> BaseEmbeddingService:
    """
    Factory function to create embedding service based on configuration.
    
    Reads EMBEDDING_BACKEND from settings and returns appropriate service:
    - "openai" → OpenAIEmbeddingService (cloud, requires API key)
    - "ollama" → OllamaEmbeddingService (local, free)
    
    Returns:
        Embedding service instance
        
    Raises:
        ValueError: If EMBEDDING_BACKEND invalid
        ImportError: If required dependencies not installed
        ConnectionError: If service not accessible
        
    Example:
        >>> from app.embedding_service import get_embedding_service
        >>> service = get_embedding_service()
        >>> service.model  # 'nomic-embed-text' (if EMBEDDING_BACKEND=ollama)
        >>> service.dimensions  # 768
        >>> embedding = service.generate_embedding("test")
        >>> len(embedding)  # 768
    """
    backend = settings.EMBEDDING_BACKEND.lower()
    
    logger.info(f"Initializing embedding service: backend={backend}")
    
    if backend == EmbeddingBackend.OPENAI.value:
        # Import here to avoid circular dependencies
        from app.openai_embedding_service import EmbeddingService as OpenAIEmbeddingService
        
        logger.info(
            f"Using OpenAI embeddings: model={settings.OPENAI_EMBEDDING_MODEL}, "
            f"dimensions=1536"
        )
        
        return OpenAIEmbeddingService(
            api_key=settings.OPENAI_API_KEY,
            model=settings.OPENAI_EMBEDDING_MODEL
        )
        
    elif backend == EmbeddingBackend.OLLAMA.value:
        from app.ollama_embedding_service import OllamaEmbeddingService
        
        logger.info(
            f"Using Ollama embeddings: model={settings.OLLAMA_EMBEDDING_MODEL}, "
            f"base_url={settings.OLLAMA_BASE_URL}"
        )
        
        return OllamaEmbeddingService(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.OLLAMA_EMBEDDING_MODEL
        )
        
    else:
        raise ValueError(
            f"Unknown embedding backend: '{backend}'. "
            f"Supported: {[e.value for e in EmbeddingBackend]}"
        )


def get_embedding_dimensions() -> int:
    """
    Get expected embedding dimensions for current backend.
    
    Returns:
        Number of dimensions (768 for Ollama, 1536 for OpenAI)
        
    Example:
        >>> from app.embedding_service import get_embedding_dimensions
        >>> dims = get_embedding_dimensions()  # 768 (if EMBEDDING_BACKEND=ollama)
    """
    backend = settings.EMBEDDING_BACKEND.lower()
    
    if backend == EmbeddingBackend.OPENAI.value:
        # OpenAI text-embedding-3-small has 1536 dimensions
        return 1536
    elif backend == EmbeddingBackend.OLLAMA.value:
        # Ollama dimensions depend on model
        model_dims = {
            "nomic-embed-text": 768,
            "mxbai-embed-large": 1024,
            "all-minilm": 384,
            "snowflake-arctic-embed": 1024,
        }
        return model_dims.get(settings.OLLAMA_EMBEDDING_MODEL, 768)
    else:
        logger.warning(f"Unknown backend {backend}, defaulting to 768 dimensions")
        return 768


def get_embedding_model_name() -> str:
    """
    Get the embedding model name for current backend.
    
    Returns:
        Model name string
        
    Example:
        >>> from app.embedding_service import get_embedding_model_name
        >>> model = get_embedding_model_name()  # 'nomic-embed-text'
    """
    backend = settings.EMBEDDING_BACKEND.lower()
    
    if backend == EmbeddingBackend.OPENAI.value:
        return settings.OPENAI_EMBEDDING_MODEL
    elif backend == EmbeddingBackend.OLLAMA.value:
        return settings.OLLAMA_EMBEDDING_MODEL
    else:
        return "unknown"


def get_embedding_column_name() -> str:
    """
    Get the document_chunks column name for the active embedding backend.
    
    Returns:
        Column name string (embedding_768 or embedding_1536)
        
    Raises:
        ValueError: If the active embedding dimensions are unsupported
        
    Example:
        >>> from app.embedding_service import get_embedding_column_name
        >>> get_embedding_column_name()
        'embedding_768'
    """
    dimensions = get_embedding_dimensions()
    return get_embedding_column_name_for_dimensions(dimensions)


def get_embedding_column_name_for_dimensions(dimensions: int) -> str:
    """
    Map embedding dimensions to the appropriate document_chunks column.
    
    Args:
        dimensions: Embedding vector dimensions
        
    Returns:
        Column name string
        
    Raises:
        ValueError: If dimensions are not supported by the schema
    """
    if dimensions == 768:
        return "embedding_768"
    if dimensions == 1536:
        return "embedding_1536"
    raise ValueError(
        f"Unsupported embedding dimensions: {dimensions}. "
        "Add a new embedding column or switch to a supported backend."
    )


# Convenience exports
__all__ = [
    "get_embedding_service",
    "get_embedding_dimensions",
    "get_embedding_model_name",
    "get_embedding_column_name",
    "get_embedding_column_name_for_dimensions",
    "BaseEmbeddingService",
]
