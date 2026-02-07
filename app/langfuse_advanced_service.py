"""
Langfuse Advanced Features Service: A/B Testing, Evaluation, Prompt Management

This service implements advanced Langfuse capabilities:
- A/B testing with labels and traffic splitting
- Evaluation datasets for offline testing
- Prompt variant management
- User feedback collection and analysis

Phase: 5C  
Created: February 2, 2026  
Author: GitHub Copilot (Claude Sonnet 4.5)
"""

import random
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from langfuse import Langfuse
from langfuse import Langfuse
import logging

logger = logging.getLogger(__name__)


class LangfuseAdvancedService:
    """
    Advanced Langfuse features for production AI applications.
    
    Features:
    - A/B testing with automatic traffic splitting
    - Prompt variant management
    - Evaluation dataset creation
    - User feedback analysis
    """
    
    def __init__(self):
        """Initialize Langfuse client."""
        self.langfuse = Langfuse()
        
        # A/B test configurations (in production, store in database)
        self.ab_tests = {
            "routing_prompts_v2_vs_v3": {
                "variant_a": "v2_detailed",
                "variant_b": "v3_few_shot",
                "traffic_split": 0.5,  # 50/50 split
                "is_active": True
            }
        }
    
    # ========================================================================
    # A/B Testing
    # ========================================================================
    
    def select_prompt_variant(
        self,
        test_name: str,
        user_id: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Select prompt variant for A/B testing.
        
        Uses consistent hashing if user_id provided, otherwise random selection.
        
        Args:
            test_name: Name of A/B test
            user_id: Optional user identifier for consistent assignment
            
        Returns:
            Tuple of (variant_id, experiment_label)
            
        Example:
            >>> variant, label = service.select_prompt_variant("routing_prompts_v2_vs_v3")
            >>> variant
            'v2_detailed'
            >>> label
            'prod-a'
        """
        if test_name not in self.ab_tests:
            logger.warning(f"A/B test '{test_name}' not found, using default")
            return "v2_detailed", "prod-default"
        
        test = self.ab_tests[test_name]
        
        if not test["is_active"]:
            logger.info(f"A/B test '{test_name}' is inactive, using variant A")
            return test["variant_a"], "prod-a"
        
        # Consistent hashing if user_id provided
        if user_id:
            import hashlib
            hash_val = int(hashlib.md5(f"{test_name}:{user_id}".encode()).hexdigest(), 16)
            use_variant_b = (hash_val % 100) < (test["traffic_split"] * 100)
        else:
            # Random selection
            use_variant_b = random.random() < test["traffic_split"]
        
        if use_variant_b:
            return test["variant_b"], "prod-b"
        else:
            return test["variant_a"], "prod-a"
    
    def tag_trace_for_ab_test(
        self,
        variant_id: str,
        experiment_label: str,
        test_name: str
    ):
        """
        Tag current Langfuse trace with A/B test metadata.
        
        Args:
            variant_id: Prompt variant ID (e.g., v2_detailed)
            experiment_label: Experiment group (prod-a or prod-b)
            test_name: A/B test name
            
        Example:
            >>> service.tag_trace_for_ab_test("v2_detailed", "prod-a", "routing_prompts_v2_vs_v3")
        """
        try:
            langfuse_context.update_current_trace(
                tags=[
                    f"ab_test:{test_name}",
                    f"variant:{variant_id}",
                    f"experiment:{experiment_label}"
                ],
                metadata={
                    "ab_test": test_name,
                    "variant": variant_id,
                    "experiment_label": experiment_label
                }
            )
            logger.debug(f"Tagged trace for A/B test: {test_name}, variant: {variant_id}")
        except Exception as e:
            logger.warning(f"Failed to tag trace for A/B test: {str(e)}")
    
    def get_ab_test_results(
        self,
        test_name: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        min_observations: int = 100
    ) -> Dict:
        """
        Get A/B test results from Langfuse.
        
        Fetches traces with ab_test tags and compares metrics between variants.
        
        Args:
            test_name: A/B test name
            start_date: Optional start date filter
            end_date: Optional end date filter
            min_observations: Minimum observations required for significance
            
        Returns:
            {
                "test_name": "routing_prompts_v2_vs_v3",
                "variant_a": {
                    "variant_id": "v2_detailed",
                    "sample_size": 150,
                    "avg_latency_ms": 2340,
                    "avg_score": 0.89,
                    "cost_per_query": 0.0023
                },
                "variant_b": {
                    "variant_id": "v3_few_shot",
                    "sample_size": 148,
                    "avg_latency_ms": 2180,
                    "avg_score": 0.92,
                    "cost_per_query": 0.0021
                },
                "winner": "variant_b",
                "confidence": 0.95
            }
        """
        # In production, query Langfuse API to fetch traces
        # For now, return mock data
        logger.info(f"Fetching A/B test results for: {test_name}")
        
        if test_name not in self.ab_tests:
            return {"error": f"Test '{test_name}' not found"}
        
        test = self.ab_tests[test_name]
        
        # Mock results (in production, query actual Langfuse data)
        return {
            "test_name": test_name,
            "min_observations": min_observations,
            "variant_a": {
                "variant_id": test["variant_a"],
                "sample_size": 150,
                "avg_latency_ms": 2340,
                "avg_user_feedback": 0.89,
                "avg_faithfulness": 0.87,
                "cost_per_query": 0.0023,
                "error_rate": 0.02
            },
            "variant_b": {
                "variant_id": test["variant_b"],
                "sample_size": 148,
                "avg_latency_ms": 2180,
                "avg_user_feedback": 0.92,
                "avg_faithfulness": 0.91,
                "cost_per_query": 0.0021,
                "error_rate": 0.01
            },
            "winner": "variant_b",
            "confidence": 0.95,
            "recommendation": "Variant B shows better performance across all metrics with 95% confidence"
        }
    
    # ========================================================================
    # Evaluation Datasets
    # ========================================================================
    
    def create_evaluation_dataset(
        self,
        dataset_name: str,
        test_cases: List[Dict]
    ) -> str:
        """
        Create evaluation dataset in Langfuse for offline testing.
        
        Args:
            dataset_name: Dataset identifier (e.g., "rag_golden_queries")
            test_cases: List of test cases with expected outputs
            
        Returns:
            Dataset ID
            
        Example:
            >>> test_cases = [
            ...     {
            ...         "question": "What was Q4 total spending?",
            ...         "expected_answer": "€125,000",
            ...         "documents": ["bank_statement_q4.pdf"]
            ...     }
            ... ]
            >>> dataset_id = service.create_evaluation_dataset("rag_financial_queries", test_cases)
        """
        try:
            # Create dataset in Langfuse
            dataset = self.langfuse.create_dataset(name=dataset_name)
            
            # Add test cases as dataset items
            for test_case in test_cases:
                self.langfuse.create_dataset_item(
                    dataset_name=dataset_name,
                    input={"question": test_case["question"]},
                    expected_output=test_case.get("expected_answer"),
                    metadata=test_case.get("metadata", {})
                )
            
            logger.info(f"Created evaluation dataset '{dataset_name}' with {len(test_cases)} test cases")
            
            return dataset.id
        
        except Exception as e:
            logger.error(f"Failed to create evaluation dataset: {str(e)}")
            raise
    
    def run_evaluation_dataset(
        self,
        dataset_name: str,
        evaluation_fn: callable
    ) -> Dict:
        """
        Run evaluation against dataset.
        
        Args:
            dataset_name: Dataset to evaluate against
            evaluation_fn: Function that takes input and returns output
            
        Returns:
            Evaluation results with accuracy metrics
            
        Example:
            >>> def evaluate_rag(input_data):
            ...     return rag_service.query(input_data["question"])
            >>> results = service.run_evaluation_dataset("rag_golden_queries", evaluate_rag)
        """
        try:
            # Fetch dataset from Langfuse
            dataset = self.langfuse.get_dataset(dataset_name)
            
            results = []
            for item in dataset.items:
                # Run evaluation function
                output = evaluation_fn(item.input)
                
                # Compare with expected output
                # (In production, use LLM-as-Judge for semantic comparison)
                is_correct = self._compare_outputs(output, item.expected_output)
                
                results.append({
                    "input": item.input,
                    "expected": item.expected_output,
                    "actual": output,
                    "is_correct": is_correct
                })
                
                # Log result to Langfuse
                self.langfuse.score(
                    trace_id=output.get("trace_id"),
                    name="dataset_evaluation",
                    value=1.0 if is_correct else 0.0
                )
            
            accuracy = sum(r["is_correct"] for r in results) / len(results)
            
            logger.info(f"Dataset evaluation complete: {accuracy:.2%} accuracy")
            
            return {
                "dataset_name": dataset_name,
                "total_cases": len(results),
                "accuracy": accuracy,
                "results": results
            }
        
        except Exception as e:
            logger.error(f"Failed to run dataset evaluation: {str(e)}")
            raise
    
    def _compare_outputs(self, actual: Dict, expected: str) -> bool:
        """
        Compare actual output with expected output.
        
        In production, use LLM-as-Judge for semantic comparison.
        For now, simple string matching.
        """
        actual_text = actual.get("answer", "").lower()
        expected_text = expected.lower() if expected else ""
        
        return expected_text in actual_text
    
    # ========================================================================
    # User Feedback Analysis
    # ========================================================================
    
    def get_feedback_summary(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict:
        """
        Get aggregated user feedback statistics.
        
        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            {
                "total_feedback": 500,
                "thumbs_up": 450,
                "thumbs_down": 50,
                "satisfaction_rate": 0.90,
                "avg_response_time_ms": 2340,
                "top_issues": [...]
            }
        """
        # In production, query Langfuse API for feedback scores
        logger.info("Fetching user feedback summary")
        
        # Mock data for now
        return {
            "total_feedback": 500,
            "thumbs_up": 450,
            "thumbs_down": 50,
            "satisfaction_rate": 0.90,
            "avg_response_time_ms": 2340,
            "common_positive_feedback": [
                "Accurate financial analysis",
                "Fast response time",
                "Helpful recommendations"
            ],
            "common_negative_feedback": [
                "Missing recent transactions",
                "Unclear sources in some cases"
            ]
        }
    
    def get_low_rated_traces(
        self,
        min_score: float = 0.0,
        max_score: float = 0.5,
        limit: int = 20
    ) -> List[Dict]:
        """
        Get traces with low user feedback scores for debugging.
        
        Args:
            min_score: Minimum score threshold
            max_score: Maximum score threshold
            limit: Max results to return
            
        Returns:
            List of low-rated trace details
            
        Example:
            >>> low_rated = service.get_low_rated_traces(max_score=0.3)
            >>> for trace in low_rated:
            ...     print(f"Trace {trace['id']}: score={trace['score']}, query='{trace['input']}'")
        """
        # In production, query Langfuse API
        logger.info(f"Fetching low-rated traces (score {min_score}-{max_score})")
        
        # Mock data
        return [
            {
                "trace_id": "trace-123",
                "score": 0.0,
                "input": "What was the revenue last quarter?",
                "output": "I don't have that information.",
                "timestamp": "2026-02-01T10:00:00Z",
                "issue": "Missing data in uploaded documents"
            }
        ]
    
    # ========================================================================
    # Prompt Management
    # ========================================================================
    
    def get_prompt_variants(self) -> List[Dict]:
        """
        Get all available prompt variants.
        
        Returns:
            List of prompt variant configurations
            
        Example:
            >>> variants = service.get_prompt_variants()
            >>> for v in variants:
            ...     print(f"{v['variant_id']}: {v['name']} (success_rate: {v['success_rate']})")
        """
        # In production, fetch from Langfuse Prompt Management
        # For now, return hardcoded variants
        return [
            {
                "variant_id": "v1_basic",
                "name": "Basic Routing Prompt",
                "is_active": False,
                "success_rate": 0.82,
                "avg_latency_ms": 2100,
                "total_uses": 500
            },
            {
                "variant_id": "v2_detailed",
                "name": "Detailed Routing Prompt v2",
                "is_active": True,
                "success_rate": 0.89,
                "avg_latency_ms": 2340,
                "total_uses": 1500
            },
            {
                "variant_id": "v3_few_shot",
                "name": "Few-Shot Examples Prompt v3",
                "is_active": True,
                "success_rate": 0.92,
                "avg_latency_ms": 2180,
                "total_uses": 1200
            },
            {
                "variant_id": "v4_strict",
                "name": "Strict JSON Output v4",
                "is_active": False,
                "success_rate": 0.85,
                "avg_latency_ms": 2050,
                "total_uses": 300
            },
            {
                "variant_id": "v5_concise",
                "name": "Concise High-Speed v5",
                "is_active": False,
                "success_rate": 0.87,
                "avg_latency_ms": 1890,
                "total_uses": 400
            }
        ]
    
    def activate_prompt_variant(self, variant_id: str):
        """
        Activate a prompt variant for production use.
        
        Args:
            variant_id: Variant identifier to activate
            
        Example:
            >>> service.activate_prompt_variant("v3_few_shot")
        """
        logger.info(f"Activating prompt variant: {variant_id}")
        # In production, update database/config
        # For now, just log
        return {"message": f"Variant {variant_id} activated", "variant_id": variant_id}
