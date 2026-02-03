"""
Versioned prompts for agentic routing experimentation.

This module contains multiple prompt variants for testing and comparison using Langfuse.
Each prompt is designed to route financial queries to the appropriate tool (extract, query, hybrid).

Usage:
    from app.prompts.routing_prompts import ROUTING_PROMPTS
    prompt = ROUTING_PROMPTS["v2_detailed"].format(query=user_query, context=context_str)

Tracking Metrics:
- Tokens used
- Cost per request
- Latency
- Routing accuracy (via LLM-as-a-Judge)
"""

ROUTING_PROMPTS = {
    "v1_basic": """
You are a financial data routing system. Given a user query, decide the best approach:
- "extract": For structured data extraction from documents
- "query": For semantic search and Q&A over financial records
- "hybrid": For complex queries requiring both

User Query: {query}
Context: {context}

Decision (respond with JSON):
{{"action": "extract|query|hybrid", "reasoning": "explanation"}}
""",
    
    "v2_detailed": """
You are an intelligent financial assistant with access to the following tools:

**Tools:**
1. **extract**: Extract structured data (invoices, receipts, contracts)
   - Use when: User asks for specific numeric values, dates, names from documents
   - Example: "What's the total from invoice #12345?"

2. **query**: Semantic search over all financial documents
   - Use when: User asks conceptual questions requiring document understanding
   - Example: "What were our main expenses last quarter?"

3. **hybrid**: Combine extraction + semantic search
   - Use when: Complex queries need both structured data and document context
   - Example: "Compare invoice amounts from Q3 vs Q4 for vendor XYZ"

**Your Task:**
Analyze this query: "{query}"
Available context: {context}

**Respond in JSON:**
{{"action": "extract|query|hybrid", "reasoning": "step-by-step explanation", "confidence": 0.0-1.0}}
""",
    
    "v3_few_shot": """
You are a financial routing system. Learn from these examples:

**Example 1:**
Query: "Show me the invoice date from doc #123"
Decision: {{"action": "extract", "reasoning": "Specific field extraction needed"}}

**Example 2:**
Query: "What trends do we see in Q4 spending?"
Decision: {{"action": "query", "reasoning": "Requires semantic analysis of multiple docs"}}

**Example 3:**
Query: "Compare extracted totals from invoices mentioning 'software licenses'"
Decision: {{"action": "hybrid", "reasoning": "Need extraction + semantic filtering"}}

**Now analyze:**
Query: "{query}"
Context: {context}

Decision (JSON):
""",

    "v4_strict": """
You are a strict financial routing system. Follow these rules:

**Extraction Rules:**
- Query mentions specific document IDs or reference numbers → "extract"
- Query asks for exact numeric values, dates, or names → "extract"
- Keywords: "show", "get", "extract", "find value in" → "extract"

**Query Rules:**
- Query asks "what", "why", "how", "summarize" → "query"
- Query mentions trends, patterns, analysis → "query"
- Keywords: "trends", "overview", "summary", "all documents about" → "query"

**Hybrid Rules:**
- Query requires both extraction AND filtering/comparison → "hybrid"
- Query mentions "compare", "all invoices over X", "filter by" → "hybrid"

Query: "{query}"
Context: {context}

Respond ONLY with valid JSON:
{{"action": "extract|query|hybrid", "reasoning": "which rule applies", "confidence": 0.0-1.0}}
""",

    "v5_concise": """
Route financial queries to: extract (structured data), query (semantic search), or hybrid (both).

Query: "{query}"
Context: {context}

JSON response:
{{"action": "extract|query|hybrid", "reasoning": "brief explanation"}}
""",
}

# Prompt metadata for tracking
PROMPT_METADATA = {
    "v1_basic": {
        "description": "Minimal routing instructions",
        "token_estimate": 120,
        "created": "2026-01-28",
        "use_case": "Baseline comparison"
    },
    "v2_detailed": {
        "description": "Detailed tool descriptions with examples",
        "token_estimate": 250,
        "created": "2026-01-28",
        "use_case": "Better context for routing decisions"
    },
    "v3_few_shot": {
        "description": "Few-shot learning with 3 examples",
        "token_estimate": 200,
        "created": "2026-01-28",
        "use_case": "Improve accuracy via examples"
    },
    "v4_strict": {
        "description": "Explicit rules-based routing",
        "token_estimate": 220,
        "created": "2026-01-28",
        "use_case": "High accuracy, low ambiguity"
    },
    "v5_concise": {
        "description": "Minimal tokens, fast response",
        "token_estimate": 80,
        "created": "2026-01-28",
        "use_case": "Cost optimization"
    },
}
