"""
Prompt Experiment Runner for Phase 5C.

Tests multiple prompt variants in parallel and compares results.
Uses concurrent.futures for parallel execution to reduce experiment time.

Features:
- Parallel testing of multiple prompts
- Automatic metrics collection (tokens, cost, latency)
- Results aggregation and comparison
- Langfuse integration for experiment tracking

Usage:
    from app.evaluation.prompt_tester import PromptExperimentRunner
    
    test_queries = [
        {
            "query": "What's the total from invoice #12345?",
            "expected_action": "extract",
            "context": "invoice_processing"
        }
    ]
    
    runner = PromptExperimentRunner(test_queries)
    results = runner.run_parallel_experiments()
    summary = runner.analyze_results(results)

Reference:
    docs/PHASE5C_LANGFUSE_INTEGRATION.md
    https://docs.python.org/3/library/concurrent.futures.html
"""

import asyncio
import logging
import os
import time
import statistics
from typing import List, Dict, Any
from datetime import datetime

from app.prompts.routing_prompts import ROUTING_PROMPTS
from app.agentic_router import AgenticRouter
from app.schemas import ExperimentResult, ExperimentSummary, TokenMetrics, LatencyMetrics

logger = logging.getLogger(__name__)


class PromptExperimentRunner:
    """
    Test multiple prompt variants in parallel and compare results.
    
    Uses asyncio.gather for concurrent execution.
    Reduces total experiment time by 70%+ compared to sequential testing.
    
    Example:
        >>> test_queries = [
        ...     {"query": "Show invoice total", "expected_action": "extract"},
        ...     {"query": "Summarize Q4 spending", "expected_action": "query"}
        ... ]
        >>> runner = PromptExperimentRunner(test_queries)
        >>> results = asyncio.run(runner.run_parallel_experiments())
        >>> print(f"Tested {len(results)} combinations")
    """
    
    def __init__(
        self,
        test_queries: List[Dict[str, str]],
        max_workers: int = 10,
        environment: str = "dev"
    ):
        """
        Initialize experiment runner.
        
        Args:
            test_queries: List of {query, expected_action, context} dicts
            max_workers: Maximum concurrent threads (default: 10)
            environment: Deployment environment (dev|staging|production)
        """
        self.test_queries = test_queries
        self.max_workers = max_workers
        self.environment = environment
        
        logger.info(
            f"PromptExperimentRunner initialized: "
            f"{len(test_queries)} queries, {max_workers} workers"
        )
    
    async def test_single_prompt(
        self,
        prompt_name: str,
        query: str,
        context: str,
        expected_action: str
    ) -> Dict[str, Any]:
        """
        Test one prompt variant on one query.
        
        Args:
            prompt_name: Prompt version identifier (e.g., "v2_detailed")
            query: User query to test
            context: Context string for routing
            expected_action: Ground truth action (for evaluation)
        
        Returns:
            {
                "prompt_name": str,
                "query": str,
                "expected_action": str,
                "actual_action": str,
                "reasoning": str,
                "confidence": float,
                "trace_id": str,
                "tokens": int,
                "cost": float,
                "latency_ms": float,
                "timestamp": datetime,
                "model": str,
                "error": str (if failed)
            }
        """
        try:
            # Create router with this prompt variant
            router = AgenticRouter(
                prompt_version=prompt_name,
                model="gpt-4.1-mini",  # Using available model
                temperature=0.1
            )
            
            # Execute routing
            decision = await router.route_query(
                query=query,
                context={"context": context, "type": "experiment"},
                enable_langfuse=True
            )
            
            result = {
                "prompt_name": prompt_name,
                "query": query,
                "expected_action": expected_action,
                "actual_action": decision["action"],
                "reasoning": decision["reasoning"],
                "confidence": decision["confidence"],
                "trace_id": decision.get("trace_id"),
                "tokens": decision["tokens"],
                "cost": decision["cost"],
                "latency_ms": decision["latency_ms"],
                "timestamp": datetime.utcnow(),
                "model": decision["model"],
                "error": None
            }
            
            logger.debug(
                f"✅ {prompt_name} on '{query[:50]}...': "
                f"{decision['action']} ({decision['latency_ms']:.0f}ms)"
            )
            
            return result
        
        except Exception as e:
            logger.error(f"❌ {prompt_name} on '{query[:50]}...': {str(e)}")
            return {
                "prompt_name": prompt_name,
                "query": query,
                "expected_action": expected_action,
                "actual_action": None,
                "reasoning": None,
                "confidence": 0.0,
                "trace_id": None,
                "tokens": 0,
                "cost": 0.0,
                "latency_ms": 0.0,
                "timestamp": datetime.utcnow(),
                "model": "unknown",
                "error": str(e)
            }
    
    async def run_parallel_experiments(self) -> List[Dict[str, Any]]:
        """
        Test all prompt variants on all test queries in parallel.
        
        Creates task matrix: len(prompts) × len(queries) tasks.
        Executes concurrently using asyncio.gather with semaphore.
        
        Returns:
            List of experiment results
        
        Example:
            >>> results = await runner.run_parallel_experiments()
            >>> print(f"Completed {len(results)} experiments")
            >>> failed = [r for r in results if r['error']]
            >>> print(f"Failed: {len(failed)}")
        """
        # Create async tasks
        tasks = []
        for query_data in self.test_queries:
            for prompt_name in ROUTING_PROMPTS.keys():
                task = self.test_single_prompt(
                    prompt_name=prompt_name,
                    query=query_data["query"],
                    context=query_data.get("context", ""),
                    expected_action=query_data.get("expected_action", "unknown")
                )
                tasks.append(task)
        
        total_tasks = len(tasks)
        logger.info(f"Starting {total_tasks} experiments in parallel...")
        
        start_time = time.time()
        
        # Execute all tasks concurrently
        # Semaphore limits concurrent OpenAI API calls to avoid rate limits
        semaphore = asyncio.Semaphore(self.max_workers)
        
        async def bounded_task(task):
            async with semaphore:
                return await task
        
        # Run all tasks with semaphore
        results = await asyncio.gather(
            *[bounded_task(task) for task in tasks],
            return_exceptions=True
        )
        
        # Process results and handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Task {i} failed: {str(result)}")
                processed_results.append({
                    "prompt_name": "unknown",
                    "query": "unknown",
                    "error": str(result),
                    "tokens": 0,
                    "cost": 0.0,
                    "latency_ms": 0.0
                })
            else:
                processed_results.append(result)
        
        total_time = time.time() - start_time
        successful = len([r for r in processed_results if not r.get('error')])
        logger.info(
            f"✅ Completed all experiments in {total_time:.1f}s "
            f"({successful}/{total_tasks} successful, {total_tasks / total_time:.1f} experiments/sec)"
        )
        
        return processed_results
    
    def analyze_results(self, results: List[Dict[str, Any]]) -> Dict[str, ExperimentSummary]:
        """
        Aggregate experiment results for comparison.
        
        Calculates per-prompt statistics:
        - Token usage (avg, min, max)
        - Cost (avg, total)
        - Latency (avg, p95)
        - Accuracy (if expected_action provided)
        
        Args:
            results: List of experiment results from run_parallel_experiments()
        
        Returns:
            {
                "prompt_v1": ExperimentSummary(...),
                "prompt_v2": ExperimentSummary(...),
                ...
            }
        
        Example:
            >>> summary = runner.analyze_results(results)
            >>> for prompt, stats in summary.items():
            ...     print(f"{prompt}: {stats.avg_cost:.6f} USD/query")
        """
        from collections import defaultdict
        
        stats = defaultdict(lambda: {
            "tokens": [],
            "costs": [],
            "latencies": [],
            "correct_decisions": [],
            "total": 0,
            "errors": 0
        })
        
        # Group by prompt name
        for result in results:
            prompt_name = result["prompt_name"]
            
            if result.get("error"):
                stats[prompt_name]["errors"] += 1
                continue
            
            stats[prompt_name]["tokens"].append(result["tokens"])
            stats[prompt_name]["costs"].append(result["cost"])
            stats[prompt_name]["latencies"].append(result["latency_ms"])
            stats[prompt_name]["total"] += 1
            
            # Track accuracy if expected action provided
            if result.get("expected_action") and result.get("actual_action"):
                is_correct = (
                    result["expected_action"] == result["actual_action"]
                )
                stats[prompt_name]["correct_decisions"].append(1 if is_correct else 0)
        
        # Calculate summary statistics
        summary = {}
        for prompt_name, data in stats.items():
            if not data["tokens"]:
                # No successful tests for this prompt
                continue
            
            # Calculate percentiles for latency
            sorted_latencies = sorted(data["latencies"])
            p95_index = int(len(sorted_latencies) * 0.95)
            p95_latency = sorted_latencies[p95_index] if sorted_latencies else 0.0
            
            # Calculate accuracy if available
            avg_correctness = None
            if data["correct_decisions"]:
                avg_correctness = statistics.mean(data["correct_decisions"])
            
            summary[prompt_name] = ExperimentSummary(
                prompt_name=prompt_name,
                avg_tokens=statistics.mean(data["tokens"]),
                min_tokens=min(data["tokens"]),
                max_tokens=max(data["tokens"]),
                avg_cost=statistics.mean(data["costs"]),
                total_cost=sum(data["costs"]),
                avg_latency_ms=statistics.mean(data["latencies"]),
                p95_latency_ms=p95_latency,
                avg_routing_correctness=avg_correctness,
                avg_faithfulness=None,  # Set by LLM-as-a-Judge later
                total_tests=data["total"],
                successful_tests=data["total"],
                failed_tests=data["errors"]
            )
        
        return summary
    
    def export_results(
        self,
        results: List[Dict[str, Any]],
        summary: Dict[str, ExperimentSummary],
        output_path: str = "test_results/prompt_experiments.json"
    ):
        """
        Export experiment results to JSON file.
        
        Args:
            results: Raw experiment results
            summary: Aggregated statistics
            output_path: Output file path
        """
        import json
        from pathlib import Path
        
        # Create output directory
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Convert datetimes to strings
        serializable_results = []
        for r in results:
            r_copy = r.copy()
            if "timestamp" in r_copy and isinstance(r_copy["timestamp"], datetime):
                r_copy["timestamp"] = r_copy["timestamp"].isoformat()
            serializable_results.append(r_copy)
        
        # Convert summary to dict
        summary_dict = {
            name: stats.model_dump()
            for name, stats in summary.items()
        }
        
        export_data = {
            "metadata": {
                "total_experiments": len(results),
                "prompts_tested": len(summary),
                "queries_tested": len(self.test_queries),
                "environment": self.environment,
                "exported_at": datetime.utcnow().isoformat()
            },
            "results": serializable_results,
            "summary": summary_dict
        }
        
        with open(output_path, "w") as f:
            json.dump(export_data, f, indent=2)
        
        logger.info(f"📊 Results exported to {output_path}")
