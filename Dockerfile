# Multi-stage Dockerfile for allocator-bot
# Build stage
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=0

RUN apt-get update && apt-get install -y build-essential git

WORKDIR /app
COPY . /app
RUN uv sync --locked --no-dev

# Runtime stage
FROM python:3.12-slim-bookworm
WORKDIR /app

# Create non-root user
RUN groupadd --gid 1000 app && useradd --uid 1000 --gid app --shell /bin/bash --create-home app

# Copy application from builder
COPY --from=builder --chown=app:app /app /app

# Switch to non-root user
USER app

# Place executables in PATH
ENV PATH="/app/.venv/bin:$PATH"

# Expose port
EXPOSE 4299

# Run the application
CMD ["openbb-api", "--app", "allocator_bot.__main__:get_app", "--factory", "--host", "0.0.0.0", "--port", "4299"]
