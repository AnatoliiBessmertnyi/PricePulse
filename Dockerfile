# ============================================
# Stage 1: Build dependencies
# ============================================
FROM python:3.12-slim AS builder

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml uv.lock ./

# Install dependencies (cached layer)
RUN uv sync --frozen --no-dev --no-install-project

# Copy application code
COPY . .

# Install Playwright browsers
RUN uv run playwright install chromium --with-deps

# ============================================
# Stage 2: Runtime
# ============================================
FROM python:3.12-slim AS runtime

# Install runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Playwright/Chromium dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libxfixes3 \
    libxext6 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libexpat1 \
    libfontconfig1 \
    libfreetype6 \
    # Utilities
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install uv in runtime
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -G audio,video appuser

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Copy application code from builder
COPY --from=builder --chown=appuser:appuser /app /app

# Copy Playwright browser cache from builder (root user cache)
COPY --from=builder --chown=appuser:appuser /root/.cache/ms-playwright /home/appuser/.cache/ms-playwright

# Add .venv to PATH and set UV cache directory
ENV PATH="/app/.venv/bin:/usr/local/bin:$PATH"
ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1
ENV UV_CACHE_DIR="/tmp/uv-cache"
ENV PLAYWRIGHT_BROWSERS_PATH="/home/appuser/.cache/ms-playwright"

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"

# Default command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
