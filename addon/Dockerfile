ARG BUILD_FROM

FROM python:3.12-slim-bookworm AS builder
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock README.md ./
COPY src ./src

RUN uv sync --frozen

FROM ${BUILD_FROM}
WORKDIR /app

# Bring along Python, uv, dependencies, and the application from the builder stage
COPY --from=builder /usr/local /usr/local
COPY --from=builder /app /app

COPY addon/run.sh /run.sh
RUN chmod a+x /run.sh
ENV PATH="/usr/local/bin:${PATH}"

CMD [ "/run.sh" ]
