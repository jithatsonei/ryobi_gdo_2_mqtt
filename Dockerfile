FROM python:3.13-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml uv.lock README.md ./
COPY src ./src

# Sync dependencies
RUN uv sync --frozen

# Run the application
CMD ["uv", "run", "ryobi-gdo-2-mqtt"]
