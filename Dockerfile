# 2hao-analyst Production Dockerfile
# Build: docker build -t 2hao-analyst:v10 .
# Run: docker run --rm -e DEEPSEEK_API_KEY=xxx -e TAVILY_API_KEY=xxx 2hao-analyst:v10 "贵州茅台" --type listed_company

FROM python:3.11-slim

# System dependencies for playwright, matplotlib, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    curl \
    wget \
    git \
    fonts-dejavu-core \
    fonts-liberation2 \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (better layer caching)
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r <(pip compile pyproject.toml -o - 2>/dev/null || echo "") \
    || pip install --no-cache-dir \
        python-docx>=1.1.0 \
        python-pptx>=0.6.21 \
        matplotlib>=3.7.0 \
        numpy>=1.24.0 \
        pandas>=2.0.0 \
        PyYAML>=6.0 \
        requests>=2.31.0 \
        openpyxl>=3.1.2 \
        Pillow>=10.0.0 \
        fpdf2>=2.7.0 \
        akshare>=1.14.0 \
        openai>=1.0.0 \
        tavily-python \
        yfinance \
        playwright \
        sentence-transformers \
        prometheus-client \
        fastapi \
        uvicorn \
        httpx

# Install playwright browsers
RUN playwright install --with-deps chromium 2>/dev/null || true

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p output logs benchmark/golden/listed_company benchmark/golden/industry_deep \
    benchmark/golden/unlisted_company benchmark/golden/earnings_notes benchmark/golden/decision_memo \
    data/private_data

# Set Python path
ENV PYTHONPATH=/app

# Non-root user for security
RUN useradd -m -u 1000 analyst && chown -R analyst:analyst /app
USER analyst

# Health check endpoint (will be served by FastAPI if web module enabled)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import sys; sys.path.insert(0, '/app'); from main import run_pipeline; print('OK')" || exit 1

# Default entrypoint
ENTRYPOINT ["python", "main.py"]

# Default command (can be overridden)
CMD ["--help"]