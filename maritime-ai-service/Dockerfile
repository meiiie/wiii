# Wiii Service Dockerfile
# by The Wiii Lab
# Multimodal RAG with Vision support (PyMuPDF)

FROM python:3.11-slim

# Install system dependencies
# - libpq-dev/gcc: PostgreSQL driver
# - curl: health check
# - Chromium libs: Playwright headless browser (Sprint 152-153)
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    curl \
    # Playwright Chromium dependencies
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium browser (Sprint 152: headless browser scraping)
RUN python -m playwright install chromium 2>/dev/null || true

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser

# Copy Playwright browser cache to appuser home (installed as root)
# Must mkdir -p first — useradd creates home but not .cache/
RUN mkdir -p /home/appuser/.cache \
    && cp -r /root/.cache/ms-playwright /home/appuser/.cache/ms-playwright 2>/dev/null || true
RUN chown -R appuser:appuser /home/appuser/.cache 2>/dev/null || true

USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health/live || exit 1

# Run application
CMD ["gunicorn", "app.main:app", "-w", "1", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--timeout", "180"]
