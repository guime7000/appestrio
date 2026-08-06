FROM node:22-alpine AS frontend-build

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

COPY frontend/ ./
RUN npm run build


FROM python:3.14-slim AS backend-build

ENV PYTHONUNBUFFERED=1

# Install uv
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/

# Compile bytecode
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#compiling-bytecode
ENV UV_COMPILE_BYTECODE=1

# uv Cache
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#caching
ENV UV_LINK_MODE=copy

WORKDIR /app/

# Install dependencies
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=backend/uv.lock,target=uv.lock \
    --mount=type=bind,source=backend/pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-workspace --package app

COPY ./backend/scripts /app/scripts

COPY ./backend/pyproject.toml ./backend/alembic.ini /app/

COPY ./backend/app /app/app

# Sync the project
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=backend/uv.lock,target=uv.lock \
    --mount=type=bind,source=backend/pyproject.toml,target=pyproject.toml \
    uv sync --frozen --package app


FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app/

# Place executables in the environment at the front of the path
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#using-the-environment
ENV PATH="/app/.venv/bin:$PATH"

# Runtime only needs the synced venv and app code, not uv itself or the
# build cache, so this stage stays lean.
COPY --from=backend-build /app/.venv /app/.venv
COPY --from=backend-build /app/scripts /app/scripts
COPY --from=backend-build /app/pyproject.toml /app/alembic.ini /app/
COPY --from=backend-build /app/app /app/app

COPY --from=frontend-build /frontend/dist /app/static

# Single worker: init_db() runs Alembic migrations in the FastAPI lifespan,
# and multiple workers each running migrations concurrently against the same
# SQLite file races and can crash on startup.
CMD ["fastapi", "run", "--workers", "1"]
