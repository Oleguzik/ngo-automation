"""
AI Service for cost/profit analysis using OpenAI.

PHASE 3: Cost & Profit Analysis with LLM
- Extract structured data from receipts/invoices
- Analyze cost patterns
- Generate profit/loss insights
- Provide cost optimization recommendations
"""

from openai import OpenAI
from app.config import settings
from app import schemas
from typing import Optional, Dict, Any
from decimal import Decimal
import json
import logging
import re

logger = logging.getLogger(__name__)


class AIService:
    """OpenAI-based AI service for cost/profit analysis"""
    
    def __init__(self):
        """Initialize OpenAI client"""
        if not settings.OPENAI_API_KEY:
            logger.warning("OpenAI API key not configured. AI features disabled.")
            self.client = None
        else:
            self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
            self.model = settings.OPENAI_MODEL
    
    def extract_cost_from_text(self, text: str) -> Dict[str, Any]:
        """
        Extract cost data from document text using OpenAI Structured Outputs.
        
        Uses OpenAI's native Pydantic schema enforcement for guaranteed JSON compliance.
        Reference: https://platform.openai.com/docs/guides/structured-outputs
        
        Args:
            text: Extracted text from receipt/invoice
            
        Returns:
            Structured cost data: {date, vendor, items, amount, ...}
        """
        if not self.client:
            logger.error("OpenAI client not initialized")
            return {}
        
        system_prompt = """You are an expert at extracting cost/expense data from documents.
        Extract the following information from the provided text:
        - date: Date of purchase (YYYY-MM-DD format preferred)
        - vendor: Name of store/vendor
        - category: Category of expense (Salaries, Rent, Supplies, Transport, Services, Other)
        - description: Brief description of what was purchased
        - amount: Total amount (as number, no currency symbols)
        - currency: Currency code (EUR, USD, etc.) 
        - items: List of individual items with name, amount, quantity, unit
        - confidence: Confidence level (0.0 to 1.0) for the extraction accuracy
        
        Extract data accurately and return in the provided structure."""
        
        # Use OpenAI Structured Outputs with Pydantic schema enforcement
        # This guarantees JSON compliance and eliminates parsing errors
        try:
            response = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Extract cost data from this document:\n\n{text}"},
                ],
                response_format=schemas.ExtractedCostData,  # Pydantic schema
            )
            
            # The .parsed field contains the validated Pydantic model
            parsed_model = response.choices[0].message.parsed
            
            if not parsed_model:
                logger.error("OpenAI returned empty parsed result")
                return {}
            
            # Convert to dict, excluding None values
            cleaned = json.loads(parsed_model.model_dump_json(exclude_none=True))
            logger.info(f"Successfully extracted cost data with structured outputs: {cleaned}")
            return cleaned
            
        except Exception as e:
            logger.error(f"OpenAI structured extraction error: {e}")
            # Fallback: Try with legacy JSON mode if structured outputs fail
            try:
                logger.warning("Falling back to legacy JSON mode")
                response = self.client.chat.completions.create(
                    model=self.model,
                    temperature=0,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Extract cost data from this document:\n\n{text}"},
                    ],
                )
                result_text = (response.choices[0].message.content or "").strip()
                data = json.loads(result_text)
                model = schemas.ExtractedCostData.model_validate(data)
                cleaned = json.loads(model.model_dump_json(exclude_none=True))
                logger.info(f"Successfully extracted cost data (fallback mode): {cleaned}")
                return cleaned
            except Exception as fallback_error:
                logger.error(f"Cost extraction fallback failed: {fallback_error}")
                return {}
    
    def extract_profit_from_text(self, text: str) -> Dict[str, Any]:
        """
        Extract profit/revenue data from document text using OpenAI Structured Outputs.
        
        Uses OpenAI's native Pydantic schema enforcement for guaranteed JSON compliance.
        Reference: https://platform.openai.com/docs/guides/structured-outputs
        
        Args:
            text: Extracted text from donation letter, invoice, bank statement
            
        Returns:
            Structured profit data: {date, source, amount, donor_name, ...}
        """
        if not self.client:
            logger.error("OpenAI client not initialized")
            return {}
        
        system_prompt = """You are an expert at extracting revenue/income/profit data from financial documents.
        
        IMPORTANT: Focus on INCOMING money (revenue/income), NOT outgoing (expenses/costs).
        
        Document types and what to extract:
        - DONATION RECEIPTS: Extract the donation amount, donor name, date, and purpose
        - BANK STATEMENTS: Extract ONLY the CREDIT/INCOMING transactions (look for '+' or 'Credit' column)
        - INVOICES SENT: Extract the total amount the organization is RECEIVING from clients
        - GRANT AWARDS: Extract grant amount, funding source, date
        
        Extract these fields and return as JSON:
        - date: Date of transaction (YYYY-MM-DD format preferred, or original format)
        - source: Source type (donation, grant, sales, service_fee, fundraiser, bank_transfer, other)
        - amount: Total amount RECEIVED (as plain number, no currency symbols)
        - currency: Currency code (EUR, USD, GBP, etc.)
        - donor_name: Name of donor/payer/client if clearly stated
        - description: Clear description of what this revenue is for
        - reference: Transaction reference, invoice number, donation ID if available
        - transaction_items: For bank statements with multiple credits, list each as {date, description, amount}
        - confidence: Your confidence level (0.0 to 1.0) in extraction accuracy
        
        Examples:
        - Donation receipt "€2,500" → amount: 2500, source: "donation"
        - Bank statement "Transfer IN: +€25,000" → amount: 25000, source: "bank_transfer"
        - Invoice "Total Due: €16,570.75" → amount: 16570.75, source: "service_fee"
        
        Return ONLY valid JSON, no additional text."""
        
        # Use OpenAI Structured Outputs with Pydantic schema enforcement
        try:
            response = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Extract profit/revenue data from this document:\n\n{text}"},
                ],
                response_format=schemas.ExtractedProfitData,  # Pydantic schema
            )
            
            parsed_model = response.choices[0].message.parsed
            
            if not parsed_model:
                logger.error("OpenAI returned empty parsed result for profit data")
                return {}
            
            cleaned = json.loads(parsed_model.model_dump_json(exclude_none=True))
            logger.info(f"Successfully extracted profit data with structured outputs: {cleaned}")
            return cleaned
            
        except Exception as e:
            logger.error(f"OpenAI structured profit extraction error: {e}")
            # Fallback: Try with legacy JSON mode
            try:
                logger.warning("Falling back to legacy JSON mode for profit extraction")
                response = self.client.chat.completions.create(
                    model=self.model,
                    temperature=0,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Extract profit/revenue data from this document:\n\n{text}"},
                    ],
                )
                result_text = (response.choices[0].message.content or "").strip()
                data = json.loads(result_text)
                model = schemas.ExtractedProfitData.model_validate(data)
                cleaned = json.loads(model.model_dump_json(exclude_none=True))
                logger.info(f"Successfully extracted profit data (fallback mode): {cleaned}")
                return cleaned
            except Exception as fallback_error:
                logger.error(f"Profit extraction fallback failed: {fallback_error}")
                return {}
    
    def analyze_cost_profit_data(
        self,
        summary: str,
        analysis_type: str = "summary",
        custom_prompt: Optional[str] = None
    ) -> str:
        """
        Analyze cost and profit data using OpenAI.
        
        Args:
            summary: Cost/profit summary data as formatted string
            analysis_type: Type of analysis (summary, detailed, forecast, anomaly)
            custom_prompt: Custom analysis prompt from user
            
        Returns:
            AI-generated analysis text
        """
        if not self.client:
            logger.error("OpenAI client not initialized")
            return "AI analysis unavailable. Please configure OpenAI API key."
        
        if custom_prompt:
            user_message = f"{custom_prompt}\n\n{summary}"
        else:
            analysis_prompts = {
                "summary": f"Provide a brief 2-3 sentence summary of the cost and profit situation based on this data:\n\n{summary}",
                "detailed": f"Analyze the cost and profit data in detail. Identify patterns, issues, and opportunities.\n\n{summary}",
                "forecast": f"Based on the cost and profit trends, forecast the next 30 days and identify potential issues.\n\n{summary}",
                "anomaly": f"Identify any unusual or anomalous spending patterns in the cost data.\n\n{summary}",
            }
            user_message = analysis_prompts.get(analysis_type, analysis_prompts["summary"])
        
        system_prompt = """You are a financial advisor for NGOs. 
        Analyze the provided cost and profit data and provide insights and recommendations.
        Be concise, practical, and focused on actionable insights."""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=1500,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_message
                    }
                ]
            )
            
            analysis_text = response.choices[0].message.content
            logger.info(f"AI analysis generated successfully")
            return analysis_text
            
        except Exception as e:
            logger.error(f"OpenAI analysis error: {e}")
            return f"Error during analysis: {str(e)}"
    
    def identify_cost_optimization(self, cost_data: str) -> list[str]:
        """
        Generate cost optimization recommendations using OpenAI.
        
        Args:
            cost_data: Cost summary data
            
        Returns:
            List of optimization recommendations
        """
        if not self.client:
            return []
        
        system_prompt = """You are a cost optimization expert for NGOs.
        Based on the cost data provided, suggest 3-5 specific, actionable cost reduction opportunities.
        Format your response as a JSON array of strings."""
        
        user_message = f"Based on this cost data, what are specific ways to reduce costs?\\n\\n{cost_data}\\n\\nRespond with a JSON array of recommendations."
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=1000,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_message
                    }
                ]
            )
            
            result_text = response.choices[0].message.content
            recommendations = json.loads(result_text)
            return recommendations if isinstance(recommendations, list) else []
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return []


# Global AI service instance
ai_service = AIService()
