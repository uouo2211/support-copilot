# Build and run on the selected Docker host, not in the macOS Python environment.
FROM ghcr.io/astral-sh/uv:0.9.5 AS uv
FROM python:3.12.10-slim-bookworm

COPY --from=uv /uv /uvx /usr/local/bin/
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH"
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

RUN groupadd --gid 10001 copilot \
    && useradd --uid 10001 --gid copilot --create-home copilot
COPY --chown=copilot:copilot app ./app
COPY --chown=copilot:copilot migrations ./migrations
COPY --chown=copilot:copilot fixtures ./fixtures
COPY --chown=copilot:copilot scripts ./scripts
COPY --chown=copilot:copilot tests ./tests
COPY --chown=copilot:copilot evals ./evals
COPY --chown=copilot:copilot alembic.ini ./

USER copilot
EXPOSE 8000
# web and worker use the same image; Compose overrides the worker command.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
