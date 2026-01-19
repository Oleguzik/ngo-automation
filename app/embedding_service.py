"""
Phase 5 RAG Foundation: Embedding Service

Generates vector embeddings using OpenAI's text-embedding-3-small model.
- Model: text-embedding-3-small
- Dimensions: 1536
- Cost: $0.02 per 1M tokens
- Used for semantic search and RAG retrieval

Reference: docs/00-spec-rag-implementation.md Section 2.1
           docs/02-architecture-phase5.md Section 4.1
           docs/PHASE5_IMPLEMENTATION_DECISIONS.md Section 1
"""

import os
import logging
import time
from typing import List
import openai
from tenacity import retry, wait_exponential, stop_after_attempt

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Generate vector embeddings using OpenAI API.
    
    Attributes:
        model: Embedding model name (text-embedding-3-small)
        dimensions: Number of dimensions in embedding vector (1536)
        total_tokens: Cumulative token count for cost tracking
        total_cost: Cumulative cost in USD
        
    From spec (00-spec-rag-implementation.md):
    - Model: text-embedding-3-small
    - Dimensions: 1536
    - Cost: $0.02 per 1M tokens (~$0.02-0.50/month based on volume)
    """

    def __init__(self, api_key: str = None):
        """
        Initialize embedding service with OpenAI API credentials.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)

        Raises:
            ValueError: If API key not provided and not in environment
        """
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY environment variable."
            )

        self.client = openai.OpenAI(api_key=api_key)
        self.model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        self.dimensions = 1536
        self.total_tokens = 0
        self.total_cost = 0.0

        logger.info(
            f"EmbeddingService initialized with model={self.model}, "
            f"dimensions={self.dimensions}"
        )

    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=10),
        stop=stop_after_attempt(3),
    )
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for single text chunk.

        From 00-spec-rag-implementation.md:
        - Input: 500-token text chunk
        - Output: 1536-dimensional vector
        - Used for semantic search via cosine similarity

        Args:
            text: Input text to embed (recommended 50-2000 chars ~ 10-500 tokens)

        Returns:
            List of 1536 floats representing the embedding vector

        Raises:
            openai.RateLimitError: If rate limited (will retry up to 3 times)
            openai.AuthenticationError: If API key invalid
            ValueError: If text empty or too short

        Example:
            >>> service = EmbeddingService()
            >>> embedding = service.generate_embedding("Financial report Q4 2025")
            >>> len(embedding)  # 1536
            >>> type(embedding[0])  # float
        """
        # Validation
        if not text or len(text.strip()) < 10:
            raise ValueError(
                "Text must be at least 10 characters (excluding whitespace)"
            )

        try:
            start_time = time.time()

            # Call OpenAI API
            response = self.client.embeddings.create(
                input=text, model=self.model, dimensions=self.dimensions
            )

            # Extract embedding vector
            embedding = response.data[0].embedding
            tokens = response.usage.prompt_tokens

            # Track metrics
            elapsed = time.time() - start_time
            cost = (tokens / 1_000_000) * 0.02
            self.total_tokens += tokens
            self.total_cost += cost

            # Validate
            if len(embedding) != self.dimensions:
                raise ValueError(
                    f"Expected {self.dimensions} dimensions, got {len(embedding)}"
                )

            logger.info(
                f"Generated embedding: {len(embedding)} dims, "
                f"{tokens} tokens, ${cost:.6f}, {elapsed*1000:.1f}ms"
            )

            return embedding

        except openai.RateLimitError as e:
            logger.warning(f"Rate limited, retrying: {str(e)}")
            raise
        except openai.AuthenticationError as e:
            logger.error(f"Authentication error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Embedding generation failed: {str(e)}")
            raise

    def generate_embeddings_batch(
        self, texts: List[str], batch_size: int = None
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.

        Batch processing is more efficient than individual calls.
        From 00-spec: Maximum batch size is 100 texts per call.

        Args:
            texts: List of texts to embed (max 100 per batch)
            batch_size: Process in chunks (default from EMBEDDING_BATCH_SIZE env)

        Returns:
            List of embedding vectors, one per text

        Raises:
            ValueError: If more than 100 texts provided
            openai.RateLimitError: If rate limited

        Example:
            >>> texts = ["Document 1", "Document 2", "Document 3"]
            >>> embeddings = service.generate_embeddings_batch(texts)
            >>> len(embeddings)  # 3
            >>> len(embeddings[0])  # 1536
        """
        batch_size = batch_size or int(
            os.getenv("EMBEDDING_BATCH_SIZE", "100")
        )

        if len(texts) > batch_size:
            raise ValueError(
                f"Cannot embed more than {batch_size} texts at once. "
                f"Requested: {len(texts)}"
            )

        if not texts:
            raise ValueError("Texts list cannot be empty")

        try:
            start_time = time.time()

            response = self.client.embeddings.create(
                input=texts, model=self.model, dimensions=self.dimensions
            )

            embeddings = [item.embedding for item in response.data]
            tokens = response.usage.prompt_tokens

            # Track metrics
            elapsed = time.time() - start_time
            cost = (tokens / 1_000_000) * 0.02
            self.total_tokens += tokens
            self.total_cost += cost

            logger.info(
                f"Generated {len(embeddings)} embeddings in batch: "
                f"{tokens} tokens, ${cost:.6f}, {elapsed*1000:.1f}ms"
            )

            return embeddings

        except Exception as e:
            logger.error(f"Batch embedding generation failed: {str(e)}")
            raise

    def get_cost_summary(self) -> dict:
        """
        Get cumulative cost and token usage.

        Returns:
            Dict with total_tokens, total_cost, avg_cost_per_token

        Example:
            >>> service.get_cost_summary()
            {
                'total_tokens': 5000,
                'total_cost': 0.0001,
                'avg_cost_per_token': 0.00000002
            }
        """
        avg_cost_per_token = (
            self.total_cost / self.total_tokens
            if self.total_tokens > 0
            else 0
        )

        return {
            "total_tokens": self.total_tokens,
            "total_cost": round(self.total_cost, 6),
            "avg_cost_per_token": avg_cost_per_token,
            "model": self.model,
            "dimensions": self.dimensions,
        }

    def reset_metrics(self) -> None:
        """Reset cumulative token and cost tracking."""
        self.total_tokens = 0
        self.total_cost = 0.0
        logger.info("Embedding service metrics reset")


# Singleton instance for application
_embedding_service_instance = None


def get_embedding_service() -> EmbeddingService:
    """
    Get or create singleton EmbeddingService instance.

    Used for dependency injection in FastAPI endpoints.

    Returns:
        EmbeddingService instance

    Example:
        from app.embedding_service import get_embedding_service

        @app.post("/embed")
        def embed(text: str, service: EmbeddingService = Depends(get_embedding_service)):
            embedding = service.generate_embedding(text)
            return embedding
    """
    global _embedding_service_instance
    if _embedding_service_instance is None:
        _embedding_service_instance = EmbeddingService()
    return _embedding_service_instance
