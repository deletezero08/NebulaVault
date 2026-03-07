FROM python:3.13-slim

WORKDIR /app

# Install OS-level dependencies for PyMuPDF and Tesseract OCR
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-chi-sim \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy all files
COPY . .

# Expose API port
EXPOSE 8000

# Start server
CMD ["python", "main.py"]
