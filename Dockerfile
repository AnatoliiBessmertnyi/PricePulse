FROM python:3.12-slim
WORKDIR /app
RUN pip install uv
ENV UV_LINK_MODE=copy
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen
RUN uv run playwright install chromium
RUN uv run playwright install-deps chromium
COPY . .
EXPOSE 8000
