"""
Phase 5D: Ollama Embedding Service

Local embedding generation using Ollama API (free, no API key required).
- Models: nomic-embed-text (768 dims), mxbai-embed-large (1024 dims), all-minilm (384 dims)
- Cost: $0 (runs locally)
- Performance: ~50ms per embedding (faster than OpenAI due to local execution)

Reference: docs/00-spec-ollama-integration.md
"""

import logging
import time
from typing import List, Dict, Any
import requests
from tenacity import retry, wait_exponential, stop_after_attempt
from app.config import settings

logger = logging.getLogger(__name__)


class OllamaEmbeddingService:
    """
    Generate vector embeddings using local Ollama API.
    
    Attributes:
        base_url: Ollama API endpoint (default: http://ollama:11434)
        model: Embedding model name (default: nomic-embed-text)
        dimensions: Number of dimensions in embedding vector
        total_tokens: Cumulative token count for tracking
        total_requests: Number of embedding requests made
        total_latency: Cumulative latency in seconds
        
    From spec (00-spec-ollama-integration.md):
    - Model: nomic-embed-text (default, 768 dims)
    - Alternative: mxbai-embed-large (1024 dims, better quality)
    - Alternative: all-minilm (384 dims, faster)
    - Cost: $0 (local execution)
    - Performance: ~50ms per embedding
    """

    # Model dimension mapping
    MODEL_DIMENSIONS = {
        "nomic-embed-text": 768,
        "mxbai-embed-large": 1024,
        "all-minilm": 384,
        "snowflake-arctic-embed": 1024,
    }

    def __init__(
        self,
        base_url: str = None,
        model: str = None
    ):
        """
        Initialize Ollama embedding service.

        Args:
            base_url: Ollama API endpoint (defaults to settings.OLLAMA_BASE_URL)
            model: Embedding model name (defaults to settings.OLLAMA_EMBEDDING_MODEL)

        Raises:
            ConnectionError: If Ollama service is not accessible
            ValueError: If model not supported
        """
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.OLLAMA_EMBEDDING_MODEL
        
        # Get dimensions for model
        self.dimensions = self.MODEL_DIMENSIONS.get(self.model)
        if not self.dimensions:
            logger.warning(
                f"Unknown model {self.model}, will detect dimensions from first response"
            )
            self.dimensions = None  # Will be set on first embedding
        
        # Metrics tracking
        self.total_tokens = 0
        self.total_requests = 0
        self.total_latency = 0.0

        # Verify Ollama service is accessible
        try:
            self._verify_connection()
            logger.info(
                f"OllamaEmbeddingService initialized: "
                f"base_url={self.base_url}, model={self.model}, "
                f"dimensions={self.dimensions or 'auto-detect'}"
            )
        except Exception as e:
            logger.error(f"Failed to connect to Ollama service: {e}")
            raise ConnectionError(
                f"Ollama service not accessible at {self.base_url}. "
                f"Ensure Docker service is running: docker-compose up -d ollama"
            ) from e

    def _verify_connection(self):
        """Verify Ollama service is running and model is available."""
        try:
            # Check if Ollama is running
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=5
            )
            response.raise_for_status()
            
            models = response.json().get("models", [])
            model_names = [m["name"] for m in models]
            
            logger.info(f"Ollama service connected. Available models: {model_names}")
            
            # Check if our model is pulled
            if not any(self.model in name for name in model_names):
                logger.warning(
                    f"Model {self.model} not found. "
                    f"Run: docker exec ngo_ollama ollama pull {self.model}"
                )
                
        except requests.RequestException as e:
            raise ConnectionError(f"Cannot connect to Ollama API: {e}")

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
    )
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for single text chunk.

        Args:
            text: Input text to embed (recommended 50-2000 chars)

        Returns:
            List of floats representing the embedding vector
            
        Raises:
            requests.HTTPError: If Ollama API returns error
            ValueError: If text empty or too short
            ConnectionError: If Ollama service unavailable

        Example:
            >>> service = OllamaEmbeddingService()
            >>> embedding = service.generate_embedding("Financial report Q4 2025")
            >>> len(embedding)  # 768 (for nomic-embed-text)
            >>> type(embedding[0])  # float
        """
        # Validation
        if not text or len(text.strip()) < 10:
            raise ValueError(
                "Text must be at least 10 characters (excluding whitespace)"
            )

        try:
            start_time = time.time()

            # Call Ollama API
            response = requests.post(
                f"{self.base_url}/api/embed",
                json={
                    "model": self.model,
                    "input": text
                },
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Extract embedding vector (Ollama returns {"embeddings": [[...]]} )
            embeddings = data.get("embeddings", [])
            if not embeddings or not embeddings[0]:
                raise ValueError(f"Empty embedding returned from Ollama: {data}")
                
            embedding = embeddings[0]

            # Auto-detect dimensions on first call if unknown
            if self.dimensions is None:
                self.dimensions = len(embedding)
                logger.info(f"Auto-detected dimensions: {self.dimensions}")

            # Track metrics
            elapsed = time.time() - start_time
            self.total_requests += 1
            self.total_latency += elapsed
            # Note: Ollama doesn't return token counts, estimate from text length
            estimated_tokens = len(text.split())
            self.total_tokens += estimated_tokens

            logger.debug(
                f"Generated embedding: {len(embedding)} dims, "
                f"{elapsed:.3f}s, ~{estimated_tokens} tokens"
            )

            # Validate dimensions match expected
            if len(embedding) != self.dimensions:
                logger.error(
                    f"Dimension mismatch: expected {self.dimensions}, "
                    f"got {len(embedding)}"
                )

            return embedding

        except requests.RequestException as e:
            logger.error(f"Ollama API error: {e}")
            raise ConnectionError(f"Failed to generate embedding: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error generating embedding: {e}")
            raise

    def generate_embeddings_batch(
        self,
        texts: List[str],
        batch_size: int = 100
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batches.

        Args:
            texts: List of texts to embed
            batch_size: Number of texts per batch (Ollama supports batching)

        Returns:
            List of embedding vectors (same order as input)

        Example:
            >>> service = OllamaEmbeddingService()
            >>> embeddings = service.generate_embeddings_batch([
            ...     "Invoice 001",
            ...     "Receipt 2025-Q4",
            ...     "Bank statement"
            ... ])
            >>> len(embeddings)  # 3
            >>> all(len(e) == 768 for e in embeddings)  # True
        """
        if not texts:
            return []

        embeddings = []
        
        # Process in batches
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            try:
                start_time = time.time()
                
                # Ollama supports batch embedding
                response = requests.post(
                    f"{self.base_url}/api/embed",
                    json={
                        "model": self.model,
                        "input": batch  # Send list of texts
                    },
                    timeout=60
                )
                response.raise_for_status()
                
                data = response.json()
                batch_embeddings = data.get("embeddings", [])
                
                if len(batch_embeddings) != len(batch):
                    raise ValueError(
                        f"Expected {len(batch)} embeddings, got {len(batch_embeddings)}"
                    )
                
                embeddings.extend(batch_embeddings)
                
                # Track metrics
                elapsed = time.time() - start_time
                self.total_requests += 1
                self.total_latency += elapsed
                
                logger.info(
                    f"Batch {i//batch_size + 1}: {len(batch)} embeddings "
                    f"in {elapsed:.2f}s ({len(batch)/elapsed:.1f} emb/s)"
                )
                
            except Exception as e:
                logger.error(f"Batch embedding failed for batch {i//batch_size + 1}: {e}")
                raise

        return embeddings

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get service metrics for monitoring.

        Returns:
            Dictionary with:
            - model: Model name
            - dimensions: Vector dimensions
            - total_requests: Number of API calls
            - total_tokens: Estimated tokens processed
            - total_latency: Total time spent (seconds)
            - avg_latency: Average latency per request
            - total_cost: Always $0 (Ollama is free)
        """
        avg_latency = (
            self.total_latency / self.total_requests
            if self.total_requests > 0
            else 0
        )
        
        return {
            "backend": "ollama",
            "model": self.model,
            "base_url": self.base_url,
            "dimensions": self.dimensions,
            "total_requests": self.total_requests,
            "total_tokens": self.total_tokens,
            "total_latency": round(self.total_latency, 2),
            "avg_latency": round(avg_latency, 3),
            "total_cost": 0.0,  # Ollama is free!
        }

    def check_health(self) -> Dict[str, Any]:
        """
        Check if Ollama service is healthy and model is loaded.
        
        Returns:
            Health status with service info
        """
        try:
            # Test embedding generation
            test_embedding = self.generate_embedding("health check")
            
            return {
                "status": "healthy",
                "backend": "ollama",
                "model": self.model,
                "dimensions": len(test_embedding),
                "base_url": self.base_url,
                "message": "Ollama embedding service operational"
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "backend": "ollama",
                "error": str(e),
                "message": "Ollama service not accessible"
            }
