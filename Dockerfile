FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
# - gcc: C compiler for Python packages
# - postgresql-client: For DB migrations and CLI
# - tesseract-ocr: OCR engine for image text extraction
# - tesseract-ocr-deu: German language support for OCR (Phase 3 MVP)
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    tesseract-ocr \
    tesseract-ocr-deu \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
