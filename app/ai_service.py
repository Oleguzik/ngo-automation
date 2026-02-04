"""
AI Service for cost/profit analysis using OpenAI.

PHASE 3: Cost & Profit Analysis with LLM
- Extract structured data from receipts/invoices
- Analyze cost patterns
- Generate profit/loss insights
- Provide cost optimization recommendations
- Support for both unstructured text and structured table data (XLSX, CSV)
"""

from openai import OpenAI
from app.config import settings
from app import schemas
from typing import Optional, Dict, Any, List
from decimal import Decimal
import json
import logging
import re

logger = logging.getLogger(__name__)


class AIService:
    """OpenAI-based AI service for cost/profit analysis with structured data support"""
    
    def __init__(self):
        """Initialize OpenAI client"""
        if not settings.OPENAI_API_KEY:
            logger.warning("OpenAI API key not configured. AI features disabled.")
            self.client = None
        else:
            self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
            self.model = settings.OPENAI_MODEL
    
    def chat(
        self,
        messages: list,
        system: str = None,
        temperature: float = 0.1,
        max_tokens: int = 1000
    ) -> Dict[str, Any]:
        """
        General chat completion for RAG and other use cases.
        
        Args:
            messages: List of message dicts with role and content
            system: System prompt (if not in messages)
            temperature: LLM temperature (0.0-1.0)
            max_tokens: Maximum tokens in response
            
        Returns:
            Dict with 'content' key containing the response text
            
        Raises:
            ValueError: If OpenAI client not configured
        """
        if not self.client:
            raise ValueError("OpenAI API key not configured")
        
        # Build messages list
        all_messages = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=all_messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            content = response.choices[0].message.content
            return {"content": content}
            
        except Exception as e:
            logger.error(f"Chat completion failed: {str(e)}")
            raise ValueError(f"Chat completion failed: {str(e)}")
    
    def _extract_from_structured_data(self, text: str, analysis_type: str = "cost") -> Optional[Dict[str, Any]]:
        """
        Parse structured table data (spreadsheets, CSV) directly before AI processing.
        
        Identifies table headers and extracts rows, avoiding AI confusion with structured format.
        Falls back to None if not a table format.
        
        Args:
            text: Extracted text (may contain table with pipe separators)
            analysis_type: "cost" or "profit" to determine what to extract
            
        Returns:
            Extracted structured data dict, or None if not a table format
        """
        try:
            logger.debug(f"Starting structured data extraction (type={analysis_type})")
            
            # Check if this looks like a table (has pipe separators and headers)
            lines = text.strip().split('\n')
            logger.debug(f"Text has {len(lines)} lines")
            if len(lines) < 2:
                logger.debug("Not enough lines for a table")
                return None  # Not enough lines for a table
            
            # Look for pipe-separated headers
            has_pipes = any('|' in line for line in lines[:3])
            if not has_pipes:
                logger.debug("No pipe separators found in first 3 lines")
                return None  # Not a pipe-separated table
            
            logger.debug("Detected pipe-separated format")
            
            # Parse header row - look for financial keywords
            # Common header keywords in German and English
            header_keywords = [
                'datum', 'date', 'beschreibung', 'description', 'betrag', 'amount',
                'kategorie', 'category', 'einnahmen', 'income', 'ausgaben', 'expense',
                'vendor', 'lieferant', 'kost', 'total', 'summe'
            ]
            
            header_line = None
            data_start_idx = 0
            
            for idx, line in enumerate(lines):
                if '|' in line:
                    # Skip separator lines (all dashes)
                    cleaned = line.replace('|', '').replace('-', '').replace('=', '').replace('>', '').strip()
                    if not cleaned or not any(c.isalnum() for c in cleaned):
                        continue
                    
                    # Check if this line contains header keywords
                    line_lower = line.lower()
                    has_keyword = any(keyword in line_lower for keyword in header_keywords)
                    
                    if has_keyword:
                        header_line = line
                        data_start_idx = idx + 1
                        logger.debug(f"Found header with keywords at line {idx}: {header_line[:80]}")
                        break
            
            if not header_line:
                logger.warning("Could not find header line")
                return None
            
            # Parse headers
            headers = [h.strip().lower() for h in header_line.split('|') if h.strip()]
            logger.info(f"Detected table headers: {headers}")
            
            if not headers:
                return None
            
            # Detect complex dual-column formats (Einnahmen + Ausgaben in same row)
            header_str = ' '.join(headers)
            has_income = 'einnahmen' in header_str or 'income' in header_str
            has_expense = 'ausgaben' in header_str or 'expense' in header_str or 'cost' in header_str
            
            if has_income and has_expense:
                logger.warning(f"Detected complex dual-column format (Income + Expenses). Falling back to AI extraction.")
                return None  # Let AI handle complex layouts
            
            # Parse first data row
            if data_start_idx >= len(lines):
                logger.warning("No data rows after header")
                return None
            
            data_row = None
            for idx in range(data_start_idx, len(lines)):
                line = lines[idx].strip()
                logger.info(f"Checking line {idx} for data: '{line[:40] if line else 'EMPTY'}'")
                # Skip empty lines
                if not line:
                    logger.info(f"  Line {idx} is empty, skipping")
                    continue
                # Skip separator lines (all dashes and pipes, no alphanumeric)
                non_separator_chars = line.replace('|', '').replace('-', '')
                is_separator_line = not any(c.isalnum() for c in non_separator_chars)
                logger.info(f"  Line {idx} separator check: is_separator={is_separator_line}")
                if is_separator_line:
                    logger.info(f"  Line {idx} is separator line, skipping")
                    continue
                # Must have pipe character
                if '|' not in line:
                    logger.info(f"  Line {idx} has no pipe, skipping")
                    continue
                    
                # This is a data line
                parts = [p.strip() for p in line.split('|') if p.strip()]
                logger.info(f"  Line {idx} has {len(parts)} parts (need >= {len(headers) - 1})")
                if len(parts) >= len(headers) - 1:  # Allow one less part
                    data_row = parts
                    logger.info(f"  -> FOUND DATA ROW at line {idx}: {parts}")
                    break
                else:
                    logger.info(f"  -> Not enough parts ({len(parts)} < {len(headers) - 1}), continuing")
            
            if not data_row:
                logger.warning("Could not find data row")
                return None
            
            # Map values to headers
            row_dict = {}
            for i, header in enumerate(headers):
                if i < len(data_row):
                    row_dict[header] = data_row[i]
            
            logger.info(f"Parsed table row: {row_dict}")
            
            # Build structured response based on analysis type
            if analysis_type == "cost":
                result = self._build_cost_from_row(row_dict, headers, lines, data_start_idx)
            else:  # profit
                result = self._build_profit_from_row(row_dict, headers, lines, data_start_idx)
            
            if result:
                logger.info(f"Successfully extracted {analysis_type} data from table: {result}")
            else:
                logger.warning(f"_build_{analysis_type}_from_row returned None")
            
            return result
            
        except Exception as e:
            logger.error(f"Structured data parsing failed: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _build_cost_from_row(self, row_dict: Dict[str, str], headers: list, all_lines: list, data_start_idx: int) -> Optional[Dict[str, Any]]:
        """Build ExtractedCostData from parsed table row."""
        try:
            logger.debug(f"Building cost from row_dict: {row_dict}")
            
            # Map common column names (German and English)
            date_val = (row_dict.get('datum') or row_dict.get('date') or 
                       row_dict.get('date_val') or '')
            description = (row_dict.get('beschreibung') or row_dict.get('description') or 
                          row_dict.get('item') or row_dict.get('name') or '')
            amount_str = (row_dict.get('betrag (eur)') or row_dict.get('amount') or 
                         row_dict.get('betrag') or '')
            category_val = row_dict.get('kategorie') or row_dict.get('category') or ''
            
            logger.debug(f"Extracted values - date: {date_val}, desc: {description}, amount_str: {amount_str}, cat: {category_val}")
            
            # Parse amount
            amount = None
            if amount_str:
                try:
                    amount_str_clean = amount_str.replace('€', '').replace(',', '.').strip()
                    amount = float(amount_str_clean)
                    logger.debug(f"Parsed amount: {amount} from {amount_str}")
                except Exception as parse_err:
                    logger.debug(f"Failed to parse amount '{amount_str}': {parse_err}")
            
            if amount is None or amount == 0:
                logger.warning(f"No valid amount found in row: {row_dict}")
                return None  # No valid amount found
            
            # Build items from remaining rows if available
            items = []
            for idx in range(data_start_idx + 1, min(data_start_idx + 6, len(all_lines))):  # Up to 5 more rows
                line = all_lines[idx].strip()
                if line and '|' in line and '-' not in line.replace('|', ''):
                    parts = [p.strip() for p in line.split('|') if p.strip()]
                    if len(parts) >= 2:
                        item_name = parts[0]
                        item_amount_str = parts[-1] if len(parts) > 2 else ''
                        try:
                            item_amount = float(item_amount_str.replace('€', '').replace(',', '.'))
                            items.append({
                                "name": item_name,
                                "amount": item_amount,
                                "quantity": None,
                                "unit": None
                            })
                        except:
                            pass
            
            result = {
                "date": date_val if date_val else None,
                "vendor": "Financial Report" if not description or description == '-' else description,
                "category": category_val if category_val else "Other",
                "description": description if description else "Transaction from spreadsheet",
                "amount": amount,
                "currency": "EUR",
                "items": items if items else None,
                "confidence": 0.95  # High confidence for direct table parsing
            }
            
            logger.info(f"Built cost result: {result}")
            return result
        except Exception as e:
            logger.error(f"Failed to build cost from row: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _build_profit_from_row(self, row_dict: Dict[str, str], headers: list, all_lines: list, data_start_idx: int) -> Optional[Dict[str, Any]]:
        """Build ExtractedProfitData from parsed table row."""
        try:
            # Map common column names (German and English)
            date_val = (row_dict.get('datum') or row_dict.get('date') or 
                       row_dict.get('date_val') or '')
            description = (row_dict.get('beschreibung') or row_dict.get('description') or 
                          row_dict.get('source') or row_dict.get('name') or '')
            amount_str = (row_dict.get('betrag (eur)') or row_dict.get('amount') or 
                         row_dict.get('betrag') or '')
            category_val = row_dict.get('kategorie') or row_dict.get('category') or row_dict.get('type') or ''
            
            # Parse amount
            amount = None
            if amount_str:
                try:
                    amount_str_clean = amount_str.replace('€', '').replace(',', '.').strip()
                    amount = float(amount_str_clean)
                except:
                    pass
            
            if amount is None or amount == 0:
                return None  # No valid amount found
            
            # Build transaction items from remaining rows
            transaction_items = []
            for idx in range(data_start_idx + 1, min(data_start_idx + 6, len(all_lines))):  # Up to 5 more rows
                line = all_lines[idx].strip()
                if line and '|' in line and '-' not in line.replace('|', ''):
                    parts = [p.strip() for p in line.split('|') if p.strip()]
                    if len(parts) >= 2:
                        item_date = parts[0]
                        item_desc = parts[1] if len(parts) > 2 else parts[0]
                        item_amount_str = parts[-1] if len(parts) > 1 else ''
                        try:
                            item_amount = float(item_amount_str.replace('€', '').replace(',', '.'))
                            transaction_items.append({
                                "date": item_date,
                                "description": item_desc,
                                "amount": item_amount
                            })
                        except:
                            pass
            
            return {
                "date": date_val if date_val else None,
                "source": category_val if category_val else "financial_transaction",
                "amount": amount,
                "currency": "EUR",
                "donor_name": None,
                "description": description if description else "Financial transaction",
                "reference": None,
                "transaction_items": transaction_items if transaction_items else None,
                "confidence": 0.95  # High confidence for direct table parsing
            }
        except Exception as e:
            logger.debug(f"Failed to build profit from row: {e}")
            return None
    
    def extract_cost_from_text(self, text: str) -> Dict[str, Any]:
        """
        Extract cost data from document text using OpenAI Structured Outputs.
        
        Uses OpenAI's native Pydantic schema enforcement for guaranteed JSON compliance.
        Handles both unstructured (receipts/invoices) and structured (tables/spreadsheets) data.
        Reference: https://platform.openai.com/docs/guides/structured-outputs
        
        Args:
            text: Extracted text from receipt/invoice/spreadsheet
            
        Returns:
            Structured cost data: {date, vendor, items, amount, ...}
        """
        # Try to extract from structured data first (tables)
        # This works WITHOUT OpenAI API, so do it before checking client
        structured_result = self._extract_from_structured_data(text, analysis_type="cost")
        if structured_result:
            logger.info(f"Extracted cost data from structured data (table): {structured_result}")
            return structured_result
        
        # Only use AI if not structured data
        if not self.client:
            logger.error("OpenAI client not initialized")
            return {}
        
        system_prompt = """You are an expert at extracting cost/expense data from documents.
        The document may be:
        - Unstructured text (receipts, invoices, free-form documents)
        - Structured tables (spreadsheets with headers like Date, Description, Amount)
        
        If processing a TABLE/SPREADSHEET with column headers:
        - Identify header row (Date | Description | Amount | Category, etc.)
        - Extract the FIRST ROW of data as the primary transaction
        - Use table headers to map values to fields
        - If multiple rows exist, create items list from additional rows
        
        If processing free-form TEXT:
        - Extract date, vendor, amount, description as usual
        
        Required fields to extract:
        - date: Date of purchase (YYYY-MM-DD format preferred, or original format)
        - vendor: Name of store/vendor/description from header
        - category: Category of expense (Salaries, Rent, Supplies, Transport, Services, Other)
        - description: Brief description of what was purchased
        - amount: Total amount (as NUMBER only, no currency symbols)
        - currency: Currency code (EUR, USD, etc.)
        - items: List of individual items (if multiple rows in table)
        - confidence: Confidence level (0.0 to 1.0) for extraction accuracy
        
        Return data accurately in the provided structure."""
        
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
        Handles both unstructured (donation letters) and structured (bank statements, spreadsheets) data.
        Reference: https://platform.openai.com/docs/guides/structured-outputs
        
        Args:
            text: Extracted text from donation letter, invoice, bank statement, spreadsheet
            
        Returns:
            Structured profit data: {date, source, amount, donor_name, ...}
        """
        # Try to extract from structured data first (tables/spreadsheets)
        # This works WITHOUT OpenAI API, so do it before checking client
        structured_result = self._extract_from_structured_data(text, analysis_type="profit")
        if structured_result:
            logger.info(f"Extracted profit data from structured data (table): {structured_result}")
            return structured_result
        
        # Only use AI if not structured data
        if not self.client:
            logger.error("OpenAI client not initialized")
            return {}
        
        system_prompt = """You are an expert at extracting revenue/income/profit data from financial documents.
        
        IMPORTANT: Focus on INCOMING money (revenue/income), NOT outgoing (expenses/costs).
        
        The document may be:
        - Unstructured text (donation receipts, grant letters, donation confirmations)
        - Structured tables (bank statements, donation logs, revenue spreadsheets)
        
        If processing a TABLE/SPREADSHEET with column headers:
        - Identify header row (Date | Description | Amount | Category, etc.)
        - Extract the FIRST ROW of data as the primary transaction
        - Use table headers to map values to fields
        - If multiple rows exist, create transaction_items list from additional rows
        
        If processing free-form TEXT:
        - Extract date, source, amount, donor_name as usual
        
        Document types and what to extract:
        - DONATION RECEIPTS: Extract the donation amount, donor name, date, and purpose
        - BANK STATEMENTS: Extract ONLY the CREDIT/INCOMING transactions (look for '+' or 'Credit' column)
        - INVOICES SENT: Extract the total amount the organization is RECEIVING from clients
        - GRANT AWARDS: Extract grant amount, funding source, date
        
        Extract these fields:
        - date: Date of transaction (YYYY-MM-DD format preferred, or original format)
        - source: Source type (donation, grant, sales, service_fee, fundraiser, bank_transfer, other)
        - amount: Total amount RECEIVED (as NUMBER only, no currency symbols)
        - currency: Currency code (EUR, USD, GBP, etc.)
        - donor_name: Name of donor/payer/client if clearly stated
        - description: Clear description of what this revenue is for
        - reference: Transaction reference, invoice number, donation ID if available
        - transaction_items: For spreadsheets/bank statements with multiple rows, list each as {date, description, amount}
        - confidence: Your confidence level (0.0 to 1.0) in extraction accuracy
        
        Examples:
        - Donation receipt "€2,500" → amount: 2500, source: "donation"
        - Bank statement "Transfer IN: +€25,000" → amount: 25000, source: "bank_transfer"
        - Invoice "Total Due: €16,570.75" → amount: 16570.75, source: "service_fee"
        - Table with rows → extract first row, add rest to transaction_items
        
        Return data accurately in the provided structure."""
        
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
    
    def identify_cost_optimization(self, cost_data: str) -> List[str]:
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
        
        user_message = f"Based on this cost data, what are specific ways to reduce costs?\n\n{cost_data}\n\nRespond with a JSON array of recommendations."
        
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
