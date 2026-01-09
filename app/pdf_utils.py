"""
PDF text extraction utility for document processing.
Extracts text from PDF files for AI analysis.
"""

from PyPDF2 import PdfReader
from typing import Optional
import io


def extract_text_from_pdf(file_bytes: bytes) -> Optional[str]:
    """
    Extract text content from PDF file bytes.
    
    Args:
        file_bytes: PDF file as bytes
        
    Returns:
        Extracted text string or None if extraction failed
        
    Example:
        >>> with open("receipt.pdf", "rb") as f:
        >>>     text = extract_text_from_pdf(f.read())
        >>> print(text)
    """
    try:
        # Create PDF reader from bytes
        pdf_file = io.BytesIO(file_bytes)
        pdf_reader = PdfReader(pdf_file)
        
        # Extract text from all pages
        text_parts = []
        for page_num, page in enumerate(pdf_reader.pages):
            page_text = page.extract_text()
            if page_text.strip():
                text_parts.append(f"--- Page {page_num + 1} ---\n{page_text}")
        
        # Combine all pages
        full_text = "\n\n".join(text_parts)
        
        return full_text if full_text.strip() else None
        
    except Exception as e:
        print(f"Error extracting text from PDF: {str(e)}")
        return None


def get_pdf_metadata(file_bytes: bytes) -> dict:
    """
    Extract metadata from PDF file.
    
    Args:
        file_bytes: PDF file as bytes
        
    Returns:
        Dictionary with PDF metadata (title, author, pages, etc.)
    """
    try:
        pdf_file = io.BytesIO(file_bytes)
        pdf_reader = PdfReader(pdf_file)
        
        metadata = {
            "num_pages": len(pdf_reader.pages),
            "is_encrypted": pdf_reader.is_encrypted,
        }
        
        # Add document info if available
        if pdf_reader.metadata:
            metadata.update({
                "title": pdf_reader.metadata.get("/Title", ""),
                "author": pdf_reader.metadata.get("/Author", ""),
                "subject": pdf_reader.metadata.get("/Subject", ""),
                "creator": pdf_reader.metadata.get("/Creator", ""),
            })
        
        return metadata
        
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    # Test extraction
    import sys
    import os
    
    test_files = [
        "test_pdfs/receipt_grocery_2026-01-05.pdf",
        "test_pdfs/invoice_consulting_2025-12-15.pdf",
        "test_pdfs/bank_statement_dec2025.pdf",
        "test_pdfs/donation_receipt_2025-001.pdf",
    ]
    
    print("🔍 Testing PDF text extraction...\n")
    
    for pdf_path in test_files:
        if not os.path.exists(pdf_path):
            print(f"⚠️  File not found: {pdf_path}")
            continue
            
        print(f"\n{'='*60}")
        print(f"📄 File: {pdf_path}")
        print('='*60)
        
        with open(pdf_path, "rb") as f:
            file_bytes = f.read()
            
        # Extract metadata
        metadata = get_pdf_metadata(file_bytes)
        print(f"\n📊 Metadata:")
        print(f"   Pages: {metadata.get('num_pages', 'N/A')}")
        print(f"   Encrypted: {metadata.get('is_encrypted', 'N/A')}")
        
        # Extract text
        text = extract_text_from_pdf(file_bytes)
        
        if text:
            print(f"\n📝 Extracted Text (first 500 chars):")
            print(f"   {text[:500]}...")
            print(f"\n   Total length: {len(text)} characters")
        else:
            print("\n❌ Failed to extract text")
    
    print("\n" + "="*60)
    print("✅ PDF extraction test complete!")
