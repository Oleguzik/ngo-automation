"""
RAG (Retrieval-Augmented Generation) Service for Phase 5B.

Provides semantic search over document chunks and AI-powered Q&A using:
- Vector similarity search (pgvector)
- OpenAI embeddings (text-embedding-3-small)
- GPT-4o-mini for answer generation
- Prompt engineering for factual, citation-rich responses

Architecture:
    1. Embed user question
    2. Search similar chunks using vector similarity
    3. Construct prompt with system instructions + context
    4. Generate answer using GPT-4o-mini
    5. Extract citations and calculate confidence score
"""

import logging
import time
from typing import List, Dict, Any, Optional
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.ai_service import AIService
from app.crud import search_similar_chunks
from app.embedding_service import EmbeddingService
from app.models import DocumentChunk, DocumentProcessing
from app.schemas import SourceCitation, RAGResponse

logger = logging.getLogger(__name__)

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
    Orchestrate Retrieval-Augmented Generation pipeline.
    
    Pipeline:
        1. Embed query → 1536-dimensional vector
        2. Vector search → Retrieve top-K similar chunks
        3. Construct prompt → System instructions + chunks + question
        4. Generate answer → GPT-4o-mini with low temperature
        5. Parse citations → Extract source information
        6. Calculate confidence → Aggregate chunk similarities
    """
    
    def __init__(self):
        """Initialize RAG service with dependencies"""
        self.embedding_service = EmbeddingService()
        self.ai_service = AIService()
    
    def query(
        self,
        question: str,
        organization_id: int,
        db: Session,
        top_k: int = 10,
        temperature: float = RAG_TEMPERATURE,
        min_similarity: float = 0.7
    ) -> RAGResponse:
        """
        Answer a question using RAG pipeline.
        
        Retrieves document chunks matching the question, constructs a prompt
        with retrieved context, generates an answer using GPT-4o-mini, and
        parses citations from the response.
        
        Args:
            question: Natural language question about financial documents
            organization_id: Organization ID for isolation/filtering
            db: Database session
            top_k: Maximum chunks to retrieve (1-50, default 10)
            temperature: LLM temperature (0.0-1.0, lower=more factual)
            min_similarity: Minimum similarity threshold (0.0-1.0, default 0.7)
        
        Returns:
            RAGResponse with answer, sources, confidence score
        
        Raises:
            ValueError: If question is empty or invalid
            HTTPException: If search fails or AI service unavailable
        
        Example:
            >>> service = RAGService()
            >>> response = service.query(
            ...     question="How much did we spend on consulting in Q4?",
            ...     organization_id=1,
            ...     db=db_session
            ... )
            >>> print(response.answer)
            "Based on documents, consulting was €15,000..."
        
        Performance:
            - Embedding generation: ~150ms (OpenAI API)
            - Vector search: ~50ms (pgvector with IVFFlat)
            - GPT-4o-mini generation: ~1000-2000ms
            - Total typical: 1.5-2.5 seconds
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
            logger.debug(f"Searching similar chunks (top_k={top_k})")
            search_results = search_similar_chunks(
                query_embedding=query_embedding,
                organization_id=organization_id,
                db=db,
                top_k=top_k,
                min_similarity=min_similarity
            )
            logger.info(
                f"Vector search complete",
                extra={
                    "chunks_found": len(search_results),
                    "min_similarity": min_similarity
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
                    chunk_id=UUID(chunk_id) if isinstance(chunk_id, str) else chunk_id,
                    similarity_score=round(float(similarity), 3),
                    page_number=page_num
                )
                source_citations.append(citation)
            except (ValidationError, ValueError) as e:
                logger.warning(f"Failed to create citation: {str(e)}")
            
            similarity_scores.append(float(similarity))
        
        context = "\n".join(context_parts)
        
        logger.debug(f"Context constructed: {len(context)} chars from {len(search_results)} chunks")
        
        # Step 4: Generate answer with GPT-4o-mini
        try:
            prompt = RAG_SYSTEM_PROMPT.format(
                context=context,
                question=question
            )
            
            logger.debug(f"Calling GPT-4o-mini (temperature={temperature})")
            response = self.ai_service.chat(
                messages=[
                    {"role": "system", "content": RAG_SYSTEM_PROMPT[:200] + "..."},  # Truncate for logging
                    {"role": "user", "content": question}
                ],
                system=RAG_SYSTEM_PROMPT.format(context=context, question=""),
                temperature=temperature,
                max_tokens=1000
            )
            
            answer = response.get("content", "").strip()
            
            if not answer:
                answer = "Unable to generate answer from retrieved documents."
            
            logger.info(
                f"Answer generated",
                extra={
                    "answer_length": len(answer),
                    "chunks_used": len(search_results)
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
