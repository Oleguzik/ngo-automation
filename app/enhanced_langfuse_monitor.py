"""
Enhanced Langfuse monitoring and tracing for the NGO financial system.

Provides comprehensive observability for document processing, embeddings, RAG queries,
and agentic routing with cost tracking and performance metrics.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
from contextlib import contextmanager
import logging
import time
from enum import Enum

logger = logging.getLogger(__name__)


class OperationType(str, Enum):
    """Types of operations being traced."""
    EMBEDDING_GENERATION = "embedding_generation"
    VECTOR_SEARCH = "vector_search"
    RAG_QUERY = "rag_query"
    DOCUMENT_EXTRACTION = "document_extraction"
    AGENT_ROUTING = "agent_routing"


@dataclass
class EmbeddingMetrics:
    """Metrics for embedding generation operations."""
    texts_processed: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    avg_latency_ms: float = 0.0
    model: str = "nomic-embed-text"
    dimensions: int = 768
    
    def __post_init__(self):
        """Validate metrics values."""
        if self.texts_processed < 0 or self.total_tokens < 0:
            raise ValueError("Metrics must be non-negative")


@dataclass
class RagMetrics:
    """Metrics for RAG query operations."""
    queries_processed: int = 0
    chunks_retrieved: int = 0
    avg_chunk_similarity: float = 0.0
    generation_tokens: int = 0
    total_cost: float = 0.0
    avg_latency_ms: float = 0.0
    model: str = "gpt-4o-mini"
    
    def __post_init__(self):
        """Validate metrics values."""
        if self.queries_processed < 0 or self.chunks_retrieved < 0:
            raise ValueError("Metrics must be non-negative")
        if not (0 <= self.avg_chunk_similarity <= 1):
            raise ValueError("Similarity must be between 0 and 1")


@dataclass
class VectorSearchMetrics:
    """Metrics for vector search operations."""
    searches_performed: int = 0
    chunks_indexed: int = 0
    avg_latency_ms: float = 0.0
    total_queries: int = 0
    cache_hits: int = 0
    
    def __post_init__(self):
        """Validate metrics values."""
        if self.searches_performed < 0 or self.cache_hits < 0:
            raise ValueError("Metrics must be non-negative")


@dataclass
class DocumentExtractionMetrics:
    """Metrics for document extraction operations."""
    documents_processed: int = 0
    chunks_created: int = 0
    extraction_success_rate: float = 0.0
    avg_extraction_latency_ms: float = 0.0
    total_cost: float = 0.0
    failed_extractions: int = 0
    
    def __post_init__(self):
        """Validate metrics values."""
        if not (0 <= self.extraction_success_rate <= 1):
            raise ValueError("Success rate must be between 0 and 1")


@dataclass
class AgentMetrics:
    """Metrics for agentic routing operations."""
    routing_decisions: int = 0
    extract_route_count: int = 0
    rag_route_count: int = 0
    hybrid_route_count: int = 0
    clarify_route_count: int = 0
    avg_routing_latency_ms: float = 0.0
    total_cost: float = 0.0
    
    def __post_init__(self):
        """Validate metrics values."""
        if self.routing_decisions < 0:
            raise ValueError("Routing decisions count must be non-negative")


@dataclass
class OperationTrace:
    """Single operation trace record."""
    operation_type: OperationType
    organization_id: int
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    duration_ms: float = 0.0
    tokens_used: int = 0
    cost: float = 0.0
    status: str = "pending"
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def complete(self, status: str = "success", error: Optional[str] = None, 
                cost: float = 0.0, tokens: int = 0):
        """Mark operation as complete."""
        self.end_time = datetime.utcnow()
        self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000
        self.status = status
        self.error = error
        self.cost = cost
        self.tokens_used = tokens


class EnhancedLangfuseMonitor:
    """
    Enhanced monitoring and tracing using Langfuse.
    
    Provides context managers for automatic trace recording of:
    - Embedding generation with cost tracking
    - Vector search performance
    - RAG query pipeline with chunk retrieval metrics
    - Document extraction with success rate tracking
    - Agentic routing decisions with cost attribution
    """
    
    def __init__(self, enable_tracing: bool = False, organization_id: int = 1):
        """
        Initialize enhanced monitor.
        
        Args:
            enable_tracing: Whether to enable Langfuse tracing
            organization_id: ID of organization for trace context
        """
        self.enable_tracing = enable_tracing
        self.organization_id = organization_id
        self.embedding_metrics = EmbeddingMetrics()
        self.rag_metrics = RagMetrics()
        self.vector_search_metrics = VectorSearchMetrics()
        self.extraction_metrics = DocumentExtractionMetrics()
        self.agent_metrics = AgentMetrics()
        self.traces: List[OperationTrace] = []
    
    @property
    def monitoring_enabled(self) -> bool:
        """Whether monitoring/tracing is currently enabled."""
        return self.enable_tracing
    
    def add_rag_retrieval_span(
        self,
        rag_context: Dict[str, Any],
        chunks_found: int = 0,
        avg_similarity: float = 0.0,
        retrieval_time: float = 0.0
    ) -> None:
        """
        Add retrieval span to RAG monitoring context.
        
        Args:
            rag_context: RAG monitoring context dict
            chunks_found: Number of chunks retrieved
            avg_similarity: Average similarity score
            retrieval_time: Time taken for retrieval in seconds
        """
        if not rag_context:
            return
        spans = rag_context.setdefault("spans", {})
        spans["retrieval"] = {
            "chunks_found": chunks_found,
            "avg_similarity": avg_similarity,
            "retrieval_time_ms": round(retrieval_time * 1000, 2),
        }
        self.rag_metrics.chunks_retrieved += chunks_found
        self.rag_metrics.avg_chunk_similarity = avg_similarity
        logger.debug(f"RAG retrieval span: {chunks_found} chunks, sim={avg_similarity:.3f}")
    
    def add_rag_generation_span(
        self,
        rag_context: Dict[str, Any],
        model: str = "gpt-4.1-mini",
        tokens_used: int = 0,
        generation_time: float = 0.0,
        answer: str = "",
        confidence: float = 0.0
    ) -> None:
        """
        Add generation span to RAG monitoring context.
        
        Args:
            rag_context: RAG monitoring context dict
            model: LLM model used
            tokens_used: Token count for generation
            generation_time: Time taken for generation in seconds
            answer: Generated answer text
            confidence: Confidence score
        """
        if not rag_context:
            return
        spans = rag_context.setdefault("spans", {})
        spans["generation"] = {
            "model": model,
            "tokens_used": tokens_used,
            "generation_time_ms": round(generation_time * 1000, 2),
            "answer_length": len(answer),
            "confidence": confidence,
        }
        self.rag_metrics.generation_tokens += tokens_used
        logger.debug(f"RAG generation span: {tokens_used} tokens, {generation_time:.2f}s")
        
    @contextmanager
    def trace_embedding_generation(self, texts_count: int = 0, model: str = "nomic-embed-text"):
        """
        Context manager for tracing embedding generation.
        
        Args:
            texts_count: Number of texts being embedded
            model: Embedding model name
            
        Yields:
            Trace metadata dict for recording results
        """
        trace = OperationTrace(
            operation_type=OperationType.EMBEDDING_GENERATION,
            organization_id=self.organization_id,
            metadata={"texts_count": texts_count, "model": model}
        )
        
        try:
            yield trace.metadata
            trace.complete(status="success")
            self.embedding_metrics.texts_processed += texts_count
        except Exception as e:
            trace.complete(status="error", error=str(e))
            logger.error(f"Embedding generation failed: {str(e)}")
            raise
        finally:
            self.traces.append(trace)
    
    @contextmanager
    def trace_vector_search(self, query: str = "", top_k: int = 5):
        """
        Context manager for tracing vector search operations.
        
        Args:
            query: Search query text
            top_k: Number of results to retrieve
            
        Yields:
            Trace metadata dict
        """
        trace = OperationTrace(
            operation_type=OperationType.VECTOR_SEARCH,
            organization_id=self.organization_id,
            metadata={"query": query[:100], "top_k": top_k}
        )
        
        try:
            yield trace.metadata
            trace.complete(status="success")
            self.vector_search_metrics.searches_performed += 1
        except Exception as e:
            trace.complete(status="error", error=str(e))
            logger.error(f"Vector search failed: {str(e)}")
            raise
        finally:
            self.traces.append(trace)
    
    @contextmanager
    def trace_rag_query(self, question: str = "", chunks_retrieved: int = 0):
        """
        Context manager for tracing RAG query pipeline.
        
        Args:
            question: User question
            chunks_retrieved: Number of chunks retrieved
            
        Yields:
            Trace metadata dict
        """
        trace = OperationTrace(
            operation_type=OperationType.RAG_QUERY,
            organization_id=self.organization_id,
            metadata={"question": question[:100], "chunks_retrieved": chunks_retrieved}
        )
        
        try:
            yield trace.metadata
            trace.complete(status="success")
            self.rag_metrics.queries_processed += 1
            self.rag_metrics.chunks_retrieved += chunks_retrieved
        except Exception as e:
            trace.complete(status="error", error=str(e))
            logger.error(f"RAG query failed: {str(e)}")
            raise
        finally:
            self.traces.append(trace)
    
    @contextmanager
    def trace_document_extraction(self, document_name: str = "", doc_type: str = ""):
        """
        Context manager for tracing document extraction.
        
        Args:
            document_name: Name of document
            doc_type: Type of document (invoice, receipt, etc.)
            
        Yields:
            Trace metadata dict
        """
        trace = OperationTrace(
            operation_type=OperationType.DOCUMENT_EXTRACTION,
            organization_id=self.organization_id,
            metadata={"document": document_name[:50], "type": doc_type}
        )
        
        try:
            yield trace.metadata
            trace.complete(status="success")
            self.extraction_metrics.documents_processed += 1
        except Exception as e:
            trace.complete(status="error", error=str(e))
            self.extraction_metrics.failed_extractions += 1
            logger.error(f"Document extraction failed: {str(e)}")
            raise
        finally:
            self.traces.append(trace)
    
    @contextmanager
    def trace_agent_routing(self, question: str = ""):
        """
        Context manager for tracing agentic routing decisions.
        
        Args:
            question: User question for routing
            
        Yields:
            Trace metadata dict
        """
        trace = OperationTrace(
            operation_type=OperationType.AGENT_ROUTING,
            organization_id=self.organization_id,
            metadata={"question": question[:100]}
        )
        
        try:
            yield trace.metadata
            trace.complete(status="success")
            self.agent_metrics.routing_decisions += 1
        except Exception as e:
            trace.complete(status="error", error=str(e))
            logger.error(f"Agent routing failed: {str(e)}")
            raise
        finally:
            self.traces.append(trace)
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary of all traced operations.
        
        Returns:
            Dictionary with metrics summary
        """
        return {
            "embedding_metrics": {
                "texts_processed": self.embedding_metrics.texts_processed,
                "total_tokens": self.embedding_metrics.total_tokens,
                "total_cost": self.embedding_metrics.total_cost,
            },
            "rag_metrics": {
                "queries_processed": self.rag_metrics.queries_processed,
                "chunks_retrieved": self.rag_metrics.chunks_retrieved,
                "avg_chunk_similarity": self.rag_metrics.avg_chunk_similarity,
            },
            "vector_search_metrics": {
                "searches_performed": self.vector_search_metrics.searches_performed,
                "cache_hits": self.vector_search_metrics.cache_hits,
            },
            "extraction_metrics": {
                "documents_processed": self.extraction_metrics.documents_processed,
                "chunks_created": self.extraction_metrics.chunks_created,
                "failed_extractions": self.extraction_metrics.failed_extractions,
            },
            "agent_metrics": {
                "routing_decisions": self.agent_metrics.routing_decisions,
                "extract_route_count": self.agent_metrics.extract_route_count,
                "rag_route_count": self.agent_metrics.rag_route_count,
            },
            "total_traces": len(self.traces),
        }


# Decorator functions for easy usage
def trace_embedding(func):
    """Decorator to trace embedding generation functions."""
    def wrapper(*args, **kwargs):
        monitor = EnhancedLangfuseMonitor()
        with monitor.trace_embedding_generation():
            return func(*args, **kwargs)
    return wrapper


def trace_rag_query_operation(func):
    """Decorator to trace RAG query operations."""
    def wrapper(*args, **kwargs):
        monitor = EnhancedLangfuseMonitor()
        with monitor.trace_rag_query():
            return func(*args, **kwargs)
    return wrapper


def trace_agent_decision(func):
    """Decorator to trace agent routing decisions."""
    def wrapper(*args, **kwargs):
        monitor = EnhancedLangfuseMonitor()
        with monitor.trace_agent_routing():
            return func(*args, **kwargs)
    return wrapper


# Aliases for backward compatibility with importers
trace_rag_query = trace_rag_query_operation
trace_agent = trace_agent_decision

# Module-level singleton instance
enhanced_monitor = EnhancedLangfuseMonitor()
