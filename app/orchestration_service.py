"""
OrchestrationService: Multi-step agent orchestration for complex financial analysis.

This service coordinates AI agent planning, execution, and synthesis for tasks
that require multiple steps to complete (e.g., "Analyze Q4 spending trends").

Workflow:
1. PLAN: Generate step-by-step execution plan using LLM
2. EXECUTE: Run each step sequentially with tool calls
3. SYNTHESIZE: Combine step outputs into coherent final result

Key Features:
- Planning with GPT-4o-mini (structured JSON output)
- Sequential step execution with state tracking
- Tool dispatch (RAG query, data fetch, calculations, analysis)
- Cost tracking per task/step
- Langfuse trajectory tracing
- Error handling and graceful degradation

Phase: 5C  
Created: February 2, 2026  
Author: GitHub Copilot (Claude Sonnet 4.5)
"""

from typing import Dict, List, Any, Optional
import uuid
import json
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from langfuse.decorators import langfuse_context, observe

from app import models, crud, schemas
from app.ai_service import AIService
from app.rag_service import RAGService
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class OrchestrationService:
    """
    Multi-step agent orchestration service.
    
    Coordinates planning, execution, and synthesis for complex
    financial analysis tasks that require multiple steps.
    
    Example:
        service = OrchestrationService()
        result = service.execute_task(
            objective="Analyze Q4 spending trends",
            organization_id=1,
            db=db_session
        )
    """
    
    def __init__(self):
        """Initialize orchestration service with AI and RAG services."""
        self.ai_service = AIService()
        self.rag_service = RAGService()
        self.max_retries = 3
        
    @observe(name="agent_task_execution")
    def execute_task(
        self,
        objective: str,
        organization_id: int,
        db: Session,
        context: Optional[Dict] = None,
        max_steps: int = 10
    ) -> Dict[str, Any]:
        """
        Execute multi-step agent task.
        
        Workflow:
        1. PLAN: Generate step-by-step execution plan
        2. EXECUTE: Run each step sequentially with tool calls
        3. SYNTHESIZE: Combine step outputs into final result
        
        Args:
            objective: User's goal (e.g., "Analyze Q4 spending trends")
            organization_id: Organization context
            db: Database session
            context: Additional context for planning (date ranges, filters, etc.)
            max_steps: Maximum steps allowed (cost control)
            
        Returns:
            {
                "task_id": uuid,
                "status": "completed",
                "plan": [...],
                "result": {...},
                "steps_executed": 4,
                "total_cost": 0.12,
                "duration_seconds": 15.3
            }
            
        Raises:
            Exception: If critical error occurs during execution
        """
        logger.info(f"Starting agent task for org {organization_id}: {objective}")
        
        # 1. Create AgentTask record
        task = self._create_task(db, objective, organization_id, context, max_steps)
        
        try:
            # 2. PLAN: Generate execution plan
            logger.info(f"Task {task.id}: Generating plan (max_steps={max_steps})")
            task.status = "planning"
            db.commit()
            
            plan = self._generate_plan(objective, context, max_steps)
            task.plan = plan
            db.commit()
            
            logger.info(f"Task {task.id}: Plan generated with {len(plan)} steps")
            
            # Update Langfuse trace
            langfuse_context.update_current_trace(
                tags=["agent_orchestration", f"org:{organization_id}", "phase:planning"],
                metadata={
                    "objective": objective,
                    "max_steps": max_steps,
                    "plan_steps": len(plan),
                    "task_id": str(task.id)
                }
            )
            
            # 3. EXECUTE: Run each step
            task.status = "executing"
            task.started_at = datetime.utcnow()
            db.commit()
            
            step_results = []
            for idx, step_plan in enumerate(plan, start=1):
                logger.info(f"Task {task.id}: Executing step {idx}/{len(plan)}: {step_plan.get('action')}")
                
                step_result = self._execute_step(
                    task=task,
                    step_number=idx,
                    step_plan=step_plan,
                    previous_results=step_results,
                    db=db,
                    organization_id=organization_id
                )
                step_results.append(step_result)
                task.current_step = idx
                db.commit()
                
                # Early termination if step failed critically
                if step_result.get("status") == "critical_error":
                    raise Exception(f"Critical error in step {idx}: {step_result.get('error')}")
            
            # 4. SYNTHESIZE: Combine results
            logger.info(f"Task {task.id}: Synthesizing {len(step_results)} step results")
            final_result = self._synthesize_results(
                objective=objective,
                plan=plan,
                step_results=step_results,
                organization_id=organization_id
            )
            
            # 5. Update task completion
            task.status = "completed"
            task.result = final_result
            task.completed_at = datetime.utcnow()
            db.commit()
            
            duration = (task.completed_at - task.created_at).total_seconds()
            logger.info(f"Task {task.id}: Completed in {duration:.2f}s, cost: ${float(task.total_cost_usd):.4f}")
            
            # 6. Update Langfuse trace
            langfuse_context.update_current_trace(
                tags=["completed"],
                metadata={
                    "status": "completed",
                    "steps_executed": len(step_results),
                    "total_cost": float(task.total_cost_usd),
                    "duration_seconds": duration
                }
            )
            
            return {
                "task_id": str(task.id),
                "status": task.status,
                "plan": plan,
                "result": final_result,
                "steps_executed": len(step_results),
                "total_cost": float(task.total_cost_usd),
                "duration_seconds": duration
            }
            
        except Exception as e:
            # Handle errors gracefully
            logger.error(f"Task {task.id}: Failed with error: {str(e)}")
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = datetime.utcnow()
            db.commit()
            
            langfuse_context.update_current_trace(
                tags=["error", "failed"],
                metadata={"error": str(e), "task_id": str(task.id)}
            )
            
            raise
    
    def _generate_plan(
        self,
        objective: str,
        context: Optional[Dict],
        max_steps: int
    ) -> List[Dict]:
        """
        Generate step-by-step execution plan using LLM.
        
        Uses GPT-4o-mini with structured output to ensure plan quality.
        
        Args:
            objective: User's analysis goal
            context: Additional context (date ranges, filters, etc.)
            max_steps: Maximum allowed steps
            
        Returns:
            List of step dictionaries with action, description, and tool_input
        """
        system_prompt = """You are a financial analysis planning agent for an NGO.

Your task is to create a step-by-step execution plan to achieve the user's objective.

Available tools:
- rag_query: Search and retrieve information from uploaded documents (PDFs, invoices, receipts)
- fetch_transactions: Get financial transactions from database with date/type filters
- calculate_metrics: Compute financial metrics (totals, averages, trends, percentages)
- analyze_trends: Identify patterns and trends in data using statistical analysis
- generate_recommendations: Create actionable insights and budget recommendations

Rules:
1. Break down complex objectives into 3-10 atomic steps
2. Each step should use exactly ONE tool
3. Steps should be sequential and build on each other
4. Be specific about tool inputs (filters, date ranges, queries)
5. Final step should always synthesize findings
6. Consider data dependencies (fetch data before analyzing it)
7. Keep steps focused and measurable

Output format (JSON):
{
  "steps": [
    {
      "step_number": 1,
      "action": "fetch_transactions",
      "description": "Fetch all Q4 2025 expense transactions",
      "tool_input": {"date_from": "2025-10-01", "date_to": "2025-12-31", "type": "expense"},
      "expected_output": "List of expense transactions with amounts and categories"
    },
    {
      "step_number": 2,
      "action": "calculate_metrics",
      "description": "Calculate total spending and category breakdown",
      "tool_input": {"metrics": ["total", "by_category", "average"]},
      "expected_output": "Financial metrics with totals and averages"
    },
    ...
  ],
  "reasoning": "This plan will achieve the objective by first gathering Q4 data, then analyzing spending patterns, and finally generating recommendations based on the analysis."
}
"""
        
        context_str = json.dumps(context) if context else 'None provided'
        user_prompt = f"""Objective: {objective}

Context: {context_str}

Create a plan with maximum {max_steps} steps to achieve this objective."""

        logger.info(f"Generating plan for objective: {objective}")
        
        # Call LLM with structured output
        response = self.ai_service.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.3  # Lower temperature for more focused planning
        )
        
        plan_data = json.loads(response.choices[0].message.content)
        steps = plan_data.get("steps", [])
        
        logger.info(f"Plan generated with {len(steps)} steps: {plan_data.get('reasoning', 'No reasoning provided')}")
        
        return steps
    
    def _execute_step(
        self,
        task: models.AgentTask,
        step_number: int,
        step_plan: Dict,
        previous_results: List[Dict],
        db: Session,
        organization_id: int
    ) -> Dict[str, Any]:
        """
        Execute a single step in the agent task.
        
        Dispatches to appropriate tool based on action type and logs
        execution details in AgentStep record.
        
        Args:
            task: Parent AgentTask
            step_number: Current step number (1-indexed)
            step_plan: Step definition from plan
            previous_results: Results from previous steps
            db: Database session
            organization_id: Organization context
            
        Returns:
            {
                "status": "completed",
                "step_number": 1,
                "result": {...},
                "tokens_used": 150,
                "cost_usd": 0.0023
            }
        """
        # Create AgentStep record
        step = models.AgentStep(
            id=uuid.uuid4(),
            task_id=task.id,
            step_number=step_number,
            step_name=step_plan.get("description", f"Step {step_number}"),
            action=step_plan["action"],
            input_data=step_plan.get("tool_input", {}),
            status="running",
            started_at=datetime.utcnow()
        )
        db.add(step)
        db.commit()
        
        try:
            # Dispatch to tool
            action = step_plan["action"]
            tool_input = step_plan.get("tool_input", {})
            
            logger.info(f"Step {step_number}: Calling tool '{action}' with input: {tool_input}")
            
            if action == "rag_query":
                result = self._tool_rag_query(tool_input, organization_id, db)
            elif action == "fetch_transactions":
                result = self._tool_fetch_transactions(tool_input, organization_id, db)
            elif action == "calculate_metrics":
                result = self._tool_calculate_metrics(tool_input, previous_results)
            elif action == "analyze_trends":
                result = self._tool_analyze_trends(tool_input, previous_results)
            elif action == "generate_recommendations":
                result = self._tool_generate_recommendations(tool_input, previous_results)
            else:
                raise ValueError(f"Unknown action: {action}")
            
            # Update step completion
            step.status = "completed"
            step.output_data = result
            step.completed_at = datetime.utcnow()
            step.duration_seconds = Decimal(str((step.completed_at - step.started_at).total_seconds()))
            
            # Update cost tracking
            tokens = result.get("tokens_used", 0)
            cost = Decimal(str(result.get("cost_usd", 0.0)))
            step.tokens_used = tokens
            step.cost_usd = cost
            
            task.total_tokens_used += tokens
            task.total_cost_usd += cost
            
            db.commit()
            
            logger.info(f"Step {step_number}: Completed successfully (tokens: {tokens}, cost: ${float(cost):.4f})")
            
            return {
                "status": "completed",
                "step_number": step_number,
                "result": result,
                "tokens_used": tokens,
                "cost_usd": float(cost)
            }
            
        except Exception as e:
            # Log error but continue execution (soft fail)
            logger.error(f"Step {step_number}: Error - {str(e)}")
            step.status = "error"
            step.error_message = str(e)
            step.completed_at = datetime.utcnow()
            if step.started_at:
                step.duration_seconds = Decimal(str((step.completed_at - step.started_at).total_seconds()))
            db.commit()
            
            return {
                "status": "error",
                "step_number": step_number,
                "error": str(e)
            }
    
    def _synthesize_results(
        self,
        objective: str,
        plan: List[Dict],
        step_results: List[Dict],
        organization_id: int
    ) -> Dict[str, Any]:
        """
        Synthesize step results into coherent final answer.
        
        Uses LLM to combine all step outputs into actionable insights.
        
        Args:
            objective: Original user objective
            plan: Execution plan
            step_results: Results from all executed steps
            organization_id: Organization context
            
        Returns:
            {
                "summary": "Comprehensive analysis report...",
                "step_count": 5,
                "successful_steps": 5
            }
        """
        system_prompt = """You are a financial analyst synthesizing research findings.

Your task is to combine the results from multiple analysis steps into a coherent,
actionable report that answers the user's original objective.

Guidelines:
1. Start with an executive summary (2-3 sentences)
2. Reference specific findings from each step
3. Highlight key insights and trends with numbers
4. Provide 3-5 actionable recommendations
5. Include relevant data points and citations
6. Be concise but comprehensive (300-500 words)
7. Use bullet points for clarity
8. Focus on actionable insights

Format:
**Executive Summary:**
[2-3 sentence overview]

**Key Findings:**
- Finding 1 (from Step X)
- Finding 2 (from Step Y)
...

**Recommendations:**
1. Recommendation with data-driven reasoning
2. ...

**Conclusion:**
[Brief wrap-up]
"""

        # Build context from step results
        context_parts = []
        for idx, (step_plan, step_result) in enumerate(zip(plan, step_results), start=1):
            if step_result.get("status") == "completed":
                result_data = step_result.get("result", {})
                context_parts.append(
                    f"Step {idx} ({step_plan['action']}): {step_plan['description']}\n"
                    f"Result: {json.dumps(result_data, indent=2)}"
                )
            else:
                context_parts.append(
                    f"Step {idx} ({step_plan['action']}): FAILED - {step_result.get('error', 'Unknown error')}"
                )
        
        context = "\n\n".join(context_parts)
        
        user_prompt = f"""Original Objective: {objective}

Analysis Results from {len(step_results)} steps:

{context}

Synthesize these findings into a comprehensive financial analysis report."""

        logger.info("Synthesizing results with LLM")
        
        response = self.ai_service.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2  # Low temperature for factual synthesis
        )
        
        synthesis = response.choices[0].message.content
        
        return {
            "summary": synthesis,
            "step_count": len(step_results),
            "successful_steps": sum(1 for r in step_results if r.get("status") == "completed"),
            "failed_steps": sum(1 for r in step_results if r.get("status") == "error")
        }
    
    # ========================================================================
    # Tool Implementations
    # ========================================================================
    
    def _tool_rag_query(self, tool_input: Dict, organization_id: int, db: Session) -> Dict:
        """
        Execute RAG query tool.
        
        Searches uploaded documents using semantic search and generates
        answers with citations.
        """
        question = tool_input.get("query", tool_input.get("question", ""))
        top_k = tool_input.get("top_k", 5)
        
        logger.info(f"RAG query: '{question}' (top_k={top_k})")
        
        result = self.rag_service.query(
            question=question,
            organization_id=organization_id,
            db=db,
            top_k=top_k
        )
        
        return {
            "answer": result["answer"],
            "sources": result["sources"],
            "confidence": result.get("confidence", 0.0),
            "tokens_used": result.get("tokens_used", 0),
            "cost_usd": result.get("cost_usd", 0.0)
        }
    
    def _tool_fetch_transactions(self, tool_input: Dict, organization_id: int, db: Session) -> Dict:
        """
        Fetch transactions with filters.
        
        Retrieves financial transactions from database based on date range
        and transaction type filters.
        """
        from datetime import datetime as dt
        
        date_from = tool_input.get("date_from")
        date_to = tool_input.get("date_to")
        transaction_type = tool_input.get("type")  # "income" or "expense"
        
        logger.info(f"Fetching transactions: from={date_from}, to={date_to}, type={transaction_type}")
        
        # Build query
        query = db.query(models.Transaction).filter(
            models.Transaction.organization_id == organization_id
        )
        
        if date_from:
            query = query.filter(models.Transaction.date >= dt.fromisoformat(date_from))
        if date_to:
            query = query.filter(models.Transaction.date <= dt.fromisoformat(date_to))
        if transaction_type:
            query = query.filter(models.Transaction.transaction_type == transaction_type)
        
        transactions = query.all()
        
        logger.info(f"Found {len(transactions)} transactions")
        
        return {
            "transactions": [
                {
                    "id": str(t.id),
                    "date": t.date.isoformat() if t.date else None,
                    "amount": float(t.amount) if t.amount else 0.0,
                    "description": t.description,
                    "type": t.transaction_type,
                    "category": getattr(t, 'category', 'uncategorized')
                }
                for t in transactions
            ],
            "count": len(transactions),
            "total_amount": sum(float(t.amount) if t.amount else 0.0 for t in transactions),
            "tokens_used": 0,
            "cost_usd": 0.0
        }
    
    def _tool_calculate_metrics(self, tool_input: Dict, previous_results: List[Dict]) -> Dict:
        """
        Calculate financial metrics from previous step data.
        
        Computes totals, averages, min/max, and category breakdowns.
        """
        # Extract transactions from previous results
        transactions = []
        for result in previous_results:
            if result.get("status") == "completed":
                step_result = result.get("result", {})
                if "transactions" in step_result:
                    transactions.extend(step_result["transactions"])
        
        if not transactions:
            logger.warning("No transaction data found in previous steps")
            return {"error": "No transaction data found in previous steps", "tokens_used": 0, "cost_usd": 0.0}
        
        # Calculate metrics
        total = sum(t["amount"] for t in transactions)
        average = total / len(transactions) if transactions else 0
        max_transaction = max(transactions, key=lambda t: t["amount"]) if transactions else None
        min_transaction = min(transactions, key=lambda t: t["amount"]) if transactions else None
        
        # Category breakdown
        by_category = {}
        for t in transactions:
            category = t.get("category", "uncategorized")
            if category not in by_category:
                by_category[category] = {"count": 0, "total": 0.0}
            by_category[category]["count"] += 1
            by_category[category]["total"] += t["amount"]
        
        logger.info(f"Calculated metrics for {len(transactions)} transactions: total=${total:.2f}")
        
        return {
            "total": round(total, 2),
            "average": round(average, 2),
            "count": len(transactions),
            "max_transaction": max_transaction,
            "min_transaction": min_transaction,
            "by_category": by_category,
            "tokens_used": 0,
            "cost_usd": 0.0
        }
    
    def _tool_analyze_trends(self, tool_input: Dict, previous_results: List[Dict]) -> Dict:
        """
        Analyze trends using LLM.
        
        Uses GPT-4o-mini to identify patterns, anomalies, and trends
        in financial data.
        """
        # Extract data summary from previous results
        data_summary = json.dumps([r.get("result", {}) for r in previous_results if r.get("status") == "completed"], indent=2)
        
        prompt = f"""Analyze the following financial data and identify key trends:

{data_summary}

Provide:
1. Top 3 trends (increasing/decreasing patterns, seasonal effects)
2. Anomalies or outliers (unusual transactions or spending patterns)
3. Month-over-month or quarter-over-quarter comparisons if applicable
4. Key insights with specific numbers

Be concise and data-driven. Use bullet points."""

        logger.info("Analyzing trends with LLM")
        
        response = self.ai_service.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        analysis = response.choices[0].message.content
        tokens = response.usage.total_tokens
        cost = tokens * 0.00015 / 1000  # GPT-4o-mini pricing: $0.150 per 1M tokens
        
        return {
            "analysis": analysis,
            "tokens_used": tokens,
            "cost_usd": cost
        }
    
    def _tool_generate_recommendations(self, tool_input: Dict, previous_results: List[Dict]) -> Dict:
        """
        Generate recommendations based on analysis.
        
        Uses LLM to create actionable budget recommendations from
        financial analysis results.
        """
        # Extract data summary
        data_summary = json.dumps([r.get("result", {}) for r in previous_results if r.get("status") == "completed"], indent=2)
        
        prompt = f"""Based on this financial analysis, provide 3-5 actionable recommendations:

{data_summary}

Each recommendation should include:
1. What to do (specific action)
2. Why (data-driven reasoning with numbers)
3. Expected impact (quantified if possible)
4. Priority (high/medium/low)

Focus on budget optimization, cost reduction, and financial efficiency.
Be specific and actionable."""

        logger.info("Generating recommendations with LLM")
        
        response = self.ai_service.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4  # Slightly higher for creative recommendations
        )
        
        recommendations = response.choices[0].message.content
        tokens = response.usage.total_tokens
        cost = tokens * 0.00015 / 1000
        
        return {
            "recommendations": recommendations,
            "tokens_used": tokens,
            "cost_usd": cost
        }
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    def _create_task(
        self,
        db: Session,
        objective: str,
        organization_id: int,
        context: Optional[Dict],
        max_steps: int
    ) -> models.AgentTask:
        """
        Create AgentTask database record.
        
        Args:
            db: Database session
            objective: User's analysis goal
            organization_id: Organization context
            context: Additional context dict
            max_steps: Maximum allowed steps
            
        Returns:
            Created AgentTask instance
        """
        task = models.AgentTask(
            id=uuid.uuid4(),
            organization_id=organization_id,
            objective=objective,
            context=context or {},
            max_steps=max_steps,
            status="pending",
            langfuse_trace_id=langfuse_context.get_current_trace_id()
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        
        logger.info(f"Created task {task.id} for org {organization_id}")
        
        return task
