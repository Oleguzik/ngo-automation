"""
RAG (Retrieval-Augmented Generation) Service for Phase 5B + Phase 5C Langfuse Integration.

Provides semantic search over document chunks and AI-powered Q&A using:
- Vector similarity search (pgvector)
- OpenAI embeddings (text-embedding-3-small)
- GPT-4.1-mini for answer generation
- Prompt engineering for factual, citation-rich responses

Phase 5C Additions:
- Langfuse observability with @observe decorator
- Background evaluation via LLM-as-a-Judge
- Automatic faithfulness scoring
- Trace ID tracking for experiment analysis

Architecture:
    1. Embed user question
    2. Search similar chunks using vector similarity
    3. Construct prompt with system instructions + context
    4. Generate answer using GPT-4.1-mini
    5. Extract citations and calculate confidence score
    6. Schedule background evaluation (faithfulness check)
"""

import logging
import time
import os
from typing import List, Dict, Any, Optional
from decimal import Decimal

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import ValidationError

# Langfuse imports
try:
    from langfuse import observe, get_client
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    logging.warning("Langfuse not installed. Observability disabled.")

from app.ai_service import AIService
from app.crud import search_similar_chunks
from app.embedding_service import get_embedding_service
from app.enhanced_langfuse_monitor import enhanced_monitor, trace_rag_query
from app.models import DocumentChunk, DocumentProcessing
from app.schemas import SourceCitation, RAGResponse
from app.semantic_cache import get_semantic_cache
from app.ollama_chat_service import get_ollama_chat_service
from app.config import settings

logger = logging.getLogger(__name__)

# Initialize Langfuse if available
if LANGFUSE_AVAILABLE and os.getenv("LANGFUSE_PUBLIC_KEY"):
    langfuse = get_client()
else:
    langfuse = None


# Temperature for factual answers (0.1 = low variability)
RAG_TEMPERATURE = 0.1

# System prompt for RAG queries
RAG_SYSTEM_PROMPT = """
You are a helpful financial advisor for a nonprofit organization.

Your role:
- Answer questions about financial documents using ONLY the provided context
- Be factual and concise, citing specific figures and dates
- Maintain organizational perspective and confidentiality
- Acknowledge data limitations if information is incomplete

Instructions:
1. If the answer is NOT in the provided chunks, respond: "I don't have that information in the uploaded documents."
2. Always cite sources using the format: [Source: document_name, page X]
3. Be specific with amounts, dates, and percentages from the documents
4. Do not make assumptions or extrapolate beyond provided data
5. If multiple interpretations exist, note the ambiguity

Context from Financial Documents:
{context}

Question: {question}

Answer based ONLY on the provided context above. Be concise and cite sources.
"""


class RAGService:
    """
    Orchestrate Retrieval-Augmented Generation pipeline with semantic caching.
    
    Pipeline:
        1. Check semantic cache for similar question (95%+ similarity)
        2. If cache hit → Return cached answer (saves ~$0.35 per query)
        3. If cache miss → Continue with full RAG pipeline
        4. Embed query → 1536-dimensional vector
        5. Vector search → Retrieve top-K similar chunks
        6. Construct prompt → System instructions + chunks + question
        7. Generate answer → GPT-4.1-mini with low temperature
        8. Parse citations → Extract source information
        9. Calculate confidence → Aggregate chunk similarities
        10. Cache result for future similar queries
    
    Cost optimization:
        - Cache hits: No API calls (save ~$0.35/query)
        - Cache misses: Full pipeline (~$0.40/query for embedding + GPT)
        - With 30% hit rate: Reduce costs by ~35% monthly
        - Typical hit rate: 20-40% for financial Q&A
    """
    
    def __init__(self, use_cache: bool = True):
        """
        Initialize RAG service with optional semantic caching.
        
        Args:
            use_cache: Enable semantic caching (default True)
        """
        self.embedding_service = get_embedding_service()
        self.ai_service = AIService()
        self.ollama_chat = get_ollama_chat_service()
        self.use_cache = use_cache
        self.semantic_cache = get_semantic_cache() if use_cache else None
        
        # Determine which LLM backend to use
        self.llm_backend = settings.LLM_BACKEND.lower()
        self.model_name = settings.OPENAI_MODEL if self.llm_backend == "openai" else settings.OLLAMA_CHAT_MODEL
        
        logger.info(f"RAGService initialized: llm_backend={self.llm_backend}, model={self.model_name}")
    
    async def query_async(
        self,
        question: str,
        organization_id: int,
        db: Session,
        top_k: int = 10,
        temperature: float = RAG_TEMPERATURE,
        min_similarity: float = 0.5
    ) -> RAGResponse:
        """
        Answer a question using RAG pipeline with semantic caching (async).
        
        Attempts to retrieve from semantic cache before running full pipeline.
        If similar question exists in cache (95%+ similarity), returns cached answer.
        Otherwise, runs full RAG pipeline and caches result.
        
        Args:
            question: Natural language question about financial documents
            organization_id: Organization ID for isolation/filtering
            db: Database session
            top_k: Maximum chunks to retrieve (1-50, default 10)
            temperature: LLM temperature (0.0-1.0, lower=more factual)
            min_similarity: Minimum similarity threshold (0.0-1.0, default 0.7)
        
        Returns:
            RAGResponse with answer, sources, confidence score
        
        Example:
            >>> response = await service.query_async(
            ...     question="How much consulting in Q4?",
            ...     organization_id=1,
            ...     db=db
            ... )
        """
        # Try cache first
        if self.use_cache and self.semantic_cache:
            cached_response = await self.semantic_cache.get(
                question=question,
                organization_id=organization_id
            )
            if cached_response:
                return cached_response
        
        # Cache miss or disabled → run full pipeline
        response = await self._run_pipeline(
            question=question,
            organization_id=organization_id,
            db=db,
            top_k=top_k,
            temperature=temperature,
            min_similarity=min_similarity
        )
        
        # Cache result
        if self.use_cache and self.semantic_cache:
            await self.semantic_cache.set(
                question=question,
                rag_response=response,
                organization_id=organization_id
            )
        
        return response
    
    
    @trace_rag_query
    def query(
        self,
        question: str,
        organization_id: int,
        db: Session,
        top_k: int = 3,  # Reduced from 10 for faster Ollama performance
        temperature: float = RAG_TEMPERATURE,
        min_similarity: float = 0.5,
        background_tasks: Optional[BackgroundTasks] = None,
        enable_evaluation: bool = False,
        rag_context: Dict[str, Any] = None  # Injected by decorator
    ) -> RAGResponse:
        """
        Answer a question using RAG pipeline (synchronous wrapper).
        
        This is the main synchronous endpoint for RAG queries.
        Internally uses async pipeline with caching.
        
        Phase 5C Addition:
        - Accepts BackgroundTasks for asynchronous evaluation
        - Schedules faithfulness check via LLM-as-a-Judge
        - Sends scores to Langfuse for experiment tracking
        
        Args:
            question: Natural language question about financial documents
            organization_id: Organization ID for isolation/filtering
            db: Database session
            top_k: Maximum chunks to retrieve (1-50, default 10)
            temperature: LLM temperature (0.0-1.0, lower=more factual)
            min_similarity: Minimum similarity threshold (0.0-1.0, default 0.7)
            background_tasks: FastAPI BackgroundTasks for async evaluation (optional)
            enable_evaluation: Enable automatic quality evaluation (default: False)
        
        Returns:
            RAGResponse with answer, sources, confidence score, trace_id
        
        Raises:
            ValueError: If question is empty or invalid
            HTTPException: If search fails or AI service unavailable
        
        Example:
            >>> service = RAGService()
            >>> response = service.query(
            ...     question="How much did we spend on consulting in Q4?",
            ...     organization_id=1,
            ...     db=db_session,
            ...     background_tasks=background_tasks,
            ...     enable_evaluation=True
            ... )
            >>> print(response.answer)
            "Based on documents, consulting was €15,000..."
            >>> print(response.trace_id)  # For Langfuse dashboard
            "trace-abc123"
        """
        # Try cache first
        if self.use_cache and self.semantic_cache:
            cached_response = self.semantic_cache.get_sync(
                question=question,
                organization_id=organization_id
            )
            if cached_response:
                return cached_response
        
        # Cache miss or disabled → run full pipeline
        response = self._run_pipeline(
            question=question,
            organization_id=organization_id,
            db=db,
            top_k=top_k,
            temperature=temperature,
            min_similarity=min_similarity,
            rag_context=rag_context  # Pass monitoring context
        )
        
        # Schedule background evaluation if enabled
        if enable_evaluation and background_tasks and LANGFUSE_AVAILABLE and langfuse:
            from app.evaluation_service import RAGEvaluator
            
            # Create trace for this query using SDK v3 API
            with langfuse.start_as_current_observation(
                as_type="span",
                name="rag_query",
                input={"question": question, "organization_id": organization_id},
                output={"answer": response.answer},
                metadata={
                    "chunks_used": response.chunks_used,
                    "confidence": response.confidence,
                    "top_k": top_k,
                    "min_similarity": min_similarity,
                    "tags": ["rag", "phase5c"]  # Move tags to metadata for v3
                }
            ) as rag_trace:
                # Get the trace ID for evaluation
                trace_id = langfuse.get_current_trace_id()
                
                # Construct context from sources
                context_str = "\n\n".join([
                    f"[{s.document_name}] Similarity: {s.similarity_score}"
                    for s in response.sources
                ])
                
                # Schedule faithfulness evaluation
                evaluator = RAGEvaluator()
                background_tasks.add_task(
                    evaluator.evaluate_faithfulness,
                    trace_id=trace_id,
                    query=question,
                    context=context_str,
                    response=response.answer
                )
                
                logger.info(f"Scheduled faithfulness evaluation for trace {trace_id}")
                
                # Add trace_id to response metadata (create new response with additional data)
                base_url = os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")
                response_dict = response.model_dump()
                # Note: RAGResponse doesn't have metadata field, so we'll add trace info to a copy
                response_dict["trace_id"] = trace_id
                # Don't modify the original response, just log trace info
                
                logger.info(f"🎉 RAG query with Langfuse tracing completed: {base_url}/trace/{trace_id}")
        
        # Cache result
        if self.use_cache and self.semantic_cache:
            self.semantic_cache.set_sync(
                question=question,
                rag_response=response,
                organization_id=organization_id
            )
        
        return response
    
    def _run_pipeline(
        self,
        question: str,
        organization_id: int,
        db: Session,
        top_k: int = 10,
        temperature: float = RAG_TEMPERATURE,
        min_similarity: float = 0.5,
        rag_context: Dict[str, Any] = None  # Monitoring context
    ) -> RAGResponse:
        """
        Execute full RAG pipeline (internal method).
        
        This is the core RAG pipeline that:
        1. Embeds question
        2. Searches for similar chunks
        3. Generates answer with GPT-4.1-mini
        4. Extracts citations and calculates confidence
        
        Called by query() either after cache miss or directly if caching disabled.
        """
        start_time = time.time()
        
        # Validate inputs
        if not question or not question.strip():
            raise ValueError("Question cannot be empty")
        
        question = question.strip()
        
        logger.info(
            f"RAG Query started",
            extra={
                "organization_id": organization_id,
                "question": question[:100],
                "top_k": top_k,
                "min_similarity": min_similarity
            }
        )
        
        # Step 1: Embed the question
        try:
            logger.debug(f"Embedding question ({len(question)} chars)")
            query_embedding = self.embedding_service.generate_embedding(question)
            logger.debug(f"Question embedded: {len(query_embedding)} dimensions")
        except Exception as e:
            logger.error(f"Failed to embed question: {str(e)}", exc_info=True)
            raise ValueError(f"Failed to embed question: {str(e)}")
        
        # Step 2: Search for similar chunks
        try:
            retrieval_start = time.time()
            logger.debug(f"Searching similar chunks (top_k={top_k})")
            search_results = search_similar_chunks(
                query_embedding=query_embedding,
                organization_id=organization_id,
                db=db,
                top_k=top_k,
                min_similarity=min_similarity
            )
            retrieval_time = time.time() - retrieval_start
            
            # Track retrieval metrics with enhanced monitoring
            avg_similarity = sum(r.get("similarity_score", 0.0) for r in search_results) / len(search_results) if search_results else 0.0
            if rag_context and enhanced_monitor.monitoring_enabled:
                enhanced_monitor.add_rag_retrieval_span(
                    rag_context,
                    chunks_found=len(search_results),
                    avg_similarity=avg_similarity,
                    retrieval_time=retrieval_time
                )
            
            logger.info(
                f"Vector search complete",
                extra={
                    "chunks_found": len(search_results),
                    "min_similarity": min_similarity,
                    "retrieval_time_ms": round(retrieval_time * 1000, 2),
                    "avg_similarity": round(avg_similarity, 3)
                }
            )
        except Exception as e:
            logger.error(f"Vector search failed: {str(e)}", exc_info=True)
            raise ValueError(f"Vector search failed: {str(e)}")
        
        # Handle no results case
        if not search_results:
            logger.info(
                f"No relevant chunks found for question",
                extra={"organization_id": organization_id}
            )
            return RAGResponse(
                question=question,
                answer="I don't have information about that topic in the uploaded documents. Please upload additional documents or try a different question.",
                sources=[],
                confidence=0.0,
                chunks_used=0,
                query_time_ms=round((time.time() - start_time) * 1000, 2)
            )
        
        # Step 3: Construct context from retrieved chunks
        context_parts = []
        source_citations: List[SourceCitation] = []
        similarity_scores: List[float] = []
        
        for i, result in enumerate(search_results, 1):
            # Add chunk to context
            doc_name = result.get("document_name", "Unknown Document")
            chunk_text = result.get("chunk_text", "")
            similarity = result.get("similarity_score", 0.0)
            chunk_id = result.get("chunk_id", "")
            metadata = result.get("metadata", {})
            
            # Extract page number if available
            page_num = None
            if metadata and isinstance(metadata, dict):
                page_num = metadata.get("page")
            
            context_parts.append(
                f"[Document {i}: {doc_name}]\n{chunk_text}\n"
            )
            
            # Create source citation
            try:
                citation = SourceCitation(
                    document_name=doc_name,
                    chunk_id=int(chunk_id) if chunk_id else 0,
                    similarity_score=round(float(similarity), 3),
                    page_number=page_num
                )
                source_citations.append(citation)
            except (ValidationError, ValueError) as e:
                logger.warning(f"Failed to create citation: {str(e)}")
            
            similarity_scores.append(float(similarity))
        
        context = "\n".join(context_parts)
        
        logger.debug(f"Context constructed: {len(context)} chars from {len(search_results)} chunks")
        
        # Step 4: Generate answer using configured LLM backend (OpenAI or Ollama)
        try:
            generation_start = time.time()
            prompt = RAG_SYSTEM_PROMPT.format(
                context=context,
                question=question
            )
            
            logger.debug(f"Calling {self.llm_backend.upper()} {self.model_name} (temperature={temperature})")
            
            # Choose backend based on configuration
            if self.llm_backend == "ollama":
                # Use Ollama local model
                response = self.ollama_chat.generate(
                    messages=[
                        {"role": "system", "content": RAG_SYSTEM_PROMPT.format(context=context, question="")},
                        {"role": "user", "content": question}
                    ],
                    temperature=temperature,
                    max_tokens=1000
                )
            else:
                # Use OpenAI (default)
                response = self.ai_service.chat(
                    messages=[
                        {"role": "system", "content": RAG_SYSTEM_PROMPT[:200] + "..."},  # Truncate for logging
                        {"role": "user", "content": question}
                    ],
                    system=RAG_SYSTEM_PROMPT.format(context=context, question=""),
                    temperature=temperature,
                    max_tokens=1000
                )
            
            generation_time = time.time() - generation_start
            
            answer = response.get("content", "").strip()
            
            if not answer:
                answer = "Unable to generate answer from retrieved documents."
            
            # Track generation metrics
            tokens_used = response.get("usage", {}).get("total_tokens") or response.get("tokens_used", len(answer) // 4)
            if rag_context and enhanced_monitor.monitoring_enabled:
                enhanced_monitor.add_rag_generation_span(
                    rag_context,
                    model=self.model_name,
                    tokens_used=tokens_used,
                    generation_time=generation_time,
                    answer=answer,
                    confidence=0.0  # Will be updated below
                )
            
            logger.info(
                f"Answer generated",
                extra={
                    "answer_length": len(answer),
                    "chunks_used": len(search_results),
                    "generation_time_ms": round(generation_time * 1000, 2),
                    "tokens_used": tokens_used
                }
            )
        except Exception as e:
            logger.error(f"Answer generation failed: {str(e)}", exc_info=True)
            raise ValueError(f"Failed to generate answer: {str(e)}")
        
        # Step 5: Calculate confidence score
        # Average similarity of top chunks
        if similarity_scores:
            confidence = sum(similarity_scores) / len(similarity_scores)
            confidence = min(1.0, max(0.0, confidence))  # Clamp to 0-1
        else:
            confidence = 0.0
        
        # Update generation span with confidence score
        if rag_context and enhanced_monitor.monitoring_enabled:
            # Update the generation span with calculated confidence
            generation_spans = rag_context.get("spans", {})
            if "generation" in generation_spans:
                generation_span = generation_spans["generation"]
                # Note: Cannot modify span output after creation in Langfuse
                # This is informational for our tracking
                logger.debug(f"Final confidence score: {confidence:.3f}")
        
        logger.info(
            f"RAG Query completed",
            extra={
                "organization_id": organization_id,
                "chunks_used": len(search_results),
                "confidence": round(confidence, 3),
                "total_time_ms": round((time.time() - start_time) * 1000, 2)
            }
        )
        
        return RAGResponse(
            question=question,
            answer=answer,
            sources=source_citations,
            confidence=round(confidence, 3),
            chunks_used=len(search_results),
            query_time_ms=round((time.time() - start_time) * 1000, 2)
        )
    
    def _extract_citations_from_answer(self, answer: str) -> List[str]:
        """
        Extract source citations from answer text.
        
        Looks for patterns like: [Source: filename, page X]
        
        Args:
            answer: Generated answer text
        
        Returns:
            List of citation strings found
        
        Example:
            >>> answer = "Result: €5000 [Source: invoice.pdf, page 1]"
            >>> citations = self._extract_citations_from_answer(answer)
            >>> citations
            ['[Source: invoice.pdf, page 1]']
        """
        import re
        pattern = r'\[Source: [^\]]+\]'
        return re.findall(pattern, answer)
