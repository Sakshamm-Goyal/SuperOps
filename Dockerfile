# SuperOps Python services (api, worker, ui). Base image pinned by tag; pin by digest at release (docs/OPERATIONS.md).
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.7.3 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY greenops greenops
COPY experiments experiments
COPY sql sql
COPY migrations migrations
COPY config config
COPY sandbox sandbox
COPY scripts scripts
COPY data/manifests data/manifests
COPY deploy deploy
COPY experiments/support/dev experiments/support/dev
# Writable dirs exist in the image so named volumes inherit the non-root owner on first mount.
RUN mkdir -p /sandbox /app/var /app/data/generated /app/.evaluator && chown -R 10001:10001 /sandbox /app/var /app/data /app/.evaluator /app/experiments
ENV PYTHONPATH=/app PATH=/app/.venv/bin:$PATH
USER 10001
