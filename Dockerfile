# Dockerfile for Research-to-Blog Pipeline
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY tests/ ./tests/
COPY examples/ ./examples/
COPY pyproject.toml .
COPY README.md .
COPY LICENSE .

# Create data directories
RUN mkdir -p data/chroma data/cache outputs

# Expose API port
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO

# Default command: run API server
CMD ["uvicorn", "app.api.server:app", "--host", "0.0.0.0", "--port", "8000"]

