"""
RAG Evaluation Service for Phase 5B Quality Assurance + Phase 5C Langfuse Integration.

Evaluates RAG pipeline quality using LangSmith-recommended metrics:
1. Retrieval Quality: Are retrieved chunks relevant to the question?
2. Answer Quality: Does answer match retrieved context?
3. Citation Accuracy: Are citations correct and verifiable?
4. Hallucination Detection: Does answer contain unsupported claims?
5. Confidence Calibration: Is confidence score accurate?

Phase 5C Additions (Langfuse):
6. Routing Correctness: Did agentic router choose correct tool?
7. Reasoning Clarity: Is routing reasoning logical and well-explained?

Architecture:
    - Uses LLM-as-judge pattern for semantic evaluation
    - Tracks metrics for regression detection
    - Supports offline (curated datasets) and online (production) evaluation
    - Cost: ~$0.01 per evaluation (GPT-4.1-mini)
    - Langfuse integration for automatic scoring and trace management

Reference: docs-langchain LangSmith evaluation patterns
           docs/PHASE5B_FINAL_REPORT.md RAG quality metrics
           docs/PHASE5C_LANGFUSE_INTEGRATION.md Prompt experimentation
"""

import logging
import os
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID
import json

from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from openai import AsyncOpenAI

# Langfuse imports
try:
    from langfuse import Langfuse
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    logging.warning("Langfuse not installed. Install with: pip install langfuse")

from app.ai_service import AIService
from app.models import DocumentChunk
from app.schemas import RAGResponse, SourceCitation, JudgeResult, RouteEvaluationInput

logger = logging.getLogger(__name__)

# Initialize Langfuse client if available
if LANGFUSE_AVAILABLE and os.getenv("LANGFUSE_PUBLIC_KEY"):
    langfuse = Langfuse(
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        host=os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")
    )
    logger.info("Langfuse initialized successfully")
else:
    langfuse = None
    logger.info("Langfuse disabled (missing credentials or package)")

# Initialize OpenAI client for GPT-4 judge
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))



@dataclass
class RetrievalEvaluation:
    """Results from retrieval quality evaluation."""
    
    relevance_score: float = Field(..., description="0-1, higher = more relevant chunks")
    coverage_score: float = Field(..., description="0-1, does top-k cover question aspects?")
    diversity_score: float = Field(..., description="0-1, chunks provide diverse perspectives?")
    feedback: str = Field(..., description="Qualitative feedback on retrieval")
    
    @property
    def mean_score(self) -> float:
        """Average of all retrieval metrics."""
        return (self.relevance_score + self.coverage_score + self.diversity_score) / 3


@dataclass
class AnswerEvaluation:
    """Results from answer quality evaluation."""
    
    factuality_score: float = Field(..., description="0-1, facts supported by chunks?")
    relevance_score: float = Field(..., description="0-1, answer addresses question?")
    conciseness_score: float = Field(..., description="0-1, concise without losing info?")
    hallucination_score: float = Field(..., description="0-1, higher = more hallucinations")
    citation_coverage: float = Field(..., description="0-1, key facts cited?")
    feedback: str = Field(..., description="Qualitative feedback on answer")
    
    @property
    def mean_score(self) -> float:
        """Average answer quality (excluding hallucination)."""
        scores = [
            self.factuality_score,
            self.relevance_score,
            self.conciseness_score,
            1.0 - self.hallucination_score,  # Invert: lower hallucination = higher quality
            self.citation_coverage
        ]
        return sum(scores) / len(scores)


@dataclass
class RAGEvaluationResult:
    """Complete RAG evaluation result."""
    
    retrieval_eval: RetrievalEvaluation
    answer_eval: AnswerEvaluation
    passed: bool = Field(..., description="Overall pass (both evals > thresholds)")
    pass_reason: str = Field(..., description="Explanation of pass/fail")
    
    @property
    def overall_score(self) -> float:
        """Weighted average of retrieval and answer quality."""
        # 60% answer quality, 40% retrieval (answer matters more)
        return (0.6 * self.answer_eval.mean_score) + (0.4 * self.retrieval_eval.mean_score)


class RAGEvaluator:
    """
    Evaluate RAG pipeline quality for regression detection and quality assurance.
    
    Uses GPT-4.1-mini as judge for semantic evaluation of:
    - Retrieval relevance (do chunks match question?)
    - Answer factuality (is answer supported by chunks?)
    - Hallucination detection (are claims from context?)
    - Citation accuracy (are citations correct?)
    
    Typical evaluation flow:
        1. Run RAG query → Get answer + chunks
        2. Evaluate retrieval quality
        3. Evaluate answer quality
        4. Aggregate scores → Pass/fail decision
        5. Log for monitoring dashboard
    
    Cost tracking:
        - Each evaluation: ~400-500 tokens from GPT-4.1-mini
        - Cost: ~$0.01 per evaluation
        - Monthly budget: ~$50 for 5000 evaluations
    """
    
    def __init__(self, ai_service: Optional[AIService] = None):
        """
        Initialize evaluator with AI service.
        
        Args:
            ai_service: AI service for LLM evaluation (uses GPT-4.1-mini)
                       Defaults to global AIService instance
        """
        self.ai_service = ai_service or AIService()
        
        # Evaluation thresholds for pass/fail decisions
        self.retrieval_quality_threshold = 0.75  # Retrieved chunks relevant?
        self.answer_quality_threshold = 0.80      # Answer factually correct?
        self.hallucination_threshold = 0.10       # Allow max 10% hallucination rate
    
    def evaluate_retrieval(
        self,
        chunks: List[Dict[str, Any]],
        question: str,
        top_k_expected: int = 5
    ) -> RetrievalEvaluation:
        """
        Evaluate quality of retrieved chunks.
        
        Checks:
        - Relevance: Are chunks topically related to question?
        - Coverage: Do chunks address main question aspects?
        - Diversity: Do chunks provide multiple perspectives?
        
        Args:
            chunks: List of retrieved chunks with text, source, similarity
            question: Original user question
            top_k_expected: Expected number of chunks for evaluation
        
        Returns:
            RetrievalEvaluation with scores and feedback
        
        Example:
            >>> chunks = [
            ...     {"text": "Q4 revenue: €50,000", "source": "report.pdf", "similarity": 0.92},
            ...     {"text": "Consulting costs: €5,000", "source": "invoice.pdf", "similarity": 0.85}
            ... ]
            >>> eval = evaluator.evaluate_retrieval(chunks, "What was Q4 revenue?")
            >>> print(f"Relevance: {eval.relevance_score}")
        """
        chunk_texts = "\n".join([
            f"[{c.get('source', 'Unknown')} - similarity: {c.get('similarity', 0):.2f}] {c.get('text', '')}"
            for c in chunks[:top_k_expected]
        ])
        
        evaluation_prompt = f"""
Evaluate the relevance of these retrieved chunks to the question.

Question: "{question}"

Retrieved Chunks:
{chunk_texts}

Evaluate on:
1. Relevance (0-1): Are chunks topically related to the question?
2. Coverage (0-1): Do chunks address main aspects of the question?
3. Diversity (0-1): Do chunks provide multiple perspectives or sources?

Respond in JSON format:
{{
    "relevance_score": <float 0-1>,
    "coverage_score": <float 0-1>,
    "diversity_score": <float 0-1>,
    "feedback": "<brief explanation>"
}}
"""
        
        try:
            response = self.ai_service.chat(
                messages=[{"role": "user", "content": evaluation_prompt}],
                temperature=0.1,  # Deterministic evaluation
                max_tokens=300
            )
            
            # Parse JSON response
            response_text = response.get("content", "{}").strip()
            
            # Extract JSON if embedded in text
            import json as json_module
            try:
                result = json_module.loads(response_text)
            except json_module.JSONDecodeError:
                # Try to extract JSON from response
                import re
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    result = json_module.loads(json_match.group())
                else:
                    raise ValueError(f"Could not parse evaluation: {response_text}")
            
            return RetrievalEvaluation(
                relevance_score=float(result.get("relevance_score", 0.5)),
                coverage_score=float(result.get("coverage_score", 0.5)),
                diversity_score=float(result.get("diversity_score", 0.5)),
                feedback=result.get("feedback", "No feedback")
            )
        
        except Exception as e:
            logger.error(f"Retrieval evaluation failed: {str(e)}", exc_info=True)
            # Return neutral evaluation on error
            return RetrievalEvaluation(
                relevance_score=0.5,
                coverage_score=0.5,
                diversity_score=0.5,
                feedback=f"Evaluation error: {str(e)}"
            )
    
    def evaluate_answer(
        self,
        answer: str,
        question: str,
        chunks: List[Dict[str, Any]]
    ) -> AnswerEvaluation:
        """
        Evaluate quality of generated answer.
        
        Checks:
        - Factuality: Are claims supported by chunks?
        - Relevance: Does answer address the question?
        - Hallucination: Are there unsupported claims?
        - Citation coverage: Are important facts cited?
        - Conciseness: Is answer clear and concise?
        
        Args:
            answer: Generated RAG answer
            question: Original user question
            chunks: Retrieved chunks used for context
        
        Returns:
            AnswerEvaluation with scores and feedback
        
        Example:
            >>> answer = "Q4 revenue was €50,000 [Source: report.pdf]"
            >>> question = "What was Q4 revenue?"
            >>> eval = evaluator.evaluate_answer(answer, question, chunks)
            >>> print(f"Hallucination: {eval.hallucination_score}")
        """
        chunk_context = "\n".join([
            f"- {c.get('source', 'Unknown')}: {c.get('text', '')}"
            for c in chunks
        ])
        
        evaluation_prompt = f"""
Evaluate the quality of this RAG answer against the provided context.

Question: "{question}"

Answer: "{answer}"

Context Chunks (sources):
{chunk_context}

Evaluate on:
1. Factuality (0-1): Are claims in the answer supported by the context?
2. Relevance (0-1): Does the answer address the question?
3. Conciseness (0-1): Is the answer clear and not overly verbose?
4. Hallucination (0-1): How much of the answer is NOT supported by context? (0=no hallucination, 1=entirely hallucinated)
5. Citation Coverage (0-1): Are important facts properly cited?

Also identify:
- Key unsupported claims (hallucinations)
- Missing citations for important facts

Respond in JSON format:
{{
    "factuality_score": <float 0-1>,
    "relevance_score": <float 0-1>,
    "conciseness_score": <float 0-1>,
    "hallucination_score": <float 0-1>,
    "citation_coverage": <float 0-1>,
    "unsupported_claims": [<list of unsupported claims>],
    "missing_citations": [<list of uncited facts>],
    "feedback": "<brief explanation>"
}}
"""
        
        try:
            response = self.ai_service.chat(
                messages=[{"role": "user", "content": evaluation_prompt}],
                temperature=0.1,  # Deterministic evaluation
                max_tokens=400
            )
            
            response_text = response.get("content", "{}").strip()
            
            # Parse JSON response
            import json as json_module
            try:
                result = json_module.loads(response_text)
            except json_module.JSONDecodeError:
                import re
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    result = json_module.loads(json_match.group())
                else:
                    raise ValueError(f"Could not parse evaluation: {response_text}")
            
            return AnswerEvaluation(
                factuality_score=float(result.get("factuality_score", 0.5)),
                relevance_score=float(result.get("relevance_score", 0.5)),
                conciseness_score=float(result.get("conciseness_score", 0.5)),
                hallucination_score=float(result.get("hallucination_score", 0.5)),
                citation_coverage=float(result.get("citation_coverage", 0.5)),
                feedback=result.get("feedback", "No feedback")
            )
        
        except Exception as e:
            logger.error(f"Answer evaluation failed: {str(e)}", exc_info=True)
            # Return neutral evaluation on error
            return AnswerEvaluation(
                factuality_score=0.5,
                relevance_score=0.5,
                conciseness_score=0.5,
                hallucination_score=0.5,
                citation_coverage=0.5,
                feedback=f"Evaluation error: {str(e)}"
            )
    
    def evaluate_rag_response(
        self,
        rag_response: RAGResponse,
        question: str,
        chunks: List[Dict[str, Any]],
        organization_id: int
    ) -> RAGEvaluationResult:
        """
        Complete RAG evaluation: retrieval + answer quality.
        
        Performs comprehensive evaluation and determines pass/fail:
        - Pass: Both retrieval and answer above thresholds
        - Fail: Either metric below threshold (logs issue for monitoring)
        
        Args:
            rag_response: RAGResponse from RAG pipeline
            question: Original user question
            chunks: Retrieved chunks used for context
            organization_id: Organization for tracking
        
        Returns:
            RAGEvaluationResult with detailed scores and pass/fail
        
        Example:
            >>> response = rag_service.query(question, org_id=1, db=db)
            >>> eval_result = evaluator.evaluate_rag_response(response, question, chunks, org_id=1)
            >>> if not eval_result.passed:
            ...     logger.warning(f"RAG quality issue: {eval_result.pass_reason}")
        """
        # Evaluate retrieval quality
        retrieval_eval = self.evaluate_retrieval(
            chunks=chunks,
            question=question,
            top_k_expected=len(chunks)
        )
        
        # Evaluate answer quality
        answer_eval = self.evaluate_answer(
            answer=rag_response.answer,
            question=question,
            chunks=chunks
        )
        
        # Determine pass/fail
        retrieval_pass = retrieval_eval.mean_score >= self.retrieval_quality_threshold
        answer_pass = (
            answer_eval.mean_score >= self.answer_quality_threshold and
            answer_eval.hallucination_score <= self.hallucination_threshold
        )
        
        passed = retrieval_pass and answer_pass
        
        # Generate pass reason
        if passed:
            pass_reason = "All metrics above thresholds"
        else:
            reasons = []
            if not retrieval_pass:
                reasons.append(
                    f"Retrieval quality {retrieval_eval.mean_score:.2f} "
                    f"< {self.retrieval_quality_threshold}"
                )
            if not answer_pass:
                if answer_eval.mean_score < self.answer_quality_threshold:
                    reasons.append(
                        f"Answer quality {answer_eval.mean_score:.2f} "
                        f"< {self.answer_quality_threshold}"
                    )
                if answer_eval.hallucination_score > self.hallucination_threshold:
                    reasons.append(
                        f"Hallucination {answer_eval.hallucination_score:.2f} "
                        f"> {self.hallucination_threshold}"
                    )
            pass_reason = "; ".join(reasons)
        
        result = RAGEvaluationResult(
            retrieval_eval=retrieval_eval,
            answer_eval=answer_eval,
            passed=passed,
            pass_reason=pass_reason
        )
        
        # Log evaluation result
        logger.info(
            f"RAG evaluation completed",
            extra={
                "organization_id": organization_id,
                "passed": passed,
                "overall_score": round(result.overall_score, 3),
                "retrieval_score": round(retrieval_eval.mean_score, 3),
                "answer_score": round(answer_eval.mean_score, 3),
                "hallucination": round(answer_eval.hallucination_score, 3)
            }
        )
        
        return result
    
    # ===================================================================
    # PHASE 5C: Langfuse Integration for Routing & Prompt Experimentation
    # ===================================================================
    
    async def evaluate_routing_decision(
        self,
        trace_id: str,
        evaluation_input: RouteEvaluationInput
    ):
        """
        Evaluate if the routing decision was correct using LLM-as-a-Judge.
        
        Runs in background via FastAPI BackgroundTasks.
        Uses GPT-4 (smarter model) to evaluate GPT-4.1-mini (faster model).
        
        Args:
            trace_id: Langfuse trace ID for scoring
            evaluation_input: RouteEvaluationInput with query, expected/actual actions
        
        Returns:
            None (scores sent to Langfuse asynchronously)
        
        Example:
            >>> eval_input = RouteEvaluationInput(
            ...     query="What's the total from invoice #123?",
            ...     expected_action="extract",
            ...     actual_action="extract",
            ...     reasoning="Specific field extraction needed",
            ...     context="invoice_processing"
            ... )
            >>> await evaluator.evaluate_routing_decision("trace-123", eval_input)
        """
        if not langfuse:
            logger.warning("Langfuse not available - skipping routing evaluation")
            return
        
        system_prompt = """
You are an expert evaluator for financial AI systems.

Your task: Judge if the routing decision was correct.

**Routing Actions:**
- extract: For specific data extraction (amounts, dates, names)
- query: For semantic search and Q&A over documents
- hybrid: For complex queries needing both

**Evaluation Criteria:**
1: Decision matches expected action AND reasoning is logical
0: Decision is wrong OR reasoning is flawed

Be strict. Even if the action is technically correct, score 0 if reasoning is poor.
"""
        
        user_message = f"""
**Query:** {evaluation_input.query}
**Context:** {evaluation_input.context}

**Expected Action:** {evaluation_input.expected_action}
**Actual Action:** {evaluation_input.actual_action}
**System Reasoning:** {evaluation_input.reasoning}

**Your Evaluation:**
"""
        
        try:
            # Use Structured Outputs (guarantees JSON matching Pydantic schema)
            completion = await openai_client.beta.chat.completions.parse(
                model="gpt-4o",  # Smarter judge model
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                response_format=JudgeResult
            )
            
            result: JudgeResult = completion.choices[0].message.parsed
            
            # Send score to Langfuse
            langfuse.score(
                trace_id=trace_id,
                name="routing_correctness",
                value=result.score,
                comment=result.reasoning
            )
            
            logger.info(
                f"[Eval] Trace {trace_id}: Score {result.score} - {result.reasoning}"
            )
            
        except Exception as e:
            logger.error(f"[Eval Error] Routing evaluation failed: {str(e)}", exc_info=True)
    
    async def evaluate_faithfulness(
        self,
        trace_id: str,
        query: str,
        context: str,
        response: str
    ):
        """
        Check if RAG response is faithful to retrieved context.
        
        Prevents hallucinations by comparing response to source chunks.
        Runs in background via FastAPI BackgroundTasks.
        
        Args:
            trace_id: Langfuse trace ID for scoring
            query: User's original question
            context: Retrieved chunks (concatenated)
            response: Generated RAG answer
        
        Returns:
            None (scores sent to Langfuse asynchronously)
        
        Example:
            >>> await evaluator.evaluate_faithfulness(
            ...     trace_id="trace-456",
            ...     query="What was Q4 revenue?",
            ...     context="Q4 revenue was €50,000 [report.pdf]",
            ...     response="Q4 revenue was €50,000"
            ... )
        """
        if not langfuse:
            logger.warning("Langfuse not available - skipping faithfulness evaluation")
            return
        
        system_prompt = """
You are a strict financial auditor. Check if the 'Response' is fully based on 'Context'.

**Scoring:**
1: Response is 100% grounded in context (no invented facts)
0: Response contains information not in context (hallucination)

Be extremely critical of numbers and dates.
"""
        
        user_message = f"Query: {query}\n\nContext: {context}\n\nResponse: {response}"
        
        try:
            completion = await openai_client.beta.chat.completions.parse(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                response_format=JudgeResult
            )
            
            result: JudgeResult = completion.choices[0].message.parsed
            
            langfuse.score(
                trace_id=trace_id,
                name="faithfulness",
                value=result.score,
                comment=result.reasoning
            )
            
            logger.info(
                f"[Faithfulness] Trace {trace_id}: Score {result.score} - {result.reasoning}"
            )
            
        except Exception as e:
            logger.error(f"[Eval Error] Faithfulness evaluation failed: {str(e)}", exc_info=True)
