"""
Agentic Router for Phase 5C - Intelligent Query Routing with Langfuse Observability.

Routes financial queries to the appropriate tool:
- extract: Structured data extraction from documents
- query: Semantic search and Q&A over financial records
- hybrid: Complex queries requiring both extraction and semantic search

Features:
- Multiple prompt variants for experimentation
- Full Langfuse observability (tokens, cost, latency)
- Automatic evaluation via LLM-as-a-Judge
- Background quality scoring

Architecture:
    User Query → AgenticRouter → Decision (extract|query|hybrid)
    ↓
    Langfuse Trace (metrics, evaluation)

Reference:
    docs/PHASE5C_LANGFUSE_INTEGRATION.md
    app/prompts/routing_prompts.py
"""

import logging
import os
import time
from typing import Dict, Any, Optional, Literal
import json

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

# Langfuse imports
try:
    from langfuse import Langfuse, get_client, propagate_attributes
    # Try importing langfuse_context for proper tags support
    try:
        from langfuse import Langfuse
        LANGFUSE_CONTEXT_AVAILABLE = True
    except (ImportError, AttributeError):
        langfuse_context = None
        LANGFUSE_CONTEXT_AVAILABLE = False
    
    LANGFUSE_AVAILABLE = True
    
    if LANGFUSE_CONTEXT_AVAILABLE:
        logging.info("Langfuse SDK 3.7.0+ (stable) loaded with langfuse_context")
        logging.info("Using proper tags via langfuse_context.update_current_trace()")
    else:
        logging.info("Langfuse SDK 3.7.0 (stable) loaded")
        logging.info("langfuse_context not available - using metadata workaround only")
    logging.info("Maintaining metadata workaround for backward compatibility")
except ImportError:
    LANGFUSE_AVAILABLE = False
    LANGFUSE_CONTEXT_AVAILABLE = False
    langfuse_context = None
    logging.warning("Langfuse not installed. Install with: pip install langfuse")

from app.prompts.routing_prompts import ROUTING_PROMPTS, PROMPT_METADATA

logger = logging.getLogger(__name__)

# Initialize clients
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

if LANGFUSE_AVAILABLE and os.getenv("LANGFUSE_PUBLIC_KEY"):
    langfuse = Langfuse(
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        host=os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")
    )
    logger.info("AgenticRouter: Langfuse initialized")
else:
    langfuse = None
    logger.info("AgenticRouter: Langfuse disabled")


class RoutingDecision(BaseModel):
    """Structured routing decision from LLM."""
    action: Literal["extract", "query", "hybrid"] = Field(
        description="Tool to use for query"
    )
    reasoning: str = Field(
        description="Explanation for routing choice",
        min_length=10
    )
    confidence: float = Field(
        default=0.8,
        description="Confidence in decision (0.0 - 1.0)",
        ge=0.0,
        le=1.0
    )


class AgenticRouter:
    """
    Intelligent query router with Langfuse observability.
    
    Analyzes user queries and routes them to the appropriate tool
    (extract, query, or hybrid) based on query intent and context.
    
    Example:
        >>> router = AgenticRouter(prompt_version="v2_detailed")
        >>> decision = await router.route_query(
        ...     query="What's the total from invoice #123?",
        ...     context={"type": "invoice_processing"}
        ... )
        >>> print(decision["action"])  # "extract"
    """
    
    def __init__(
        self,
        prompt_version: str = "v2_detailed",
        model: str = "gpt-4.1-mini",  # Using available model
        temperature: float = 0.1
    ):
        """
        Initialize router with prompt configuration.
        
        Args:
            prompt_version: Prompt variant from routing_prompts.py
            model: OpenAI model (gpt-4.1-mini available, gpt-5.1 for accuracy)
            temperature: Sampling temperature (0.0 = deterministic, 1.0 = creative)
        """
        self.prompt_version = prompt_version
        self.model = model
        self.temperature = temperature
        
        # Validate prompt exists
        if prompt_version not in ROUTING_PROMPTS:
            available = list(ROUTING_PROMPTS.keys())
            raise ValueError(
                f"Unknown prompt version '{prompt_version}'. "
                f"Available: {available}"
            )
        
        self.prompt_template = ROUTING_PROMPTS[prompt_version]
        self.metadata = PROMPT_METADATA.get(prompt_version, {})
        
        logger.info(
            f"AgenticRouter initialized: prompt={prompt_version}, model={model}"
        )
    
    async def route_query(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        enable_langfuse: bool = True,
        enable_quality_scoring: bool = False
    ) -> Dict[str, Any]:
        """
        Route query to appropriate tool with full observability.
        
        Args:
            query: User's financial query
            context: Additional context (org_id, document_type, etc.)
            enable_langfuse: Enable Langfuse tracing (default: True)
            enable_quality_scoring: Enable LLM-as-Judge quality scoring (default: False)
        
        Returns:
            {
                "action": "extract|query|hybrid",
                "reasoning": "explanation",
                "confidence": 0.0-1.0,
                "trace_id": "langfuse-trace-id" (if enabled),
                "tokens": int,
                "cost": float,
                "latency_ms": float,
                "quality_score": float (0.0-1.0, only if enable_quality_scoring=True)
            }
        
        Raises:
            ValueError: If query is empty or invalid
        
        Example:
            >>> decision = await router.route_query(
            ...     query="Compare Q3 vs Q4 spending",
            ...     context={"organization_id": 1, "type": "financial_analysis"},
            ...     enable_quality_scoring=True
            ... )
            >>> print(decision["action"])  # "hybrid"
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        
        context = context or {}
        context_str = json.dumps(context, indent=2)
        
        # Format prompt
        formatted_prompt = self.prompt_template.format(
            query=query,
            context=context_str
        )
        
        # Track timing
        start_time = time.time()
        
        # Create Langfuse trace if enabled
        trace_id = None
        trace_context = None
        
        if enable_langfuse and langfuse:
            # Use context manager to create trace
            # IMPROVED: Use proper tags array via langfuse_context (Langfuse 3.7.0+)
            # Reference: https://langfuse.com/docs/observability/features/tags
            trace_context = langfuse.start_observation(
                name=f"agentic_routing_{self.prompt_version}",
                input={"query": query, "context": context},
                metadata={
                    # WORKAROUND (for backward compatibility): Store tags in metadata 
                    "_tags": f"agentic_routing,prompt:{self.prompt_version},model:{self.model}",
                    # Regular metadata for filtering
                    "experiment": "routing_optimization_jan2026",
                    "temperature": str(self.temperature),  # Must be string <=200 chars
                    "prompt_version": self.prompt_version
                }
            )
            trace_id = trace_context.trace_id
            
            # PROPER APPROACH: Add tags as proper array for better dashboard grouping
            if LANGFUSE_CONTEXT_AVAILABLE and langfuse_context:
                try:
                    langfuse_context.update_current_trace(
                        tags=[
                            "agentic_routing", 
                            f"prompt:{self.prompt_version}",
                            f"model:{self.model}"
                        ]
                    )
                    logger.debug(f"Langfuse tags added: agentic_routing, prompt:{self.prompt_version}, model:{self.model}")
                except Exception as e:
                    logger.warning(f"Failed to add proper tags (fallback to metadata): {str(e)}")
            else:
                logger.debug("langfuse_context not available - using metadata tags only")
        
        try:
            # OpenAI call with Structured Outputs
            response = await openai_client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": formatted_prompt},
                    {"role": "user", "content": query}
                ],
                temperature=self.temperature,
                response_format=RoutingDecision
            )
            
            decision: RoutingDecision = response.choices[0].message.parsed
            latency_ms = (time.time() - start_time) * 1000
            
            # Calculate cost based on model
            # gpt-4.1-mini: estimated $0.00020/1K input, $0.00060/1K output
            # gpt-3.5-turbo: $0.0015/1K input, $0.002/1K output
            # gpt-4o-mini: $0.00015/1K input, $0.0006/1K output
            if "gpt-3.5-turbo" in self.model:
                input_cost = response.usage.prompt_tokens * 0.0015 / 1000
                output_cost = response.usage.completion_tokens * 0.002 / 1000
            elif "gpt-4.1" in self.model or "gpt-4o" in self.model:
                input_cost = response.usage.prompt_tokens * 0.00020 / 1000
                output_cost = response.usage.completion_tokens * 0.00060 / 1000
            else:  # fallback to mini pricing
                input_cost = response.usage.prompt_tokens * 0.00015 / 1000
                output_cost = response.usage.completion_tokens * 0.0006 / 1000
            total_cost = input_cost + output_cost
            
            # Log to Langfuse if enabled
            if enable_langfuse and langfuse and trace_context:
                # Update observation with output
                trace_context.update(
                    output=decision.model_dump(),
                    usage={
                        "input": response.usage.prompt_tokens,
                        "output": response.usage.completion_tokens,
                        "total": response.usage.total_tokens
                    },
                    metadata={
                        # Metadata values must be strings <=200 chars (Langfuse requirement)
                        "latency_ms": f"{latency_ms:.2f}",
                        "cost_usd": f"{total_cost:.6f}",
                        "confidence": f"{decision.confidence:.2f}",
                        "action": decision.action,  # Store routing decision for filtering
                        "model": self.model
                    }
                )
                # End the observation
                trace_context.end()
            
            result = {
                "action": decision.action,
                "reasoning": decision.reasoning,
                "confidence": decision.confidence,
                "trace_id": trace_id,
                "tokens": response.usage.total_tokens,
                "cost": total_cost,
                "latency_ms": latency_ms,
                "model": self.model,
                "prompt_version": self.prompt_version
            }
            
            # Add quality scoring if enabled
            if enable_quality_scoring and trace_id:
                try:
                    from app.evaluation.routing_judge import RoutingJudge
                    judge = RoutingJudge(model="gpt-4.1-mini")
                    judgment = await judge.judge_routing(
                        query=query,
                        actual_route=decision.action,
                        trace_id=trace_id,
                        metadata={
                            "prompt_version": self.prompt_version,
                            "confidence": decision.confidence
                        }
                    )
                    result["quality_score"] = 1.0 if judgment.is_correct else 0.0
                    result["expected_route"] = judgment.expected_route
                    result["judge_reasoning"] = judgment.reasoning
                    
                    logger.info(
                        f"Quality score: {result['quality_score']} "
                        f"(expected: {judgment.expected_route})"
                    )
                except Exception as e:
                    logger.warning(f"Quality scoring failed: {str(e)}")
                    result["quality_score"] = None
            
            logger.info(
                f"Routing decision: {decision.action} "
                f"(tokens={response.usage.total_tokens}, "
                f"latency={latency_ms:.0f}ms, "
                f"cost=${total_cost:.6f})"
            )
            
            return result
        
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Routing failed after {latency_ms:.0f}ms: {str(e)}",
                exc_info=True
            )
            
            # Log error to Langfuse
            if enable_langfuse and langfuse and trace_context:
                trace_context.update(
                    output={"error": str(e)},
                    level="ERROR"
                )
                trace_context.end()
            
            raise
    
    async def route_query_batch(
        self,
        queries: list[str],
        context: Optional[Dict[str, Any]] = None
    ) -> list[Dict[str, Any]]:
        """
        Route multiple queries in parallel (future enhancement).
        
        Args:
            queries: List of user queries
            context: Shared context for all queries
        
        Returns:
            List of routing decisions
        
        Note:
            Currently executes sequentially. Use concurrent.futures
            for parallel execution in production.
        """
        results = []
        for query in queries:
            decision = await self.route_query(query, context)
            results.append(decision)
        return results
