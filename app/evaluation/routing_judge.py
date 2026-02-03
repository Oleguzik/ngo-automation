"""
LLM-as-Judge evaluation for routing decisions.

This service evaluates the quality of routing decisions made by the AgenticRouter
by using GPT-4 as a judge to determine if the route was correct.
"""

from typing import Dict, Optional
from pydantic import BaseModel, Field
from openai import AsyncOpenAI
import asyncio
from langfuse import Langfuse, get_client
import os


class JudgmentResult(BaseModel):
    """Result of a routing judgment."""
    
    is_correct: bool = Field(..., description="Whether the routing decision was correct")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in judgment (0-1)")
    reasoning: str = Field(..., description="Explanation for the judgment")
    expected_route: str = Field(..., description="What the correct route should have been")


class RoutingJudge:
    """
    LLM-as-Judge for evaluating routing decisions.
    
    Uses GPT-4 to evaluate whether the AgenticRouter made the correct decision
    for a given query, tracking accuracy and providing explanations.
    """
    
    JUDGE_PROMPT = """You are an expert evaluator of AI routing systems for financial document processing.

Your task is to judge whether the routing decision was CORRECT for the given query.

Available routes:
- extract: Extract structured data from financial documents (invoices, receipts, bank statements)
- rag_query: Answer questions about financial data using semantic search + AI generation
- hybrid: Both extract AND query (e.g., "extract invoice and tell me total")
- clarify: Query is ambiguous or cannot be handled

Query: {query}

Routing Decision: {actual_route}

Evaluate if this routing decision was CORRECT. Consider:
1. Does the query ask to extract data? → extract or hybrid
2. Does the query ask a question about data? → rag_query or hybrid  
3. Is the query unclear or out of scope? → clarify
4. Does it ask for both extraction and analysis? → hybrid

Respond in JSON format:
{{
  "is_correct": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation of your judgment",
  "expected_route": "The correct route (extract|rag_query|hybrid|clarify)"
}}"""

    def __init__(self, model: str = "gpt-4.1-mini"):
        """
        Initialize the routing judge.
        
        Args:
            model: OpenAI model to use for judgment (default: gpt-4.1-mini)
        """
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = model
        self.langfuse = get_client()
    
    async def judge_routing(
        self,
        query: str,
        actual_route: str,
        trace_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> JudgmentResult:
        """
        Judge whether a routing decision was correct.
        
        Args:
            query: The user's query
            actual_route: The route that was chosen
            trace_id: Optional Langfuse trace ID to attach score to
            metadata: Optional metadata for the judgment
            
        Returns:
            JudgmentResult with correctness, confidence, and reasoning
        """
        prompt = self.JUDGE_PROMPT.format(
            query=query,
            actual_route=actual_route
        )
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.0  # Deterministic for evaluation
            )
            
            import json
            result_dict = json.loads(response.choices[0].message.content)
            result = JudgmentResult(**result_dict)
            
            # Add score to Langfuse if trace_id provided
            if trace_id:
                score_metadata = metadata or {}
                score_metadata.update({
                    "expected_route": result.expected_route,
                    "reasoning": result.reasoning
                })
                
                self.langfuse.score(
                    trace_id=trace_id,
                    name="routing_accuracy",
                    value=1.0 if result.is_correct else 0.0,
                    comment=result.reasoning
                )
                
                # Also add confidence as a separate score
                self.langfuse.score(
                    trace_id=trace_id,
                    name="judge_confidence",
                    value=result.confidence,
                    comment=f"Judge confidence in {actual_route} decision"
                )
            
            return result
            
        except Exception as e:
            # Fallback result on error
            return JudgmentResult(
                is_correct=False,
                confidence=0.0,
                reasoning=f"Judgment failed: {str(e)}",
                expected_route="unknown"
            )
    
    async def batch_judge(
        self,
        evaluations: list[Dict],
        max_concurrent: int = 5
    ) -> list[JudgmentResult]:
        """
        Judge multiple routing decisions in parallel.
        
        Args:
            evaluations: List of dicts with keys: query, actual_route, trace_id, metadata
            max_concurrent: Maximum concurrent judgments
            
        Returns:
            List of JudgmentResult objects
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def judge_with_semaphore(eval_data: Dict) -> JudgmentResult:
            async with semaphore:
                return await self.judge_routing(**eval_data)
        
        tasks = [judge_with_semaphore(eval_data) for eval_data in evaluations]
        results = await asyncio.gather(*tasks)
        
        return results


# Convenience function for synchronous usage
def judge_routing_sync(
    query: str,
    actual_route: str,
    trace_id: Optional[str] = None,
    metadata: Optional[Dict] = None,
    model: str = "gpt-4.1-mini"
) -> JudgmentResult:
    """
    Synchronous wrapper for judge_routing.
    
    Args:
        query: The user's query
        actual_route: The route that was chosen
        trace_id: Optional Langfuse trace ID to attach score to
        metadata: Optional metadata for the judgment
        model: Model to use for judgment
        
    Returns:
        JudgmentResult with correctness, confidence, and reasoning
    """
    judge = RoutingJudge(model=model)
    return asyncio.run(judge.judge_routing(query, actual_route, trace_id, metadata))
