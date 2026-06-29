FROM python:3.12-slim

WORKDIR /app

RUN pip install uv

ENV UV_LINK_MODE=copy

COPY pyproject.toml uv.lock README.md ./

RUN uv sync --frozen

COPY . .

EXPOSE 8000
